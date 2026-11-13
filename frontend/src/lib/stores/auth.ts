// Auth store using simple module-level state

export interface User {
	name: string;
	role: string;
	hospital: string;
}

let currentUser: User | null = null;

export function getUser(): User | null {
	return currentUser;
}

export function login(name: string, role: string, hospital: string) {
	currentUser = { name, role, hospital };
}

export function logout() {
	currentUser = null;
}

export function isLoggedIn(): boolean {
	return currentUser !== null;
}
