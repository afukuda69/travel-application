# Prompt 001 — FastAPI backend

Date: 2026-09-11

Build a FastAPI backend in backend/ that reads hotels.csv and trips.csv
from the backend/ folder on startup, joins them by hotel_id, and exposes
a GET /search?hotel_name= endpoint that does a case-insensitive partial
match on hotel_name and returns the matching combined records as JSON, or
an empty list if none match. Also enable CORS for a Vue frontend running
on localhost.
