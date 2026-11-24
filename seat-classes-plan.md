# Seat Classes Plan (Economy, Business, Galaxium)

## Top-Level Overview

**Goal:** Let passengers book a seat in one of three classes — Economy, Business, Galaxium — each with its own price and its own seat availability per flight.

**Decisions (confirmed with user):**
- Price = flight base price × class multiplier. Economy 1x, Business 1.5x, Galaxium 2.5x. `Flight.price` stays the base (Economy) price. Multipliers are defined in one place only.
- Each flight tracks seat availability separately per class. The old single `seats_available` counter is replaced by three per-class counts.
- `seat_class` is optional when booking and defaults to `economy`, so existing REST and MCP callers keep working.
- A booking stores its `seat_class` and a snapshot of the price paid, so past bookings don't change if multipliers change later.
- Seed data uses an explicit hand-picked split per flight. Galaxium is the smallest class, and each flight keeps its existing seat total.

**Non-goals:**
- Individual seat numbers or seat maps.
- The empty `booking_system_inventory_hold_service/` directory.
- DB migrations. `seed()` clears all data and runs `create_all` on every startup ([`seed.py`](booking_system_backend/seed.py:6)). A stale `booking.db` file from an older schema must be deleted manually (note for the implementer).

**Approach:** Backend first (model, then logic, then API surface, then tests), then frontend. Each sub-task leaves the repo working.

**Backward compatibility:** `FlightOut` keeps `price` (the Economy price) and `seats_available` (the total across classes). It adds a per-class breakdown.

---

## Sub-Task 1 — Seat class definition and data model

**Intent:** Introduce the seat class concept and store per-class capacity on flights and class details on bookings.

**Expected Outcomes:**
- A single source of truth for the classes and multipliers, plus a helper that computes a class price from a base price.
- `Flight` has per-class seat counts instead of `seats_available`.
- `Booking` has `seat_class` and `price_paid`.

**Todo List:**
1. Add a small module in the backend defining the three classes (`economy`, `business`, `galaxium`), their multipliers, and a price helper that rounds to an integer.
2. Replace `Flight.seats_available` with three non-null integer columns, one per class.
3. Add `seat_class` (string, non-null) and `price_paid` (integer, non-null) to `Booking`.
4. Decide a mapping from class name to the corresponding `Flight` column (for example a helper or attribute-name convention) so services don't hardcode three-way branches.

**Relevant Context:**
- [`booking_system_backend/models.py`](booking_system_backend/models.py:12) — `Flight`, `Booking`
- Existing code style: plain SQLAlchemy `Column` declarations, `String` for classes and timestamps.

**Implementation Notes for Next Sub-Tasks:**
- Module: [`booking_system_backend/seat_classes.py`](booking_system_backend/seat_classes.py)
- Seat classes: `SEAT_CLASSES = ("economy", "business", "galaxium")`, `DEFAULT_SEAT_CLASS = "economy"`
- Multipliers: `SEAT_CLASS_MULTIPLIERS = {"economy": 1.0, "business": 1.5, "galaxium": 2.5}`
- Helper for price: `calculate_class_price(base_price: int, seat_class: str) -> int` (rounds to integer)
- Flight column mapping: `CLASS_SEAT_COLUMNS = {"economy": "seats_economy", "business": "seats_business", "galaxium": "seats_galaxium"}` and helper `get_seat_column_name(seat_class: str) -> str`
- Model columns on `Flight`: `seats_economy`, `seats_business`, `seats_galaxium` (Integer, non-null)
- Model columns on `Booking`: `seat_class` (String, non-null), `price_paid` (Integer, non-null)

**Status:** `[x] done`

---

## Sub-Task 2 — Seed data

**Intent:** Keep demo data consistent with the new model.

**Expected Outcomes:**
- Each seeded flight has explicit per-class seat counts that sum to the old `seats_available`, with Galaxium smallest.
- Seeded bookings have a valid `seat_class` and a matching `price_paid`.

**Todo List:**
1. Replace `seats_available=N` on each seeded flight with explicit per-class counts. Suggested split (Economy / Business / Galaxium):
   - Earth→Mars 5: 3/1/1
   - Earth→Moon 3: 2/1/0
   - Mars→Earth 7: 4/2/1
   - Venus→Earth 2: 1/1/0
   - Jupiter→Europa 1: 1/0/0
   - Earth→Venus 4: 2/1/1
   - Moon→Mars 6: 3/2/1
   - Mars→Jupiter 2: 1/1/0
   - Europa→Earth 3: 2/1/0
   - Earth→Pluto 1: 1/0/0
2. When generating the 20 random bookings, pick a random `seat_class` and compute `price_paid` with the helper from Sub-Task 1. Seeded bookings already don't adjust seat counts, so keep that behaviour.

**Relevant Context:**
- [`booking_system_backend/seed.py`](booking_system_backend/seed.py:30)

**Implementation Notes for Next Sub-Tasks:**
- [`seed.py`](booking_system_backend/seed.py) now builds each flight with `seats_economy`, `seats_business` and `seats_galaxium`, using the split from the todo list above. Totals per flight match the old `seats_available`.
- Seeded bookings get a random `seat_class` (from `SEAT_CLASSES`) and `price_paid = calculate_class_price(flight.price, seat_class)`. Seat counts are not adjusted for seeded bookings, so a flight's counts can be higher than what the bookings imply (same as before). Seeded cancelled/completed/booked bookings all have a class and price.
- Verified by running `seed()` from a temp copy of the backend `.py` files with the project venv (`booking_system_backend/.venv/bin/python`): 10 flights, 20 bookings, every `price_paid` matches the helper. The system `python3` has no `sqlalchemy`, so use the `.venv` interpreter.
- Sub-Task 3 gotchas: Several seeded flights have 0 seats in Business and/or Galaxium (Earth→Moon, Venus→Earth, Mars→Jupiter, Europa→Earth: Galaxium 0; Jupiter→Europa and Earth→Pluto: Business and Galaxium 0). They are good natural cases for the per-class `NO_SEATS_AVAILABLE` check. `seed.py` is the only non-test place besides `server.py` and `services/` that referenced `seats_available`; it no longer does.
- `seed()` uses `sqlite:///./booking.db` relative to the working directory. An existing `booking_system_backend/booking.db` (gitignored) may have the old schema. `create_all` won't alter existing tables, so delete it before running the server or `seed()` there.

**Status:** `[x] done`

---

## Sub-Task 3 — Booking and flight service logic

**Intent:** Make booking, cancelling and listing class-aware.

**Expected Outcomes:**
- `book_flight` accepts an optional `seat_class` (default `economy`), validates it, checks availability in that class only, decrements that class's count, and stores `seat_class` and `price_paid` on the booking.
- `cancel_booking` restores the seat to the class on the booking.
- `list_flights` returns the per-class breakdown and the total.

**Todo List:**
1. Add an invalid-class error (for example `INVALID_SEAT_CLASS`) using the existing `ErrorResponse` pattern. The details should list the valid classes.
2. Replace the single "no seats" check with a per-class check. Keep the `NO_SEATS_AVAILABLE` error code but mention the class in the message.
3. Keep the existing check order: flight exists, then seats, then user. Add class validation before the flight lookup or right after it.
4. On cancel, increment the booking's class count. This is a flight-missing-safe update, as it is today.
5. Treat bookings without a class as not applicable (the DB is re-seeded, so no legacy rows).

**Relevant Context:**
- [`booking_system_backend/services/booking.py`](booking_system_backend/services/booking.py:7) — `book_flight`, `cancel_booking`
- [`booking_system_backend/services/flight.py`](booking_system_backend/services/flight.py) — `list_flights`

**Implementation Notes for Next Sub-Tasks:**
- `book_flight` signature now includes `seat_class: str = DEFAULT_SEAT_CLASS`. It validates the class against `SEAT_CLASSES` (`INVALID_SEAT_CLASS`), checks availability for that specific class (`NO_SEATS_AVAILABLE`), decrements the corresponding column via `get_seat_column_name`, computes `price_paid = calculate_class_price(flight.price, seat_class)`, and sets `seat_class` and `price_paid` on `Booking`.
- Check order preserved: flight exists -> seat class valid -> class seats available -> user exists & name matches.
- `cancel_booking` restores the seat to the column mapped from `booking.seat_class` via `get_seat_column_name(booking.seat_class)`.
- `flight.py` (`list_flights`) remains untouched. Because `FlightOut` currently expects `seats_available` which is no longer on `Flight`, calling `list_flights` will raise a Pydantic validation error until Sub-Task 4 updates `FlightOut` / schemas.
- Verified with in-memory SQLite database covering invalid seat classes, per-class sold out checks, multi-class bookings with accurate multipliers (Economy 1x, Business 1.5x, Galaxium 2.5x), and seat restoration on cancellation.

**Status:** `[x] done`

---

## Sub-Task 4 — Schemas, REST and MCP surface

**Intent:** Expose the new data and the optional input through every interface.

**Expected Outcomes:**
- `FlightOut` keeps `price` and `seats_available` (total). It adds a list of per-class entries (`seat_class`, `price`, `seats_available`).
- `BookingRequest` accepts an optional `seat_class` (default `economy`).
- `BookingOut` adds `seat_class` and `price_paid`.
- The REST `/book` endpoint and the MCP `book_flight` tool pass `seat_class` through, and their docstrings describe the classes (the docstrings serve as AI-agent documentation).

**Todo List:**
1. Update the Pydantic schemas. `FlightOut` needs a computed total and the per-class list, since `from_attributes` won't derive them automatically from three columns.
2. Update the `/book` endpoint and the MCP `book_flight` tool signature and docstrings.
3. Update `list_flights` and `/flights` docstrings to mention classes.
4. Update the backend README API and MCP tool docs.

**Relevant Context:**
- [`booking_system_backend/schemas.py`](booking_system_backend/schemas.py:5)
- [`booking_system_backend/server.py`](booking_system_backend/server.py:19) — MCP tools at lines 19-97, REST endpoints at lines 139-166
- [`booking_system_backend/README.md`](booking_system_backend/README.md)

**Implementation Notes for Next Sub-Tasks:**
- [`schemas.py`](booking_system_backend/schemas.py): new `SeatClassOut(seat_class, price, seats_available)`. `FlightOut` now has `price` (Economy base), `seats_available` (total) and `seat_classes: list[SeatClassOut]` (always 3 entries, in order economy, business, galaxium). It is built by a `@model_validator(mode="before")` that, when given an object with `seats_economy` (a `Flight` ORM row), computes the total and the list with `calculate_class_price`. So `FlightOut.model_validate(flight_row)` still works. Passing a plain dict or kwargs (no `seats_economy` attribute) skips the validator, so those must include `seats_available` and `seat_classes` explicitly. The field is named `seat_classes` (not `classes`).
- `BookingRequest.seat_class: str = "economy"` (not validated in the schema; the service returns `INVALID_SEAT_CLASS`, so REST returns HTTP 200 with an `ErrorResponse` body, as for other errors). `BookingOut` adds `seat_class: str` and `price_paid: int`, so the `Booking` rows in tests must set both (non-null columns).
- [`server.py`](booking_system_backend/server.py): REST `/book` and MCP `book_flight(user_id, name, flight_id, seat_class="economy")` pass `seat_class` to `booking.book_flight`. The MCP input schema marks only `user_id`, `name`, `flight_id` as required. Docstrings of `list_flights`, `/flights`, `book_flight`, `/book`, `cancel_booking`, `/cancel` describe classes, multipliers and default. [`services/flight.py`](booking_system_backend/services/flight.py) only got a docstring change; `list_flights` code is unchanged.
- Exact response shapes (verified with TestClient on in-memory SQLite, flight price 1,000,000, seats 3/1/0):
  - `GET /flights` item: `{"flight_id":1,"origin":"Earth","destination":"Mars","departure_time":"a","arrival_time":"b","price":1000000,"seats_available":4,"seat_classes":[{"seat_class":"economy","price":1000000,"seats_available":3},{"seat_class":"business","price":1500000,"seats_available":1},{"seat_class":"galaxium","price":2500000,"seats_available":0}]}`
  - `POST /book` success (no seat_class sent): `{"booking_id":1,"user_id":1,"flight_id":1,"status":"booked","booking_time":"...","seat_class":"economy","price_paid":1000000}`; with `"seat_class":"business"`: `seat_class":"business","price_paid":1500000`.
  - `POST /book` sold-out class: `{"success":false,"error":"No seats available","error_code":"NO_SEATS_AVAILABLE","details":"No seats available in galaxium class for this flight. Please check other classes or flights."}`
  - `POST /book` invalid class: `{"success":false,"error":"Invalid seat class","error_code":"INVALID_SEAT_CLASS","details":"Invalid seat class 'x'. Valid seat classes are: economy, business, galaxium."}`
  - `POST /cancel/{id}` and `GET /bookings/{user_id}` return the same `BookingOut` shape (with `seat_class`, `price_paid`); cancelling restores the seat in the booked class.
- Test hints for Sub-Task 5: `conftest.py` fixtures use `Flight(..., seats_economy=, seats_business=, seats_galaxium=)`. For REST tests with in-memory SQLite and `TestClient`, use `StaticPool` with `check_same_thread=False` (a plain in-memory engine fails with a "SQLite objects created in a thread" error in the endpoint threadpool); check how the existing `conftest.py` already handles this. Pass `Booking(..., seat_class=..., price_paid=...)` when constructing bookings directly. The `/flights` total `seats_available` is the sum of the three class columns.
- Importing `server` does not start the app or create `booking.db` (the DB is only touched in the FastAPI lifespan, `init_db()` + `seed()`, and `TestClient` without a `with` block doesn't run the lifespan). `booking_system_backend/README.md` now documents the classes, the `/flights` shape, the optional `seat_class` for REST and MCP, and lists `seat_classes.py` in the project structure. Sub-Task 8 item 2 is therefore already largely done.

**Status:** `[x] done`

---

## Sub-Task 5 — Backend tests

**Intent:** Keep the existing suite green on the new model and cover the new behaviour.

**Expected Outcomes:**
- Existing tests and fixtures build flights with per-class seats instead of `seats_available`.
- New tests cover class pricing, per-class availability, default class, invalid class and cancel restoring the right class.

**Todo List:**
1. Update flight construction in `conftest.py`, `test_services.py` and `test_rest.py`. Assertions on `seats_available == N` become per-class assertions.
2. Add tests: default is Economy; Business and Galaxium prices equal base × multiplier; booking a sold-out class fails while other classes still have seats; invalid class returns the error; cancel restores the booked class; `/flights` returns the breakdown and total.
3. Run `pytest` from `booking_system_backend/` and make sure everything passes.

**Relevant Context:**
- [`booking_system_backend/tests/conftest.py`](booking_system_backend/tests/conftest.py:88)
- [`booking_system_backend/tests/test_services.py`](booking_system_backend/tests/test_services.py)
- [`booking_system_backend/tests/test_rest.py`](booking_system_backend/tests/test_rest.py)

**Implementation Notes for Next Sub-Tasks:**
- Result: `booking_system_backend/.venv/bin/python -m pytest` from `booking_system_backend/` gives **51 passed** (29 existing + 22 new, counting parametrized cases), 0 failures. The only warnings are pre-existing deprecations (`declarative_base`, class-based Pydantic `Config`, `datetime.utcnow()` in `services/booking.py`). No application code was changed, and no bugs were found in Sub-Tasks 1-4.
- [`conftest.py`](booking_system_backend/tests/conftest.py): `sample_flight_data` now uses `seats_economy=3, seats_business=1, seats_galaxium=1` (the fixture is currently unused by any test). The DB/client fixtures needed no changes (`StaticPool` was already used).
- Existing tests: flights are built with per-class seats (3/1/1 where they had 5, 2/1/1 where they had 4, 0/0/0 for the "no seats" test). Direct `Booking(...)` rows now set `seat_class="economy"` and `price_paid=1000000`. Seat assertions after book/cancel check all three class columns.
- New tests: `TestSeatClasses` in [`test_services.py`](booking_system_backend/tests/test_services.py) and `TestSeatClassEndpoints` in [`test_rest.py`](booking_system_backend/tests/test_rest.py). They cover the default class, price = base × multiplier for all 3 classes (parametrized), only the booked class is decremented, a sold-out class fails while the others still book, a class selling out after its last seat, `INVALID_SEAT_CLASS` (state unchanged), cancel restoring the booked class (parametrized in services), the `/flights` and `list_flights` breakdown and total, and `seat_class`/`price_paid` in booking, cancel and `get_bookings` responses.
- Gotcha for later work: the `search_and_replace` tool reported success on some edits to these test files without persisting them. Re-grep after bulk edits.
- Pytest leaves `__pycache__` (gitignored). `booking.db` is untouched by the tests (it already existed, is gitignored, and may have the old schema, so delete it before running the server).

**Status:** `[x] done`

---

## Sub-Task 6 — Frontend types, API client and display

**Intent:** Show class pricing and availability to users.

**Expected Outcomes:**
- TypeScript types match the new API.
- `FlightCard` shows the price and availability of each class. It shows "Sold Out" for the whole flight only when every class is sold out.
- `BookingCard` shows the booked class and the price paid, instead of the flight's base price.

**Todo List:**
1. Update `Flight`, `Booking` and `BookingRequest` types, and add a `SeatClass` type.
2. Update `bookFlight` in the API client to send `seat_class`.
3. Update `FlightCard` for per-class rows, keeping the existing low-seat and sold-out styling.
4. Update `BookingCard` to show the class and `price_paid`.
5. Add a small shared label and formatting helper for class names if more than one component needs it.

**Relevant Context:**
- [`booking_system_frontend/src/types/index.ts`](booking_system_frontend/src/types/index.ts:3)
- [`booking_system_frontend/src/services/api.ts`](booking_system_frontend/src/services/api.ts:77)
- [`booking_system_frontend/src/components/flights/FlightCard.tsx`](booking_system_frontend/src/components/flights/FlightCard.tsx:12)
- [`booking_system_frontend/src/components/bookings/BookingCard.tsx`](booking_system_frontend/src/components/bookings/BookingCard.tsx:94)
- Note: `UserIdentification.tsx` has uncommitted changes in git. It is unrelated to this task, so don't touch it.

**Implementation Notes for Next Sub-Tasks:**
- Types in [`types/index.ts`](booking_system_frontend/src/types/index.ts): `SeatClass = 'economy' | 'business' | 'galaxium'`; `FlightSeatClass { seat_class: SeatClass; price: number; seats_available: number }`; `Flight` now has `seats_available` (total) and `seat_classes: FlightSeatClass[]` (always 3 entries, order economy, business, galaxium; `price` is the Economy price); `Booking` adds `seat_class: SeatClass` and `price_paid: number`; `BookingRequest` adds optional `seat_class?: SeatClass`.
- [`api.ts`](booking_system_frontend/src/services/api.ts): `bookFlight(data: BookingRequest)` already posts `data` as-is, so `seat_class` is sent whenever it is in the request object. Only the doc comment changed. Omitting it makes the backend default to `economy`.
- Shared helper in [`utils/formatters.ts`](booking_system_frontend/src/utils/formatters.ts): `SEAT_CLASS_LABELS: Record<SeatClass, string>` and `formatSeatClass(seatClass: SeatClass): string` (returns "Economy" / "Business" / "Galaxium"). Use `formatCurrency` (existing, USD, no decimals) for prices. For the dropdown option text use e.g. `` `${formatSeatClass(c.seat_class)} — ${formatCurrency(c.price)} (${c.seats_available} left)` ``. The task spec's example "1,500,000" has no `$`; the existing `formatCurrency` adds `$`, which is fine for consistency with the rest of the UI.
- [`FlightCard.tsx`](booking_system_frontend/src/components/flights/FlightCard.tsx): replaced the single price and seats rows with one row per entry in `flight.seat_classes` (class name, seats line, price on the right). Per-class styling: `seats_available <= 2` uses the existing orange low-seat style, `0` shows "Sold Out" with the price dimmed. The Book button and the whole-flight "Sold Out" use `flight.seats_available === 0` (total), so it is disabled only when every class is sold out. The unused `DollarSign` import was removed.
- [`BookingCard.tsx`](booking_system_frontend/src/components/bookings/BookingCard.tsx): the old "Price" (`flight.price`) row is replaced by "Class" (`formatSeatClass(booking.seat_class)`) and "Price Paid" (`formatCurrency(booking.price_paid)`). They are still inside the `flight ?` branch, as the old price row was.
- `BookingModal.tsx` was not changed. It still compiles because `seat_class` is optional, and it still shows `flight.price` (the Economy price) until Sub-Task 7. It sends no `seat_class`, so it books Economy.
- Verification: `npm run build` in `booking_system_frontend/` passes (`tsc -b` + `vite build`). `npm run lint` reports 10 pre-existing problems (9 errors, 1 warning), none introduced by Sub-Task 6: `no-explicit-any` in `BookingModal.tsx:46`, `UserIdentification.tsx:70`, `Flights.tsx:50`, `MyBookings.tsx:41,70`, `api.ts:110` (`isErrorResponse`); `react-refresh/only-export-components` in `hooks/useUser.tsx:50`; unused `error` in the `formatters.ts` catch blocks (lines now 86 and 115, existing code); `exhaustive-deps` warning in `MyBookings.tsx:28`. Sub-Task 7 will add to `BookingModal.tsx`, so avoid adding a new `any` there (line 46 is existing).
- `npm run build` writes `booking_system_frontend/dist/`, which is gitignored. `node_modules/` already existed.

**Status:** `[x] done`

---

## Sub-Task 7 — Class selection in the booking flow

**Intent:** Let the user choose a class and see the right total before confirming.

**Expected Outcomes:**
- `BookingModal` has a seat class **dropdown** (labelled e.g. "Seat Class"). Each option shows the class name, its price and seats left (e.g. "Business — 1,500,000 (2 left)"). Sold-out options are disabled, and the default is the cheapest class with seats.
- The "Total Price" updates with the selected class, and the request sends `seat_class`.
- Booking errors (for example a class sold out meanwhile) still show as toasts, and flights reload after success.

**Todo List:**
1. Add selected-class state to `BookingModal`, initialised when the flight changes.
2. Render the dropdown as a native `<select>` (there is no select component in `components/common/`), styled like the existing input in [`Input.tsx`](booking_system_frontend/src/components/common/Input.tsx) (`bg-white/5 border border-white/10 rounded-lg text-star-white focus:ring-cosmic-purple`). Each `<option>` shows the class name, price and seats left, and is disabled when sold out. Place it between the flight summary and the price block.
3. Send `seat_class` in `bookFlight`, and use the class price for the total.
4. Check that `Flights.tsx` needs no change beyond what `FlightCard` and `BookingModal` require. The page only passes the flight through.
5. Run the frontend build and lint (`npm run build` and the lint script in `booking_system_frontend/`) and fix any type errors. Check manually via `./start.sh`.

**Relevant Context:**
- [`booking_system_frontend/src/components/bookings/BookingModal.tsx`](booking_system_frontend/src/components/bookings/BookingModal.tsx:17)
- [`booking_system_frontend/src/components/common/Input.tsx`](booking_system_frontend/src/components/common/Input.tsx) — styling reference for the dropdown
- [`booking_system_frontend/src/pages/Flights.tsx`](booking_system_frontend/src/pages/Flights.tsx:58)

**Implementation Notes for Next Sub-Tasks:**
- Only [`BookingModal.tsx`](booking_system_frontend/src/components/bookings/BookingModal.tsx) changed. [`Flights.tsx`](booking_system_frontend/src/pages/Flights.tsx) needs no change (it only passes the flight through, and `onSuccess` already reloads flights). `UserIdentification.tsx` was not touched.
- State: `selectedClass: SeatClass` (initial `'economy'`). A `useEffect` on `[flight, isOpen]` sets it to the cheapest class with `seats_available > 0` (by `price`), so it resets on every open or flight change. The hooks (`useState`, `useEffect`) are placed before the existing `if (!flight) return null`. If every class is sold out, the state is left unchanged (the Book button on `FlightCard` is already disabled in that case).
- Dropdown: native `<select id="seat-class">` with a `<label htmlFor>` "Seat Class", between the flight summary and the Passenger Information card. It uses the same classes as `.input-field` (written inline, since `Input.tsx` is input-only) and each `<option>` has `className="bg-space-blue text-star-white"` for readability on the dark theme. Option text: `Business — $1,500,000 (1 left)`, or `Galaxium — $1,250,000 (sold out)` with the option `disabled`. The select is disabled while a booking is in flight.
- Total Price uses `formatCurrency(selectedPrice)`, where `selectedPrice` comes from `flight.seat_classes` (falls back to `flight.price`). `bookFlight` now sends `seat_class: selectedClass`. The error toast path is unchanged.
- Verification: `npm run build` passes. `npm run lint` shows no new problems; the only one in this file is the existing `catch (error: any)` (now line 60). Not done: a manual browser check via `./start.sh`.
- End-to-end (curl, fresh DB, backend `server:app`): `/flights` returns `seat_classes`; `POST /book` with `seat_class: "business"` gives `price_paid` 1500000; repeating it returns `NO_SEATS_AVAILABLE` mentioning business; galaxium on flight 2 (0 seats) returns `NO_SEATS_AVAILABLE`; omitting `seat_class` books economy at 1000000; per-class counts decrement correctly.
- Gotcha: port 8080 was already in use by an older `server.py` process (PID 5782, started before the schema change, returns flights without `seat_classes`). It was left running, so restart the backend before checking manually. For the curl test the app was run via `python -m uvicorn server:app --port 8081`, since the port is hardcoded in `server.py`. The stale `booking.db` was deleted, and the test run's `booking.db` was removed afterwards, so the next server start creates a fresh one.

**Status:** `[x] done`

---

## Sub-Task 8 — Documentation

**Intent:** Keep docs accurate.

**Expected Outcomes:** Root and backend READMEs describe seat classes, multipliers, per-class availability, and the optional `seat_class` parameter.

**Todo List:**
1. Update the domain and features sections of the root `README.md`.
2. Confirm the backend README changes from Sub-Task 4 cover the endpoints and MCP tool.

**Relevant Context:**
- [`README.md`](README.md), [`booking_system_backend/README.md`](booking_system_backend/README.md)

**Implementation Notes:**
- Root [`README.md`](README.md) updated: added seat classes feature bullet, detailed "Seat Classes & Pricing" subsection with multiplier table (Economy 1x base price, Business 1.5x, Galaxium 2.5x), per-class availability per flight, optional `seat_class` parameter (default `economy`) in REST and MCP APIs, and seat class dropdown in booking UI.
- Backend [`booking_system_backend/README.md`](booking_system_backend/README.md) confirmed: endpoints and MCP tools with per-class and optional `seat_class` docs already in place; fixed stray "doc" typo.
- Frontend [`booking_system_frontend/README.md`](booking_system_frontend/README.md) updated: reflected per-class pricing and seat availability in Features, API endpoints, and User Flows.
- Verified all backend pytest tests (51 passed) and frontend build (`npm run build`).

**Status:** `[x] done`
