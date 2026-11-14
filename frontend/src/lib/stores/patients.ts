// Patient requests entered on this device.
// Temporary: there is no backend intake endpoint yet. Requests are kept in
// sessionStorage so a page reload does not lose them; replace with POST /api/...
// once the intake API exists.

export interface Patient {
	id: string;
	name: string;
	location: string;
	needsTransport: boolean;
	willingToDrive: boolean;
	description: string;
	createdAt: string;
	// Times are entered manually by the nurse only; undefined when not entered.
	examTime?: string; // format "HH:MM", npr. "10:00"
	departureTime?: string; // format "HH:MM", npr. "07:30"
	returnTime?: string; // format "HH:MM", npr. "16:00"
}

const STORAGE_KEY = 'opticare.patients';

function load(): Patient[] {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		return raw ? (JSON.parse(raw) as Patient[]) : [];
	} catch {
		return [];
	}
}

function save(patients: Patient[]): void {
	try {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(patients));
	} catch {
		// Storage unavailable (private mode, blocked): keep working in memory.
	}
}

let patients: Patient[] = load();

export function getPatients(): Patient[] {
	return patients;
}

export function addPatient(patient: Omit<Patient, 'id' | 'createdAt'>): Patient {
	// Times are stored exactly as entered; nothing is generated or defaulted.
	const newPatient: Patient = {
		...patient,
		id: crypto.randomUUID(),
		createdAt: new Date().toISOString()
	};
	patients = [newPatient, ...patients];
	save(patients);
	return newPatient;
}

export function removePatient(id: string): void {
	patients = patients.filter((p) => p.id !== id);
	save(patients);
}
