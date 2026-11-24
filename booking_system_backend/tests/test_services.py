import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import User, Flight, Booking
from schemas import ErrorResponse
from services import flight, user, booking


class TestFlightService:
    """Test flight service functions."""

    def test_list_flights_empty(self, db_session):
        """Test listing flights when database is empty."""
        result = flight.list_flights(db_session)
        assert result == []

    def test_list_flights_with_data(self, db_session):
        """Test listing flights with data in database."""
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

        result = flight.list_flights(db_session)
        assert len(result) == 1
        assert result[0].origin == "Earth"
        assert result[0].destination == "Mars"


class TestUserService:
    """Test user service functions."""

    def test_register_user_success(self, db_session):
        """Test successful user registration."""
        result = user.register_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"
        assert result.user_id > 0

    def test_register_user_duplicate_email(self, db_session):
        """Test registration with duplicate email."""
        user.register_user(db_session, "User 1", "test@example.com")
        result = user.register_user(db_session, "User 2", "test@example.com")

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "EMAIL_EXISTS"

    def test_get_user_success(self, db_session):
        """Test successful user retrieval."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()

        result = user.get_user(db_session, "Test User", "test@example.com")
        assert result.name == "Test User"
        assert result.email == "test@example.com"

    def test_get_user_not_found(self, db_session):
        """Test user retrieval when not found."""
        result = user.get_user(db_session, "NonExistent", "none@example.com")
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"


class TestBookingService:
    """Test booking service functions."""

    def test_book_flight_success(self, db_session):
        """Test successful flight booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert result.status == "booked"
        assert result.user_id == user_obj.user_id
        assert result.flight_id == flight_obj.flight_id

        # Verify seat was decremented
        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 2
        assert flight_obj.seats_business == 1
        assert flight_obj.seats_galaxium == 1

    def test_book_flight_not_found(self, db_session):
        """Test booking non-existent flight."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.commit()
        user_obj = db_session.query(User).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "FLIGHT_NOT_FOUND"

    def test_book_flight_no_seats(self, db_session):
        """Test booking when no seats available."""
        db_session.add(User(name="Test User", email="test@example.com"))
        db_session.add(Flight(
            origin="Earth",
            destination="Mars",
            departure_time="2099-01-01T09:00:00Z",
            arrival_time="2099-01-01T17:00:00Z",
            price=1000000,
            seats_economy=0,
            seats_business=0,
            seats_galaxium=0
        ))
        db_session.commit()

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NO_SEATS_AVAILABLE"

    def test_book_flight_user_not_found(self, db_session):
        """Test booking with non-existent user."""
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
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, 999, "Fake User", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "USER_NOT_FOUND"

    def test_book_flight_name_mismatch(self, db_session):
        """Test booking with wrong name for user ID."""
        db_session.add(User(name="Real Name", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        result = booking.book_flight(db_session, user_obj.user_id, "Wrong Name", flight_obj.flight_id)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NAME_MISMATCH"

    def test_cancel_booking_success(self, db_session):
        """Test successful booking cancellation."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert result.status == "cancelled"

        # Verify seat was restored
        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert flight_obj.seats_business == 1
        assert flight_obj.seats_galaxium == 1

    def test_cancel_booking_not_found(self, db_session):
        """Test cancelling non-existent booking."""
        result = booking.cancel_booking(db_session, 999)
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "BOOKING_NOT_FOUND"

    def test_cancel_booking_already_cancelled(self, db_session):
        """Test cancelling already cancelled booking."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="cancelled",
            booking_time="2099-01-01T10:00:00Z",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        booking_obj = db_session.query(Booking).first()
        result = booking.cancel_booking(db_session, booking_obj.booking_id)

        assert isinstance(result, ErrorResponse)
        assert result.error_code == "ALREADY_CANCELLED"

    def test_get_bookings_success(self, db_session):
        """Test getting user bookings."""
        db_session.add(User(name="Test User", email="test@example.com"))
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

        user_obj = db_session.query(User).first()
        flight_obj = db_session.query(Flight).first()

        db_session.add(Booking(
            user_id=user_obj.user_id,
            flight_id=flight_obj.flight_id,
            status="booked",
            booking_time="2099-01-01T10:00:00Z",
            seat_class="economy",
            price_paid=1000000
        ))
        db_session.commit()

        result = booking.get_bookings(db_session, user_obj.user_id)
        assert len(result) == 1
        assert result[0].status == "booked"

    def test_get_bookings_empty(self, db_session):
        """Test getting bookings when user has none."""
        result = booking.get_bookings(db_session, 999)
        assert result == []


class TestSeatClasses:
    """Test seat class behaviour in flight and booking services."""

    def _setup(self, db_session, economy=3, business=2, galaxium=1):
        """Add a user and a flight with the given per-class seats."""
        db_session.add(User(name="Test User", email="test@example.com"))
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
        return db_session.query(User).first(), db_session.query(Flight).first()

    def test_list_flights_per_class_breakdown(self, db_session):
        """Test list_flights returns per-class prices/seats and the total."""
        self._setup(db_session, economy=3, business=2, galaxium=0)

        result = flight.list_flights(db_session)
        assert len(result) == 1
        assert result[0].price == 1000000
        assert result[0].seats_available == 5
        assert [(c.seat_class, c.price, c.seats_available) for c in result[0].seat_classes] == [
            ("economy", 1000000, 3),
            ("business", 1500000, 2),
            ("galaxium", 2500000, 0),
        ]

    def test_book_flight_defaults_to_economy(self, db_session):
        """Test booking without a seat class books economy at the base price."""
        user_obj, flight_obj = self._setup(db_session)

        result = booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id)
        assert result.seat_class == "economy"
        assert result.price_paid == 1000000

        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 2
        assert flight_obj.seats_business == 2
        assert flight_obj.seats_galaxium == 1

    @pytest.mark.parametrize("seat_class,expected_price", [
        ("economy", 1000000),
        ("business", 1500000),
        ("galaxium", 2500000),
    ])
    def test_book_flight_price_is_base_times_multiplier(self, db_session, seat_class, expected_price):
        """Test price_paid equals base price x class multiplier (1x, 1.5x, 2.5x)."""
        user_obj, flight_obj = self._setup(db_session)

        result = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, seat_class
        )
        assert result.seat_class == seat_class
        assert result.price_paid == expected_price

    def test_book_flight_decrements_only_booked_class(self, db_session):
        """Test booking a class only decrements that class."""
        user_obj, flight_obj = self._setup(db_session, economy=3, business=2, galaxium=1)

        booking.book_flight(db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "business")

        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert flight_obj.seats_business == 1
        assert flight_obj.seats_galaxium == 1

    def test_book_flight_sold_out_class_while_others_have_seats(self, db_session):
        """Test a sold-out class fails even though other classes have seats."""
        user_obj, flight_obj = self._setup(db_session, economy=3, business=2, galaxium=0)

        result = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "galaxium"
        )
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "NO_SEATS_AVAILABLE"
        assert "galaxium" in result.details

        # Other classes are still bookable and nothing changed
        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert flight_obj.seats_business == 2
        assert flight_obj.seats_galaxium == 0
        assert db_session.query(Booking).count() == 0

        result = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "business"
        )
        assert result.status == "booked"

    def test_book_flight_class_sells_out_after_last_seat(self, db_session):
        """Test booking the last seat of a class makes the next attempt fail."""
        user_obj, flight_obj = self._setup(db_session, economy=3, business=2, galaxium=1)

        first = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "galaxium"
        )
        second = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "galaxium"
        )
        assert first.status == "booked"
        assert isinstance(second, ErrorResponse)
        assert second.error_code == "NO_SEATS_AVAILABLE"

    def test_book_flight_invalid_seat_class(self, db_session):
        """Test booking with an unknown seat class returns INVALID_SEAT_CLASS."""
        user_obj, flight_obj = self._setup(db_session)

        result = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "first"
        )
        assert isinstance(result, ErrorResponse)
        assert result.error_code == "INVALID_SEAT_CLASS"
        for valid_class in ("economy", "business", "galaxium"):
            assert valid_class in result.details

        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert flight_obj.seats_business == 2
        assert flight_obj.seats_galaxium == 1
        assert db_session.query(Booking).count() == 0

    @pytest.mark.parametrize("seat_class", ["economy", "business", "galaxium"])
    def test_cancel_booking_restores_booked_class(self, db_session, seat_class):
        """Test cancelling restores the seat to the class that was booked."""
        user_obj, flight_obj = self._setup(db_session, economy=3, business=2, galaxium=1)

        booked = booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, seat_class
        )
        result = booking.cancel_booking(db_session, booked.booking_id)
        assert result.status == "cancelled"
        assert result.seat_class == seat_class

        db_session.refresh(flight_obj)
        assert flight_obj.seats_economy == 3
        assert flight_obj.seats_business == 2
        assert flight_obj.seats_galaxium == 1

    def test_get_bookings_includes_class_and_price(self, db_session):
        """Test get_bookings returns seat_class and price_paid."""
        user_obj, flight_obj = self._setup(db_session)
        booking.book_flight(
            db_session, user_obj.user_id, "Test User", flight_obj.flight_id, "business"
        )

        result = booking.get_bookings(db_session, user_obj.user_id)
        assert len(result) == 1
        assert result[0].seat_class == "business"
        assert result[0].price_paid == 1500000
