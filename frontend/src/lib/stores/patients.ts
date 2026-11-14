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
	// Ručno uneseno ili AI simulirano vrijeme pregleda
	examTime?: string; // format "HH:MM", npr. "10:00"
	departureTime?: string; // format "HH:MM", npr. "07:30"
	returnTime?: string; // format "HH:MM", npr. "16:00"
}

const STORAGE_KEY = 'opticare.patients';

// 6 početnih dummy klijenata s realističnim podacima za Ličko-senjsku županiju
const DUMMY_PATIENTS: Patient[] = [
	{
		id: 'dummy-1',
		name: 'Petar Šavorić',
		location: 'Gospić',
		needsTransport: true,
		willingToDrive: false,
		description: 'Kardiološki pregled (KBC Rebro)',
		createdAt: new Date(Date.now() - 3600000 * 5).toISOString(),
		examTime: '10:00',
		departureTime: '07:30',
		returnTime: '16:00'
	},
	{
		id: 'dummy-2',
		name: 'Marija Rukavina',
		location: 'Otočac',
		needsTransport: true,
		willingToDrive: false,
		description: 'Oftalmološki pregled (OB Gospić)',
		createdAt: new Date(Date.now() - 3600000 * 4).toISOString(),
		examTime: '10:30',
		departureTime: '08:00',
		returnTime: '15:30'
	},
	{
		id: 'dummy-3',
		name: 'Ivan Horvat',
		location: 'Korenica',
		needsTransport: true,
		willingToDrive: false,
		description: 'Fizikalna terapija i rehabilitacija',
		createdAt: new Date(Date.now() - 3600000 * 3).toISOString(),
		examTime: '11:15',
		departureTime: '07:45',
		returnTime: '16:30'
	},
	{
		id: 'dummy-4',
		name: 'Ana Devčić',
		location: 'Senj',
		needsTransport: false,
		willingToDrive: true,
		description: 'Radiološka dijagnostika (MR)',
		createdAt: new Date(Date.now() - 3600000 * 2).toISOString(),
		examTime: '11:00',
		departureTime: '08:15',
		returnTime: '15:00'
	},
	{
		id: 'dummy-5',
		name: 'Josip Kovačević',
		location: 'Perušić',
		needsTransport: false,
		willingToDrive: false,
		description: 'Ortopedski kontrolni pregled',
		createdAt: new Date(Date.now() - 3600000 * 1).toISOString(),
		examTime: '11:30',
		departureTime: '09:00',
		returnTime: '14:30'
	},
	{
		id: 'dummy-6',
		name: 'Katarina Modrić',
		location: 'Brinje',
		needsTransport: false,
		willingToDrive: true,
		description: 'Kontrola internista (EKG i ultrazvuk)',
		createdAt: new Date().toISOString(),
		examTime: '12:00',
		departureTime: '08:30',
		returnTime: '16:15'
	}
];

export function generateSimulatedTimes(): {
	examTime: string;
	departureTime: string;
	returnTime: string;
} {
	const presets = [
		{ examTime: '10:00', departureTime: '07:30', returnTime: '16:00' },
		{ examTime: '10:30', departureTime: '08:00', returnTime: '15:30' },
		{ examTime: '11:15', departureTime: '08:15', returnTime: '16:30' },
		{ examTime: '12:00', departureTime: '08:45', returnTime: '17:00' },
		{ examTime: '09:30', departureTime: '07:00', returnTime: '14:30' }
	];
	const randomPreset = presets[Math.floor(Math.random() * presets.length)];
	return randomPreset;
}

function load(): Patient[] {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw) as Patient[];
			if (parsed.length > 0) return parsed;
		}
		// Ako nema podataka u storageu, inicijaliziramo s dummy klijentima
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(DUMMY_PATIENTS));
		return DUMMY_PATIENTS;
	} catch {
		return DUMMY_PATIENTS;
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
	// Ako vremena nisu unesena ručno, AI ih automatski simulira
	const simulated = generateSimulatedTimes();
	const newPatient: Patient = {
		...patient,
		examTime: patient.examTime?.trim() ? patient.examTime : simulated.examTime,
		departureTime: patient.departureTime?.trim() ? patient.departureTime : simulated.departureTime,
		returnTime: patient.returnTime?.trim() ? patient.returnTime : simulated.returnTime,
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
