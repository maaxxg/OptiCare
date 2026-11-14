// API klijent za vozačku rutu prema specifikaciji GET /driver/{token}/route i POST /driver/{token}/status.
// Sukladno arhitekturi (E10-T1 [M]): prikazuje samo vrijeme ukrcaja, ime, adresu i napomenu o pokretljivosti,
// bez odjela i bez razloga pregleda (zaštita privatnosti).

export type StopStatus =
	'pending' | 'arrived' | 'picked_up' | 'dropped_off' | 'no_show' | 'delayed';

export interface DriverStop {
	id: string;
	order: number;
	pickupTime: string; // format "07:15"
	patientName: string;
	address: string;
	mobilityNote?: string; // npr. "Samostalno pokretan", "Invalidska kolica", "Kat 2 bez lifta, pomoć do vozila"
	appointmentDeadline: string; // rok/termin u bolnici za ovog pacijenta, npr. "09:00", "09:30"
	status: StopStatus;
}

export interface DriverRouteResponse {
	token: string;
	vehicleTitle: string; // npr. "Sanitetski prijevoz — Gospić 1"
	driverRole: string; // "Vozač"
	date: string; // "2026-11-18" (formatiran u Europe/Zagreb)
	destination: string; // "Opća bolnica Gospić"
	firstAppointmentTime: string; // "09:00" - prvi termin u bolnici na ovoj ruti
	stops: DriverStop[];
}

// Inicijalni mock podaci ako backend E7 još nije aktivan
const MOCK_ROUTES: Record<string, DriverRouteResponse> = {
	demo: {
		token: 'demo',
		vehicleTitle: 'Sanitetski prijevoz — Gospić 1',
		driverRole: 'Vozač',
		date: '2026-11-18', // 18. 11. 2026. je srijeda
		destination: 'Opća bolnica Gospić',
		firstAppointmentTime: '09:00',
		stops: [
			{
				id: 'stop-1',
				order: 1,
				pickupTime: '07:15',
				patientName: 'Marko Horvat',
				address: 'Ulica Lipova 12, Gornje Selo',
				mobilityNote: 'Samostalno pokretan, pomoć pri ulasku',
				appointmentDeadline: '09:00',
				status: 'picked_up'
			},
			{
				id: 'stop-2',
				order: 2,
				pickupTime: '07:25',
				patientName: 'Ana Kovač',
				address: 'Bregovita 5, Donje Selo',
				mobilityNote: 'Teže pokretna (štap)',
				appointmentDeadline: '09:15',
				status: 'picked_up'
			},
			{
				id: 'stop-3',
				order: 3,
				pickupTime: '07:40',
				patientName: 'Ivan Marić',
				address: 'Vrtna 18, Gornje Selo',
				mobilityNote: 'Invalidska kolica (potrebna rampa)',
				appointmentDeadline: '09:30',
				status: 'pending'
			},
			{
				id: 'stop-4',
				order: 4,
				pickupTime: '07:55',
				patientName: 'Marija Novak',
				address: 'Školska 3, Donje Selo',
				mobilityNote: '1. kat bez lifta, potrebna pratnja do vozila',
				appointmentDeadline: '10:00',
				status: 'pending'
			}
		]
	}
};

// Lokalna memorija statusa dok backend ne bude spojen
const memoryStatusStore = new Map<string, Record<string, StopStatus>>();

/**
 * Dohvaća rutu vozača preko jednodnevnog tokena: GET /driver/{token}/route
 */
export async function getDriverRoute(token: string): Promise<DriverRouteResponse> {
	try {
		// Pokušaj poziva stvarnog backenda ako postoji
		const res = await fetch(`/api/driver/${encodeURIComponent(token)}/route`);
		if (res.ok) {
			const data = (await res.json()) as DriverRouteResponse;
			return data;
		}
	} catch {
		// Backend nije dostupan — koristi mock ugovor
	}

	// Mock fallback (za 'demo' ili bilo koji uneseni token)
	const base = MOCK_ROUTES[token] ?? {
		...MOCK_ROUTES.demo,
		token
	};

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

	return base;
}

/**
 * Ažurira status stajališta: POST /driver/{token}/status
 */
export async function updateDriverStopStatus(
	token: string,
	stopId: string,
	status: StopStatus
): Promise<void> {
	try {
		const res = await fetch(`/api/driver/${encodeURIComponent(token)}/status`, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ stopId, status, timestamp: new Date().toISOString() })
		});
		if (res.ok) return;
	} catch {
		// fallback
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
	// Parsiramo datum vodeći računa o vremenskoj zoni Europe/Zagreb
	const parts = isoDateStr.split('-');
	if (parts.length === 3) {
		const year = parseInt(parts[0], 10);
		const month = parseInt(parts[1], 10) - 1;
		const day = parseInt(parts[2], 10);
		const d = new Date(Date.UTC(year, month, day, 12, 0, 0));
		const formatter = new Intl.DateTimeFormat('hr-HR', {
			timeZone: 'Europe/Zagreb',
			weekday: 'long',
			day: 'numeric',
			month: 'long'
		});
		const formatted = formatter.format(d);
		return formatted.charAt(0).toUpperCase() + formatted.slice(1);
	}

	const d = new Date(isoDateStr);
	const formatter = new Intl.DateTimeFormat('hr-HR', {
		timeZone: 'Europe/Zagreb',
		weekday: 'long',
		day: 'numeric',
		month: 'long'
	});
	const formatted = formatter.format(d);
	return formatted.charAt(0).toUpperCase() + formatted.slice(1);
}

/**
 * Vraća URL za navigaciju do zadane adrese (Google Maps / Apple Maps kompatibilno)
 */
export function getNavigationUrl(address: string): string {
	return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}`;
}
