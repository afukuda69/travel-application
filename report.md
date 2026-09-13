# Travel Application — Part 1

## Repository and commit
https://github.com/afukuda69/travel-application — commit 063b7edcece48518744d48c067311897fb251e79

## Implementation
The Vue frontend provides a text input and Search button. On submit, it calls
the FastAPI backend's /search endpoint with the hotel name. FastAPI loads
hotels.csv and trips.csv on startup, joins them by hotel_id, performs a
case-insensitive partial match against hotel_name, and returns the matching
combined records as JSON (or an empty array if none match). The frontend
renders results in a table with Hotel Name, City, Trip Name, Check In,
Check Out, and Nightly Rate, or shows a "No results found" message when
there are no matches.

## Verification
- Action: Searched "Harbor Lantern Hotel" — Expected: table shows matching
  hotel and trip rows — Observed: matched expected result, two trips returned
  (Boston Harbor Weekend, Boston Autumn Weekend), both $150/night.
- Action: Searched "zzz" — Expected: "No results found" message displayed —
  Observed: matched expected result.

Screenshots:
- https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/search-success.png
- https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/search-no-results.png

## Project context and next steps
- README: https://github.com/afukuda69/travel-application/blob/main/README.md
- AGENTS.md: https://github.com/afukuda69/travel-application/blob/main/AGENTS.md
- Design note: https://github.com/afukuda69/travel-application/blob/main/docs/design-note.md
- Prompts: https://github.com/afukuda69/travel-application/tree/main/prompts
- Handoff: https://github.com/afukuda69/travel-application/blob/main/handoffs/current.md

Known limitations: search matches by hotel name only, not city. Next task:
Part 2 — seed SQLite with the supplied data and implement full CRUD
(create, read, update/cancel, delete) for bookings through the frontend.