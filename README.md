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

### Prelazak s mock adaptera na stvarne servise

Zadano je sve `mock` i radi bez mreže i bez ključeva. Za stvarne servise postavi u `.env`:

- LLM (bilo koji OpenAI-kompatibilni poslužitelj): `LLM_BACKEND=api`, `LLM_BASE_URL` (do `/chat/completions`, bez tog nastavka), `LLM_MODEL` i, ako ga poslužitelj traži, `LLM_API_KEY`.
- Rute: `ROUTING_BACKEND=ors` i `ORS_API_KEY` (po potrebi `ORS_BASE_URL`).

Nakon izmjene ponovno pokreni backend. Za demo koristi samo sintetičke podatke jer upiti odlaze na vanjske servise.

## Provjere

```sh
cd backend && uv run python check.py   # ruff, format check, mypy, pytest
cd frontend && npm run check:all       # prettier, eslint, svelte-check
```

GitHub Actions (`.github/workflows/ci.yml`) pokreće obje provjere na svaki push na `main` i na svaki pull request; backend testovi tada rade nad PostGIS servisom.

Testovi baze (`backend/tests/test_db_postgis.py`, `backend/tests/test_db_schema.py`) su opcionalni i lokalno se preskaču. Za pokretanje: `docker compose up db`, zatim `cd backend && RUN_DB_TESTS=1 uv run pytest tests/test_db_postgis.py tests/test_db_schema.py` (PowerShell: `$env:RUN_DB_TESTS=1; uv run pytest tests/test_db_postgis.py tests/test_db_schema.py`). Testovi sheme sami pokreću migracije (`upgrade head`, `downgrade base`) nad bazom iz `DATABASE_URL`, pa je koriste samo za razvojnu bazu: na kraju svakog testa shema se vraća na prazno stanje.

## Migracije baze

Shema se primjenjuje Alembicom. Prvo pokreni bazu (`docker compose up db`), zatim:

```sh
cd backend
uv run alembic upgrade head
```

(PowerShell: isto, `cd backend; uv run alembic upgrade head`.) Povratak na prazno stanje: `uv run alembic downgrade base`. Iz kontejnera: `docker compose exec backend alembic upgrade head`, ako je backend pokrenut preko Composea.
