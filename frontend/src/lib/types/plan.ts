// Mirror of backend/app/plan_schemas.py (GET /api/plan?date=YYYY-MM-DD).
// Datetimes are ISO 8601 strings with the Europe/Zagreb offset; times are "HH:MM:SS".
// Enum values are codes: show Croatian labels from GET /api/codebooks.

export type PlanSource = 'mock' | 'solver';
export type StopKind =
	| 'depot_start'
	| 'pickup_home'
	| 'dropoff_facility'
	| 'pickup_facility'
	| 'dropoff_home'
	| 'depot_end';
export type EstimateSource = 'rules' | 'model';
export type AssignmentStatus = 'proposed' | 'confirmed' | 'modified' | 'completed';
export type UnservedReason =
	| 'no_slot_in_window'
	| 'no_eligible_vehicle'
	| 'no_vehicle_capacity'
	| 'max_ride_time'
	| 'location_missing'
	| 'solver_timeout'
	| 'sanitetski_order_needed';

export interface GeoPoint {
	lat: number;
	lon: number;
}

export interface Estimate {
	minutes: number;
	source: EstimateSource;
	version: string | null;
}

export interface PlanFacility {
	id: number;
	key: string;
	name: string;
	address: string | null;
	location: GeoPoint;
}

export interface PlanPatient {
	id: number;
	first_name: string;
	last_name: string;
	phone: string;
	address: string | null;
	settlement: string;
	municipality: string;
	location: GeoPoint | null;
	mobility_class: string;
	transport_entitlement: string;
	support_level: string;
}

export interface PlanSlot {
	id: number;
	facility_id: number;
	department: string;
	start_time: string;
	end_time: string | null;
}

export interface OutboundLeg {
	vehicle_id: number;
	pickup_time: string;
	facility_arrival_time: string;
}

export interface ReturnLeg {
	vehicle_id: number;
	pickup_time: string;
	home_dropoff_time: string;
}

export interface PlanAssignment {
	id: number;
	request_id: number;
	status: AssignmentStatus;
	is_locked: boolean;
	patient: PlanPatient;
	slot: PlanSlot;
	visit_type: string;
	urgency_class: string;
	outbound: OutboundLeg;
	return_leg: ReturnLeg | null;
	visit_duration: Estimate;
	carpool_driver_confirmed: boolean | null;
}

export interface RouteStop {
	seq: number;
	kind: StopKind;
	assignment_id: number | null;
	facility_id: number | null;
	location: GeoPoint;
	label: string;
	arrival_time: string;
	departure_time: string;
}

export interface PlanVehicle {
	id: number;
	key: string | null;
	name: string | null;
	provider_type: string;
	seats: number;
	wheelchair_spots: number;
	stretcher_spots: number;
	shift_start: string;
	shift_end: string;
	base_settlement: string | null;
	base_location: GeoPoint;
	driver_name: string | null;
	driver_phone: string | null;
	stops: RouteStop[];
	total_km: number | null;
	total_minutes: number | null;
}

export interface UnservedRequest {
	request_id: number;
	patient: PlanPatient;
	facility_id: number;
	department: string;
	visit_type: string;
	urgency_class: string;
	earliest_date: string;
	latest_date: string;
	reason: UnservedReason;
	reason_text: string;
}

export interface PlanMetrics {
	served: number;
	unserved: number;
	vehicles_used: number;
	planned_trips: number;
	baseline_trips: number;
	total_km: number;
	baseline_km: number;
}

export interface PlanResponse {
	date: string;
	source: PlanSource;
	generated_at: string;
	facilities: PlanFacility[];
	vehicles: PlanVehicle[];
	assignments: PlanAssignment[];
	unserved: UnservedRequest[];
	metrics: PlanMetrics | null;
}
