import re
from dataclasses import asdict

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import config
import controller
import places_lookup
import zip_lookup
from models import init_db

DEMO_ZIP_POSTCODE = "16802"
ZIP_PATTERN = re.compile(r"\d{5}")

app = FastAPI(title="Travel Application API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:8080",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


class BookingCreate(BaseModel):
    trip_id: str
    user_id: int


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "geoapify_api_key": "configured" if config.is_geoapify_configured() else "not configured",
    }


def _resolve_zip_or_error(postcode: str) -> zip_lookup.ZipLocation:
    try:
        return zip_lookup.lookup_zip(postcode)
    except zip_lookup.GeoapifyNotConfiguredError:
        raise HTTPException(status_code=503, detail="Geoapify API key is not configured")
    except zip_lookup.ZipNotResolvedError:
        raise HTTPException(status_code=404, detail="ZIP code could not be resolved")
    except zip_lookup.GeoapifyRequestError:
        raise HTTPException(status_code=502, detail="Geoapify request failed")


def _require_valid_zip(zip_code: str) -> None:
    if not ZIP_PATTERN.fullmatch(zip_code):
        raise HTTPException(status_code=422, detail="ZIP code must be exactly 5 digits")


@app.get("/api/demo/zip-location")
def demo_zip_location():
    return asdict(_resolve_zip_or_error(DEMO_ZIP_POSTCODE))


@app.get("/api/zip-location")
def zip_location(zip_code: str = Query("", alias="zip")):
    _require_valid_zip(zip_code)
    return asdict(_resolve_zip_or_error(zip_code))


@app.get("/api/hotels/nearby")
def hotels_nearby(zip_code: str = Query("", alias="zip")):
    _require_valid_zip(zip_code)
    location = _resolve_zip_or_error(zip_code)

    try:
        hotels = places_lookup.find_nearby_hotels(location.latitude, location.longitude)
    except places_lookup.GeoapifyNotConfiguredError:
        raise HTTPException(status_code=503, detail="Geoapify API key is not configured")
    except places_lookup.PlacesRateLimitedError:
        raise HTTPException(status_code=429, detail="Geoapify rate limit exceeded")
    except places_lookup.PlacesRequestError:
        raise HTTPException(status_code=502, detail="Geoapify Places request failed")

    return {
        "location": asdict(location),
        "hotels": [asdict(hotel) for hotel in hotels],
        "radius_m": places_lookup.SEARCH_RADIUS_METERS,
    }


@app.get("/search")
def search(hotel_name: str = ""):
    return controller.search_hotel_trips(hotel_name)


@app.get("/users")
def get_users():
    return controller.list_users()


@app.get("/bookings")
def get_bookings():
    return controller.list_bookings()


@app.post("/bookings", status_code=201)
def create_booking(payload: BookingCreate):
    try:
        return controller.create_booking(payload.trip_id, payload.user_id)
    except controller.TripNotFoundError:
        raise HTTPException(status_code=404, detail="Trip not found")
    except controller.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")


@app.patch("/bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int):
    try:
        return controller.cancel_booking(booking_id)
    except controller.BookingNotFoundError:
        raise HTTPException(status_code=404, detail="Booking not found")


@app.delete("/bookings/{booking_id}", status_code=204)
def delete_booking(booking_id: int):
    try:
        controller.delete_booking(booking_id)
    except controller.BookingNotFoundError:
        raise HTTPException(status_code=404, detail="Booking not found")
    return Response(status_code=204)
