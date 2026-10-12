# StayAlessio - Assignment 2, Part 2: Business Intelligence with RAG and an LLM

## Project access
- **Repository:** https://github.com/afukuda69/travel-application
- **Assessed commit (code):** `5d90078da071ca5ba597311f22d188a2574d071a`. Later commits add only this report, screenshots, and the demo video.
- **Stack:** Vue 3 + Vite frontend; FastAPI + SQLite backend (MVC); Geoapify Geocoding and Places (Part 1); OpenRouter (NVIDIA Nemotron, free tier) for the chatbot; Leaflet with OpenStreetMap tiles.

### Configuration
Create a `.env` file at the **project root** (beside `frontend/` and `backend/`):

```
GEOAPIFY_API_KEY=your_geoapify_key
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
```

`.env` is listed in `.gitignore` and has never been committed. All keys are read only by the backend (`backend/config.py`). Model requests run only on the backend (`backend/chat.py`); keys are never sent to the browser or included in responses or errors. Restart the backend after changing `.env`.

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
npm run dev        # open the printed URL, e.g. http://localhost:5175
```

On first start the backend creates `backend/travel.db` and runs additive, repeatable migrations. To use the chatbot, search a ZIP (e.g. 94010) and click **Add to Local** on a few hotels; each saved hotel receives simulated nightly rates and rooms for Oct 10-14, 2026.

## Summary of changes from Part 1
- **Local storage foundation (Oct 1 tutorial):** new tables `saved_hotels`, `saved_hotel_zip_searches`, and `demo_hotel_nights`; Add to Local / Remove from Local; local-first ZIP lookup ("Saved locally" vs "API results"). Fixed a bug where saved results showed "Invalid LatLng object" and a blank map.
- **RAG chatbot:** new `POST /api/chat` (`backend/chat.py`) and `frontend/src/components/HotelChat.vue`, placed inside the Nearby Hotels card directly below the ZIP search.
- **UI:** renamed the app to StayAlessio ("Search less. Stay better."), with a centered purple-and-black theme.
- **Tests:** grew from 29 to 80 backend tests (saved hotels, chat validation, and chat flows).
- **Preserved:** Assignment 1 tables and records, the Part 1 API, ZIP search, and synchronized list/map selection.

## How the chatbot works
1. The user types a question, e.g. "Cheapest saved hotel in 94010 for Oct 10-12?"
2. **Stage 1 (LLM proposes SQL).** The backend sends the question, the schema of the three local tables, and the query rules:
   - rates are in cents
   - a stay from check-in A to checkout B covers nights A through B-1
   - a hotel qualifies only if it has a row with rooms available for **every** requested night
   - for cheapest/compare questions, return all qualifying hotels
   - use only values from the database or the question, never outside facts

   The model returns either SQL or a sentinel: `INSUFFICIENT_DATA`, `READ_ONLY_REFUSAL`, or `UNCLEAR`.
3. **Backend validation and read-only execution.** The SQL runs on a `mode=ro` SQLite connection with SQLite's own query authorizer (`set_authorizer`). The authorizer allows only reads of the three local tables and denies INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, PRAGMA, ATTACH, and any other table at compile time, before anything runs. Multi-statement input is rejected, and results are capped at `LIMIT 50`. The remote model never touches SQLite.
4. **Stage 2 (LLM answers from retrieved rows).** The original question and the retrieved rows go back to the model. It must answer only from those rows, in labeled fields (Hotel, Location, Stay, Nightly rate, Total cost, Availability, Reason), in dollars, without guessing.
5. **Frontend.** Shows the answer, a "simulated course data" note, and expandable **View query** (proposed SQL) and **View source records** (retrieved rows).

| Status | When | Stage 2 called? |
|---|---|---|
| `answer` | SQL ran and returned rows | Yes |
| `no_match` | SQL ran and returned zero rows (decided by the backend, not the model) | No |
| `insufficient_data` | The question needs data the schema lacks | No; no SQL run |
| `rejected` | A modification request, or proposed SQL denied by the authorizer | No |
| `unclear` | The input isn't a question about saved hotels | No; no SQL run |
| `error` | Model failure (502), rate limit (429), or not configured (503) | No |

## Research notes
Builds on the Part 1 research (Geoapify, Leaflet, Hotels.com).

| Source | Useful features | Problems or omissions | Decision adopted |
|---|---|---|---|
| [Navan Edge AI trip planner](https://navan.com) | A single large prompt box with a button inside it; suggestion chips that show what to ask | Answers don't show where the data came from; promotional banners compete with the input | Adopted the large rounded input with Ask inside it and suggestion chips; added visible "View query" and "View source records" so every answer is traceable |
| [OpenRouter API docs](https://openrouter.ai/docs) and [free models](https://openrouter.ai/models?fmt=free) | OpenAI-compatible REST endpoint; free Nemotron models | Free models have rate limits and availability can change; output is non-deterministic | Called it with the existing `httpx` (no new dependency); mapped 429 to a distinct "rate limited" state; tests mock the model so they use no quota |
| [SQLite authorizer (`sqlite3_set_authorizer`)](https://www.sqlite.org/c3ref/set_authorizer.html) and [URI `mode=ro`](https://www.sqlite.org/uri.html) | The engine itself can deny actions and tables at compile time; read-only connections | Keyword filtering of model SQL is easy to bypass | Used the authorizer plus a read-only connection instead of regex checks |
| Assignment brief (RAG section) | Defines the question, proposed SQL, retrieval, second request, and grounded answer flow | No guidance on how to show non-answers | Added explicit `insufficient_data`, `rejected`, and `unclear` states in addition to the required answer, no-match, and error states |

## Early mockup
Prepared **before** the chatbot was implemented. It was committed in `7d63326` at 13:37 on 2026-10-12; the chatbot code came later in `6c1248d`.

![Part 2 mockup](https://github.com/afukuda69/travel-application/blob/main/docs/mockups/a2p2-mockup.png?raw=true)

Mockup link: https://github.com/afukuda69/travel-application/blob/main/docs/mockups/a2p2-mockup.png

**Changes during implementation:**
- **Placement and controls:** kept as sketched (inside Nearby Hotels, below the ZIP search; rounded input with Ask inside; answer box with expandable SQL and records).
- **Chips:** replaced the "2 Bedroom" chip with "Rooms on Oct 10", because the saved data has no room types, so a bedroom question could only be answered by guessing.
- **Labels:** renamed "Proposed SQL" / "Retrieved records" to "View query" / "View source records".
- **Answer format:** changed from one sentence to labeled fields (Hotel, Location, Stay, Nightly rate, Total cost, Availability, Reason) so the cost and reason are easy to scan.
- **States:** split the sketched ERROR state into **rejected** (read-only refusal, in red), **insufficient data**, **unclear input**, and service **error**, after testing showed these cases need different messages (see Verification).
- **Example values:** the sketch used placeholder rates ($100/night, $200). The demo data has Crowne Plaza edited to $80/night, so the real answer is $160.

## Demo video
- **Part 2 chatbot demo (1:39):** https://github.com/afukuda69/travel-application/blob/main/docs/demo/chatbot-demo.mov

  Shows ZIP 94010 returning "Saved locally" results with simulated rates; the cheapest-stay question with the proposed SQL and retrieved records expanded; the SFO question returning insufficient data; the delete request rejected; and an unrelated input handled.
- **Local-storage evidence (in-class activity):** Add/Remove, the Write Changes edit reread in the frontend, and local-first lookup with error handling (submitted separately).

## Verification record
Live observations on **2026-10-12**, ZIP **94010** (Burlingame), three saved hotels: Crowne Plaza San Francisco Airport, Courtyard by Marriott San Francisco Airport Burlingame, and DoubleTree Hotel San Francisco Airport.

**Test data:** each saved hotel has nights Oct 10-14 at the default 10000 cents and 20 rooms. Crowne Plaza's `nightly_rate_cents` was edited in DB Browser to 8000 for 2026-10-10 and 2026-10-11, then Write Changes.

### Live model calls (OpenRouter, real responses)

| Input | Expected | Observed |
|---|---|---|
| "Cheapest saved hotel in 94010 for Oct 10-12?" | Crowne Plaza; nights Oct 10 and 11 only (checkout excluded); $80 x 2 = $160; the other two hotels $200; per-night rows visible | **Matched.** The SQL selected `stay_date IN ('2026-10-10','2026-10-11')`, `rooms_available > 0`, and `HAVING COUNT(*) = 2`, ordered by total, with no `LIMIT 1`. View source records showed 6 rows (2 per hotel). The answer: Crowne Plaza, Oct 10-12 (2 nights), $80, total $160; reason: Courtyard and DoubleTree both cost $200 total. Checked against the records. |
| "most expensive hotel in 94010 for Oct 10 - Oct 12?" | Courtyard and DoubleTree tied at $200; Crowne Plaza cheaper at $160 | **Matched.** The answer named Courtyard ($100/night, $200 total) and stated the tie with DoubleTree, and that Crowne Plaza is cheaper at $160. |
| "Which saved hotel is closest to SFO airport?" | Insufficient data; the database has no airport locations; no SQL run | **Matched.** "SFO airport coordinates not in database." No query or records shown. |
| "Delete all saved hotels" | Rejected as read-only; nothing changed | **Matched.** Red "Not allowed: this assistant is read-only and cannot change saved hotels or make bookings." No SQL run. The banner still read "3 hotel(s) you've saved here" afterward. |
| "Then, in DB Browser" (accidental paste) | Treated as unclear, with guidance | **Matched.** "I can answer questions about your saved hotels' locations, stay dates, nightly rates, and availability. Try: 'Cheapest saved hotel for Oct 10-12?'" |
| Keyboard: Tab to the question box, type, press Enter; Tab to the chips and the View query / View source records toggles | Submits with Enter; all controls reachable with a visible focus ring | Matched (2026-10-12): typed the question and pressed Enter to submit; Tab moved focus to the suggestion chips with a visible purple focus ring (shown on "Rooms on Oct 10"), then to View query and View source records. (by code: Enter submits and Shift+Enter adds a newline; chips are `<button>` elements; the toggles are native `<details>` elements) |
| Part 1 regression: click a hotel pin on the map | The same hotel is highlighted in the list | Matched on 2026-09-30 (Part 1 screenshot below); list/map code unchanged except the saved-results coordinate fix |

### Fixtures and mocks (labeled, no live model calls)
The fixed JSON sample is at [`backend/tests/fixtures/chat_sample.json`](https://github.com/afukuda69/travel-application/blob/main/backend/tests/fixtures/chat_sample.json) (label `chat_sample_fixture`), with one labeled example per status. The model call (`chat._call_openrouter`) is mocked, and every database-changing test uses a temporary SQLite file, never `travel.db`.

**To repeat the checks:**
```bash
cd backend
source .venv/bin/activate
python -m pytest            # or: python -m unittest discover -s tests -p "test_*.py"
```
**Result on 2026-10-12: 80 passed.**

| Check (mocked) | Expected | Result |
|---|---|---|
| Model proposes `DELETE`, `DROP`, or `UPDATE` | Denied by the authorizer; status `rejected`; database row counts unchanged | Pass |
| Multi-statement SQL | Rejected | Pass |
| Model proposes a table outside the three local tables | Denied | Pass |
| SQL with no LIMIT, or LIMIT over 50 | LIMIT 50 enforced | Pass |
| Model failure / HTTP 429 / missing key | `error` with 502 / 429 / 503; key never exposed | Pass |
| Query returns zero rows | `no_match` without a second model call | Pass |
| Airport-distance question | `insufficient_data`; no SQL executed | Pass |
| "Delete all saved hotels" | `rejected`; no SQL executed; database unchanged | Pass |
| Unrelated input | `unclear`; no SQL executed | Pass |
| Per-night totals | Correct total; a hotel missing one requested night excluded; all qualifying hotels passed to stage 2 | Pass |
| Empty question | 422 | Pass |
| Saved-hotels storage (from the tutorial) | Duplicate saves create no extra rows and don't overwrite rates; removal deletes only related rows | Pass |

### Corrections made (first versions vs. revised)
On the first live run, four answers failed the grounding requirement. Screenshots of each are linked below.

1. **Hedged answer (cheapest stay).** The model's SQL returned only `SUM(...)` with `LIMIT 1`. The answer then said it "cannot confirm availability or cost" even though $160 was correct, and claimed only one hotel existed. **Fix:** require per-night rows, a `HAVING COUNT(*)` check for complete stays, and all qualifying hotels for comparisons; stage 2 must not hedge about data that is present.
2. **Hallucinated distance (SFO).** The answer stated the hotel was "2.17 miles from SFO airport", which can only have come from outside knowledge, since the database has no airport locations. **Fix:** stage 1 may use only database or question values and returns `INSUFFICIENT_DATA` otherwise; the backend skips SQL and stage 2.
3. **Silent rewrite of a delete request.** The model turned "Delete all saved hotels" into a SELECT and gave a vague reply. **Fix:** the `READ_ONLY_REFUSAL` sentinel, shown as a red "Not allowed" state. The authorizer remains the hard guarantee if the model ever emits real write SQL.
4. **Confusing reply to unrelated input.** The reply used technical wording ("the rows provided contain..."). **Fix:** the `UNCLEAR` state with an example question; stage 2 is told never to mention rows, columns, or cents.

Earlier, during local storage: saved results showed "Invalid LatLng object: (undefined, undefined)" and a blank map, because local results lacked the coordinates the map needed. This was fixed before the chatbot work (commit `fd91fc4`).

### Screenshots
**Before the fixes (first versions):**
- [Cheapest stay: hedged answer, LIMIT 1](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/before-1-cheapest-hedged.png)
- [SFO: hallucinated distance](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/before-2-sfo-hallucinated.png)
- [Delete request: vague reply](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/before-3-delete-vague.png)
- [Unrelated input: technical reply](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/before-4-unclear-input.png)

**After the fixes:**
- [Cheapest stay: $160, with SQL and records](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/after-1-cheapest.png)
- [SFO: insufficient data](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/after-2-sfo-insufficient.png)
- [Delete request: rejected](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/after-3-delete-rejected.png)
- [Unrelated input: unclear](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/after-4-unclear-input.png)
- [Most expensive stay: tie explained](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p2/after-5-most-expensive.png)

**Part 1 regression:**
- [Map pin selects the same hotel in the list](https://github.com/afukuda69/travel-application/blob/main/docs/screenshots/a2p1/map-pin-select_16802.png)

### Remaining limitations
- **Data scope:** nightly rates and availability are simulated course data, only for Oct 10-14, 2026, and only for hotels the user has saved. Questions outside that scope return no-match or insufficient data.
- **Model behavior:** the free model's output is non-deterministic, so the SQL wording can differ between runs. The `insufficient_data`, `rejected`, and `unclear` routing depends on the model following its instructions; the read-only connection plus authorizer is the hard guarantee that nothing is modified.
- **No-match path:** a zero-row result skips the second model call by design. The live demo traces both model requests on the successful questions.
- **Rate limits:** free-tier limits can return the 429 "rate limited" state.
- **Availability field:** the summary shows a single room count. The per-night counts are in View source records.
- **No booking:** the chatbot does not book, change, or delete records.

## AI disclosure and evidence log
| Tool | Model | Use |
|---|---|---|
| Claude Code (VS Code) | Claude Sonnet 5 (high effort, as shown by `/model`) | Implemented the schema, local storage, the chatbot backend and frontend, and the tests; ran the test suites |
| Claude (claude.ai) | Claude Opus 5.5 | Planning, mockup reference, Claude Code prompt drafting, reviewing outputs and screenshots, writing this report |
| OpenRouter | `nvidia/nemotron-3-nano-30b-a3b:free` | The chatbot's runtime model (SQL proposal and grounded answer) |

| Prompt excerpt (Claude Code) | Result / linked change |
|---|---|
| "Add a saved_hotels table ... hotel_id: the API's provider ID, used as the primary key ... Add a demo_hotel_nights table ... DEFAULT 10000 ... DEFAULT 20 ... Use an additive, repeatable migration" (tutorial prompt) | Schema, commit `91f9516` |
| "Bug: when ZIP 94010 returns 'Saved locally' results, the UI shows 'Invalid LatLng object: (undefined, undefined)' and the Leaflet map is blank ..." | **Revised approach:** local results now carry coordinates and the map falls back to centering on saved hotels; commit `fd91fc4` |
| "Add a RAG chatbot using OpenRouter ... First LLM request: send the question, the schema ... and ask for a single SQLite SELECT. Validate the proposed SQL before running it ... Execute on a read-only SQLite connection (mode=ro)" | `backend/chat.py`, `HotelChat.vue`, `test_chat*.py`; commit `6c1248d`. Claude Code chose SQLite's authorizer over keyword matching. |
| "Four test questions exposed grounding and state problems ... INCIDENT 1: cheapest stay answered with a hedge ... INCIDENT 2: SFO distance hallucinated ... INCIDENT 3: delete request not shown as rejected ... INCIDENT 4: unrelated input produced a confusing answer" | **Failed first version revised:** per-night rules, `INSUFFICIENT_DATA` / `READ_ONLY_REFUSAL` / `UNCLEAR` sentinels, new UI states, and 11 more tests; commit `5d90078` |
| "Rename the app's displayed name and tagline ... 'StayAlessio' ... 'Search less. Stay better.' ... text-only change" | Header and title; commit `71a481a` |

No API keys, `.env` contents, or private information appear in this report, the screenshots, or the recording.
