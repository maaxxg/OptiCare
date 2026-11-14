# Upute za implementaciju — OptiCare Frontend promjene

> [!IMPORTANT]
> **Smiješ mijenjati SAMO datoteke unutar `frontend/` mape.** Ostale mape (`backend/`, `data/`, `db/`, `docs/`, `ml/`) smiješ samo čitati/gledati kao referencu. Nikada ne mijenjaj ništa izvan `frontend/`.

---

## Tehnički kontekst

- **Framework:** SvelteKit (Svelte 5 s runes modom)
- **Adapter:** `@sveltejs/adapter-static` (client-only, `ssr = false` u `+layout.ts`)
- **Stanje:** Nema backenda za sada — koristi se `sessionStorage` putem store-a u `src/lib/stores/patients.ts`
- **CSS:** Globalni stilovi u `src/lib/styles/global.css`, komponente koriste `<style>` blokove
- **Jezični mod:** Svelte 5 runes (`$state`, `$props`, `$derived`, itd.) — **NE koristi** Svelte 4 syntax (`export let`, `$:`, itd.)
- **Rute:** SvelteKit file-based routing u `src/routes/`
- **Import aliasi:** `#lib` → `./src/lib`, `#lib/*` → `./src/lib/*`
- **Jezik sučelja:** Hrvatski

---

## Postojeća struktura datoteka

```
frontend/
├── src/
│   ├── app.html                          # Glavni HTML shell
│   ├── app.d.ts                          # TypeScript deklaracije
│   ├── lib/
│   │   ├── index.ts                      # Lib barrel export
│   │   ├── assets/
│   │   │   └── favicon.svg               # TRENUTNI favicon (Svelte logo — treba zamijeniti)
│   │   ├── stores/
│   │   │   └── patients.ts               # Patient store (sessionStorage)
│   │   └── styles/
│   │       └── global.css                # Globalni CSS stilovi
│   └── routes/
│       ├── +layout.svelte                # Root layout (favicon, global CSS import)
│       ├── +layout.ts                    # ssr = false
│       ├── +page.svelte                  # Dashboard (home page)
│       ├── unos/
│       │   └── +page.svelte              # Obrazac za unos pacijenta
│       └── raspored/
│           └── +page.svelte              # Raspored/tablica pacijenata
├── util/
│   ├── OptiCare_Full.svg                 # FULL logo (tekst + ikona) — koristiti kao logo
│   ├── OptiCare_Ikona.svg               # SAMO ikona (srce/ruka) — koristiti kao favicon
│   ├── WhatsApp Image ... 00.20.13.jpeg  # Dizajn mockup rasporeda (referenca)
│   ├── WhatsApp Image ... 02.18.07.jpeg  # Dizajn mockup s popup notifikacijom
│   └── WhatsApp Image ... 02.18.06.jpeg  # Dizajn popup notifikacije (detalj)
├── package.json
├── vite.config.ts
└── tsconfig.json
```

---

## Zadaci za implementaciju

### 1. Zamjena favicona — `OptiCare_Ikona.svg` umjesto Svelte loga

**Što napraviti:**

- Kopiraj sadržaj datoteke `frontend/util/OptiCare_Ikona.svg` u `frontend/src/lib/assets/favicon.svg` (zamijeni postojeći Svelte logo favicon).
- `+layout.svelte` već importa `#lib/assets/favicon.svg` i koristi ga kao `<link rel="icon">` — dakle samo treba zamijeniti sadržaj te datoteke; import ostaje isti.

**Sadržaj `OptiCare_Ikona.svg`:**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<svg id="Layer_2" data-name="Layer 2" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 136.36 88.18">
  <defs>
    <style>
      .cls-1 {
        fill: #92c18b;
      }
    </style>
  </defs>
  <g id="Layer_2-2" data-name="Layer 2">
    <g id="Template_20261114_005138.jpg" data-name="Template 20261114 005138.jpg">
      <path class="cls-1" d="M135.85,39.17q-2.5,13.59-14.64,23.09t-27.02,18.61l-5.93,3.69-3.46,2.15c-1.03.71-2.15,1.15-3.36,1.34-.57.09-1.14.13-1.69.13H20.05c-2.74,0-4.97-2.23-4.97-4.97,0-1.37.56-2.61,1.45-3.51.9-.9,2.14-1.45,3.51-1.45h15.96c1.37,0,2.61-.56,3.52-1.45.9-.9,1.45-2.14,1.45-3.51,0-2.29-1.54-4.21-3.65-4.79-.05-.01-.1-.03-.16-.04-.37-.09-30.98,0-30.98,0q-.69,0-1.32-.18c-2.1-.58-3.65-2.5-3.65-4.79,0-1.37.56-2.61,1.45-3.52.9-.9,2.14-1.45,3.51-1.45h30.43c1.12-.14,2.13-.65,2.9-1.42.9-.9,1.45-2.14,1.45-3.51,0-2.4-1.71-4.4-3.97-4.87-.32-.06-.66-.1-1-.1l-22.19.1c-.34,0-.68-.04-1-.1-2.26-.46-3.97-2.47-3.97-4.87,0-1.37.56-2.61,1.45-3.51.9-.9,2.14-1.45,3.51-1.45h22.19c1.37,0,2.61-.56,3.52-1.45.9-.9,1.45-2.14,1.45-3.51,0-2.74-2.23-4.97-4.97-4.97H4.97c-2.74,0-4.97-2.22-4.97-4.97,0-1.37.56-2.61,1.45-3.52.9-.9,2.14-1.45,3.51-1.45h36.97q2.55-9.08,10.21-14.35Q60.97-1.55,72.08.52q6.27,1.15,11.33,4.84,5.06,3.67,8.11,9.02c3.17-2.59,6.77-4.44,10.8-5.52q6.05-1.64,12.31-.48,11.12,2.04,17.19,10.87,6.08,8.82,4.02,19.94v-.02Z"/>
    </g>
  </g>
</svg>
```

---

### 2. Zamjena zelenog kruga s OptiCare_Full.svg logom

**Što napraviti:**

- Na svim stranicama (`+page.svelte`, `unos/+page.svelte`, `raspored/+page.svelte`) postoji `<div class="logo-dot"></div>` — to je zeleni krug koji služi kao placeholder za logo.
- Zamijeni taj zeleni krug sa SVG slikom `OptiCare_Full.svg`.

**Koraci:**

1. Kopiraj `frontend/util/OptiCare_Full.svg` u `frontend/src/lib/assets/opticare-logo.svg`
2. U svakoj stranici koja koristi `<div class="logo-dot"></div>`, zamijeni sa:
   ```svelte
   <img src={logo} alt="OptiCare" class="logo-full" />
   ```
   I dodaj import na vrhu `<script>` bloka:
   ```ts
   import logo from '#lib/assets/opticare-logo.svg';
   ```
3. U `global.css`, promijeni `.logo-dot` stil ili dodaj novi `.logo-full`:
   ```css
   .logo-full {
   	height: 48px;
   	width: auto;
   	flex-shrink: 0;
   }
   ```
4. Obriši ili zakomentiraj stari `.logo-dot` CSS ako ga više ništa ne koristi.

---

### 3. Login stranica za doktora — PRVA STRANICA

**Što napraviti:**

- Napravi novu login stranicu koja se prikazuje **PRIJE** dashboarda.
- Login je samo za doktora/sestru (ne za pacijenta). Ovo je frontend-only (nema backend auth-a za sada).
- Login treba biti prva stvar koju korisnik vidi.

**Implementacija:**

#### 3a. Napravi auth store: `src/lib/stores/auth.ts`

```ts
// Simple client-side auth state.
// No real authentication — just tracks if the doctor has "logged in" on this device.

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
```

#### 3b. Napravi login rutu: `src/routes/login/+page.svelte`

- Stranica s OptiCare logom (Full SVG) na vrhu, centrirano
- Naslov: "Prijava u sustav"
- Polja:
  - **Korisničko ime** (text input)
  - **Lozinka** (password input)
- Gumb: "Prijavi se" (zeleni, kao `btn-primary`)
- Validacija: oba polja moraju biti popunjena. Za sada prihvati **bilo koji** unos (nema backend provjere).
- Na uspješnu "prijavu": pozovi `login(korisničkoIme)` iz auth store-a i preusmjeri na `/` (dashboard) pomoću `goto(resolve('/'))`.
- Vizualni stil: isti kao ostatak app-a (zelena tema, pill inputi, zaobljeni kutovi). Logo na vrhu, centrirano. Forma centrirano na stranici. Ugodan, čist dizajn.

#### 3c. Dodaj auth guard u `+layout.svelte`

U root `+layout.svelte`, dodaj provjeru: ako korisnik **nije** prijavljen i **nije** na `/login` ruti, preusmjeri ga na `/login`.

```svelte
<script lang="ts">
	import favicon from '#lib/assets/favicon.svg';
	import '#lib/styles/global.css';
	import type { LayoutProps } from './$types';
	import { isLoggedIn } from '#lib/stores/auth.js';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { onMount } from 'svelte';

	let { children }: LayoutProps = $props();

	onMount(() => {
		if (!isLoggedIn() && page.url.pathname !== resolve('/login')) {
			goto(resolve('/login'));
		}
	});
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

{@render children()}
```

> [!WARNING]
> Provjeri da `page` radi ispravno u Svelte 5 / SvelteKit kontekstu. Možda treba koristiti `import { page } from '$app/state'` ili `import { page } from '$app/stores'`, ovisno o verziji. Provjeri SvelteKit docs za Svelte 5.

#### 3d. Dodaj logout gumb na dashboard (`+page.svelte`)

- Gore desno na dashboard stranici (u headeru, pored loga) prikaži ime doktora i mali "Odjava" link/gumb.
- Klik na "Odjava" poziva `logout()` iz auth store-a i preusmjerava na `/login`.

---

### 4. Ručni unos vremena pregleda — gumb sa strane na unos stranici

**Što napraviti:**

- Na stranici `unos/+page.svelte`, dodaj mogućnost da doktor **ručno unese vrijeme pregleda** za pacijenta.
- Ovo je gumb/panel sa strane (sidebar drawer ili collapsible sekcija) koji se otvara klikom.

**Implementacija:**

#### 4a. Proširi `Patient` interface u `patients.ts`

Dodaj polja:

```ts
export interface Patient {
	id: string;
	name: string;
	location: string;
	needsTransport: boolean;
	willingToDrive: boolean;
	description: string;
	createdAt: string;
	// Novo: ručno uneseno vrijeme pregleda
	examTime?: string; // format "HH:MM", npr. "10:00"
	departureTime?: string; // format "HH:MM", npr. "07:30"
	returnTime?: string; // format "HH:MM", npr. "16:00"
}
```

#### 4b. Dodaj floating side-button na `unos/+page.svelte`

- **Gumb sa strane** (fiksno pozicioniran na desnoj strani ekrana, vertikalan tekst ili ikona sata) s tekstom "⏰ Vrijeme" ili slično.
- Klik otvara **side panel** (drawer) koji izlazi s desne strane.
- U side panelu su tri `<input type="time">` polja:
  - **Vrijeme pregleda** (examTime)
  - **Vrijeme polaska** (departureTime)
  - **Vrijeme povratka** (returnTime)
- Ova polja su **opcionalna** — doktor ih ne mora ispuniti. Ako ih ispuni, spremaju se uz pacijenta.
- Panel se zatvara klikom na X ili klikom izvan panela.

**CSS za side panel:**

```css
.side-panel {
	position: fixed;
	top: 0;
	right: 0;
	width: 320px;
	max-width: 90vw;
	height: 100vh;
	background: #fff;
	box-shadow: -4px 0 20px rgba(0, 0, 0, 0.15);
	padding: 32px 24px;
	z-index: 200;
	transform: translateX(100%);
	transition: transform 0.3s ease;
}

.side-panel.open {
	transform: translateX(0);
}

.side-panel-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.3);
	z-index: 199;
}

.side-panel-trigger {
	position: fixed;
	right: 0;
	top: 50%;
	transform: translateY(-50%);
	background: var(--green);
	color: white;
	border: none;
	padding: 16px 8px;
	border-radius: 12px 0 0 12px;
	cursor: pointer;
	writing-mode: vertical-lr;
	font-weight: 600;
	font-size: 0.9rem;
	z-index: 50;
	box-shadow: var(--shadow-md);
}
```

#### 4c. Ažuriraj `addPatient` poziv

Kad se forma submitta, proslijedi i vremena iz side panela (ako su unesena):

```ts
addPatient({
	name: name.trim(),
	location,
	needsTransport,
	willingToDrive,
	description: description.trim(),
	examTime: examTime || undefined,
	departureTime: departureTime || undefined,
	returnTime: returnTime || undefined
});
```

---

### 5. Automatski redirect na raspored + popup notifikacija nakon unosa pacijenta

**Što napraviti:**

- Kad se pacijent **uspješno unese** (submit forme), umjesto samo toast poruke:
  1. Preusmjeri korisnika na **`/raspored`** stranicu pomoću `goto(resolve('/raspored'))`
  2. Na raspored stranici prikaži **popup notifikaciju** (modal) sa informacijama o novounesenom pacijentu

**Dizajn popup notifikacije** (prema WhatsApp mockupima u `util/` mapi):

Popup je centriran modal s bijelom pozadinom, zaobljenim kutovima i sjenom, koji sadrži:

```
┌─────────────────────────────────┐
│                                 │
│   Odgovor agenta umjetne        │
│       inteligencije:            │
│                                 │
│  Nakon analize podataka         │
│  pacijenta preporučam termin    │
│  za [vrsta pregleda] na         │
│  [ustanova] u [vrijeme],        │
│  organizirani prijevoz bi      │
│  pokupio pacijenta u [polazak]  │
│  i pretpostavljeno vrijeme      │
│  povratka je [povratak]         │
│                                 │
│  ┌─────────────────────────┐    │
│  │    Prihvati termin      │    │  ← zeleni gumb
│  └─────────────────────────┘    │
│  ┌─────────────────────────┐    │
│  │   Preporuči novi termin │    │  ← bijeli gumb s bordurom
│  └─────────────────────────┘    │
│  ┌─────────────────────────┐    │
│  │  Ručno upiši novi termin│    │  ← bijeli gumb s bordurom
│  └─────────────────────────┘    │
│  ┌─────────────────────────┐    │
│  │     Prekid radnji       │    │  ← crvenkasti/ružičasti gumb
│  └─────────────────────────┘    │
│                                 │
│  ┌─────────────────────────┐    │
│  │  ⏸ Stavi na čekanje     │    │  ← NOVO: žuti/narančasti gumb
│  └─────────────────────────┘    │
│                                 │
└─────────────────────────────────┘
```

**Implementacija:**

#### 5a. Napravi notifikacijski store: `src/lib/stores/notification.ts`

```ts
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

export function clearPendingNotification(): void {
	try {
		sessionStorage.removeItem(STORAGE_KEY);
	} catch {
		/* ignore */
	}
}
```

#### 5b. Izmijeni `unos/+page.svelte` handleSubmit

Nakon što se pacijent spremi, postavi pending notifikaciju i preusmjeri na raspored:

```ts
import { setPendingNotification } from '#lib/stores/notification.js';

function handleSubmit(e: SubmitEvent) {
	e.preventDefault();
	// ... validacija ...

	const newPatient = addPatient({
		name: name.trim(),
		location,
		needsTransport,
		willingToDrive,
		description: description.trim(),
		examTime: examTime || undefined,
		departureTime: departureTime || undefined,
		returnTime: returnTime || undefined
	});

	// Postavi notifikaciju za raspored stranicu
	setPendingNotification({
		patientName: newPatient.name,
		description: newPatient.description,
		location: newPatient.location,
		examTime: newPatient.examTime,
		departureTime: newPatient.departureTime,
		returnTime: newPatient.returnTime,
		needsTransport: newPatient.needsTransport,
		onHold: false
	});

	// Preusmjeri na raspored
	goto(resolve('/raspored'));
}
```

#### 5c. Izmijeni `raspored/+page.svelte` — prikaži popup

Na `onMount`, provjeri postoji li pending notifikacija. Ako da, prikaži modal.

```svelte
<script lang="ts">
	import {
		getPendingNotification,
		clearPendingNotification,
		type PendingNotification
	} from '#lib/stores/notification.js';
	import { onMount } from 'svelte';

	let notification: PendingNotification | null = $state(null);
	let showModal = $state(false);

	onMount(() => {
		const pending = getPendingNotification();
		if (pending) {
			notification = pending;
			showModal = true;
		}
	});

	function acceptTerm() {
		clearPendingNotification();
		showModal = false;
		// Termin je prihvaćen — pacijent ostaje u rasporedu
	}

	function recommendNewTerm() {
		// Za sada samo zatvori modal i ostavi pacijenta
		clearPendingNotification();
		showModal = false;
	}

	function manualEntry() {
		// Otvori mogućnost ručnog unosa vremena
		// Ovdje možeš prikazati input polja za vrijeme unutar modala
		// ili preusmjeriti natrag na unos
		clearPendingNotification();
		showModal = false;
	}

	function cancelAction() {
		clearPendingNotification();
		showModal = false;
	}

	function putOnHold() {
		// Stavi notifikaciju na čekanje — termin se NE unosi
		// Notifikacija ostaje spremljena s onHold = true
		if (notification) {
			notification.onHold = true;
			// NE briši notifikaciju — ostaje do kad doktor ne odluči
		}
		showModal = false;
	}

	function resumeFromHold() {
		// Doktor skida s čekanja — prikaži modal ponovo
		if (notification) {
			notification.onHold = false;
			showModal = true;
		}
	}
</script>
```

**Modal HTML:**

```svelte
{#if showModal && notification}
	<div class="modal-overlay" onclick={cancelAction}>
		<div class="modal-card" onclick|stopPropagation>
			<h2 class="modal-title">Odgovor agenta umjetne inteligencije:</h2>
			<p class="modal-text">
				Nakon analize podataka pacijenta preporučam termin za {notification.description} u {notification.location}
				{#if notification.examTime}
					u {notification.examTime}
				{/if}
				{#if notification.needsTransport}
					, organizirani prijevoz bi pokupio pacijenta
					{#if notification.departureTime}
						u {notification.departureTime}
					{/if}
					{#if notification.returnTime}
						i pretpostavljeno vrijeme povratka je {notification.returnTime}
					{/if}
				{/if}
			</p>

			<div class="modal-actions">
				<button class="modal-btn modal-btn-green" onclick={acceptTerm}> Prihvati termin </button>
				<button class="modal-btn modal-btn-outline" onclick={recommendNewTerm}>
					Preporuči novi termin
				</button>
				<button class="modal-btn modal-btn-outline" onclick={manualEntry}>
					Ručno upiši novi termin
				</button>
				<button class="modal-btn modal-btn-red" onclick={cancelAction}> Prekid radnji </button>
				<button class="modal-btn modal-btn-yellow" onclick={putOnHold}> ⏸ Stavi na čekanje </button>
			</div>
		</div>
	</div>
{/if}
```

**"Na čekanju" indikator** — kad je notifikacija on hold, prikaži mali banner/gumb na vrhu raspored stranice:

```svelte
{#if notification && notification.onHold}
	<div class="on-hold-banner">
		<span>⏸ Termin za <strong>{notification.patientName}</strong> je na čekanju</span>
		<button class="btn-resume" onclick={resumeFromHold}>Nastavi</button>
	</div>
{/if}
```

---

### 6. Modal CSS stilovi

Dodaj u `global.css` ili u `<style>` blok raspored stranice:

```css
/* ─── Modal ────────────────────────── */

.modal-overlay {
	position: fixed;
	inset: 0;
	background: rgba(0, 0, 0, 0.5);
	display: flex;
	align-items: center;
	justify-content: center;
	z-index: 300;
}

.modal-card {
	background: #fff;
	border-radius: 24px;
	padding: 36px 32px;
	max-width: 400px;
	width: 90vw;
	box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
	text-align: center;
}

.modal-title {
	font-size: 1.4rem;
	font-weight: 800;
	margin-bottom: 16px;
	color: var(--text);
}

.modal-text {
	font-size: 0.95rem;
	color: var(--text-muted);
	margin-bottom: 28px;
	line-height: 1.6;
}

.modal-actions {
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.modal-btn {
	width: 100%;
	padding: 14px 20px;
	border-radius: var(--radius-pill);
	font-size: 1rem;
	font-weight: 600;
	font-family: var(--font-sans);
	cursor: pointer;
	transition:
		opacity 0.2s,
		transform 0.1s;
	border: 2px solid transparent;
}

.modal-btn:active {
	transform: scale(0.98);
}

.modal-btn-green {
	background: var(--green);
	color: white;
	border-color: var(--green-dark);
}

.modal-btn-outline {
	background: white;
	color: var(--text);
	border-color: #d4d4d4;
}

.modal-btn-red {
	background: #fce4e4;
	color: #c0392b;
	border-color: #f0c0c0;
}

.modal-btn-yellow {
	background: #fff3cd;
	color: #856404;
	border-color: #ffc107;
}

/* ─── On-hold banner ────────────────── */

.on-hold-banner {
	display: flex;
	align-items: center;
	justify-content: space-between;
	background: #fff3cd;
	border: 1px solid #ffc107;
	border-radius: var(--radius-md);
	padding: 12px 20px;
	margin-bottom: 20px;
	font-size: 0.92rem;
}

.btn-resume {
	background: var(--green);
	color: white;
	border: none;
	padding: 8px 20px;
	border-radius: var(--radius-pill);
	font-weight: 600;
	cursor: pointer;
	font-size: 0.85rem;
}
```

---

### 7. Prikaži ručno unesena vremena u raspored tablici

Na `raspored/+page.svelte`, u tablici gdje su stupci "Vrijeme polaska", "Vrijeme pregleda", "Vrijeme povratka" — ako pacijent ima `examTime`, `departureTime` ili `returnTime`, prikaži ih umjesto "—".

Zamijeni:

```svelte
<span class="center-col"><span class="time-badge-pill">—</span></span>
<span class="center-col"><span class="time-badge-pill">—</span></span>
<span class="center-col"><span class="time-badge-pill">—</span></span>
```

Sa:

```svelte
<span class="center-col">
	<span class="time-badge-pill">{p.departureTime ?? '—'}</span>
</span>
<span class="center-col">
	<span class="time-badge-pill">{p.examTime ?? '—'}</span>
</span>
<span class="center-col">
	<span class="time-badge-pill">{p.returnTime ?? '—'}</span>
</span>
```

---

## Sažetak svih promjena (checklist)

- [ ] **`src/lib/assets/favicon.svg`** — zamijeni sadržaj s `OptiCare_Ikona.svg`
- [ ] **`src/lib/assets/opticare-logo.svg`** — kopiraj `OptiCare_Full.svg` ovdje (nova datoteka)
- [ ] **`src/lib/stores/auth.ts`** — nova datoteka: auth store
- [ ] **`src/lib/stores/notification.ts`** — nova datoteka: notifikacijski store
- [ ] **`src/lib/stores/patients.ts`** — dodaj opcionalna polja `examTime`, `departureTime`, `returnTime` u `Patient` interface
- [ ] **`src/lib/styles/global.css`** — dodaj `.logo-full`, modal, side-panel, on-hold-banner stilove; makni ili zadrži `.logo-dot`
- [ ] **`src/routes/+layout.svelte`** — dodaj auth guard (redirect na `/login` ako nije prijavljen)
- [ ] **`src/routes/login/+page.svelte`** — nova datoteka: login stranica
- [ ] **`src/routes/+page.svelte`** — zamijeni `logo-dot` s Full SVG logom; dodaj ime doktora i logout gumb
- [ ] **`src/routes/unos/+page.svelte`** — zamijeni `logo-dot` s Full SVG logom; dodaj side panel za ručni unos vremena; ažuriraj `handleSubmit` da preusmjeri na `/raspored` s pending notifikacijom
- [ ] **`src/routes/raspored/+page.svelte`** — zamijeni `logo-dot` s Full SVG logom; dodaj modal za popup notifikaciju; dodaj on-hold banner; prikaži ručno unesena vremena u tablici

> [!CAUTION]
> **NE modificiraj** ništa izvan `frontend/` mape. Backend, data, docs, db i ml mape su samo za čitanje/referencu.

> [!TIP]
>
> - Koristi Svelte 5 runes syntax (`$state`, `$props`, `$derived`) — **NE** koristi stari Svelte 4 syntax.
> - Svi tekstovi na sučelju su na **hrvatskom** jeziku.
> - `onclick|stopPropagation` u Svelte 5 se piše kao `onclick={(e) => e.stopPropagation()}` ili koristi Svelte event modifier ako je dostupan. Provjeri Svelte 5 docs.
> - Testiraj da `sessionStorage` radi ispravno za sve store-ove.
