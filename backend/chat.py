import json
import re
import sqlite3

import httpx

import config
import models

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
REQUEST_TIMEOUT_SECONDS = 30.0
MAX_ROW_LIMIT = 50

ALLOWED_TABLES = {"saved_hotels", "saved_hotel_zip_searches", "demo_hotel_nights"}

SCHEMA_DESCRIPTION = """
saved_hotels(hotel_id TEXT PRIMARY KEY, name TEXT, address TEXT, latitude REAL, longitude REAL)
saved_hotel_zip_searches(hotel_id TEXT, zip TEXT, locality TEXT, center_latitude REAL, center_longitude REAL)
demo_hotel_nights(hotel_id TEXT, stay_date TEXT, nightly_rate_cents INTEGER, rooms_available INTEGER)
""".strip()

QUERY_RULES = """
- nightly_rate_cents is in cents (divide by 100 for dollars).
- stay_date is in YYYY-MM-DD format.
- A stay from a check-in date to a checkout date covers every night from
  check-in through the night before checkout; the checkout night itself
  is excluded (e.g. check-in 2026-10-10, checkout 2026-10-12 covers the
  nights of 2026-10-10 and 2026-10-11 only).
""".strip()

SENTINEL_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
SENTINEL_READ_ONLY_REFUSAL = "READ_ONLY_REFUSAL"
SENTINEL_UNCLEAR = "UNCLEAR"

EXAMPLE_QUERY = """
Example — "Cheapest saved hotel in 94010 for Oct 10-12?" (checkout Oct 12
excludes the night of the 12th, so this covers Oct 10 and Oct 11 — 2
requested nights):

WITH nights AS (
    SELECT z.hotel_id, h.name, h.address, n.stay_date,
           n.nightly_rate_cents, n.rooms_available
    FROM saved_hotel_zip_searches z
    JOIN saved_hotels h ON h.hotel_id = z.hotel_id
    JOIN demo_hotel_nights n ON n.hotel_id = z.hotel_id
    WHERE z.zip = '94010'
      AND n.stay_date IN ('2026-10-10', '2026-10-11')
      AND n.rooms_available > 0
),
totals AS (
    SELECT hotel_id, name, address, COUNT(*) AS nights_found,
           SUM(nightly_rate_cents) AS total_cost_cents
    FROM nights
    GROUP BY hotel_id, name, address
    HAVING COUNT(*) = 2
)
SELECT nights.hotel_id, nights.name, nights.address, nights.stay_date,
       nights.nightly_rate_cents, nights.rooms_available,
       totals.nights_found, totals.total_cost_cents
FROM nights
JOIN totals ON totals.hotel_id = nights.hotel_id
ORDER BY totals.total_cost_cents ASC, nights.hotel_id, nights.stay_date
LIMIT 50;
""".strip()


class LLMNotConfiguredError(Exception):
    """Raised when OPENROUTER_API_KEY or OPENROUTER_MODEL is not configured."""


class LLMRateLimitedError(Exception):
    """Raised when OpenRouter responds with 429."""


class LLMRequestError(Exception):
    """Raised when the OpenRouter request fails: network error, timeout,
    other non-2xx status, or an unparseable response."""


class SQLRejectedError(Exception):
    """Raised when the LLM-proposed SQL fails validation. Carries the
    (possibly partially-processed) SQL so the caller can still show the
    caller what was rejected, without ever having executed it for real."""

    def __init__(self, message: str, proposed_sql: str | None = None):
        super().__init__(message)
        self.proposed_sql = proposed_sql


class ReadOnlyRefusalError(Exception):
    """Raised when stage 1 recognizes the question as a request to modify
    data (add/change/delete/book/cancel) rather than ask about it. Unlike
    SQLRejectedError, no SQL was ever proposed — the model refused before
    writing any."""


def _call_openrouter(messages: list[dict]) -> str:
    api_key = config.get_openrouter_api_key()
    model = config.get_openrouter_model()
    if not api_key or not model:
        raise LLMNotConfiguredError("OpenRouter API key or model is not configured")

    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={"model": model, "messages": messages, "temperature": 0},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except httpx.HTTPError:
        raise LLMRequestError("OpenRouter request failed") from None

    if response.status_code == 429:
        raise LLMRateLimitedError("OpenRouter rate limit exceeded")

    try:
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        raise LLMRequestError("OpenRouter returned an unusable response") from None


def _strip_fences(raw_text: str) -> str:
    text = raw_text.strip()
    fence_match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    return text


def _extract_sql(raw_text: str) -> str:
    text = _strip_fences(raw_text)
    # Models sometimes add a prose explanation after the SQL despite being
    # told not to — it's reliably separated from the SQL by a blank line,
    # so keep only the first paragraph.
    text = text.split("\n\n")[0].strip()
    return text


def _classify_stage1_response(raw_text: str) -> tuple[str, str | None]:
    """
    Stage 1 replies either with a SQL query, or — for three specific
    situations — one exact sentinel instead of SQL. Returns (kind,
    payload): ("sql", sql_text), ("insufficient_data", reason),
    ("read_only_refusal", None), or ("unclear", None).
    """
    text = _strip_fences(raw_text)

    match = re.match(
        rf"^{SENTINEL_INSUFFICIENT_DATA}\s*:?\s*(.*)$", text, re.IGNORECASE | re.DOTALL
    )
    if match:
        reason_text = match.group(1).strip()
        reason = reason_text.splitlines()[0].strip() if reason_text else ""
        return "insufficient_data", reason or "The saved-hotel data doesn't include that information."

    if re.match(rf"^{SENTINEL_READ_ONLY_REFUSAL}\b", text, re.IGNORECASE):
        return "read_only_refusal", None

    if re.match(rf"^{SENTINEL_UNCLEAR}\b", text, re.IGNORECASE):
        return "unclear", None

    return "sql", _extract_sql(raw_text)


def _ensure_row_limit(sql: str) -> str:
    match = re.search(r"LIMIT\s+(\d+)\s*;?\s*$", sql, re.IGNORECASE)
    if match:
        if int(match.group(1)) > MAX_ROW_LIMIT:
            return sql[: match.start()] + f"LIMIT {MAX_ROW_LIMIT}"
        return sql
    return sql.rstrip().rstrip(";").rstrip() + f" LIMIT {MAX_ROW_LIMIT}"


def _authorizer(action, arg1, arg2, dbname, source):
    """SQLite's own query authorizer — fires once per table/column access,
    pragma, function call, etc. *during compilation*, before anything
    runs. Far more robust than scanning the SQL text for forbidden
    keywords: it can't be fooled by comments, whitespace, or string
    literals, and it denies PRAGMA/ATTACH/INSERT/UPDATE/DELETE/DROP/
    ALTER/CREATE/REPLACE automatically just by never allowing them."""
    if action == sqlite3.SQLITE_SELECT:
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_OK if arg1 in ALLOWED_TABLES else sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def validate_and_run_sql(sql: str) -> tuple[str, list[dict]]:
    """
    Validates an LLM-proposed SQL string and, if it passes, executes it on
    a read-only connection. Returns (final_sql, rows).

    Raises SQLRejectedError if the SQL is empty, isn't a SELECT or
    WITH...SELECT, is more than one statement, touches any table besides
    the three allowed ones, or attempts anything other than a read
    (PRAGMA/ATTACH/INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/REPLACE/etc).

    A missing LIMIT gets one added (<=50); an existing LIMIT over 50 is
    capped at 50.
    """
    stripped = sql.strip()
    if not stripped:
        raise SQLRejectedError("The model did not propose a query.", proposed_sql=sql)

    if not re.match(r"^(WITH\b|SELECT\b)", stripped, re.IGNORECASE):
        raise SQLRejectedError(
            "Only a SELECT (or WITH ... SELECT) query is allowed.", proposed_sql=stripped
        )

    final_sql = _ensure_row_limit(stripped)

    conn = sqlite3.connect(f"file:{models.DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.set_authorizer(_authorizer)
    try:
        cursor = conn.execute(final_sql)
        rows = [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as exc:
        raise SQLRejectedError(f"Query rejected: {exc}", proposed_sql=final_sql) from None
    finally:
        conn.close()

    return final_sql, rows


def _build_sql_prompt(question: str) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You translate a traveler's question into a single SQLite "
                "SELECT query — or, in three specific cases, one exact "
                "sentinel reply instead of SQL (see below).\n\n"
                f"Tables:\n{SCHEMA_DESCRIPTION}\n\n"
                f"Rules:\n{QUERY_RULES}\n\n"
                "Ground rule: use ONLY values that appear in the database "
                "or literally in the question itself (ZIP codes, dates, "
                "hotel names the traveler already named). Never use "
                "outside knowledge — no landmark or airport coordinates, "
                "no distances to places that aren't in the database, no "
                "star ratings, no amenities, nothing that isn't in the "
                "schema or the question.\n\n"
                "Sentinel replies — if one applies, reply with ONLY that "
                "exact text and nothing else (no SQL, no explanation):\n"
                f"- If answering needs information this schema doesn't "
                f"have (e.g. distance to a named landmark/airport, star "
                f"ratings, amenities), reply exactly: "
                f"{SENTINEL_INSUFFICIENT_DATA}: <one-line reason naming "
                "what's missing>\n"
                f"- If the question asks to add, change, delete, cancel, "
                f"or book anything (not just ask about existing saved "
                f"hotels), reply exactly: {SENTINEL_READ_ONLY_REFUSAL}\n"
                f"- If the input isn't a question about saved hotels' "
                f"locations, stay dates, rates, or availability at all "
                f"(stray text, an unrelated fragment, etc.), reply "
                f"exactly: {SENTINEL_UNCLEAR}\n\n"
                "Otherwise, reply with ONLY the SQL — no explanation, no "
                "markdown code fences.\n\n"
                "For any question about a stay, a price, or availability, "
                "return PER-NIGHT rows — one row per hotel per requested "
                "night — with columns hotel_id, name, address, stay_date, "
                "nightly_rate_cents, rooms_available, plus two per-hotel "
                "aggregate columns computed with a CTE or window function: "
                "nights_found and total_cost_cents. A check-in date A to "
                "checkout date B covers nights A through the night before "
                "B (checkout excluded). Include a hotel only if it has a "
                "row for EVERY requested night with rooms_available > 0 — "
                "use HAVING COUNT(*) = <number of requested nights> to "
                "enforce this; a hotel missing even one requested night "
                "is not available for that stay and must never appear as "
                "cheaper or available. For 'cheapest'/'compare' "
                "questions, return ALL qualifying hotels ordered by "
                "total_cost_cents ascending — never LIMIT 1 — so the "
                "answer can compare them.\n\n"
                f"{EXAMPLE_QUERY}\n\n"
                "Only query these three tables. Never use PRAGMA, ATTACH, "
                "INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or REPLACE. "
                "Include a LIMIT clause of at most 50."
            ),
        },
        {"role": "user", "content": question},
    ]


def _build_answer_prompt(question: str, rows: list[dict]) -> list[dict]:
    return [
        {
            "role": "system",
            "content": (
                "You are answering a traveler directly, in plain language "
                "— say \"you\"/\"your\", never \"the rows\", \"the "
                "provided data\", \"columns\", or \"cents\". Use ONLY the "
                "JSON data given below, which already reflects every rule "
                "about which nights and hotels qualify — never add a "
                "fact that isn't in it (no outside knowledge: no "
                "landmark distances, ratings, amenities, or anything not "
                "in the data). Convert nightly_rate_cents and "
                "total_cost_cents to dollars yourself (divide by 100) "
                "and never say \"cents\".\n\n"
                "When the data includes dates, rates, and totals for a "
                "hotel, state them directly and confidently in the "
                "labeled fields below — do not hedge, and never say you "
                "'cannot confirm' something that's actually in the data. "
                "If more than one hotel qualifies, lead with the best "
                "match (e.g. the cheapest) in the fields, and name the "
                "other qualifying hotels and their totals in Reason for "
                "comparison. Only say information is missing when a "
                "specific fact you'd need truly isn't in the data (e.g. "
                "a requested night has no matching entry for a hotel — "
                "that hotel isn't available for the full stay).\n\n"
                "Format your reply as these labeled lines, one per line, "
                "omitting a label only when it truly doesn't apply:\n"
                "Hotel: <name, or the names of the hotels being compared>\n"
                "Location: <address or city>\n"
                "Stay: <the nights this covers>\n"
                "Nightly rate: <$ per night>\n"
                "Total cost: <$ total for the requested nights>\n"
                "Availability: <rooms available>\n"
                "Reason: <one sentence — why this answer, and how it "
                "compares to any other qualifying hotels>\n"
                "If the data truly doesn't answer the question, skip the "
                "labels and say plainly, in one sentence, what's missing."
            ),
        },
        {
            "role": "user",
            "content": f"Traveler's question: {question}\n\nData (JSON):\n{json.dumps(rows)}",
        },
    ]


def answer_question(question: str) -> dict:
    """
    Runs the two-stage RAG flow: ask the LLM for a SQL query, validate and
    run it read-only, then (only if rows came back) ask the LLM to answer
    using only those rows.

    Stage 1 can also reply with one of three sentinels instead of SQL —
    INSUFFICIENT_DATA, READ_ONLY_REFUSAL, or UNCLEAR — each of which
    short-circuits the flow before any SQL is generated or executed, and
    before stage 2 is ever called.

    Returns {question, proposed_sql, rows, answer, status} with status
    "answer", "no_match", "insufficient_data", or "unclear" on success.
    "no_match" is decided by us directly from an empty result set — not
    by asking the LLM to self-report "no rows," which would be one more
    place for it to hallucinate.

    Raises SQLRejectedError, ReadOnlyRefusalError, LLMNotConfiguredError,
    LLMRateLimitedError, or LLMRequestError on failure; main.py maps
    these to distinct HTTP statuses and the "rejected"/"error" response
    status values.
    """
    sql_response = _call_openrouter(_build_sql_prompt(question))
    kind, payload = _classify_stage1_response(sql_response)

    if kind == "insufficient_data":
        return {
            "question": question,
            "proposed_sql": None,
            "rows": [],
            "answer": payload,
            "status": "insufficient_data",
        }

    if kind == "read_only_refusal":
        raise ReadOnlyRefusalError()

    if kind == "unclear":
        return {
            "question": question,
            "proposed_sql": None,
            "rows": [],
            "answer": (
                "I can answer questions about your saved hotels' "
                "locations, stay dates, nightly rates, and availability. "
                "Try: \"Cheapest saved hotel for Oct 10-12?\""
            ),
            "status": "unclear",
        }

    final_sql, rows = validate_and_run_sql(payload)

    if not rows:
        return {
            "question": question,
            "proposed_sql": final_sql,
            "rows": [],
            "answer": "No saved hotels match that question. Try a different ZIP, hotel, or dates.",
            "status": "no_match",
        }

    answer_text = _call_openrouter(_build_answer_prompt(question, rows))

    return {
        "question": question,
        "proposed_sql": final_sql,
        "rows": rows,
        "answer": answer_text.strip(),
        "status": "answer",
    }
