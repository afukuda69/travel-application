# Travel Application — Part 2

## Repository and commit
https://github.com/afukuda69/travel-application — commit cfb1d6be16d0754df95cddf6a35214dca613c3cc

## Implementation
The application now uses a SQLite database with an MVC architecture instead of reading directly from CSVs. `backend/models.py` defines the Hotel, Trip, User, and Booking data classes along with the SQLite schema, connection handling, and a one-time seed step that loads hotels.csv, trips.csv, users.csv, and bookings.csv into SQLite without duplicating data on restart. `backend/controller.py` contains all CRUD logic — assembling hotel/trip/booking details and raising domain-specific exceptions — with no HTTP awareness. `backend/main.py` is now a thin routing layer that calls the controller and translates its exceptions into HTTP responses. Endpoints include GET /search, GET /users, POST /bookings, GET /bookings, PATCH /bookings/{id}/cancel, and DELETE /bookings/{id}.

The Vue frontend was redesigned with a card-based layout inspired by Priceline's search bar, replacing the plain input from Part 1. It now includes a "Booking As" traveler dropdown (populated from GET /users) alongside hotel search, a "Book" action on each search result that creates a booking via POST /bookings, and a "My Bookings" section that lists bookings via GET /bookings with Cancel (PATCH) and Delete (DELETE) actions per row. All CRUD actions are performed through the frontend as required.

## Verification
- Action: Searched "Valley Trail Inn" — Expected: matching hotel and trip rows displayed — Observed: matched expected result.
- Action: Selected a traveler and clicked Book on a result — Expected: booking created and visible in My Bookings — Observed: matched expected result.
- Action: Clicked Cancel on a booking — Expected: status changes to "cancelled" while the record remains visible — Observed: matched expected result.
- Action: Created a test booking and clicked Delete — Expected: booking removed from My Bookings — Observed: matched expected result.
- Action: Stopped and restarted both backend and frontend servers, then refreshed the browser — Expected: all bookings persist exactly as left, with no duplication of seeded starter records — Observed: matched expected result.

Screenshots:
- https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/home-page.png
- https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/search_Valley-Trail-Inn.png
- https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/booked_Valley-Trail-Inn.png
- https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/cancelled_Valley-Trail-Inn.png

Demo video (under 3 minutes): https://github.com/afukuda69/travel-application/blob/main/docs/demo/Hotel-Booking_Demo.mov

## Project context and next steps
- README: https://github.com/afukuda69/travel-application/blob/main/README.md
- AGENTS.md: https://github.com/afukuda69/travel-application/blob/main/AGENTS.md
- Design note: https://github.com/afukuda69/travel-application/blob/main/docs/design-note.md
- Prompts: https://github.com/afukuda69/travel-application/tree/main/prompts
- Handoff: https://github.com/afukuda69/travel-application/blob/main/handoffs/current.md

Known limitations: no authentication is implemented — travelers are selected from a dropdown of seeded demo users rather than logged in; hotel and trip records cannot be created or edited through the app, only bookings; no automated test suite. 