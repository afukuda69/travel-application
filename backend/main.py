from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import controller
from models import init_db

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
