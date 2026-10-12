# StayAlessio

A hotel/trip search and booking app: a FastAPI backend (SQLite-backed,
MVC-structured) exposes search and booking CRUD, and a Vue 3 frontend
lets you search hotels, book a trip as one of a few demo travelers, and
manage those bookings (cancel/delete).

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm

## Backend setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8123
```

The API is now available at `http://127.0.0.1:8123`. On first run it
creates `backend/travel.db` (SQLite, gitignored) and seeds it from
`hotels.csv` / `trips.csv` plus three demo travelers — seeding is
idempotent, so restarting the server never duplicates data or wipes
existing bookings.

### Environment variables

Secrets live in a single `.env` file at the **project root** (beside
`frontend/` and `backend/`, i.e. `/.env`, not `backend/.env`) — see
`backend/config.py`, which loads it from that fixed path. It holds:

```
GEOAPIFY_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_MODEL=
```

`OPENROUTER_API_KEY`/`OPENROUTER_MODEL` are read **only** on the backend
(`backend/chat.py`) for the saved-hotels chatbot — never sent to the
frontend and never included in any response or error message.

**The backend only reads `.env` once, at process startup** — if you add
or change a value in `.env`, you must restart the backend
(`uvicorn main:app ...`) for the change to take effect. `GET /api/health`
reports whether the key is configured, without ever exposing its value.

Endpoints:

- `GET /api/health` — basic health check; also reports
  `"geoapify_api_key": "configured"` or `"not configured"` (never the
  key itself).
- `GET /search?hotel_name=<query>` — case-insensitive partial match on
  hotel name, returns combined hotel + trip records as JSON (`[]` if
  nothing matches).
- `GET /users` — list the demo travelers (`user_id`, `name`) available to
  book as. There's no login system — see "Known limitations" below.
- `GET /bookings` — list all bookings, joined with trip/hotel/traveler
  details, most recent first.
- `POST /bookings` — body `{"trip_id": "...", "user_id": ...}`, creates a
  booking. 404s if the trip or user doesn't exist.
- `PATCH /bookings/{booking_id}/cancel` — sets a booking's status to
  `cancelled`. 404s if the booking doesn't exist.
- `DELETE /bookings/{booking_id}` — permanently removes a booking. 404s
  if it doesn't exist.
- `GET /api/saved-hotels/ids`, `GET /api/saved-hotels?zip=`,
  `POST /api/saved-hotels`, `DELETE /api/saved-hotels/{hotel_id}` — the
  local "saved hotels" feature backing the Nearby Hotels panel's Add/
  Remove buttons and local-first ZIP lookup.
- `POST /api/chat` — body `{"question": "..."}`. A two-stage RAG chatbot
  over `saved_hotels`/`saved_hotel_zip_searches`/`demo_hotel_nights`
  only: asks an LLM (via OpenRouter) for a single read-only SQL query,
  validates it (SQLite's own query authorizer — see `backend/chat.py` —
  rejects anything but a SELECT against those three tables, enforces a
  row limit of 50), runs it, then asks the LLM to answer using only the
  retrieved rows. Returns
  `{question, proposed_sql, rows, answer, status}`, where `status` is
  one of `answer` / `no_match` / `rejected` / `error` (HTTP 422 for a
  rejected query, 429 for an OpenRouter rate limit, 502/503 for other
  LLM failures).

To reset all data (including bookings and saved hotels), stop the server
and delete `backend/travel.db` — it will be recreated and reseeded on
next startup.

### Running the backend tests

```bash
cd backend
source .venv/bin/activate
python -m unittest discover -s tests -p "test_*.py"
```

All mutation tests (saved-hotels CRUD, the chatbot's SQL validation and
answer flow) run against a temporary SQLite file created per test — the
suite never touches `backend/travel.db`. The chatbot tests mock the LLM
call (`chat._call_openrouter`) rather than calling OpenRouter — no API
quota is used by the test suite. `backend/tests/fixtures/chat_sample.json`
is a labeled, fixed example of the full chat request/response flow that
`tests/test_chat.py` replays as a golden-path check.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Vite will print the local dev URL (defaults to `http://localhost:5173`,
but picks the next free port — e.g. `5174`, `5175` — if earlier ones are
already in use).

The frontend calls the backend directly at `http://127.0.0.1:8123` (see
`API_BASE` in `frontend/src/App.vue`). If you change the backend port, or
run the frontend on a port other than 5173/5174/5175/8080/3000, update
the `allow_origins` list in `backend/main.py` to match.

## Project layout

```
backend/
  models.py       Hotel/Trip/User/Booking dataclasses, schema, seeding
  controller.py   CRUD logic (search, bookings) — the business logic layer
  main.py         FastAPI routes — thin HTTP layer over controller.py
  hotels.csv, trips.csv   Seed data
  travel.db       SQLite database (gitignored, created on first run)
frontend/         Vue 3 + Vite app (single App.vue: search, book, manage)
docs/             Design notes
prompts/          Prompts used to build this project
handoffs/         Session handoff notes for continuing work
```

See [docs/design-note.md](docs/design-note.md) for how responsibilities
are split across the frontend and the backend's Model/Controller/Route
layers, and [handoffs/current.md](handoffs/current.md) for the current
state and what's not done yet.

## Known limitations

- No authentication — "Booking As" is a dropdown over a fixed set of
  three seeded demo travelers, not a real login.
- Hotels and trips are read-only reference data (seeded from CSV); only
  bookings have a write path.
- No automated test suite yet (verification has been manual/`curl`/
  browser-driven so far — see `handoffs/current.md`).
