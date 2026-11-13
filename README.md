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

Potrebno: [uv](https://docs.astral.sh/uv/) i Node.js 22 ili noviji.

Backend (http://localhost:8000, provjera na `/health`):

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

Pokretanje cijelog sustava jednom naredbom (`docker compose up`, s bazom PostgreSQL/PostGIS) dolazi u zadatku E0-T5.

## Provjere

```sh
cd backend && uv run pytest
cd frontend && npm run check
```
