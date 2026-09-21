import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "travel.db"

DEMO_TRAVELER_NAMES = ["Demo Traveler 1", "Demo Traveler 2", "Demo Traveler 3"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS hotels (
    hotel_id TEXT PRIMARY KEY,
    hotel_name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    nightly_rate_usd INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id TEXT PRIMARY KEY,
    hotel_id TEXT NOT NULL REFERENCES hotels(hotel_id),
    trip_name TEXT NOT NULL,
    check_in TEXT NOT NULL,
    check_out TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trip_id TEXT NOT NULL REFERENCES trips(trip_id),
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL
);
"""


@dataclass
class Hotel:
    hotel_id: str
    hotel_name: str
    city: str
    state: str
    nightly_rate_usd: int

    @classmethod
    def from_row(cls, row):
        return cls(
            hotel_id=row["hotel_id"],
            hotel_name=row["hotel_name"],
            city=row["city"],
            state=row["state"],
            nightly_rate_usd=row["nightly_rate_usd"],
        )


@dataclass
class Trip:
    trip_id: str
    hotel_id: str
    trip_name: str
    check_in: str
    check_out: str

    @classmethod
    def from_row(cls, row):
        return cls(
            trip_id=row["trip_id"],
            hotel_id=row["hotel_id"],
            trip_name=row["trip_name"],
            check_in=row["check_in"],
            check_out=row["check_out"],
        )


@dataclass
class User:
    user_id: int
    name: str

    @classmethod
    def from_row(cls, row):
        return cls(user_id=row["user_id"], name=row["name"])


@dataclass
class Booking:
    booking_id: int
    trip_id: str
    user_id: int
    status: str
    created_at: str

    @classmethod
    def from_row(cls, row):
        return cls(
            booking_id=row["booking_id"],
            trip_id=row["trip_id"],
            user_id=row["user_id"],
            status=row["status"],
            created_at=row["created_at"],
        )


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _seed_if_empty(conn)
    finally:
        conn.close()


def _seed_if_empty(conn):
    hotel_count = conn.execute("SELECT COUNT(*) FROM hotels").fetchone()[0]
    if hotel_count == 0:
        with open(BASE_DIR / "hotels.csv", newline="", encoding="utf-8-sig") as f:
            hotels = list(csv.DictReader(f))
        with open(BASE_DIR / "trips.csv", newline="", encoding="utf-8-sig") as f:
            trips = list(csv.DictReader(f))

        conn.executemany(
            """
            INSERT INTO hotels (hotel_id, hotel_name, city, state, nightly_rate_usd)
            VALUES (:hotel_id, :hotel_name, :city, :state, :nightly_rate_usd)
            """,
            hotels,
        )
        conn.executemany(
            """
            INSERT INTO trips (trip_id, hotel_id, trip_name, check_in, check_out)
            VALUES (:trip_id, :hotel_id, :trip_name, :check_in, :check_out)
            """,
            trips,
        )

    user_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        conn.executemany(
            "INSERT INTO users (name) VALUES (?)",
            [(name,) for name in DEMO_TRAVELER_NAMES],
        )

    conn.commit()
