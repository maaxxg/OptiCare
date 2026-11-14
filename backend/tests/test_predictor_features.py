"""Testovi za graditelj značajki za treniranje i posluživanje (E4-T3, KAN-30)."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models import (
    Assignment,
    Patient,
    TripLog,
)
from app.predictors import (
    PII_FORBIDDEN_KEYS,
    MissingFeatureError,
    PredictorInputError,
    build_features,
    build_service_time_features,
    build_support_need_features,
    build_travel_time_features,
    build_visit_duration_features,
    get_predictor,
    service_time_from_trip_log,
    visit_duration_from_trip_log,
)
from app.scoring import compute_score
from app.seed import build_seed_objects
from app.synthetic_trips import generate_synthetic_trip_logs

ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


def test_training_and_serving_produce_identical_features_for_visit_duration_and_service_time() -> (
    None
):
    plan_date = date(2026, 11, 14)
    bundle = build_seed_objects(base_date=plan_date)
    req = bundle.visit_requests[0]
    patient = req.patient
    slot = req.candidate_slots[0]
    vehicle = bundle.vehicles[0]

    serving_vd = build_visit_duration_features(
        req, patient=patient, slot=slot, reference_date=slot.start_time.astimezone(ZAGREB_TZ).date()
    )
    serving_st = build_service_time_features(patient)

    # 1. TripLog povezan preko Assignmenta (stvarna obavljena vožnja)
    arrival_door = (slot.start_time - timedelta(minutes=45)).astimezone(UTC)
    departure_door = arrival_door + timedelta(minutes=6)
    check_in = slot.start_time.astimezone(UTC)
    check_out = check_in + timedelta(minutes=52)
    assignment = Assignment(
        request=req,
        slot=slot,
        vehicle=vehicle,
        pickup_time=arrival_door,
        facility_arrival_time=check_in,
    )
    linked_log = TripLog(
        assignment=assignment,
        actual_arrival_at_door=arrival_door,
        actual_departure_from_door=departure_door,
        actual_check_in_at_facility=check_in,
        actual_check_out_from_facility=check_out,
    )

    training_vd_linked, actual_visit_min = visit_duration_from_trip_log(linked_log)
    training_st_linked, actual_boarding_min = service_time_from_trip_log(linked_log)

    assert training_vd_linked == serving_vd
    assert actual_visit_min == 52.0
    assert training_st_linked == serving_st
    assert actual_boarding_min == 6.0

    # 2. Denormalizirani TripLog redak (sintetički podaci bez Assignmenta)
    synthetic_log = TripLog(
        assignment=None,
        actual_arrival_at_door=arrival_door,
        actual_departure_from_door=departure_door,
        actual_check_in_at_facility=check_in,
        actual_check_out_from_facility=check_out,
        department=req.department,
        visit_type=req.visit_type,
        mobility_class=patient.mobility_class,
        floor=patient.floor,
        elevator=patient.elevator,
        companion=patient.companion,
        patient_age=serving_vd["patient_age"],
    )
    training_vd_synth, synth_visit_min = visit_duration_from_trip_log(synthetic_log)
    training_st_synth, synth_boarding_min = service_time_from_trip_log(synthetic_log)

    assert training_vd_synth == serving_vd
    assert synth_visit_min == 52.0
    assert training_st_synth == serving_st
    assert synth_boarding_min == 6.0


def test_all_seeded_objects_work_through_build_features_and_predictors_without_pii() -> None:
    plan_date = date(2026, 11, 14)
    bundle = build_seed_objects(base_date=plan_date)
    vehicle = bundle.vehicles[0]
    departure_dt = datetime.combine(plan_date, time(8, 0), tzinfo=ZAGREB_TZ)

    for idx, req in enumerate(bundle.visit_requests, start=1):
        patient = req.patient
        patient.id = idx
        slot = req.candidate_slots[0] if req.candidate_slots else None

        # 1. visit_duration
        vd_features = build_features(
            "visit_duration",
            request=req,
            patient=patient,
            slot_obj=slot,
            reference_date=plan_date,
        )
        assert not (set(vd_features) & PII_FORBIDDEN_KEYS)
        assert patient.mbo not in str(vd_features.values())
        vd_pred = get_predictor("visit_duration").predict(vd_features)
        assert vd_pred.value > 0
        assert vd_pred.high is not None and vd_pred.high >= vd_pred.value

        # 2. service_time
        st_features = build_features("service_time", patient=patient)
        assert not (set(st_features) & PII_FORBIDDEN_KEYS)
        assert patient.mbo not in str(st_features.values())
        st_pred = get_predictor("service_time").predict(st_features)
        assert st_pred.value > 0

        # 3. support_need
        sn_features = build_features(
            "support_need",
            patient=patient,
            request=req,
            reference_date=plan_date,
        )
        assert not (set(sn_features) & PII_FORBIDDEN_KEYS)
        assert patient.mbo not in str(sn_features.values())
        sn_pred = get_predictor("support_need").predict(sn_features)
        direct_score = compute_score(
            patient_id=patient.id,
            mobility_class=patient.mobility_class,
            distance_km=sn_features["distance_km"],
            birth_year=patient.birth_year,
            lives_alone=patient.lives_alone,
            missed_visits_last_year=patient.missed_visits_last_year,
            phone_type=patient.phone_type,
            companion_available=patient.companion,
            reference_date=plan_date,
        )
        assert sn_pred.value == direct_score.total_score
        assert sn_pred.explanation == {f.key: f.weighted_value for f in direct_score.factors}

        # 4. travel_time
        tt_features = build_features(
            "travel_time",
            patient=patient,
            request=req,
            vehicle=vehicle,
            departure_time=departure_dt,
        )
        assert not (set(tt_features) & PII_FORBIDDEN_KEYS)
        assert patient.mbo not in str(tt_features.values())
        tt_pred = get_predictor("travel_time").predict(tt_features)
        assert tt_pred.value > 0


def test_synthetic_trip_logs_extract_valid_training_pairs() -> None:
    logs = generate_synthetic_trip_logs(count=30, seed=42, end_date=date(2026, 11, 14))
    assert len(logs) == 30

    vd_predictor = get_predictor("visit_duration")
    st_predictor = get_predictor("service_time")

    for log in logs:
        vd_features, visit_target = visit_duration_from_trip_log(log)
        st_features, boarding_target = service_time_from_trip_log(log)

        assert visit_target > 0
        assert boarding_target > 0
        assert not (set(vd_features) & PII_FORBIDDEN_KEYS)
        assert not (set(st_features) & PII_FORBIDDEN_KEYS)

        # Svaki redak značajki iz treniranja mora raditi i na posluživanju (pravilo/model)
        assert vd_predictor.predict(vd_features).value > 0
        assert st_predictor.predict(st_features).value > 0


def test_feature_builder_validation_errors() -> None:
    with pytest.raises(MissingFeatureError):
        build_features("visit_duration")

    with pytest.raises(MissingFeatureError):
        build_features("service_time")

    with pytest.raises(MissingFeatureError):
        build_features("support_need")

    with pytest.raises(KeyError):
        build_features("unknown_slot")

    patient_no_loc = Patient(
        first_name="Ivo",
        last_name="Ivić",
        mbo="000000099",
        phone="+385 00 000 0099",
        settlement="Gospić",
        municipality="Gospić",
        county="Ličko-senjska",
        location=None,
    )
    with pytest.raises(MissingFeatureError):
        build_travel_time_features(patient_no_loc, {"lat": 44.5, "lon": 15.3})
    with pytest.raises(MissingFeatureError):
        build_support_need_features(patient_no_loc)

    empty_log = TripLog()
    with pytest.raises(PredictorInputError):
        visit_duration_from_trip_log(empty_log)
    with pytest.raises(PredictorInputError):
        service_time_from_trip_log(empty_log)

    # Provjera izravnih pomoćnih graditelja kad su obvezna polja postavljena
    patient_no_loc.mobility_class = "walks"
    patient_no_loc.phone_type = "landline"
    support_dict = build_support_need_features(
        patient_no_loc, distance_km=15.0, reference_date=date(2026, 11, 14)
    )
    assert support_dict["distance_km"] == 15.0
    assert support_dict["age"] is None
