from dataclasses import asdict
from datetime import datetime, timezone

from models import Booking, Hotel, Trip, User, get_connection

BOOKING_JOIN_SQL = """
    SELECT
        b.booking_id, b.trip_id, b.user_id, b.status, b.created_at,
        u.name AS user_name,
        h.hotel_id, h.hotel_name, h.city, h.state, h.nightly_rate_usd,
        t.trip_name, t.check_in, t.check_out
    FROM bookings b
    JOIN trips t ON t.trip_id = b.trip_id
    JOIN hotels h ON h.hotel_id = t.hotel_id
    JOIN users u ON u.user_id = b.user_id
"""


class TripNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class BookingNotFoundError(Exception):
    pass


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _hotel_trip_detail(row) -> dict:
    hotel = Hotel.from_row(row)
    trip = Trip.from_row(row)
    return {**asdict(hotel), **asdict(trip)}


def _booking_detail(row) -> dict:
    booking = Booking.from_row(row)
    trip = Trip.from_row(row)
    hotel = Hotel.from_row(row)
    user = User(user_id=row["user_id"], name=row["user_name"])
    return {**asdict(booking), **asdict(trip), **asdict(hotel), "user_name": user.name}


def search_hotel_trips(hotel_name: str) -> list[dict]:
    pattern = f"%{_escape_like(hotel_name.strip())}%"
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT h.hotel_id, h.hotel_name, h.city, h.state, h.nightly_rate_usd,
                   t.trip_id, t.trip_name, t.check_in, t.check_out
            FROM trips t
            JOIN hotels h ON h.hotel_id = t.hotel_id
            WHERE LOWER(h.hotel_name) LIKE LOWER(?) ESCAPE '\\'
            """,
            (pattern,),
        ).fetchall()
        return [_hotel_trip_detail(row) for row in rows]
    finally:
        conn.close()


def list_users() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT user_id, name FROM users ORDER BY user_id").fetchall()
        return [asdict(User.from_row(row)) for row in rows]
    finally:
        conn.close()


def list_bookings() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(BOOKING_JOIN_SQL + " ORDER BY b.created_at DESC").fetchall()
        return [_booking_detail(row) for row in rows]
    finally:
        conn.close()


def create_booking(trip_id: str, user_id: int) -> dict:
    conn = get_connection()
    try:
        trip = conn.execute("SELECT trip_id FROM trips WHERE trip_id = ?", (trip_id,)).fetchone()
        if trip is None:
            raise TripNotFoundError(trip_id)

        user = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if user is None:
            raise UserNotFoundError(user_id)

        created_at = datetime.now(timezone.utc).isoformat()
        cursor = conn.execute(
            "INSERT INTO bookings (trip_id, user_id, status, created_at) VALUES (?, ?, 'active', ?)",
            (trip_id, user_id, created_at),
        )
        conn.commit()
        row = conn.execute(
            BOOKING_JOIN_SQL + " WHERE b.booking_id = ?", (cursor.lastrowid,)
        ).fetchone()
        return _booking_detail(row)
    finally:
        conn.close()


def cancel_booking(booking_id: int) -> dict:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT booking_id FROM bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
        if existing is None:
            raise BookingNotFoundError(booking_id)

        conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE booking_id = ?", (booking_id,)
        )
        conn.commit()
        row = conn.execute(
            BOOKING_JOIN_SQL + " WHERE b.booking_id = ?", (booking_id,)
        ).fetchone()
        return _booking_detail(row)
    finally:
        conn.close()


def delete_booking(booking_id: int) -> None:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT booking_id FROM bookings WHERE booking_id = ?", (booking_id,)
        ).fetchone()
        if existing is None:
            raise BookingNotFoundError(booking_id)

        conn.execute("DELETE FROM bookings WHERE booking_id = ?", (booking_id,))
        conn.commit()
    finally:
        conn.close()
