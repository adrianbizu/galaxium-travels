from pydantic import BaseModel, EmailStr, model_validator
from typing import Optional
from seat_classes import SEAT_CLASSES, DEFAULT_SEAT_CLASS, CLASS_SEAT_COLUMNS, calculate_class_price


class SeatClassOut(BaseModel):
    seat_class: str
    price: int
    seats_available: int


class FlightOut(BaseModel):
    flight_id: int
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    price: int  # Economy (base) price
    seats_available: int  # Total across all classes
    seat_classes: list[SeatClassOut]  # Per-class price and availability

    class Config:
        from_attributes = True

    @model_validator(mode="before")
    @classmethod
    def from_flight_model(cls, data):
        """Build the total and per-class breakdown when validating a Flight ORM object."""
        if not hasattr(data, "seats_economy"):
            return data
        seat_classes = [
            {
                "seat_class": seat_class,
                "price": calculate_class_price(data.price, seat_class),
                "seats_available": getattr(data, CLASS_SEAT_COLUMNS[seat_class]),
            }
            for seat_class in SEAT_CLASSES
        ]
        return {
            "flight_id": data.flight_id,
            "origin": data.origin,
            "destination": data.destination,
            "departure_time": data.departure_time,
            "arrival_time": data.arrival_time,
            "price": data.price,
            "seats_available": sum(c["seats_available"] for c in seat_classes),
            "seat_classes": seat_classes,
        }


class BookingRequest(BaseModel):
    user_id: int
    name: str
    flight_id: int
    seat_class: str = DEFAULT_SEAT_CLASS


class BookingOut(BaseModel):
    booking_id: int
    user_id: int
    flight_id: int
    status: str
    booking_time: str
    seat_class: str
    price_paid: int

    class Config:
        from_attributes = True


class UserRegistration(BaseModel):
    name: str
    email: EmailStr


class UserOut(BaseModel):
    user_id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    error_code: str
    details: Optional[str] = None
