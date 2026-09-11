import csv
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Travel Application API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

combined_records = []


def load_records():
    hotels_by_id = {}
    with open(BASE_DIR / "hotels.csv", newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            hotels_by_id[row["hotel_id"]] = row

    records = []
    with open(BASE_DIR / "trips.csv", newline="", encoding="utf-8-sig") as f:
        for trip in csv.DictReader(f):
            hotel = hotels_by_id.get(trip["hotel_id"], {})
            records.append({**hotel, **trip})
    return records


@app.on_event("startup")
def on_startup():
    global combined_records
    combined_records = load_records()


@app.get("/search")
def search(hotel_name: str = ""):
    query = hotel_name.strip().lower()
    if not query:
        return combined_records
    return [
        record
        for record in combined_records
        if query in record.get("hotel_name", "").lower()
    ]
