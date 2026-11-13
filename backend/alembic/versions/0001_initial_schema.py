"""Initial schema with PostGIS geography columns and core tables.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-13 22:55:00

"""
from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "municipalities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("county", sa.String(length=120), nullable=False),
        sa.Column("population_65_plus_share", sa.Float(), nullable=True),
        sa.Column(
            "boundary",
            geoalchemy2.types.Geography(
                geometry_type="MULTIPOLYGON",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_municipalities_name", "municipalities", ["name"], unique=True)
    op.create_index(
        "idx_municipalities_boundary",
        "municipalities",
        ["boundary"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "facilities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("settlement", sa.String(length=120), nullable=False),
        sa.Column("municipality", sa.String(length=120), nullable=False),
        sa.Column("county", sa.String(length=120), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_facilities_key", "facilities", ["key"], unique=True)
    op.create_index(
        "idx_facilities_location",
        "facilities",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=32), nullable=True),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=True),
        sa.Column("mbo", sa.String(length=9), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=False),
        sa.Column("phone_type", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("settlement", sa.String(length=120), nullable=False),
        sa.Column("municipality", sa.String(length=120), nullable=False),
        sa.Column("county", sa.String(length=120), nullable=False),
        sa.Column(
            "location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=True,
                spatial_index=False,
            ),
            nullable=True,
        ),
        sa.Column("mobility_class", sa.String(length=32), nullable=False),
        sa.Column("lives_alone", sa.Boolean(), nullable=False),
        sa.Column("companion", sa.Boolean(), nullable=False),
        sa.Column("floor", sa.Integer(), nullable=False),
        sa.Column("elevator", sa.Boolean(), nullable=False),
        sa.Column("transport_entitlement", sa.String(length=32), nullable=False),
        sa.Column("social_order_today", sa.Boolean(), nullable=False),
        sa.Column("own_car", sa.Boolean(), nullable=False),
        sa.Column("carpool_driver_seats", sa.Integer(), nullable=False),
        sa.Column("carpool_consent", sa.Boolean(), nullable=False),
        sa.Column("driver_registration_valid", sa.Boolean(), nullable=False),
        sa.Column("driver_insurance_valid", sa.Boolean(), nullable=False),
        sa.Column("driver_license_valid", sa.Boolean(), nullable=False),
        sa.Column("volunteer_partner", sa.String(length=120), nullable=True),
        sa.Column("missed_visits_last_year", sa.Integer(), nullable=False),
        sa.Column("consent_given", sa.Boolean(), nullable=False),
        sa.Column("story", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_patients_key", "patients", ["key"], unique=True)
    op.create_index("ix_patients_mbo", "patients", ["mbo"], unique=True)
    op.create_index("ix_patients_municipality", "patients", ["municipality"], unique=False)
    op.create_index(
        "idx_patients_location",
        "patients",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "slots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("facility_id", sa.Integer(), nullable=True),
        sa.Column("facility_key", sa.String(length=64), nullable=False),
        sa.Column("facility_name", sa.String(length=200), nullable=True),
        sa.Column(
            "facility_location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=True,
                spatial_index=False,
            ),
            nullable=True,
        ),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_slots_facility_id", "slots", ["facility_id"], unique=False)
    op.create_index("ix_slots_facility_key", "slots", ["facility_key"], unique=False)
    op.create_index("ix_slots_department", "slots", ["department"], unique=False)
    op.create_index("ix_slots_start_time", "slots", ["start_time"], unique=False)
    op.create_index(
        "idx_slots_facility_location",
        "slots",
        ["facility_location"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "visit_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("patient_id", sa.Integer(), nullable=False),
        sa.Column("referral_ref", sa.String(length=64), nullable=True),
        sa.Column("facility_id", sa.Integer(), nullable=True),
        sa.Column("facility_key", sa.String(length=64), nullable=False),
        sa.Column("department", sa.String(length=64), nullable=False),
        sa.Column("visit_type", sa.String(length=64), nullable=False),
        sa.Column("urgency_class", sa.String(length=64), nullable=False),
        sa.Column("earliest_date", sa.Date(), nullable=False),
        sa.Column("latest_date", sa.Date(), nullable=False),
        sa.Column("recurrence", sa.String(length=64), nullable=True),
        sa.Column("preferred_time_of_day", sa.String(length=32), nullable=True),
        sa.Column("slot_request_pending", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_visit_requests_patient_id", "visit_requests", ["patient_id"], unique=False)
    op.create_index(
        "ix_visit_requests_referral_ref", "visit_requests", ["referral_ref"], unique=False
    )
    op.create_index(
        "ix_visit_requests_facility_id", "visit_requests", ["facility_id"], unique=False
    )
    op.create_index(
        "ix_visit_requests_facility_key", "visit_requests", ["facility_key"], unique=False
    )
    op.create_index(
        "ix_visit_requests_department", "visit_requests", ["department"], unique=False
    )
    op.create_index(
        "ix_visit_requests_earliest_date", "visit_requests", ["earliest_date"], unique=False
    )
    op.create_index(
        "ix_visit_requests_latest_date", "visit_requests", ["latest_date"], unique=False
    )
    op.create_index("ix_visit_requests_status", "visit_requests", ["status"], unique=False)

    op.create_table(
        "visit_request_candidate_slots",
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["visit_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("request_id", "slot_id"),
    )

    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("seats", sa.Integer(), nullable=False),
        sa.Column("wheelchair_spots", sa.Integer(), nullable=False),
        sa.Column("stretcher_spots", sa.Integer(), nullable=False),
        sa.Column("shift_start", sa.Time(), nullable=False),
        sa.Column("shift_end", sa.Time(), nullable=False),
        sa.Column("base_settlement", sa.String(length=120), nullable=True),
        sa.Column("base_municipality", sa.String(length=120), nullable=True),
        sa.Column(
            "base_location",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
                spatial_index=False,
            ),
            nullable=False,
        ),
        sa.Column("driver_name", sa.String(length=120), nullable=True),
        sa.Column("driver_phone", sa.String(length=40), nullable=True),
        sa.Column("patient_driver_id", sa.Integer(), nullable=True),
        sa.Column("has_driver_assistance", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["patient_driver_id"], ["patients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vehicles_key", "vehicles", ["key"], unique=True)
    op.create_index("ix_vehicles_provider_type", "vehicles", ["provider_type"], unique=False)
    op.create_index(
        "ix_vehicles_patient_driver_id", "vehicles", ["patient_driver_id"], unique=False
    )
    op.create_index(
        "idx_vehicles_base_location",
        "vehicles",
        ["base_location"],
        unique=False,
        postgresql_using="gist",
    )

    op.create_table(
        "assignments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("slot_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("return_vehicle_id", sa.Integer(), nullable=True),
        sa.Column("backup_vehicle_id", sa.Integer(), nullable=True),
        sa.Column("pickup_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("facility_arrival_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("return_pickup_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("home_dropoff_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_order", sa.Integer(), nullable=True),
        sa.Column("return_order", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column("carpool_confirmed", sa.Boolean(), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["backup_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["request_id"], ["visit_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["return_vehicle_id"], ["vehicles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_assignments_request_id", "assignments", ["request_id"], unique=False)
    op.create_index("ix_assignments_slot_id", "assignments", ["slot_id"], unique=False)
    op.create_index("ix_assignments_vehicle_id", "assignments", ["vehicle_id"], unique=False)
    op.create_index("ix_assignments_status", "assignments", ["status"], unique=False)

    op.create_table(
        "trip_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("assignment_id", sa.Integer(), nullable=True),
        sa.Column("actual_arrival_at_door", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_departure_from_door", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_check_in_at_facility", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_check_out_from_facility", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actual_dropoff_at_home", sa.DateTime(timezone=True), nullable=True),
        sa.Column("driver_status_event", sa.String(length=32), nullable=True),
        sa.Column("recorded_by", sa.String(length=32), nullable=True),
        sa.Column("distance_km", sa.Float(), nullable=True),
        sa.Column("department", sa.String(length=64), nullable=True),
        sa.Column("visit_type", sa.String(length=64), nullable=True),
        sa.Column("mobility_class", sa.String(length=32), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("elevator", sa.Boolean(), nullable=True),
        sa.Column("companion", sa.Boolean(), nullable=True),
        sa.Column("patient_age", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assignment_id"], ["assignments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trip_logs_assignment_id", "trip_logs", ["assignment_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_trip_logs_assignment_id", table_name="trip_logs")
    op.drop_table("trip_logs")

    op.drop_index("ix_assignments_status", table_name="assignments")
    op.drop_index("ix_assignments_vehicle_id", table_name="assignments")
    op.drop_index("ix_assignments_slot_id", table_name="assignments")
    op.drop_index("ix_assignments_request_id", table_name="assignments")
    op.drop_table("assignments")

    op.drop_index("idx_vehicles_base_location", table_name="vehicles", postgresql_using="gist")
    op.drop_index("ix_vehicles_patient_driver_id", table_name="vehicles")
    op.drop_index("ix_vehicles_provider_type", table_name="vehicles")
    op.drop_index("ix_vehicles_key", table_name="vehicles")
    op.drop_table("vehicles")

    op.drop_table("visit_request_candidate_slots")

    op.drop_index("ix_visit_requests_status", table_name="visit_requests")
    op.drop_index("ix_visit_requests_latest_date", table_name="visit_requests")
    op.drop_index("ix_visit_requests_earliest_date", table_name="visit_requests")
    op.drop_index("ix_visit_requests_department", table_name="visit_requests")
    op.drop_index("ix_visit_requests_facility_key", table_name="visit_requests")
    op.drop_index("ix_visit_requests_facility_id", table_name="visit_requests")
    op.drop_index("ix_visit_requests_referral_ref", table_name="visit_requests")
    op.drop_index("ix_visit_requests_patient_id", table_name="visit_requests")
    op.drop_table("visit_requests")

    op.drop_index("idx_slots_facility_location", table_name="slots", postgresql_using="gist")
    op.drop_index("ix_slots_start_time", table_name="slots")
    op.drop_index("ix_slots_department", table_name="slots")
    op.drop_index("ix_slots_facility_key", table_name="slots")
    op.drop_index("ix_slots_facility_id", table_name="slots")
    op.drop_table("slots")

    op.drop_index("idx_patients_location", table_name="patients", postgresql_using="gist")
    op.drop_index("ix_patients_municipality", table_name="patients")
    op.drop_index("ix_patients_mbo", table_name="patients")
    op.drop_index("ix_patients_key", table_name="patients")
    op.drop_table("patients")

    op.drop_index("idx_facilities_location", table_name="facilities", postgresql_using="gist")
    op.drop_index("ix_facilities_key", table_name="facilities")
    op.drop_table("facilities")

    op.drop_index(
        "idx_municipalities_boundary", table_name="municipalities", postgresql_using="gist"
    )
    op.drop_index("ix_municipalities_name", table_name="municipalities")
    op.drop_table("municipalities")
