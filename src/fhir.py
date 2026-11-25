"""Export a plan as a FHIR R4 Bundle of MedicationRequest resources, the format hospital systems
and India's national health-record scheme (ABDM) build on.

HONEST LIMITS: this is the FHIR R4 shape, not a validated ABDM profile. Medicines carry text only
(no RxNorm, SNOMED or Indian drug codes) because the app does not identify drugs, it reads names.
Status is "active" only for an item a signed-in pharmacist verified; everything else is "draft", so a
receiving system never mistakes a patient's own transcription for a clinical order.
"""
from datetime import datetime, timezone

from src.ics import course_days
from src.schedule import parse_frequency
from src.schema import MedicationItem
from src.validator import extract_quantities

UCUM = {"mg": "mg", "g": "g", "mcg": "ug", "ml": "mL", "iu": "[IU]", "unit": "[U]"}
_TIMING_CODE = {"morning": "MORN", "afternoon": "AFT", "night": "NIGHT"}


def dose_quantity(dose: str | None) -> dict | None:
    for num, unit in extract_quantities(dose or ""):
        if unit in UCUM:
            return {"value": float(num), "unit": unit, "system": "http://unitsofmeasure.org", "code": UCUM[unit]}
        if unit in ("tablet", "capsule", "drop", "puff"):
            return {"value": float(num), "unit": unit}
    return None


def timing(frequency: str | None) -> dict:
    spec = parse_frequency(frequency)
    if spec is None:
        return {}
    if spec.as_needed:
        return {"asNeededBoolean": True}
    if spec.interval_hours:
        return {"timing": {"repeat": {"frequency": 1, "period": spec.interval_hours, "periodUnit": "h"}}}
    if spec.slots:
        return {"timing": {"repeat": {"frequency": len(spec.slots), "period": 1, "periodUnit": "d",
                                      "when": [_TIMING_CODE[s] for s in ("morning", "afternoon", "night") if s in spec.slots]}}}
    if spec.bedtime:
        return {"timing": {"repeat": {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["HS"]}}}
    return {"timing": {"repeat": {"frequency": spec.per_day, "period": 1, "periodUnit": "d"}}}


def medication_request(item: MedicationItem, index: int, patient: str, now: datetime) -> dict:
    v = item.verification
    verified = bool(v and v.kind == "pharmacist")
    instruction = {"text": " | ".join(x for x in (item.dose.value, item.frequency.value, item.duration.value, item.instructions.value) if x),
                   **timing(item.frequency.value)}
    if item.route.value:
        instruction["route"] = {"text": item.route.value}
    q = dose_quantity(item.dose.value)
    if q:
        instruction["doseAndRate"] = [{"doseQuantity": q}]
    note = "Transcribed from a prescription by MedSaarthi AI (student prototype, not a medical device). "
    note += (f"Verified by pharmacist {v.by} at {v.at}." if verified else
             "Checked by the patient only; NOT verified by a pharmacist.")
    res = {"resourceType": "MedicationRequest", "id": f"medsaarthi-{index + 1}", "status": "active" if verified else "draft",
           "intent": "plan", "medicationCodeableConcept": {"text": item.name.value},
           "subject": {"display": patient or "Patient"}, "authoredOn": now.date().isoformat(),
           "dosageInstruction": [instruction], "note": [{"text": note}]}
    days = course_days(item.duration.value)
    if days:
        res["dispenseRequest"] = {"expectedSupplyDuration": {"value": days, "unit": "days", "system": "http://unitsofmeasure.org", "code": "d"}}
    return res


def bundle(items: list[MedicationItem], patient: str = "", now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    usable = [(i, it) for i, it in enumerate(items) if it.is_usable]
    return {"resourceType": "Bundle", "type": "collection", "timestamp": now.isoformat(timespec="seconds"),
            "entry": [{"resource": medication_request(it, i, patient, now)} for i, it in usable]}
