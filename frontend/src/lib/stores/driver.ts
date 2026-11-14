// Store za mobilno sučelje vozača

export interface RouteStop {
	id: string;
	order: number;
	time: string;
	patientName: string;
	address: string;
	pickedUp: boolean;
}

export interface DriverState {
	isLoggedIn: boolean;
	name: string;
	profession: string;
	hospital: string;
	stops: RouteStop[];
	deadline: string;
}

const STORAGE_KEY = 'opticare.driver';

const DEFAULT_STOPS: RouteStop[] = [
	{
		id: 'stop-1',
		order: 1,
		time: '07:15',
		patientName: 'Marko Horvat',
		address: 'Ulica Lipova 12, Gornje Selo',
		pickedUp: true
	},
	{
		id: 'stop-2',
		order: 2,
		time: '07:25',
		patientName: 'Ana Kovač',
		address: 'Bregovita 5, Donje Selo',
		pickedUp: true
	},
	{
		id: 'stop-3',
		order: 3,
		time: '07:40',
		patientName: 'Ivan Marić',
		address: 'Vrtna 18, Gornje Selo',
		pickedUp: false
	},
	{
		id: 'stop-4',
		order: 4,
		time: '07:55',
		patientName: 'Marija Novak',
		address: 'Školska 3, Donje Selo',
		pickedUp: false
	}
];

function loadDriver(): DriverState {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (raw) {
			return JSON.parse(raw) as DriverState;
		}
	} catch {
		// ignore
	}
	return {
		isLoggedIn: false,
		name: '',
		profession: 'Vozač',
		hospital: 'Opća bolnica Gospić',
		stops: DEFAULT_STOPS,
		deadline: '09:00'
	};
}

function saveDriver(state: DriverState): void {
	try {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
	} catch {
		// ignore
	}
}

let state: DriverState = loadDriver();

export function getDriverState(): DriverState {
	return state;
}

export function isDriverLoggedIn(): boolean {
	return state.isLoggedIn;
}

export function loginDriver(name: string, profession: string, hospital: string): void {
	state = {
		...state,
		isLoggedIn: true,
		name: name || 'Vozač',
		profession: profession || 'Vozač',
		hospital: hospital || 'Opća bolnica Gospić'
	};
	saveDriver(state);
}

export function logoutDriver(): void {
	state = {
		...state,
		isLoggedIn: false
	};
	saveDriver(state);
}

export function togglePickUp(stopId: string): void {
	state = {
		...state,
		stops: state.stops.map((stop) =>
			stop.id === stopId ? { ...stop, pickedUp: !stop.pickedUp } : stop
		)
	};
	saveDriver(state);
}
