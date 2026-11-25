"""How cases and items are shown to the app (pure functions, no state)."""
from api.state import Case
from src.config import load_config
from src.schedule import plain_frequency
from src.schema import ALL_FIELDS, ReasonCode

REASON_TEXT = {
    ReasonCode.ILLEGIBLE: "I couldn't read part of this clearly.",
    ReasonCode.MISSING_NAME: "I can't find the medicine's name.",
    ReasonCode.MISSING_DOSE: "I can't find how much to take.",
    ReasonCode.MISSING_FREQUENCY: "I can't find how often to take it.",
    ReasonCode.MISSING_DURATION: "I can't find how many days to take it for.",
    ReasonCode.UNKNOWN_ABBREVIATION: "This short form is new to me, so I won't guess what it means.",
    ReasonCode.LOW_OCR_CONFIDENCE: "The photo isn't sharp enough here for me to be sure.",
    ReasonCode.CONFLICTING: "Two parts of the prescription seem to say different things.",
}


def item_json(index: int, item) -> dict:
    return {
        "index": index,
        "status": item.status.value,
        "usable": item.is_usable,
        "reasons": [{"code": r.value, "text": REASON_TEXT[r]} for r in item.reasons],
        "fields": {f: {"value": item.field(f).value, "confidence": item.field(f).confidence} for f in ALL_FIELDS},
        "frequency_plain": plain_frequency(item.frequency.value),
        "verification": item.verification.model_dump() if item.verification else None,
    }


def case_json(case: Case) -> dict:
    s1, ex = case.stage1, case.stage1.extraction
    return {
        "id": case.id,
        "patient": case.patient,
        "source": ex.prescription.source,
        "has_image": case.image is not None,
        "ocr": {"engine": s1.ocr.engine, "mean_confidence": round(s1.ocr.mean_confidence, 3),
                "lines": [{"text": l.text, "confidence": l.confidence} for l in s1.ocr.lines]},
        "injection_hits": ex.injection_hits,
        "model": ex.model_id,
        "prompt": ex.prompt_id,
        "threshold": load_config()["safety"]["confidence_threshold"],
        "items": [item_json(i, it) for i, it in enumerate(ex.prescription.items)],
    }
