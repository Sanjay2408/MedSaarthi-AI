"""Pydantic v2 data model for prescriptions.

Every extracted field carries its own confidence so the safety gate can flag
individual fields. A missing value is None, never a guessed default.
"""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

REQUIRED_FIELDS = ("name", "dose", "frequency", "duration")
ALL_FIELDS = ("name", "dose", "route", "frequency", "duration", "instructions")


class ItemStatus(str, Enum):
    CLEAR = "CLEAR"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"
    CONFIRMED = "CONFIRMED"  # a human reviewed and accepted or edited the item


class ReasonCode(str, Enum):
    ILLEGIBLE = "ILLEGIBLE"
    MISSING_DOSE = "MISSING_DOSE"
    MISSING_FREQUENCY = "MISSING_FREQUENCY"
    MISSING_DURATION = "MISSING_DURATION"
    MISSING_NAME = "MISSING_NAME"
    UNKNOWN_ABBREVIATION = "UNKNOWN_ABBREVIATION"
    LOW_OCR_CONFIDENCE = "LOW_OCR_CONFIDENCE"
    CONFLICTING = "CONFLICTING"


class FieldValue(BaseModel):
    value: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def missing(self) -> bool:
        return self.value is None or not str(self.value).strip()


class MedicationItem(BaseModel):
    name: FieldValue = Field(default_factory=FieldValue)
    dose: FieldValue = Field(default_factory=FieldValue)
    route: FieldValue = Field(default_factory=FieldValue)
    frequency: FieldValue = Field(default_factory=FieldValue)
    duration: FieldValue = Field(default_factory=FieldValue)
    instructions: FieldValue = Field(default_factory=FieldValue)
    status: ItemStatus = ItemStatus.NEEDS_CONFIRMATION
    reasons: list[ReasonCode] = Field(default_factory=list)

    def field(self, name: str) -> FieldValue:
        return getattr(self, name)

    @property
    def is_usable(self) -> bool:
        """Only usable items may be simplified, translated or scheduled."""
        return self.status in (ItemStatus.CLEAR, ItemStatus.CONFIRMED)


class Prescription(BaseModel):
    patient_alias: Optional[str] = None  # synthetic name only
    source: str = "text"  # "text" | "image"
    items: list[MedicationItem] = Field(default_factory=list)
