# Handoff — 2026-09-21

## What works

- **Backend**, MVC-structured (`backend/models.py`, `controller.py`,
  `main.py`), SQLite-backed (`backend/travel.db`, auto-created and
  idempotently seeded from `hotels.csv`/`trips.csv` + three demo
  travelers on first run — restarts don't duplicate seed data or affect
  existing bookings):
  - `GET /search?hotel_name=` — case-insensitive partial match, same
    behavior as the original CSV version, now backed by a SQL `JOIN`
    with `%`/`_` escaped in the query so those characters can't act as
    unintended SQL wildcards.
  - `GET /users` — the three seeded demo travelers.
  - `GET /bookings`, `POST /bookings` (`{trip_id, user_id}`),
    `PATCH /bookings/{id}/cancel`, `DELETE /bookings/{id}` — full
    booking lifecycle. All correctly 404 on unknown trip/user/booking
    IDs via domain exceptions (`TripNotFoundError` etc.) raised in
    `controller.py` and translated to `HTTPException` in `main.py`.
- **Frontend** (`frontend/src/App.vue`), redesigned as a card-based
  layout (loosely modeled on Priceline's search-bar layout/spacing per
  request, with an original color palette and hand-drawn icons — no
  Priceline branding, colors, or copy):
  - Search card: hotel-name field + a "Booking As" traveler dropdown
    (populated from `GET /users`, defaults to the first traveler).
  - Search Results card: same columns as before, plus a Book button per
    row that posts to `/bookings` using the selected traveler.
  - My Bookings card: hotel/trip/dates/traveler/status (colored badge)
    plus Cancel and Delete actions per row, each with its own in-flight
    disabled state.

## What was checked

- **Backend CRUD**, via `curl`: full lifecycle (search → create booking
  → list → cancel → delete → 404 on re-delete), 404s on booking with an
  unknown `trip_id` or `user_id`, and a server restart confirmed
  bookings persist and hotels/trips/users are not re-seeded (row counts
  unchanged).
- **Frontend**, both `npm run build` (succeeds) and a real headless
  Chromium run (Playwright, driven via a throwaway script — not part of
  the repo) against the live dev server + backend: searched "harbor",
  picked "Demo Traveler 2" from the dropdown, booked a result, confirmed
  it appeared in My Bookings correctly attributed to that traveler,
  cancelled it (status badge and disabled Cancel button both updated),
  deleted it (row disappeared). No browser console errors at any step.
  Screenshots were reviewed, not just DOM assertions.
- Caught and fixed one real bug during that browser pass: the 7-column
  results/bookings tables were wide enough to clip the rightmost action
  button off the card. Fixed by widening the card and letting cell text
  wrap instead of forcing `nowrap`.
- Not done: no automated test suite exists yet (no pytest, no
  vitest/Playwright wired into the repo — the Playwright check above was
  a one-off verification script, not a committed test).

## Known limitations (intentional, not oversights)

- No authentication. "Booking As" selects from three fixed demo
  travelers seeded at startup — there's no login, no way to add a
  traveler from the UI, and no per-user data isolation (anyone can see
  and cancel/delete anyone's booking).
- Hotels and trips are read-only reference data — there's no create/
  edit/delete UI or endpoint for them, only for bookings.
- No pagination or sorting on search results or the bookings list.

## Possible next steps

No specific next part has been scoped yet. Candidates, roughly in order
of likely value:

- An automated test suite (pytest against `controller.py`'s functions
  directly, since they're already HTTP-framework-agnostic; a frontend
  test runner for `App.vue`).
- Real authentication, if the demo-traveler dropdown stops being
  sufficient — would touch `models.py` (a real `users` identity model),
  `controller.py` (scoping `list_bookings`/`cancel`/`delete` to the
  caller), and the frontend (replacing the dropdown with a login flow).
- Hotel/trip management (CRUD), if the app needs to support more than
  the seeded CSV data.
