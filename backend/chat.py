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


def _extract_sql(raw_text: str) -> str:
    text = raw_text.strip()
    fence_match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.IGNORECASE | re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()
    # Models sometimes add a prose explanation after the SQL despite being
    # told not to — it's reliably separated from the SQL by a blank line,
    # so keep only the first paragraph.
    text = text.split("\n\n")[0].strip()
    return text


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
                "SELECT query. Reply with ONLY the SQL — no explanation, "
                "no markdown code fences.\n\n"
                f"Tables:\n{SCHEMA_DESCRIPTION}\n\n"
                f"Rules:\n{QUERY_RULES}\n\n"
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
                "You answer a traveler's question about their saved "
                "hotels using ONLY the JSON rows given below — never "
                "guess a price, vacancy, location, or hotel that isn't in "
                "the rows. If the rows don't fully answer the question, "
                "say so clearly rather than filling in a gap. For a "
                "multi-night stay, sum the nightly rate only for the "
                "nights present in the rows, and say explicitly if a "
                "requested night has no matching row (that night is not "
                "available) rather than assuming a rate for it. Rates "
                "are in cents in the data — report dollars.\n\n"
                "Format your reply as these labeled lines, one per line, "
                "omitting a label only when it truly doesn't apply (e.g. "
                "no single Total cost when comparing several hotels):\n"
                "Hotel: <name, or \"Multiple hotels\" if comparing>\n"
                "Location: <address or city>\n"
                "Stay dates: <the nights this covers>\n"
                "Nightly rate: <$ per night, or a per-hotel breakdown>\n"
                "Total cost: <$ total for the requested nights>\n"
                "Availability: <rooms available>\n"
                "Reason: <one sentence explaining the answer>\n"
                "If the rows don't answer the question at all, skip the "
                "labels and just explain plainly what's missing."
            ),
        },
        {
            "role": "user",
            "content": f"Question: {question}\n\nRows (JSON):\n{json.dumps(rows)}",
        },
    ]


def answer_question(question: str) -> dict:
    """
    Runs the two-stage RAG flow: ask the LLM for a SQL query, validate and
    run it read-only, then (only if rows came back) ask the LLM to answer
    using only those rows.

    Returns {question, proposed_sql, rows, answer, status} with status
    "answer" or "no_match" on success. "no_match" is decided by us
    directly from an empty result set — not by asking the LLM to
    self-report "no rows," which would be one more place for it to
    hallucinate.

    Raises SQLRejectedError, LLMNotConfiguredError, LLMRateLimitedError,
    or LLMRequestError on failure; main.py maps these to distinct HTTP
    statuses and the "rejected"/"error" response status values.
    """
    sql_response = _call_openrouter(_build_sql_prompt(question))
    proposed_sql = _extract_sql(sql_response)
    final_sql, rows = validate_and_run_sql(proposed_sql)

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
