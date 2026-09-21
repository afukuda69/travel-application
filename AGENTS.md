# AGENTS.md

Notes for AI coding agents working in this repo.

## Project shape

- `backend/` — FastAPI app, split MVC-style:
  - `models.py` — `Hotel`, `Trip`, `User`, `Booking` dataclasses, the
    SQLite schema (DDL), the connection helper, and startup seeding from
    the CSVs (hotels/trips) and demo travelers (users). No ORM — these are
    plain dataclasses with `from_row()` constructors, not SQLAlchemy
    models, so there's no live relationship traversal (e.g. no
    `hotel.trips`) — just foreign-key fields.
  - `controller.py` — all CRUD logic (search, list/create/cancel/delete
    bookings, list users) lives here as plain functions operating on the
    models. Raises `TripNotFoundError` / `UserNotFoundError` /
    `BookingNotFoundError` on missing records; doesn't know about HTTP.
  - `main.py` — thin FastAPI routes only. Each route calls into
    `controller.py` and translates its exceptions into `HTTPException`s.
    Don't put SQL or business logic directly in a route handler — that's
    the exact anti-pattern this file structure replaced.
  - SQLite file: `backend/travel.db` (gitignored, regenerated on first
    run from the CSVs + demo user seed).
- `frontend/` — Vue 3 + Vite SPA. Single component (`src/App.vue`):
  search card (hotel name + "Booking As" traveler picker), search results
  table, and a My Bookings table with Cancel/Delete. Talks to the backend
  over plain `fetch`, no state management library, no router.

## Gotchas

- **`hotels.csv` and `trips.csv` have a UTF-8 BOM.** Read with
  `encoding="utf-8-sig"` in `backend/models.py:_seed_if_empty`. Any new
  CSV loader needs the same encoding or `csv.DictReader` raises
  `KeyError` on the first column (it'll look like `hotel_id` doesn't
  exist when it's actually `﻿hotel_id`).
- **CORS origins are hardcoded** in `backend/main.py` (`allow_origins`).
  Vite falls back to the next free port if lower ones are taken locally
  — 5173/5174/5175 plus 8080/3000 are allowlisted. If the frontend runs
  somewhere else, add that origin or requests will be silently blocked by
  the browser (check the browser console, not the server logs).
- **`API_BASE` in `frontend/src/App.vue` is hardcoded** to
  `http://127.0.0.1:8123`. There's no `.env`/build-time config yet.
- **There's no auth.** `users` is a fixed set of three demo travelers
  seeded on first run (`DEMO_TRAVELER_NAMES` in `models.py`); the
  frontend's "Booking As" dropdown just picks a `user_id` from that list.
  Don't build a login flow unless asked — this was an explicit,
  intentionally-scoped-down decision.
- **SQLite persists across restarts** (unlike the old CSV-in-memory
  version). Seeding is idempotent — it only inserts hotels/trips/users if
  those tables are empty — so restarting the server does not wipe or
  duplicate bookings.
- **`LIKE` escaping**: `/search` escapes `%`/`_` in the query
  (`controller._escape_like`) so a literal percent sign or underscore in
  a hotel name search doesn't act as a SQL wildcard. Keep this if you
  touch the search query.

## Conventions

- Backend: no ORM (deliberate choice — see `controller.py` docstring-free
  functions using raw `sqlite3`). Models are dataclasses, not SQLAlchemy.
  Keep new CRUD logic in `controller.py`, not in route handlers.
- Frontend: `<script setup>` SFCs, no comments unless something is
  genuinely non-obvious.
- Don't add error-handling scaffolding for cases that can't occur (e.g. no
  need to guard against a missing CSV file — if it's missing, the app
  should fail loudly at startup).

## Next up

Part 1 (CSV search) and Part 2 (SQLite CRUD + booking/cancel/delete +
MVC split) are both done. See `handoffs/current.md` for what's verified
and what might come next — note that file may lag behind this one since
it's updated on request, not automatically.
