# AGENTS.md

Notes for AI coding agents working in this repo.

## Project shape

- `backend/` — FastAPI app (`main.py`). Loads `hotels.csv` and `trips.csv`
  into memory on startup and joins them by `hotel_id`. No database yet —
  see "Next up" below.
- `frontend/` — Vue 3 + Vite SPA. Single component (`src/App.vue`) with a
  search box and results table. Talks to the backend over plain `fetch`,
  no state management library, no router.

## Gotchas

- **`hotels.csv` and `trips.csv` have a UTF-8 BOM.** Both files are read
  with `encoding="utf-8-sig"` in `backend/main.py:load_records`. If you add
  a new CSV loader, use the same encoding or `csv.DictReader` will raise
  `KeyError` on the first column (it'll look like `hotel_id` doesn't exist
  when it's actually `﻿hotel_id`).
- **CORS origins are hardcoded** in `backend/main.py` (`allow_origins`).
  Vite falls back to the next free port if 5173 is taken locally, so both
  5173 and 5174 are allowlisted, plus 8080/3000 as common alternates. If
  the frontend runs somewhere else, add that origin or requests will be
  silently blocked by the browser (not the server — check the browser
  console, not the server logs, when debugging this).
- **`API_BASE` in `frontend/src/App.vue` is hardcoded** to
  `http://127.0.0.1:8123`. There's no `.env`/build-time config yet.
- The backend has no persistence layer — every restart reloads straight
  from the CSVs, so there are no migrations to run and nothing to seed.

## Conventions

- Backend: no ORM, no Pydantic models for the CSV rows — records are plain
  dicts read straight from `csv.DictReader`. Keep it that way unless the
  next task (SQLite) calls for real models.
- Frontend: `<script setup>` SFCs, no comments unless something is
  genuinely non-obvious.
- Don't add error-handling scaffolding for cases that can't occur (e.g. no
  need to guard against a missing CSV file — if it's missing, the app
  should fail loudly at startup).

## Next up

Part 2 of this project replaces the CSV-backed read-only search with a
SQLite-backed CRUD API. See `handoffs/current.md` for the current state
and what's expected next.
