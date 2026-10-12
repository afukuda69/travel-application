from models import get_connection

DEMO_NIGHT_DATES = [
    "2026-10-10",
    "2026-10-11",
    "2026-10-12",
    "2026-10-13",
    "2026-10-14",
]
DEFAULT_NIGHTLY_RATE_CENTS = 10000
DEFAULT_ROOMS_AVAILABLE = 20


class HotelNotSavedError(Exception):
    """Raised when trying to remove a hotel that isn't currently saved."""


def _nights_for(conn, hotel_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT stay_date, nightly_rate_cents, rooms_available
        FROM demo_hotel_nights
        WHERE hotel_id = ?
        ORDER BY stay_date
        """,
        (hotel_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _hotel_detail(conn, hotel_id: str) -> dict:
    row = conn.execute(
        "SELECT hotel_id, name, address, latitude, longitude FROM saved_hotels WHERE hotel_id = ?",
        (hotel_id,),
    ).fetchone()
    return {**dict(row), "nights": _nights_for(conn, hotel_id)}


def save_hotel(
    hotel_id: str,
    name: str | None,
    address: str | None,
    latitude: float,
    longitude: float,
    zip_code: str,
    locality: str | None,
    center_latitude: float | None = None,
    center_longitude: float | None = None,
) -> dict:
    """
    Save a hotel (from the Part 1 Places lookup) plus its ZIP context, and
    seed its demo nightly rates/availability for Oct 10-14, 2026.

    center_latitude/center_longitude are the resolved ZIP's own
    coordinates (what the map centers on for this ZIP), not the hotel's —
    optional, since older rows were saved before this was tracked; see
    list_saved_hotels_for_zip for the centroid fallback this enables.

    Idempotent / repeatable: re-saving the same hotel_id, the same
    (hotel_id, zip) pair, or the same (hotel_id, stay_date) night is a
    no-op for that row (INSERT OR IGNORE) — nothing is duplicated and
    existing rates/availability are never overwritten. All writes commit
    together.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO saved_hotels (hotel_id, name, address, latitude, longitude)
            VALUES (?, ?, ?, ?, ?)
            """,
            (hotel_id, name, address, latitude, longitude),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO saved_hotel_zip_searches
                (hotel_id, zip, locality, center_latitude, center_longitude)
            VALUES (?, ?, ?, ?, ?)
            """,
            (hotel_id, zip_code, locality, center_latitude, center_longitude),
        )
        conn.executemany(
            """
            INSERT OR IGNORE INTO demo_hotel_nights (hotel_id, stay_date, nightly_rate_cents, rooms_available)
            VALUES (?, ?, ?, ?)
            """,
            [
                (hotel_id, stay_date, DEFAULT_NIGHTLY_RATE_CENTS, DEFAULT_ROOMS_AVAILABLE)
                for stay_date in DEMO_NIGHT_DATES
            ],
        )
        conn.commit()
        return _hotel_detail(conn, hotel_id)
    finally:
        conn.close()


def list_saved_hotel_ids() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT hotel_id FROM saved_hotels").fetchall()
        return [row["hotel_id"] for row in rows]
    finally:
        conn.close()


def list_saved_hotels_for_zip(zip_code: str) -> dict:
    """
    Returns {zip, locality, latitude, longitude, hotels}. latitude/
    longitude are the ZIP's own center coordinates when a saved row has
    them; if every matching row predates that column (both NULL), they're
    computed as the centroid of the saved hotels' own coordinates instead,
    so the map always has something valid to center on for a non-empty
    result — callers never see null coordinates when hotels is non-empty.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT sh.hotel_id, sh.name, sh.address, sh.latitude, sh.longitude,
                   z.locality, z.center_latitude, z.center_longitude
            FROM saved_hotel_zip_searches z
            JOIN saved_hotels sh ON sh.hotel_id = z.hotel_id
            WHERE z.zip = ?
            ORDER BY sh.name
            """,
            (zip_code,),
        ).fetchall()

        locality = None
        center_latitude = None
        center_longitude = None
        hotels = []
        for row in rows:
            locality = locality or row["locality"]
            if center_latitude is None and row["center_latitude"] is not None:
                center_latitude = row["center_latitude"]
                center_longitude = row["center_longitude"]
            hotels.append(
                {
                    "hotel_id": row["hotel_id"],
                    "name": row["name"],
                    "address": row["address"],
                    "latitude": row["latitude"],
                    "longitude": row["longitude"],
                    "nights": _nights_for(conn, row["hotel_id"]),
                }
            )

        if center_latitude is None and hotels:
            center_latitude = sum(h["latitude"] for h in hotels) / len(hotels)
            center_longitude = sum(h["longitude"] for h in hotels) / len(hotels)

        return {
            "zip": zip_code,
            "locality": locality,
            "latitude": center_latitude,
            "longitude": center_longitude,
            "hotels": hotels,
        }
    finally:
        conn.close()


def delete_saved_hotel(hotel_id: str) -> None:
    """
    Remove a saved hotel, its ZIP associations, and its demo nightly
    records together. Children are deleted before the parent (required
    since foreign keys are enforced) and everything commits in one
    transaction — a failure partway through leaves the database exactly
    as it was before the call.
    """
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT hotel_id FROM saved_hotels WHERE hotel_id = ?", (hotel_id,)
        ).fetchone()
        if existing is None:
            raise HotelNotSavedError(hotel_id)

        conn.execute("DELETE FROM demo_hotel_nights WHERE hotel_id = ?", (hotel_id,))
        conn.execute("DELETE FROM saved_hotel_zip_searches WHERE hotel_id = ?", (hotel_id,))
        conn.execute("DELETE FROM saved_hotels WHERE hotel_id = ?", (hotel_id,))
        conn.commit()
    finally:
        conn.close()
