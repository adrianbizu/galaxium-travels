import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import User, Flight, Booking


class TestFlightsEndpoint:
    """Test /flights endpoint."""

    def test_get_flights_empty(self, client, db_session):
        """Test getting flights when database is empty."""
        response = client.get("/flights")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_flights_with_data(self, client, db_session):
        """Test getting flights with data."""
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=3,
            seats_business=1,
            seats_galaxium=1
        ))
        db_session.commit()

        response = client.get("/flights")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["origin"] == "Earth"
        assert data[0]["destination"] == "Mars"


class TestRegisterEndpoint:
    """Test /register endpoint."""

    def test_register_success(self, client, db_session, sample_user_data):
        """Test successful user registration."""
        response = client.post("/register", json=sample_user_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]
        assert data["email"] == sample_user_data["email"]
        assert "user_id" in data

    def test_register_duplicate_email(self, client, db_session, sample_user_data):
        """Test registration with duplicate email."""
        client.post("/register", json=sample_user_data)
        response = client.post("/register", json=sample_user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "EMAIL_EXISTS"


class TestUserEndpoint:
    """Test /user endpoint."""

    def test_get_user_success(self, client, db_session, sample_user_data):
        """Test successful user retrieval."""
        client.post("/register", json=sample_user_data)

        response = client.get(
            "/user",
            params={"name": sample_user_data["name"], "email": sample_user_data["email"]}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == sample_user_data["name"]

    def test_get_user_not_found(self, client, db_session):
        """Test user retrieval when not found."""
        response = client.get(
            "/user",
            params={"name": "NonExistent", "email": "none@example.com"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "USER_NOT_FOUND"


class TestBookEndpoint:
    """Test /book endpoint."""

    def test_book_flight_success(self, client, db_session, sample_user_data):
        """Test successful flight booking."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=3,
            seats_business=1,
            seats_galaxium=1
        ))
        db_session.commit()
        flight = db_session.query(Flight).first()

        # Book flight
        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight.flight_id
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "booked"
        assert data["user_id"] == user_id

    def test_book_flight_not_found(self, client, db_session, sample_user_data):
        """Test booking non-existent flight."""
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": 999
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "FLIGHT_NOT_FOUND"


class TestBookingsEndpoint:
    """Test /bookings/{user_id} endpoint."""

    def test_get_bookings_success(self, client, db_session, sample_user_data):
        """Test getting user bookings."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight and booking
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=3,
            seats_business=1,
            seats_galaxium=1
        ))
        db_session.commit()
        flight = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_id,
            flight_id=flight.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        response = client.get(f"/bookings/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == "booked"

    def test_get_bookings_empty(self, client, db_session):
        """Test getting bookings when user has none."""
        response = client.get("/bookings/999")
        assert response.status_code == 200
        assert response.json() == []


class TestCancelEndpoint:
    """Test /cancel/{booking_id} endpoint."""

    def test_cancel_booking_success(self, client, db_session, sample_user_data):
        """Test successful booking cancellation."""
        # Register user
        user_response = client.post("/register", json=sample_user_data)
        user_id = user_response.json()["user_id"]

        # Create flight and booking
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=2,
            seats_business=1,
            seats_galaxium=1
        ))
        db_session.commit()
        flight = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_id,
            flight_id=flight.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()
        booking = db_session.query(Booking).first()

        response = client.post(f"/cancel/{booking.booking_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

    def test_cancel_booking_not_found(self, client, db_session):
        """Test cancelling non-existent booking."""
        response = client.post("/cancel/999")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "BOOKING_NOT_FOUND"


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client, db_session):
        """Test health check returns OK."""
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "OK"}


class TestSeatClassEndpoints:
    """Test seat class behaviour through the REST API."""

    def _setup(self, client, db_session, sample_user_data, economy=3, business=2, galaxium=1):
        """Register a user and add a flight with the given per-class seats."""
        user_id = client.post("/register", json=sample_user_data).json()["user_id"]
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=economy,
            seats_business=business,
            seats_galaxium=galaxium
        ))
        db_session.commit()
        return user_id, db_session.query(Flight).first().flight_id

    def _seats_by_class(self, client):
        """Return {seat_class: seats_available} for the first flight from /flights."""
        flight = client.get("/flights").json()[0]
        return {c["seat_class"]: c["seats_available"] for c in flight["seat_classes"]}

    def test_get_flights_per_class_breakdown(self, client, db_session):
        """Test /flights returns the per-class breakdown and the total."""
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=3,
            seats_business=1,
            seats_galaxium=0
        ))
        db_session.commit()

        response = client.get("/flights")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["price"] == 1000000
        assert data[0]["seats_available"] == 4
        assert data[0]["seat_classes"] == [
            {"seat_class": "economy", "price": 1000000, "seats_available": 3},
            {"seat_class": "business", "price": 1500000, "seats_available": 1},
            {"seat_class": "galaxium", "price": 2500000, "seats_available": 0},
        ]

    def test_book_flight_defaults_to_economy(self, client, db_session, sample_user_data):
        """Test booking without seat_class books economy and returns class and price."""
        user_id, flight_id = self._setup(client, db_session, sample_user_data)

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "booked"
        assert data["seat_class"] == "economy"
        assert data["price_paid"] == 1000000
        assert self._seats_by_class(client) == {"economy": 2, "business": 2, "galaxium": 1}

    @pytest.mark.parametrize("seat_class,expected_price", [
        ("economy", 1000000),
        ("business", 1500000),
        ("galaxium", 2500000),
    ])
    def test_book_flight_price_is_base_times_multiplier(
        self, client, db_session, sample_user_data, seat_class, expected_price
    ):
        """Test price_paid equals base price x class multiplier (1x, 1.5x, 2.5x)."""
        user_id, flight_id = self._setup(client, db_session, sample_user_data)

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id,
            "seat_class": seat_class
        })

        assert response.status_code == 200
        data = response.json()
        assert data["seat_class"] == seat_class
        assert data["price_paid"] == expected_price

    def test_book_flight_sold_out_class(self, client, db_session, sample_user_data):
        """Test a sold-out class returns NO_SEATS_AVAILABLE while others still have seats."""
        user_id, flight_id = self._setup(client, db_session, sample_user_data, galaxium=0)

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id,
            "seat_class": "galaxium"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "NO_SEATS_AVAILABLE"
        assert self._seats_by_class(client) == {"economy": 3, "business": 2, "galaxium": 0}

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id,
            "seat_class": "business"
        })
        assert response.json()["status"] == "booked"

    def test_book_flight_invalid_seat_class(self, client, db_session, sample_user_data):
        """Test an unknown seat class returns INVALID_SEAT_CLASS."""
        user_id, flight_id = self._setup(client, db_session, sample_user_data)

        response = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id,
            "seat_class": "first"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == False
        assert data["error_code"] == "INVALID_SEAT_CLASS"
        assert self._seats_by_class(client) == {"economy": 3, "business": 2, "galaxium": 1}

    def test_cancel_booking_restores_booked_class(self, client, db_session, sample_user_data):
        """Test cancelling a booking restores the seat to the booked class."""
        user_id, flight_id = self._setup(client, db_session, sample_user_data)

        booked = client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id,
            "seat_class": "galaxium"
        }).json()
        assert self._seats_by_class(client) == {"economy": 3, "business": 2, "galaxium": 0}

        response = client.post(f"/cancel/{booked['booking_id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["seat_class"] == "galaxium"
        assert self._seats_by_class(client) == {"economy": 3, "business": 2, "galaxium": 1}

    def test_get_bookings_includes_class_and_price(self, client, db_session, sample_user_data):
        """Test /bookings/{user_id} returns seat_class and price_paid."""
        user_id, flight_id = self._setup(client, db_session, sample_user_data)
        client.post("/book", json={
            "user_id": user_id,
            "name": sample_user_data["name"],
            "flight_id": flight_id,
            "seat_class": "business"
        })

        response = client.get(f"/bookings/{user_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["seat_class"] == "business"
        assert data[0]["price_paid"] == 1500000
