# OptiCare

Telefonski sustav koji zajedno planira zdravstveni termin i prijevoz od vrata do vrata za pacijente u Hrvatskoj koji sami ne mogu doći na pregled. Hackathon AI2MED, Izazov 20. Ciljno područje: Ličko-senjska županija.

## Dokumentacija

- [`docs/ARHITEKTURA.md`](docs/ARHITEKTURA.md) — arhitektura, model podataka, planer, ML, privatnost

## Struktura

```
backend/    FastAPI: unos, bodovanje, planer, obavijesti
frontend/   SvelteKit (samo klijent): obrazac za unos, dispečerska ploča, pogled za vozača
ml/         skripte za treniranje i generator sintetičkih podataka
data/       početni podaci (samo sintetički)
docs/       arhitektura
```

## Pokretanje

### Cijeli sustav (Docker)

Potrebno: Docker s Compose pluginom.

```sh
cp .env.example .env   # po želji; bez ključeva sve radi s mock adapterima
docker compose up
```

- Frontend: http://localhost:5173 (pozivi na `/api/...` proslijeđuju se backendu, npr. http://localhost:5173/api/health)
- Backend: http://localhost:8000 (provjera na `/health`)
- Baza PostgreSQL/PostGIS: `localhost:5432` (korisnik, lozinka i baza: `opticare`, samo za razvoj). Ako je port 5432 zauzet, u `.env` postavi `DB_PORT` (npr. `DB_PORT=5433`) i isti port upiši u `DATABASE_URL`.

Backend pri pokretanju provjerava postoji li PostGIS ekstenzija i ne starta ako je nema.

### Lokalno bez Dockera za aplikaciju

Potrebno: [uv](https://docs.astral.sh/uv/) i Node.js 22 ili noviji. Bazu pokrenite iz Composea: `docker compose up db`.

Backend (http://localhost:8000):

```sh
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

Frontend (http://localhost:5173):

```sh
cd frontend
npm install
npm run dev
```

Postavke se čitaju iz varijabli okoline i neobveznog `.env` u korijenu repozitorija (vidi `.env.example`).

## Provjere

```sh
cd backend && uv run pytest
cd frontend && npm run check
```
