# [Your app name] — Part 1

## Repository and commit
https://github.com/afukuda69/travel-application — commit [paste hash here]

## Implementation
The Vue frontend provides a text input and Search button. On submit, it calls
the FastAPI backend's /search endpoint with the hotel name. FastAPI loads
hotels.csv and trips.csv on startup, joins them by hotel_id, performs a
case-insensitive partial match against hotel_name, and returns the matching
combined records as JSON (or an empty array if none match). The frontend
renders results in a table or shows a "No results found" message.

## Verification
- Action: Searched "Harbor" — Expected: table shows matching hotel and trip
  details — Observed: matched expected result.
- Action: Searched "zzz" — Expected: "No results found" message displayed —
  Observed: matched expected result.

Screenshots: [add links once uploaded — see step 4 below]

## Project context and next steps
- README: https://github.com/afukuda69/travel-application/blob/main/README.md
- AGENTS.md: https://github.com/afukuda69/travel-application/blob/main/AGENTS.md
- Design note: https://github.com/afukuda69/travel-application/blob/main/docs/design-note.md
- Prompts: https://github.com/afukuda69/travel-application/tree/main/prompts
- Handoff: https://github.com/afukuda69/travel-application/blob/main/handoffs/current.md

Known limitations: search is by hotel name only, not city. Next task:
Part 2 — seed SQLite and implement full CRUD for bookings.