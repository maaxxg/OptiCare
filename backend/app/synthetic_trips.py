"""Synthetic historical TripLog generator for ML training (E1-T4, KAN-16).

Run: `uv run python -m app.synthetic_trips` (backend dir).
Reads distribution parameters from `data/domain/synthetic_trips.yaml` and base medians/p90s
from `data/domain/urgency_and_durations.yaml` via `app.codebooks`.
The rows are training data only; they never feed a path that removes or deprioritises a patient.
"""

from __future__ import annotations

import logging
import math
import random
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.codebooks import (
    CODEBOOKS_RELATIVE_PATH,
    Codebooks,
    get_codebooks,
    load_codebooks_from_path,
)
from app.config import get_settings
from app.db import SessionLocal
from app.models import Department, DriverStatusEvent, MobilityClass, TripLog, VisitType

logger = logging.getLogger(__name__)

ZAGREB = ZoneInfo("Europe/Zagreb")
SYNTHETIC_TRIPS_PATH = Path("domain") / "synthetic_trips.yaml"
Z_P90 = 1.2815515655446004  # standard normal 90th percentile


class SyntheticTripParamsError(Exception):
    """The synthetic trips YAML is unreadable or invalid."""


class VisitMixItem(BaseModel):
    department: Department
    visit_type: VisitType
    weight: float = Field(..., ge=0)


class BoardingParams(BaseModel):
    p90_min: dict[MobilityClass, float]
    extra_min_per_floor_no_elevator: dict[MobilityClass, float]
    companion_factor: float = Field(..., gt=0)
    min_minutes: float = Field(..., gt=0)

    @model_validator(mode="after")
    def _all_mobility_classes(self) -> BoardingParams:
        _require_all_mobility(self.p90_min, "boarding.p90_min")
        _require_all_mobility(
            self.extra_min_per_floor_no_elevator, "boarding.extra_min_per_floor_no_elevator"
        )
        return self


class VisitDurationParams(BaseModel):
    age_over_75_factor: float = Field(..., gt=0)
    min_minutes: float = Field(..., gt=0)


class PatientContextParams(BaseModel):
    age_min: int = Field(..., ge=0)
    age_max: int = Field(..., ge=0)
    age_mode: int = Field(..., ge=0)
    floor_weights: dict[int, float]
    elevator_prob_if_upper_floor: float = Field(..., ge=0, le=1)
    companion_prob_by_mobility: dict[MobilityClass, float]

    @model_validator(mode="after")
    def _check(self) -> PatientContextParams:
        if not self.age_min <= self.age_mode <= self.age_max:
            raise ValueError("age_min <= age_mode <= age_max must hold")
        if any(f < 0 or w < 0 for f, w in self.floor_weights.items()) or not any(
            w > 0 for w in self.floor_weights.values()
        ):
            raise ValueError("floor_weights need floors >= 0 and at least one positive weight")
        if not all(0 <= p <= 1 for p in self.companion_prob_by_mobility.values()):
            raise ValueError("companion probabilities must be within [0, 1]")
        _require_all_mobility(self.companion_prob_by_mobility, "companion_prob_by_mobility")
        return self


class StartWindowParams(BaseModel):
    earliest_hour: int = Field(..., ge=0, le=23)
    latest_hour: int = Field(..., ge=0, le=23)
    minute_step: int = Field(..., ge=1, le=59)

    @model_validator(mode="after")
    def _ordered(self) -> StartWindowParams:
        if self.earliest_hour > self.latest_hour:
            raise ValueError("earliest_hour must be <= latest_hour")
        return self


class Range(BaseModel):
    min: float = Field(..., ge=0)
    max: float = Field(..., ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Range:
        if self.min > self.max:
            raise ValueError("min must be <= max")
        return self


class DistanceBand(Range):
    weight: float = Field(..., ge=0)


class DriveParams(BaseModel):
    mean_speed_kmh: float = Field(..., gt=0)
    speed_jitter: Range
    min_drive_min: float = Field(..., ge=0)
    return_wait_min: Range
    external_departments: list[Department]
    external_band_km: Range
    distance_bands_km: dict[str, DistanceBand]

    @model_validator(mode="after")
    def _has_weight(self) -> DriveParams:
        if not any(b.weight > 0 for b in self.distance_bands_km.values()):
            raise ValueError("distance_bands_km needs at least one positive weight")
        return self


class SyntheticTripParams(BaseModel):
    default_count: int = Field(..., ge=0)
    history_days: int = Field(..., ge=1)
    random_seed: int
    visit_mix: list[VisitMixItem] = Field(..., min_length=1)
    mobility_weights: dict[MobilityClass, float]
    boarding: BoardingParams
    visit_duration: VisitDurationParams
    patient_context: PatientContextParams
    start_window: StartWindowParams
    drive: DriveParams

    @model_validator(mode="after")
    def _weights(self) -> SyntheticTripParams:
        if not any(i.weight > 0 for i in self.visit_mix):
            raise ValueError("visit_mix needs at least one positive weight")
        if any(w < 0 for w in self.mobility_weights.values()) or not any(
            w > 0 for w in self.mobility_weights.values()
        ):
            raise ValueError("mobility_weights need non-negative values and one positive weight")
        _require_all_mobility(self.mobility_weights, "mobility_weights")
        return self


def _require_all_mobility(mapping: dict[MobilityClass, float], name: str) -> None:
    missing = set(MobilityClass) - set(mapping)
    if missing:
        raise ValueError(f"{name} is missing mobility classes: {sorted(m.value for m in missing)}")


def load_synthetic_trip_params(data_dir: Path | None = None) -> SyntheticTripParams:
    root = data_dir or get_settings().data_dir
    path = root / SYNTHETIC_TRIPS_PATH
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise SyntheticTripParamsError(
            f"Cannot read synthetic trips YAML at {path}: {exc}"
        ) from exc
    if not isinstance(raw, dict):
        raise SyntheticTripParamsError(f"Synthetic trips YAML at {path} must be a mapping")
    try:
        return SyntheticTripParams.model_validate(raw)
    except ValidationError as exc:
        raise SyntheticTripParamsError(f"Invalid synthetic trips YAML at {path}: {exc}") from exc


def _sample_lognormal_from_median_p90(
    rng: random.Random, median: float, p90: float, minimum: float = 1.0
) -> float:
    """Sample from a log-normal distribution calibrated to the given median and 90th percentile."""
    mu = math.log(max(median, 0.1))
    sigma = max(math.log(max(p90, median) / max(median, 0.1)) / Z_P90, 0.01)
    return max(minimum, rng.lognormvariate(mu, sigma))


def _sample_distance_km(rng: random.Random, department: Department, drive: DriveParams) -> float:
    """Sample one-way distance in km. External departments (KBC) use only the external band."""
    if department in drive.external_departments:
        band: Range = drive.external_band_km
    else:
        bands = list(drive.distance_bands_km.values())
        band = rng.choices(bands, weights=[b.weight for b in bands], k=1)[0]
    return round(rng.uniform(band.min, band.max), 1)


def _sample_drive_min(rng: random.Random, distance_km: float, drive: DriveParams) -> float:
    """Drive time in minutes for one direction, with speed jitter and a minimum."""
    jitter = rng.uniform(drive.speed_jitter.min, drive.speed_jitter.max)
    return max(drive.min_drive_min, (distance_km / drive.mean_speed_kmh) * 60.0 * jitter)


def generate_synthetic_trip_logs(
    count: int | None = None,
    seed: int | None = None,
    end_date: date | None = None,
    data_dir: Path | None = None,
) -> list[TripLog]:
    """Generate synthetic historical TripLog rows in memory (aware UTC datetimes)."""
    params = load_synthetic_trip_params(data_dir=data_dir)
    codebooks: Codebooks = (
        load_codebooks_from_path(data_dir / CODEBOOKS_RELATIVE_PATH)
        if data_dir is not None
        else get_codebooks()
    )
    boarding_median = codebooks.boarding_time_min
    visit_durations = {(e.department, e.visit_type): e for e in codebooks.visit_durations}

    n_rows = count if count is not None else params.default_count
    rng = random.Random(seed if seed is not None else params.random_seed)
    ref_date = end_date or datetime.now(ZAGREB).date()

    visit_pairs = [(i.department, i.visit_type) for i in params.visit_mix]
    visit_weights = [i.weight for i in params.visit_mix]
    mob_keys = list(params.mobility_weights)
    mob_weights = list(params.mobility_weights.values())

    boarding_cfg = params.boarding
    ctx = params.patient_context
    drive = params.drive
    window = params.start_window
    floor_choices = list(ctx.floor_weights)
    floor_weights = list(ctx.floor_weights.values())
    start_minutes = list(range(0, 60, window.minute_step))

    rows: list[TripLog] = []
    for _ in range(n_rows):
        department, visit_type = rng.choices(visit_pairs, weights=visit_weights, k=1)[0]
        mobility = rng.choices(mob_keys, weights=mob_weights, k=1)[0]

        floor = rng.choices(floor_choices, weights=floor_weights, k=1)[0]
        elevator = floor >= 1 and rng.random() < ctx.elevator_prob_if_upper_floor
        companion = rng.random() < ctx.companion_prob_by_mobility[mobility]
        patient_age = int(round(rng.triangular(ctx.age_min, ctx.age_max, ctx.age_mode)))

        # 1. Boarding duration (door arrival -> departure from door)
        boarding_min = _sample_lognormal_from_median_p90(
            rng,
            median=float(boarding_median[mobility]),
            p90=boarding_cfg.p90_min[mobility],
            minimum=boarding_cfg.min_minutes,
        )
        if floor > 0 and not elevator:
            boarding_min += floor * boarding_cfg.extra_min_per_floor_no_elevator[mobility]
        if companion:
            boarding_min *= boarding_cfg.companion_factor
        boarding_min = max(boarding_cfg.min_minutes, round(boarding_min, 1))

        # 2. Visit duration at facility (check-in -> check-out)
        dur_entry = visit_durations[(department, visit_type)]
        visit_min = _sample_lognormal_from_median_p90(
            rng,
            median=float(dur_entry.median_min),
            p90=float(dur_entry.p90_min),
            minimum=params.visit_duration.min_minutes,
        )
        if patient_age >= 75:
            visit_min *= params.visit_duration.age_over_75_factor
        visit_min = max(params.visit_duration.min_minutes, round(visit_min, 1))

        # 3. Drive distance and travel times
        distance_km = _sample_distance_km(rng, department, drive)
        outbound_drive_min = _sample_drive_min(rng, distance_km, drive)
        return_wait_and_drive_min = rng.uniform(
            drive.return_wait_min.min, drive.return_wait_min.max
        ) + _sample_drive_min(rng, distance_km, drive)

        # 4. Timestamps: Zagreb wall-clock start, converted to UTC; all arithmetic in UTC.
        day_offset = rng.randint(1, params.history_days)
        trip_date = ref_date - timedelta(days=day_offset)
        arrival_at_door = datetime.combine(
            trip_date,
            time(
                hour=rng.randint(window.earliest_hour, window.latest_hour),
                minute=rng.choice(start_minutes),
            ),
            tzinfo=ZAGREB,
        ).astimezone(UTC)
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
                department=department.value,
                visit_type=visit_type.value,
                mobility_class=mobility.value,
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
