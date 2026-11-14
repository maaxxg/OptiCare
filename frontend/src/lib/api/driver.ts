// API klijent za vozačku rutu prema specifikaciji GET /driver/{token}/route i POST /driver/{token}/status.
// Sukladno arhitekturi (E10-T1 [M]): prikazuje samo vrijeme ukrcaja, ime, adresu i napomenu o pokretljivosti,
// bez odjela i bez razloga pregleda (zaštita privatnosti).
// Sva polja prate snake_case konvenciju backend Pydantic modela.

export type MobilityClass = 'walks' | 'cane' | 'wheelchair' | 'stretcher';

export const MOBILITY_LABELS: Record<MobilityClass, string> = {
	walks: 'Hoda',
	cane: 'Štap',
	wheelchair: 'Kolica',
	stretcher: 'Nosila'
};

export function getMobilityIcon(mobilityClass: MobilityClass): string {
	switch (mobilityClass) {
		case 'cane':
			return '🦯';
		case 'wheelchair':
			return '♿';
		case 'stretcher':
			return '🛏️';
		case 'walks':
		default:
			return '🚶';
	}
}

export type StopStatus =
	'pending' | 'arrived' | 'picked_up' | 'dropped_off' | 'no_show' | 'delayed';

export interface DriverStop {
	id: string;
	order: number;
	pickup_time: string; // format "07:15"
	patient_name: string;
	address: string;
	mobility_class: MobilityClass;
	mobility_note?: string | null;
	appointment_deadline: string; // npr. "09:00", "09:30"
	status: StopStatus;
}

export interface DriverRouteResponse {
	token: string;
	vehicle_title: string; // npr. "Sanitetski prijevoz — Gospić 1"
	date: string; // "2026-11-18" (formatiran u Europe/Zagreb)
	destination: string; // "Opća bolnica Gospić"
	first_appointment_time: string; // "09:00" - prvi termin u bolnici na ovoj ruti
	stops: DriverStop[];
}

// Inicijalni mock podaci samo za demo rutu (E10-T1 [M]).
const MOCK_ROUTES: Record<string, DriverRouteResponse> = {
	demo: {
		token: 'demo',
		vehicle_title: 'Sanitetski prijevoz — Gospić 1',
		date: '2026-11-18', // 18. 11. 2026. je srijeda
		destination: 'Opća bolnica Gospić',
		first_appointment_time: '09:00',
		stops: [
			{
				id: 'stop-1',
				order: 1,
				pickup_time: '07:15',
				patient_name: 'Marko Horvat',
				address: 'Ulica Lipova 12, Gornje Selo',
				mobility_class: 'walks',
				mobility_note: 'Pomoć pri ulasku',
				appointment_deadline: '09:00',
				status: 'picked_up'
			},
			{
				id: 'stop-2',
				order: 2,
				pickup_time: '07:25',
				patient_name: 'Ana Kovač',
				address: 'Bregovita 5, Donje Selo',
				mobility_class: 'cane',
				mobility_note: 'Teže pokretna',
				appointment_deadline: '09:15',
				status: 'picked_up'
			},
			{
				id: 'stop-3',
				order: 3,
				pickup_time: '07:40',
				patient_name: 'Ivan Marić',
				address: 'Vrtna 18, Gornje Selo',
				mobility_class: 'wheelchair',
				mobility_note: 'Potrebna rampa za kolica',
				appointment_deadline: '09:30',
				status: 'pending'
			},
			{
				id: 'stop-4',
				order: 4,
				pickup_time: '07:55',
				patient_name: 'Marija Novak',
				address: 'Školska 3, Donje Selo',
				mobility_class: 'walks',
				mobility_note: '1. kat bez lifta, pratnja do vozila',
				appointment_deadline: '10:00',
				status: 'pending'
			}
		]
	}
};

// Lokalna memorija statusa dok backend ne bude spojen
const memoryStatusStore = new Map<string, Record<string, StopStatus>>();

// Backend E7 (FastAPI) još ne postoji u ovoj fazi (E10-T1 [M]).
// Postaviti na true kad backend endpoint /api/driver/{token}/route postane dostupan.
const USE_BACKEND = false;

/**
 * Dohvaća rutu vozača preko jednodnevnog tokena: GET /driver/{token}/route
 * Ako token nije valjan ili ruta nije pronađena, funkcija baca iznimku kako bi se prikazao ekran greške.
 */
export async function getDriverRoute(token: string): Promise<DriverRouteResponse> {
	if (USE_BACKEND) {
		const res = await fetch(`/api/driver/${encodeURIComponent(token)}/route`);
		if (!res.ok) {
			throw new Error(`Ruta za navedeni link nije pronađena (${res.status}).`);
		}
		const data = (await res.json()) as DriverRouteResponse;
		return data;
	}

	// Mock je definiran isključivo za 'demo' token; svi ostali tokeni završavaju greškom
	const base = MOCK_ROUTES[token];
	if (!base) {
		throw new Error('Ruta za ovaj link nije pronađena ili je istekla.');
	}

	// Primijeni lokalno ažurirane statuse za ovaj token
	const tokenStatuses = memoryStatusStore.get(token);
	if (tokenStatuses) {
		return {
			...base,
			stops: base.stops.map((s) => ({
				...s,
				status: tokenStatuses[s.id] ?? s.status
			}))
		};
	}

	return {
		...base,
		stops: base.stops.map((s) => ({ ...s }))
	};
}

/**
 * Ažurira status stajališta: POST /driver/{token}/status
 */
export async function updateDriverStopStatus(
	token: string,
	stopId: string,
	status: StopStatus
): Promise<void> {
	if (USE_BACKEND) {
		const res = await fetch(`/api/driver/${encodeURIComponent(token)}/status`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ stop_id: stopId, status, timestamp: new Date().toISOString() })
		});
		if (!res.ok) {
			throw new Error(`Greška pri ažuriranju statusa (${res.status}).`);
		}
		return;
	}

	// Zabilježi lokalno u memoriji
	const current = memoryStatusStore.get(token) ?? {};
	current[stopId] = status;
	memoryStatusStore.set(token, current);
}

/**
 * Formatira datum rute u lokalizirani hrvatski format u zoni Europe/Zagreb
 * Primjer: "2026-11-18" -> "Srijeda, 18. studenoga"
 */
export function formatRouteDate(isoDateStr: string): string {
	if (!isoDateStr) return '';
	const [y, m, d] = isoDateStr.split('-').map(Number);
	const date =
		!isNaN(y) && !isNaN(m) && !isNaN(d)
			? new Date(Date.UTC(y, m - 1, d, 12, 0, 0))
			: new Date(isoDateStr);

	const formatted = new Intl.DateTimeFormat('hr-HR', {
		timeZone: 'Europe/Zagreb',
		weekday: 'long',
		day: 'numeric',
		month: 'long'
	}).format(date);

	return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

/**
 * Vraća URL za navigaciju do zadane adrese (Google Maps / Apple Maps kompatibilno)
 */
export function getNavigationUrl(address: string): string {
	return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`;
}
