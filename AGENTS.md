# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Commands
- **Backend Tests (all)**: `cd booking_system_backend && .venv/bin/pytest`
- **Backend Test (single file)**: `cd booking_system_backend && .venv/bin/pytest tests/test_services.py`
- **Backend Test (single test)**: `cd booking_system_backend && .venv/bin/pytest tests/test_rest.py::TestBookEndpoint::test_book_flight_success`
- **Run Backend**: `cd booking_system_backend && .venv/bin/python server.py` (FastAPI + MCP at port 8080)
- **Frontend Build & Typecheck**: `cd booking_system_frontend && npm run build` (`tsc -b && vite build`)
- **Frontend Lint**: `cd booking_system_frontend && npm run lint` (`eslint .`)
- **Frontend Dev**: `cd booking_system_frontend && npm run dev`

## Code Style & Conventions
- **Dual Protocol Endpoints**: Business logic resides in `booking_system_backend/services/`. REST endpoints in `server.py` return `Union[ModelOut, ErrorResponse]` with HTTP 200 on business errors. MCP tools raise Python `Exception(result.details or result.error)` on `ErrorResponse`.
- **Seat Class Domain**: Seat classes (`economy`, `business`, `galaxium`) and price multipliers (1.0x, 1.5x, 2.5x) are centrally managed in `booking_system_backend/seat_classes.py`. Always use `calculate_class_price(base_price, seat_class)` and `get_seat_column_name(seat_class)`.
- **Database Sessions**: MCP tools must explicitly create and close `SessionLocal()` within `try...finally`. FastAPI endpoints use dependency injection `Depends(get_db)`.
- **Pydantic Serialization**: `FlightOut` derives `seats_available` (total) and `seat_classes` via `@model_validator(mode="before")` on ORM models. Passing plain dicts requires supplying both fields explicitly.
- **Database Reseeding**: `init_db()` and `seed()` run on every server startup in `lifespan`. Schema changes require deleting `booking.db` manually (no migration tool).
- **Test Isolation**: In-memory test SQLite engines must use `StaticPool` and `check_same_thread=False` to prevent thread crashes in FastAPI's `TestClient`.
- **Frontend API Client**: Axios response interceptor rejects error payloads; check error responses with `isErrorResponse(res)` helper.
