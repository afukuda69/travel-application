# Travel Application

A small hotel/trip search app: a FastAPI backend that joins `hotels.csv` and
`trips.csv` in memory, and a Vue 3 frontend that searches them by hotel name.

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

The API is now available at `http://127.0.0.1:8123`.

- `GET /search?hotel_name=<query>` — case-insensitive partial match on hotel
  name, returns combined hotel + trip records as JSON (`[]` if nothing
  matches).

Data is loaded from `backend/hotels.csv` and `backend/trips.csv` at startup.
Restart the server after editing either file.

## Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Vite will print the local dev URL (defaults to `http://localhost:5173`, but
picks the next free port — e.g. `5174` — if that one's already in use).

The frontend calls the backend directly at `http://127.0.0.1:8123` (see
`API_BASE` in `frontend/src/App.vue`). If you change the backend port, or
run the frontend on a port other than 5173/5174/8080/3000, update the
`allow_origins` list in `backend/main.py` to match.

## Project layout

```
backend/    FastAPI app, CSV data, requirements.txt
frontend/   Vue 3 + Vite app
docs/       Design notes
prompts/    Prompts used to build this project
handoffs/   Session handoff notes for continuing work
```

See [docs/design-note.md](docs/design-note.md) for how responsibilities are
split between frontend and backend, and
[handoffs/current.md](handoffs/current.md) for the current state and next
steps.
