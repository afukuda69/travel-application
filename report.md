# Travel Application - Assignment 2, Part 1: Live Hotel Search and Map

## Project access
- **Repository:** https://github.com/afukuda69/travel-application
- **Assessed commit:** f7d760949d645c3dda32f347766d83545650dc55

- **Stack:** Vue 3 + Vite frontend, FastAPI + SQLite backend (MVC), Geoapify Geocoding and Places APIs, Leaflet with OpenStreetMap tiles.

### Configuration
Create a `.env` file at the **project root** (beside `frontend/` and `backend/`):

```
GEOAPIFY_API_KEY=your_key_here
```

`.env` is listed in `.gitignore` and has never been committed. The key is read only by the backend (`backend/config.py`), never sent to the browser, and never included in responses or error messages. `GET /api/health` reports only whether the key is configured. Restart the backend after changing `.env`.

### Startup
```bash
# Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8123

# Frontend (second terminal)
cd frontend
npm install
npm run dev        # open the printed URL, e.g. http://localhost:5174
```

Automated backend checks (mocked Geoapify, no API quota used): `cd backend && python -m pytest`

## Changes from Assignment 1
- Added a **Nearby Hotels** section: a traveler enters a five-digit U.S. ZIP code and sees hotels within 5 km in a list and on a Leaflet map.
- New backend modules keep MVC separation: `zip_lookup.py` (Geoapify postcode geocoding) and `places_lookup.py` (Geoapify Places) sit behind `controller.py`; `main.py` only maps domain errors to HTTP status codes. New routes: `GET /api/zip-location` and `GET /api/hotels/nearby`.
- Added 29 backend unit and route tests (`backend/tests/`) covering success, invalid input, unresolved ZIPs, empty results, provider failures, rate limits, and missing configuration.
- Repository cleanup: `node_modules/`, `dist/`, `__pycache__/`, `.pyc`, `.vite/`, and `.env` are ignored and removed from version control.
- Existing search and booking features from Assignment 1 are unchanged.

## Research notes
| Source | Useful features | Problems or omissions | Decision adopted |
|---|---|---|---|
| [Geoapify Geocoding API](https://apidocs.geoapify.com/docs/geocoding/forward-geocoding/) | `type=postcode` and `filter=countrycode:us` restrict lookups to U.S. postcodes | May return a nearby or partial match instead of the exact ZIP | Accept only a result whose postcode exactly equals the input and whose country is `us`; otherwise report "ZIP not found" instead of searching a different place |
| [Geoapify Places API](https://apidocs.geoapify.com/docs/places/) | `categories=accommodation.hotel`, `filter=circle:lon,lat,5000`, `bias=proximity` | Coverage and fields vary; no prices, ratings, or availability | Show only name, address, and distance; label that data may be incomplete and is not bookable availability; cap at 20 results |
| [Leaflet documentation](https://leafletjs.com/reference.html) | Markers, popups, `invalidateSize()` | Map breaks if its container is hidden or re-mounted | Keep the map container mounted (`v-show`) and call `invalidateSize()` after results load |
| [Hotels.com](https://www.hotels.com) | Compact search bar centered on the page; simple, uncluttered design | A lot of unused white space on the page | Adapted the compact search bar layout for the ZIP search; used the extra width for a side-by-side list and map instead of leaving it empty |

## Early mockup
No mockup was prepared before implementation. The layout was planned from the Hotels.com research above and the existing Assignment 1 card-based design. The sketch below was drawn on 2026-09-30, after implementation, to document the intended layout and interface states.

![Mockup](https://github.com/afukuda69/travel-application/blob/main/docs/mockups/a2p1-mockup.png?raw=true)

Mockup link: https://github.com/afukuda69/travel-application/blob/main/docs/mockups/a2p1-mockup.png

**Notes on the sketch:** `<one line, e.g. shows ZIP box and button at top, hotel list on the left, map on the right, and where loading/error messages appear>`

## Demo video
Demo video (24 seconds): https://github.com/afukuda69/travel-application/blob/main/docs/demo/nearby-hotels_demo.mp4

Shows the home page, ZIP searches for 16802 (State College, PA) and 94010 (Burlingame, CA), the loading state, results in the list and on the map, and selecting a hotel in the list to highlight it on the map.

Screenshots:
- Home page: https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/home-page-nearby.png
- Results for ZIP 94010: https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/nearby_94010.png
- Hotel selected in list, highlighted on map: https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/nearby_94010_selected.png
- Map pin clicked, same hotel highlighted in list (16802): https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/map-pin-select_16802.png
- Invalid input (123): https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/invalid-zip_123.png
- Leading-zero ZIP (02108, Boston): https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/leading-zero_02108.png
- Unresolved ZIP (00000): https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/unresolved-zip_00000.png

## Verification record
Live searches observed on **2026-09-29** and **2026-09-30**. Result counts come from the live API and may change.

| Input / action | Expected | Observed |
|---|---|---|
| Live search, ZIP 16802 | Resolves to State College, PA; hotels within 5 km shown in list and map | Matched: "Within 5 km of 16802 (State College)", results listed and pinned |
| Live search, ZIP 94010 | Resolves to Burlingame, CA; hotels within 5 km | Matched: "Within 5 km of 94010 (Burlingame)", 20 results, nearest 651 m away |
| Click a hotel in the list | Same hotel highlighted on map with popup | Matched: Crowne Plaza San Francisco Airport highlighted and popup shown |
| Click a pin on the map (ZIP 16802, 2026-09-30) | Same hotel highlighted in the list | Matched: clicked the Carnegie Inn & Spa pin; popup opened and the same hotel was highlighted in the list |
| Submit while request is pending | Button shows "Searching...", "Loading..." displayed | Matched in demo video |
| Enter `123` (2026-09-30) | Inline error, no request sent | Matched: "Enter a ZIP code with exactly 5 digits." shown; no results loaded |
| Enter `02108` (2026-09-30) | Leading zero preserved; resolves to Boston, MA | Matched: "Within 5 km of 02108 (Boston) - 20 found." One result had no name in the API response and was honestly labeled "Unnamed hotel". Also covered by `test_leading_zero_zip_preserved_and_passed_through` |
| Enter `00000` (2026-09-30) | "We couldn't find that ZIP code."; no hotel search performed | Matched: "We couldn't find that ZIP code." shown; no list or map displayed. Also covered by `test_unresolved_zip_returns_404_and_never_calls_places` |
| Location with no hotels | "No hotels found nearby." (success, not an error) | Covered by `test_empty_hotel_results_is_200_not_error` |
| Geoapify failure | "Service unavailable" message, not an empty result | Covered by `test_zip_provider_failure_returns_502`, `test_places_provider_failure_returns_502` |
| Geoapify rate limit (429) | "Too many requests" message | Covered by `test_places_rate_limited_returns_429` |
| Missing API key | 503, key never exposed | Covered by `test_not_configured_returns_503` |
| Keyboard only (ZIP 94010, 2026-09-30): Tab to ZIP field, type, Enter; Tab through hotel list | Search submits; list items focusable with visible focus ring | Matched: search submitted with Enter and each hotel showed a focus outline while tabbing |
| `python -m pytest` in `backend/` | All tests pass with mocked Geoapify | 29 passed (2026-09-29) |

**Corrections made:** The Leaflet map did not re-render correctly between searches because its container was re-created. Fixed by keeping the container mounted and calling `invalidateSize()` (commit `e0b29ca`).

**Remaining limitations:**
- Geoapify coverage is incomplete; results are capped at 20 and are not an exhaustive hotel inventory.
- No prices, ratings, or availability are shown because the API does not provide them.
- Map tiles come from the public OpenStreetMap tile server (no key); attribution stays visible.
- Saving hotels to a shortlist is Part 2.

## AI disclosure and evidence log
- **Tool:** Claude Code in VS Code - **Model:** `<e.g. Claude Opus 4.x / Sonnet 4.x - check /model in Claude Code>`. Used for backend Geoapify modules, tests, and the Vue Nearby Hotels component.
- **Tool:** Claude (claude.ai) - **Model:** Claude Opus 5.5. Used for report review and repository cleanup guidance.

| Prompt excerpt | Result / linked change |
|---|---|
| `<prompt that created zip_lookup.py>` | `backend/zip_lookup.py`, commit `e0b29ca` |
| `<prompt asking for error-state handling>` | Distinct 404/422/429/502/503 handling, `NearbyHotels.vue` messages |
| `<prompt reporting the blank map bug>` | **Revised approach:** first version used `v-if` and re-created the map; changed to `v-show` + `invalidateSize()` |
| `<prompt asking for tests>` | `backend/tests/` (29 tests) |

