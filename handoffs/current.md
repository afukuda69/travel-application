# Handoff — 2026-09-11

## What works

- **Backend** (`backend/main.py`): FastAPI app loads `hotels.csv` and
  `trips.csv` on startup, joins them by `hotel_id`, and exposes
  `GET /search?hotel_name=` with case-insensitive partial matching.
  Returns `[]` when nothing matches. CORS is enabled for local Vite dev
  origins (5173, 5174, 8080, 3000).
- **Frontend** (`frontend/src/App.vue`): Vue 3 SPA with a text input,
  Search button, and results table (`hotel_name`, `city`, `trip_name`,
  `check_in`, `check_out`, `nightly_rate_usd`). Shows "No results found."
  on an empty result set, and a distinct message if the API can't be
  reached.

## What was checked

- Backend started under `uvicorn` and hit directly with `curl`:
  - Partial, case-insensitive match (`harbor`, `INN`) returns the correct
    joined records.
  - No-match query and empty query both return `[]` / full data as
    expected without erroring.
  - Fixed a `KeyError: 'hotel_id'` caused by a UTF-8 BOM in both CSV
    files — loader now reads with `encoding="utf-8-sig"`.
  - CORS preflight (`OPTIONS`) from `http://localhost:5173` and
    `http://localhost:5174` both return the correct
    `access-control-allow-origin` header.
- Frontend: `npm install` and `npm run build` both succeed. Ran `npm run
  dev` against the live backend and confirmed the dev server serves the
  app and the CORS-allowed origin matches the port Vite actually picked
  (5174, since 5173 was occupied by an unrelated local process on this
  machine).
- Manually tested in the browser: a successful hotel search and a
  no-match search both worked as expected (results table renders
  correctly; "No results found." shows on zero matches).
- Not done: no automated test suite exists yet (no pytest/vitest).

## Next task — Part 2: SQLite CRUD

Replace the CSV-backed, read-only data layer with a SQLite database and a
full CRUD API:

- Design tables for `hotels` and `trips` (mirroring the current CSV
  columns) and a migration/seed step that loads the existing CSVs once.
- Add `POST`/`PUT`/`DELETE` endpoints (in addition to the existing
  `GET /search`) for both hotels and trips.
- Decide whether `combined_records` stays a startup-computed in-memory
  join or becomes a live SQL join per request now that data can change
  after startup — the latter is probably correct once writes exist.
- Update the frontend if/when write operations need UI (out of scope
  until asked for).
- Add a minimal test suite (pytest for the backend at least) — none
  exists yet and this is a good point to start one, since CRUD
  correctness is harder to eyeball via `curl` than a read-only search.
