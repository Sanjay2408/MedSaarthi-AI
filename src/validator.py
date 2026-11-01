"""Deterministic safety checks. Plain Python, no LLM.

1. gate_item: missing required field or low confidence -> NEEDS_CONFIRMATION.
2. validate_output: every number (and its unit) in generated text must come
   from the confirmed structured data or the code-computed schedule.
3. detect_injection / wrap_untrusted: OCR text is data, never instructions.
"""
import re
from dataclasses import dataclass, field

from src.config import load_config
from src.schedule import default_times, parse_frequency
from src.schema import ALL_FIELDS, REQUIRED_FIELDS, ItemStatus, MedicationItem, ReasonCode

_MISSING_CODE = {
    "name": ReasonCode.MISSING_NAME,
    "dose": ReasonCode.MISSING_DOSE,
    "frequency": ReasonCode.MISSING_FREQUENCY,
    "duration": ReasonCode.MISSING_DURATION,
}


def gate_item(item: MedicationItem, threshold: float | None = None) -> MedicationItem:
    """Set status and reason codes. A human-confirmed item is left alone."""
    if item.status == ItemStatus.CONFIRMED:
        return item
    if threshold is None:
        threshold = load_config()["safety"]["confidence_threshold"]
    reasons = [r for r in item.reasons]
    for name in REQUIRED_FIELDS:
        if item.field(name).missing and _MISSING_CODE[name] not in reasons:
            reasons.append(_MISSING_CODE[name])
    # A dose with no amount ("drop", "tab") is as unusable as a missing dose. Found when
    # OCR dropped the "1" from "1 drop" and the item was otherwise CLEAR.
    if not item.dose.missing and not extract_quantities(str(item.dose.value)) and ReasonCode.MISSING_DOSE not in reasons:
        reasons.append(ReasonCode.MISSING_DOSE)
    for name in ALL_FIELDS:
        f = item.field(name)
        if not f.missing and f.confidence < threshold and ReasonCode.LOW_OCR_CONFIDENCE not in reasons:
            reasons.append(ReasonCode.LOW_OCR_CONFIDENCE)
    item.reasons = reasons
    item.status = ItemStatus.NEEDS_CONFIRMATION if reasons else ItemStatus.CLEAR
    return item


# ---------------------------------------------------------------- numbers

_NUMBER_WORDS = {
    "once": "1", "twice": "2", "thrice": "3",
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11",
    "twelve": "12", "fourteen": "14", "fifteen": "15", "twenty": "20",
    "thirty": "30", "half": "0.5",
}

_UNIT_ALIASES = {
    "mg": "mg", "milligram": "mg", "milligrams": "mg",
    "mcg": "mcg", "µg": "mcg", "microgram": "mcg", "micrograms": "mcg",
    "g": "g", "gm": "g", "gram": "g", "grams": "g",
    "ml": "ml", "millilitre": "ml", "milliliter": "ml", "millilitres": "ml", "milliliters": "ml",
    "iu": "iu", "unit": "unit", "units": "unit",
    "tab": "tablet", "tabs": "tablet", "tablet": "tablet", "tablets": "tablet",
    "cap": "capsule", "caps": "capsule", "capsule": "capsule", "capsules": "capsule",
    "drop": "drop", "drops": "drop", "puff": "puff", "puffs": "puff",
    "day": "day", "days": "day", "week": "week", "weeks": "week",
    "month": "month", "months": "month", "hour": "hour", "hours": "hour", "hrs": "hour", "hr": "hour",
}

_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d(\s?[ap]\.?m\.?)?", re.IGNORECASE)
_QTY_RE = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?)\s*(" + "|".join(sorted(map(re.escape, _UNIT_ALIASES), key=len, reverse=True)) + r")?\b",
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")\b", re.IGNORECASE)


def _normalise_num(n: str) -> str:
    return str(float(n)).rstrip("0").rstrip(".") if "." in n else str(int(n))


def extract_quantities(text: str) -> list[tuple[str, str | None]]:
    """Return (number, unit or None) pairs. Number words become digits; clock times are removed."""
    text = _TIME_RE.sub(" ", text)
    text = _WORD_RE.sub(lambda m: _NUMBER_WORDS[m.group(1).lower()], text)
    out = []
    for num, unit in _QTY_RE.findall(text):
        out.append((_normalise_num(num), _UNIT_ALIASES[unit.lower()] if unit else None))
    return out


def extract_times(text: str) -> list[str]:
    return [m.group(0).strip() for m in _TIME_RE.finditer(text)]


@dataclass
class ValidationResult:
    passed: bool
    errors: list[str] = field(default_factory=list)


def validate_output(text: str, item: MedicationItem, allowed_times: list[str] | None = None,
                    ignore_phrases: list[str] | None = None) -> ValidationResult:
    """Block output whose numbers or units are not in the confirmed item.

    allowed_times are the schedule times computed by src.schedule; any other
    clock time in the text is an error. ignore_phrases (e.g. the patient's
    name) are removed before checking.
    """
    errors: list[str] = []
    for phrase in ignore_phrases or []:
        if phrase:
            text = re.sub(re.escape(phrase), " ", text, flags=re.IGNORECASE)
    source_pairs: set[tuple[str, str | None]] = set()
    for name in ALL_FIELDS:
        f = item.field(name)
        if not f.missing:
            source_pairs.update(extract_quantities(str(f.value)))
    source_units_by_num: dict[str, set] = {}
    for n, u in source_pairs:
        source_units_by_num.setdefault(n, set()).add(u)
    # Numbers implied by the frequency code ("BD" -> "twice", "q8h" -> "8 hours").
    # They may appear bare or as hours only, never as a dose unit.
    derived: dict[str, set] = {}
    spec = parse_frequency(item.frequency.value)
    if spec:
        for n in (spec.per_day, spec.interval_hours, len(default_times(spec)) or None):
            if n:
                derived.setdefault(str(n), set()).update({None, "hour"})

    for num, unit in extract_quantities(text):
        units = source_units_by_num.get(num)
        if units is None and num not in derived:
            errors.append(f"number '{num}{' ' + unit if unit else ''}' not in confirmed data")
            continue
        if not unit:
            continue
        # A unitless number in a source field accepts any unit; derived numbers stay strict.
        if units and (unit in units or None in units):
            continue
        if unit in derived.get(num, set()):
            continue
        expected = sorted(u for u in (units or set()) | derived.get(num, set()) if u)
        errors.append(f"unit mismatch for '{num}': got '{unit}', expected {expected or 'no unit'}")

    allowed = {_canon_time(t) for t in (allowed_times or [])}
    for t in extract_times(text):
        if _canon_time(t) not in allowed:
            errors.append(f"time '{t}' not in computed schedule")

    if not item.dose.missing:
        dose_nums = {n for n, _ in extract_quantities(str(item.dose.value))}
        output_nums = {n for n, _ in extract_quantities(text)}
        if dose_nums and not dose_nums & output_nums:
            errors.append("dose missing from output")
    errors += check_semantics(text, item)
    return ValidationResult(passed=not errors, errors=errors)


_AS_NEEDED_RE = re.compile(r"\b(only\s+)?(when|as|if)\s+(you\s+)?(need|needed|required)\b|\bas[- ]needed\b", re.IGNORECASE)


def check_semantics(text: str, item: MedicationItem) -> list[str]:
    """Wording checks that need no numbers: route words and 'as needed' consistency.

    Added after the evaluation showed outputs that passed the number check but told
    the patient to use an inhaler for eye drops, or to use a QID drug 'only when needed'.
    """
    low = text.lower()
    route = (item.route.value or "").lower()
    instr = (item.instructions.value or "").lower()
    errs = []
    if route != "inhalation" and re.search(r"\binhaler\b|\bbreathe in\b", low):
        errs.append("route: inhaler wording for a non-inhaled medicine")
    if route in ("eye", "inhalation") and re.search(r"\bswallow", low):
        errs.append("route: 'swallow' wording for a non-oral medicine")
    if route != "eye" and re.search(r"\b(in|into)\s+(the|both|your|each)\s+eyes?\b", low) and "eye" not in instr:
        errs.append("route: eye wording for a non-eye medicine")
    spec = parse_frequency(item.frequency.value)
    if spec and not spec.as_needed and _AS_NEEDED_RE.search(low) and not _AS_NEEDED_RE.search(instr):
        errs.append("frequency: says 'as needed' but the prescription has a fixed schedule")
    return errs


def _canon_time(t: str) -> str:
    """'2:00 PM' and '14:00' both become '14:00'."""
    m = re.match(r"(\d{1,2}):(\d{2})\s?([ap])?", t.strip().lower())
    if not m:
        return t
    h, mins, ap = int(m.group(1)), m.group(2), m.group(3)
    if ap == "p" and h != 12:
        h += 12
    if ap == "a" and h == 12:
        h = 0
    return f"{h:02d}:{mins}"


# ---------------------------------------------------------------- injection

_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier)?\s*(instructions|rules|prompts?)",
    r"disregard\s+(all\s+|the\s+)?(previous|prior|above|earlier|system)",
    r"forget\s+(all\s+|your\s+)?(previous|prior|instructions|rules)",
    r"you\s+are\s+now\b",
    r"\bact\s+as\b",
    r"new\s+instructions?\s*:",
    r"system\s*prompt",
    r"<\s*/?\s*(system|assistant|user)\s*>",
    r"^\s*(system|assistant)\s*:",
    r"\b(double|triple|increase|decrease|halve|change|reduce)\s+(the\s+)?(dose|dosage)",
    r"\brecommend\s+(a\s+)?(different|another|stronger)\s+(drug|medicine|medication)",
    r"<<<\s*(END_)?PRESCRIPTION_DATA\s*>>>",
]
_INJECTION_RE = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in _INJECTION_PATTERNS]


def detect_injection(text: str) -> list[str]:
    """Return the matched suspicious substrings (empty list means none found)."""
    hits = []
    for rx in _INJECTION_RE:
        m = rx.search(text)
        if m:
            hits.append(m.group(0).strip())
    return hits


def wrap_untrusted(text: str) -> str:
    """Wrap OCR/user text in data delimiters after removing any forged delimiters."""
    cfg = load_config()["safety"]
    open_d, close_d = cfg["data_delimiter_open"], cfg["data_delimiter_close"]
    cleaned = re.sub(r"<<<\s*(END_)?PRESCRIPTION_DATA\s*>>>", "[removed]", text, flags=re.IGNORECASE)
    return f"{open_d}\n{cleaned}\n{close_d}"
