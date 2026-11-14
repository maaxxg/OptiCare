// Cosmetic demo login only: it accepts any input and is NOT access control.
// It just remembers a display name for this browser session. Real access
// control (if ever needed) belongs to the reverse proxy / a future auth task.

const STORAGE_KEY = 'opticare.auth';

interface AuthState {
	isLoggedIn: boolean;
	doctorName: string;
}

function loadAuth(): AuthState {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		return raw ? (JSON.parse(raw) as AuthState) : { isLoggedIn: false, doctorName: '' };
	} catch {
		return { isLoggedIn: false, doctorName: '' };
	}
}

function saveAuth(state: AuthState): void {
	try {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
	} catch {
		/* ignore */
	}
}

let state: AuthState = loadAuth();

export function isLoggedIn(): boolean {
	return state.isLoggedIn;
}

export function getDoctorName(): string {
	return state.doctorName;
}

export function login(doctorName: string): void {
	state = { isLoggedIn: true, doctorName };
	saveAuth(state);
}

export function logout(): void {
	state = { isLoggedIn: false, doctorName: '' };
	saveAuth(state);
}
