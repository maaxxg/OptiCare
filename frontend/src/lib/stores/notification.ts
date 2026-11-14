// Stores the last submitted patient info so the raspored page
// can show the AI popup notification.

export interface PendingNotification {
	patientName: string;
	description: string;
	location: string;
	examTime?: string;
	departureTime?: string;
	returnTime?: string;
	needsTransport: boolean;
	onHold: boolean; // Da li je doktor stavio na čekanje
}

const STORAGE_KEY = 'opticare.pending_notification';

export function setPendingNotification(n: PendingNotification): void {
	try {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(n));
	} catch {
		/* ignore */
	}
}

export function getPendingNotification(): PendingNotification | null {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		return raw ? (JSON.parse(raw) as PendingNotification) : null;
	} catch {
		return null;
	}
}

export function updatePendingNotification(n: PendingNotification): void {
	try {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(n));
	} catch {
		/* ignore */
	}
}

export function clearPendingNotification(): void {
	try {
		sessionStorage.removeItem(STORAGE_KEY);
	} catch {
		/* ignore */
	}
}
