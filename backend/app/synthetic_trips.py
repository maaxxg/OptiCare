"""Synthetic historical TripLog generator for ML training (E1-T4, KAN-16).

Run: `uv run python -m app.synthetic_trips` (backend dir).
Reads distribution parameters from `data/domain/synthetic_trips.yaml` and base medians/p90s
from `data/domain/urgency_and_durations.yaml` via `app.codebooks`.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.codebooks import get_boarding_time_min, get_visit_duration
from app.config import get_settings
from app.db import SessionLocal
from app.models import Department, DriverStatusEvent, MobilityClass, TripLog, VisitType

logger = logging.getLogger(__name__)

ZAGREB = ZoneInfo("Europe/Zagreb")
SYNTHETIC_TRIPS_PATH = Path("domain") / "synthetic_trips.yaml"
Z_P90 = 1.2815515655446004  # standard normal 90th percentile


def load_synthetic_trip_params(data_dir: Path | None = None) -> dict[str, Any]:
    root = data_dir or get_settings().data_dir
    path = root / SYNTHETIC_TRIPS_PATH
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid YAML root in {path}")
    return raw


def _sample_lognormal_from_median_p90(
    rng: random.Random, median: float, p90: float, minimum: float = 1.0
) -> float:
    """Sample from a log-normal distribution calibrated to the given median and 90th percentile."""
    mu = math.log(max(median, 0.1))
    sigma = max(math.log(max(p90, median) / max(median, 0.1)) / Z_P90, 0.01)
    return max(minimum, rng.lognormvariate(mu, sigma))


def _sample_distance_km(
    rng: random.Random, department: str, bands: dict[str, dict[str, float]]
) -> float:
    """Sample one-way distance in km (oncology goes to KBC -> external band)."""
    if department == Department.ONCOLOGY.value:
        band = bands["external"]
    else:
        names = list(bands.keys())
        weights = [float(bands[n]["weight"]) for n in names]
        chosen = rng.choices(names, weights=weights, k=1)[0]
        band = bands[chosen]
    return round(rng.uniform(float(band["min"]), float(band["max"])), 1)


def generate_synthetic_trip_logs(
    count: int | None = None,
    seed: int | None = None,
    end_date: date | None = None,
    data_dir: Path | None = None,
) -> list[TripLog]:
    """Generate synthetic historical TripLog rows in memory."""
    params = load_synthetic_trip_params(data_dir=data_dir)
    n_rows = count if count is not None else int(params["default_count"])
    rng = random.Random(seed if seed is not None else int(params["random_seed"]))
    ref_date = end_date or datetime.now(ZAGREB).date()
    history_days = int(params["history_days"])

    visit_mix: list[dict[str, Any]] = params["visit_mix"]
    visit_pairs = [
        (Department(item["department"]).value, VisitType(item["visit_type"]).value)
        for item in visit_mix
    ]
    visit_weights = [float(item["weight"]) for item in visit_mix]

    mob_map: dict[str, float] = params["mobility_weights"]
    mob_keys = [MobilityClass(k).value for k in mob_map]
    mob_weights = [float(mob_map[k]) for k in mob_map]

    boarding_cfg = params["boarding"]
    visit_cfg = params["visit_duration"]
    ctx_cfg = params["patient_context"]
    drive_cfg = params["drive"]

    floor_map: dict[int, float] = {int(k): float(v) for k, v in ctx_cfg["floor_weights"].items()}
    floor_choices = list(floor_map.keys())
    floor_weights = list(floor_map.values())

    rows: list[TripLog] = []
    for _ in range(n_rows):
        department, visit_type = rng.choices(visit_pairs, weights=visit_weights, k=1)[0]
        mobility = rng.choices(mob_keys, weights=mob_weights, k=1)[0]

        floor = rng.choices(floor_choices, weights=floor_weights, k=1)[0]
        elevator = (
            rng.random() < float(ctx_cfg["elevator_prob_if_floor_ge_2"]) if floor >= 2 else False
        )
        companion = rng.random() < float(ctx_cfg["companion_prob_by_mobility"][mobility])
        patient_age = int(
            round(
                rng.triangular(
                    float(ctx_cfg["age_min"]),
                    float(ctx_cfg["age_max"]),
                    float(ctx_cfg["age_mode"]),
                )
            )
        )

        # 1. Boarding duration (door arrival -> departure from door)
        base_boarding_median = float(get_boarding_time_min(mobility))
        base_boarding_p90 = float(boarding_cfg["p90_min"][mobility])
        boarding_min = _sample_lognormal_from_median_p90(
            rng,
            median=base_boarding_median,
            p90=base_boarding_p90,
            minimum=float(boarding_cfg["min_minutes"]),
        )
        if floor > 0 and not elevator:
            boarding_min += floor * float(boarding_cfg["extra_min_per_floor_no_elevator"][mobility])
        if companion:
            boarding_min *= float(boarding_cfg["companion_factor"])
        boarding_min = max(float(boarding_cfg["min_minutes"]), round(boarding_min, 1))

        # 2. Visit duration at facility (check-in -> check-out)
        dur_entry = get_visit_duration(department, visit_type)
        visit_min = _sample_lognormal_from_median_p90(
            rng,
            median=float(dur_entry.median_min),
            p90=float(dur_entry.p90_min),
            minimum=float(visit_cfg["min_minutes"]),
        )
        if patient_age >= 75:
            visit_min *= float(visit_cfg["age_over_75_factor"])
        visit_min = max(float(visit_cfg["min_minutes"]), round(visit_min, 1))

        # 3. Drive distance and travel times
        distance_km = _sample_distance_km(rng, department, drive_cfg["distance_bands_km"])
        mean_speed = float(drive_cfg["mean_speed_kmh"])
        outbound_drive_min = max(5.0, (distance_km / mean_speed) * 60.0 * rng.uniform(0.9, 1.2))
        return_wait_and_drive_min = rng.uniform(5.0, 20.0) + max(
            5.0, (distance_km / mean_speed) * 60.0 * rng.uniform(0.9, 1.2)
        )

        # 4. Timestamps on a historical day
        day_offset = rng.randint(1, history_days)
        trip_date = ref_date - timedelta(days=day_offset)
        arrival_at_door = datetime.combine(
            trip_date,
            time(hour=rng.randint(6, 11), minute=rng.choice((0, 10, 20, 30, 40, 50))),
            tzinfo=ZAGREB,
        )
        departure_from_door = arrival_at_door + timedelta(minutes=boarding_min)
        check_in = departure_from_door + timedelta(minutes=round(outbound_drive_min, 1))
        check_out = check_in + timedelta(minutes=visit_min)
        dropoff_at_home = check_out + timedelta(minutes=round(return_wait_and_drive_min, 1))

        rows.append(
            TripLog(
                assignment_id=None,
                actual_arrival_at_door=arrival_at_door,
                actual_departure_from_door=departure_from_door,
                actual_check_in_at_facility=check_in,
                actual_check_out_from_facility=check_out,
                actual_dropoff_at_home=dropoff_at_home,
                driver_status_event=DriverStatusEvent.DROPPED_OFF.value,
                recorded_by="synthetic",
                distance_km=distance_km,
                department=department,
                visit_type=visit_type,
                mobility_class=mobility,
                floor=floor,
                elevator=elevator,
                companion=companion,
                patient_age=patient_age,
                created_at=dropoff_at_home,
            )
        )

    return rows


def seed_synthetic_trip_logs(
    session: Session,
    count: int | None = None,
    seed: int | None = None,
    data_dir: Path | None = None,
) -> int:
    """Replace existing synthetic TripLog rows in the database."""
    rows = generate_synthetic_trip_logs(count=count, seed=seed, data_dir=data_dir)
    session.execute(delete(TripLog).where(TripLog.recorded_by == "synthetic"))
    session.add_all(rows)
    session.commit()
    return len(rows)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        inserted = seed_synthetic_trip_logs(session)
    logger.info("Inserted %d synthetic TripLog rows.", inserted)


if __name__ == "__main__":
    main()
