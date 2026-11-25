"""The confirmation rule, shared by the patient's "my pharmacist confirmed this" and a
pharmacist's signed review. Neither can confirm an item with a gap, and neither can invent a dose."""
from datetime import datetime, timezone

from src.schedule import parse_frequency
from src.schema import ALL_FIELDS, REQUIRED_FIELDS, FieldValue, ItemStatus, MedicationItem, Verification
from src.validator import extract_quantities


class ConfirmationError(Exception):
    def __init__(self, detail: str, missing: list[str]):
        super().__init__(detail)
        self.detail, self.missing = detail, missing


def clean_confirmation(fields: dict) -> dict:
    """Normalise what a person typed and refuse an item that is still incomplete."""
    values = {f: (fields.get(f) or "").strip() or None for f in ALL_FIELDS}
    missing = [f for f in REQUIRED_FIELDS if not values[f]]
    if values["dose"] and not extract_quantities(values["dose"]):
        missing.append("dose amount")
    if missing:
        raise ConfirmationError("Still needed: " + ", ".join(missing) + ". Please ask your pharmacist rather than guessing.", missing)
    if parse_frequency(values["frequency"]) is None:
        raise ConfirmationError("I can't turn this into dose times. Write it the way your pharmacist "
                                "says it, like twice a day, 1-0-1 or every 8 hours.", ["frequency"])
    return values


def apply_confirmation(item: MedicationItem, values: dict, verification: Verification) -> None:
    for f in ALL_FIELDS:
        setattr(item, f, FieldValue(value=values[f], confidence=1.0))
    item.reasons = []
    item.status = ItemStatus.CONFIRMED
    item.verification = verification


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
