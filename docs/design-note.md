# Design Note: Responsibilities

This app has two layers with a deliberately thin boundary: the backend
owns all data, business logic, and cross-origin policy; the frontend
owns presentation only. The backend itself is further split MVC-style
into Models, a Controller, and Routes.

## FastAPI backend (`backend/`)

### Models (`models.py`)

- Defines `Hotel`, `Trip`, `User`, and `Booking` as plain Python
  dataclasses (`from_row()` constructs one from a `sqlite3.Row`), plus
  the SQLite schema (DDL) and startup seeding.
- Deliberately **no ORM**. At this scale (a handful of tables, no
  complex queries) a real ORM's relationship traversal (`hotel.trips`,
  `trip.bookings`) buys nothing that a foreign-key column and a `JOIN`
  don't already give us, and it's one fewer dependency to reason about.
  The tradeoff: models don't traverse relationships themselves — that's
  the Controller's job, via explicit SQL joins.
- Owns seeding too, not just schema: on startup, hotels/trips load from
  CSV and three demo travelers are inserted — but only if those tables
  are empty, so restarts don't duplicate data or touch existing
  bookings. Data initialization is a Model concern, not a Route concern.

### Controller (`controller.py`)

- All CRUD logic lives here: `search_hotel_trips`, `list_users`,
  `list_bookings`, `create_booking`, `cancel_booking`, `delete_booking`.
  Each opens its own SQLite connection, does the work, and closes it —
  no shared connection state between requests to reason about.
- Deliberately **HTTP-agnostic**. Not-found cases raise plain Python
  exceptions (`TripNotFoundError`, `UserNotFoundError`,
  `BookingNotFoundError`) rather than `HTTPException` — the controller
  has no idea it's being called from a web framework. That's what makes
  it the actual business-logic layer rather than routing glue with extra
  steps: it could be called from a CLI or a test harness with zero
  changes.
- Assembles response dicts from the Model dataclasses (e.g.
  `_booking_detail` builds a `Booking`, `Trip`, `Hotel`, and `User` and
  merges their fields) rather than returning raw `sqlite3.Row` objects —
  so a booking's JSON shape is still traceable back to the models that
  define it, even though the response itself spans four tables and isn't
  an entity by itself.

### Routes (`main.py`)

- Thin on purpose: each route parses the request, calls one controller
  function, and translates its exceptions into the right
  `HTTPException` (404 for anything not found). No SQL and no business
  rules belong here — if a route handler starts doing either, that logic
  has drifted out of the Controller and should move back.
- Also owns cross-origin policy (`CORSMiddleware`) — the one piece of
  HTTP-framework-specific configuration that has no natural home in the
  Controller.

### Why split it this way

Before this split, route handlers executed raw SQL directly — no layer
you could unit-test independent of FastAPI, no reuse if a second
interface (a CLI, a script) ever needed the same operations, and no
single place to look for "what write operations exist and what can go
wrong." Now: Models define what the data *is*, the Controller defines
what you can *do* to it, and Routes define how the outside world reaches
that. Each layer only needs to understand the one below it.

## Vue frontend (`frontend/`)

- **Pure presentation layer.** One component (`App.vue`) holds the
  search card (hotel name + a "Booking As" traveler picker), a search
  results table, and a My Bookings table with Cancel/Delete. It has no
  business logic — it sends requests to the API and renders whatever
  comes back; matching, validation, and status transitions all happen
  server-side.
- **No local data model or store.** Three independent pieces of state
  (search results, the traveler list, the booking list) are tracked as
  plain `ref`s — a store (Pinia) would add structure this component
  doesn't need yet, since nothing is shared or derived across components.
- **Explicit empty/error/loading states**, per interaction: search
  ("haven't searched yet" vs. "zero matches" vs. "API unreachable"),
  bookings ("no bookings yet" vs. a load/action error), and per-row
  in-flight indicators (`Booking…`, disabled Cancel once cancelled) so
  the UI never looks idle while a request is actually in flight.
- **Visual design** follows a card-based layout (rounded search card,
  icon-labeled fields, consistent pill buttons and status badges) chosen
  to keep search, booking, and management visually cohesive as the
  surface area grew from "one input and a button" to three interactive
  sections on one page.

## Why the frontend/backend split holds

Keeping all matching and booking logic server-side means the frontend
stays swappable — a different client would get identical search and
booking behavior for free, and the data layer (SQLite today) is an
implementation detail the frontend never has to know about. It only ever
sees the JSON shapes the Controller assembles from the Models.
