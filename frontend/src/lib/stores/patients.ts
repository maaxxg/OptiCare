// Patient store using simple module-level state

export interface Patient {
	id: string;
	name: string;
	location: string;
	needsTransport: boolean;
	willingToDrive: boolean;
	description: string;
	createdAt: Date;
}

let patients: Patient[] = [];

export function getPatients(): Patient[] {
	return patients;
}

export function addPatient(patient: Omit<Patient, 'id' | 'createdAt'>): Patient {
	const newPatient: Patient = {
		...patient,
		id: crypto.randomUUID(),
		createdAt: new Date()
	};
	patients = [...patients, newPatient];
	return newPatient;
}

export function removePatient(id: string) {
	patients = patients.filter((p) => p.id !== id);
}
