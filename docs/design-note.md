# Design Note: Responsibilities

This app is split into two pieces with a deliberately thin boundary between
them: the backend owns all data and logic, the frontend owns presentation.

## FastAPI backend (`backend/`)

- **Single source of truth for data.** On startup it reads `hotels.csv` and
  `trips.csv` and joins them by `hotel_id` into a list of combined records
  held in memory (`combined_records` in `main.py`).
- **Owns the search logic.** `GET /search?hotel_name=` does the
  case-insensitive substring match server-side. The frontend never filters
  or sorts data itself — it just renders whatever the API returns.
- **Owns cross-origin policy.** CORS is configured here (`CORSMiddleware`)
  so only known local frontend origins can call the API during
  development.
- Currently stateless between requests and read-only: there's no write
  path yet, so there's nothing to keep consistent across concurrent
  requests.

## Vue frontend (`frontend/`)

- **Pure presentation layer.** One component (`App.vue`) holds a text
  input, a Search button, and a results table. It has no business logic —
  it sends whatever the user typed to `/search` and renders whatever comes
  back.
- **No local data model.** There's no store (Pinia/Vuex) because there's
  only one piece of state worth tracking (the current result set) and one
  place it's used.
- **Explicit empty/error states.** The UI distinguishes "haven't searched
  yet," "searched, zero matches" (shows "No results found."), and
  "API unreachable" (shows a distinct error message) rather than
  collapsing all three into a blank table.

## Why this split

Keeping matching logic in the backend means the frontend stays swappable —
a different client (mobile app, CLI, another SPA) gets identical search
behavior for free. It also means the data format (CSV today, SQLite in
Part 2) is an implementation detail the frontend never has to know about;
it only ever sees the joined JSON shape coming back from `/search`.
