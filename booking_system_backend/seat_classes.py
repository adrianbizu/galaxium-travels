from typing import Dict, Tuple

SEAT_CLASSES: Tuple[str, ...] = ("economy", "business", "galaxium")
DEFAULT_SEAT_CLASS: str = "economy"

SEAT_CLASS_MULTIPLIERS: Dict[str, float] = {
    "economy": 1.0,
    "business": 1.5,
    "galaxium": 2.5,
}

CLASS_SEAT_COLUMNS: Dict[str, str] = {
    "economy": "seats_economy",
    "business": "seats_business",
    "galaxium": "seats_galaxium",
}


def calculate_class_price(base_price: int, seat_class: str) -> int:
    """Compute the price for a specific seat class based on flight base price."""
    if seat_class not in SEAT_CLASS_MULTIPLIERS:
        raise ValueError(f"Invalid seat class: {seat_class}. Valid classes: {', '.join(SEAT_CLASSES)}")
    return int(round(base_price * SEAT_CLASS_MULTIPLIERS[seat_class]))


def get_seat_column_name(seat_class: str) -> str:
    """Get the Flight model attribute name for the given seat class."""
    if seat_class not in CLASS_SEAT_COLUMNS:
        raise ValueError(f"Invalid seat class: {seat_class}. Valid classes: {', '.join(SEAT_CLASSES)}")
    return CLASS_SEAT_COLUMNS[seat_class]
