"""Frequency text -> default dose times, computed in code (never by the LLM).

Reference papers found LLMs unreliable at time arithmetic, so the schedule is
deterministic. Unknown frequencies return None so the caller flags the item.
"""
import re
from dataclasses import dataclass, field

from src.schema import MedicationItem

# Default slots for "N times a day" style frequencies (user can shift them).
_DAILY_SLOTS = {
    1: ["08:00"],
    2: ["08:00", "20:00"],
    3: ["08:00", "14:00", "20:00"],
    4: ["06:00", "12:00", "18:00", "22:00"],
}
_SLOT_TIMES = {"morning": "08:00", "afternoon": "14:00", "night": "20:00"}

_ABBREV_PER_DAY = {
    "od": 1, "qd": 1, "qam": 1, "om": 1,
    "bd": 2, "bid": 2,
    "tds": 3, "tid": 3,
    "qid": 4, "qds": 4,
}
_WORD_PER_DAY = {"once": 1, "twice": 2, "thrice": 3, "one": 1, "two": 2, "three": 3, "four": 4}


@dataclass
class FrequencySpec:
    per_day: int | None = None
    interval_hours: int | None = None
    slots: dict[str, float] = field(default_factory=dict)  # 1-0-1 pattern: slot -> units
    bedtime: bool = False
    as_needed: bool = False


def parse_frequency(text: str | None) -> FrequencySpec | None:
    if not text:
        return None
    t = text.strip().lower()

    if re.search(r"\b(sos|prn)\b|as needed|when needed|if needed", t):
        return FrequencySpec(as_needed=True)

    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?|½)\s*-\s*(\d+(?:\.\d+)?|½)\s*-\s*(\d+(?:\.\d+)?|½)\s*", t)
    if m:
        vals = [0.5 if v == "½" else float(v) for v in m.groups()]
        slots = {s: v for s, v in zip(("morning", "afternoon", "night"), vals) if v > 0}
        return FrequencySpec(slots=slots) if slots else None

    m = re.search(r"(?:every|q)\s*(\d+)\s*(?:h\b|hrs?\b|hours?\b)", t)
    if m:
        hours = int(m.group(1))
        return FrequencySpec(interval_hours=hours) if 0 < hours <= 24 and 24 % hours == 0 else None

    if re.search(r"\bhs\b|at bedtime|at night|before (sleep|bed)", t):
        return FrequencySpec(per_day=1, bedtime=True)

    for abbr, n in _ABBREV_PER_DAY.items():
        if re.search(rf"\b{abbr}\b", t):
            return FrequencySpec(per_day=n)

    m = re.search(r"\b(\d+|once|twice|thrice|one|two|three|four)\s*(?:times?)?\s*(?:a|per|each|every)\s*day\b", t)
    if m:
        word = m.group(1)
        n = int(word) if word.isdigit() else _WORD_PER_DAY[word]
        return FrequencySpec(per_day=n) if n in _DAILY_SLOTS else None
    if re.search(r"\b(once|twice|thrice) daily\b|\bdaily\b", t):
        word = re.search(r"\b(once|twice|thrice)\b", t)
        return FrequencySpec(per_day=_WORD_PER_DAY[word.group(1)] if word else 1)
    return None


def default_times(spec: FrequencySpec, wake: str = "06:00") -> list[str]:
    if spec.as_needed:
        return []
    if spec.slots:
        return [_SLOT_TIMES[s] for s in ("morning", "afternoon", "night") if s in spec.slots]
    if spec.interval_hours:
        start = _to_minutes(wake)
        n = 24 // spec.interval_hours
        return [_from_minutes(start + i * spec.interval_hours * 60) for i in range(n)]
    if spec.bedtime:
        return ["22:00"]
    if spec.per_day in _DAILY_SLOTS:
        return list(_DAILY_SLOTS[spec.per_day])
    return []


def shift_times(times: list[str], minutes: int) -> list[str]:
    return [_from_minutes(_to_minutes(t) + minutes) for t in times]


def format_time(t: str, fmt: str = "24h") -> str:
    if fmt == "24h":
        return t
    h, m = map(int, t.split(":"))
    suffix = "AM" if h < 12 else "PM"
    return f"{(h % 12) or 12}:{m:02d} {suffix}"


@dataclass
class ScheduleEntry:
    medication: str
    dose: str
    times: list[str]
    as_needed: bool = False


def build_schedule(items: list[MedicationItem], wake: str = "06:00") -> tuple[list[ScheduleEntry], list[MedicationItem]]:
    """Return (schedule entries, items that could not be scheduled).

    Items that are not CLEAR/CONFIRMED, or whose frequency is unparseable,
    are returned in the second list and never scheduled.
    """
    entries, skipped = [], []
    for item in items:
        spec = parse_frequency(item.frequency.value) if item.is_usable else None
        if spec is None:
            skipped.append(item)
            continue
        entries.append(ScheduleEntry(
            medication=item.name.value,
            dose=item.dose.value,
            times=default_times(spec, wake),
            as_needed=spec.as_needed,
        ))
    return entries, skipped


def _to_minutes(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _from_minutes(total: int) -> str:
    total %= 24 * 60
    return f"{total // 60:02d}:{total % 60:02d}"
