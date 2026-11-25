"""Template realiser: a confirmed medication item -> labelled rows in any language with a pack.

Why not translate? Machine translation turned "8:00 AM, 2:00 PM, 8:00 PM" into "8 o'clock, 2
o'clock and 8 o'clock", and the check that was meant to catch that scored it 95/100. Doses, times
and durations are not prose, so code writes them from the structured data with words from a
reviewed pack. This is classical template-based natural language generation (Jurafsky and Martin,
ch. on generation): fixed, inspectable, instant, and offline.

Safety contract, checked on EVERY render (not only in tests): the numbers in the finished rows
must equal the numbers collected from the data, as a multiset. A pack string that smuggles in a
digit, drops a placeholder or garbles an order fails here and the caller falls back.
"""
import re
from collections import Counter
from dataclasses import dataclass, field

from src.lang.digits import numbers
from src.lang.pack import Pack, load_pack
from src.schedule import FrequencySpec, format_time, needs_refill, parse_frequency, period
from src.schema import MedicationItem


class RealiserError(Exception):
    """The item cannot be written safely in this language."""


@dataclass
class Row:
    key: str
    label: str
    text: str


@dataclass
class Rendered:
    lang: str
    reviewed: bool
    greeting: str
    rows: list[Row]
    footer: list[str]
    untranslated: str | None = None  # free text with no template, kept exactly as written
    digits: list[str] = field(default_factory=list)

    def row(self, key: str) -> Row | None:
        return next((r for r in self.rows if r.key == key), None)

    @property
    def when(self) -> str:
        r = self.row("when")
        return f"{r.label}: {r.text}" if r else ""

    @property
    def lines(self) -> list[str]:
        return [self.greeting] + [f"{r.label}: {r.text}" for r in self.rows] + self.footer

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    def as_dict(self) -> dict:
        return {"lang": self.lang, "reviewed": self.reviewed, "greeting": self.greeting,
                "rows": [{"key": r.key, "label": r.label, "text": r.text} for r in self.rows],
                "footer": self.footer, "untranslated": self.untranslated}


_UNIT_WORDS = {"tablet": r"tabs?|tablets?", "capsule": r"caps?|capsules?", "drop": r"drops?", "puff": r"puffs?"}

# (pattern, pack key, capture group holding a number or None). Most specific first: a match is
# blanked out so a later, shorter rule cannot match inside it.
_NOTE_RULES = [
    (r"\b(?:one|1)\s+hour\s+before\s+(?:food|meals?)\b", "hour_before_food", None),
    (r"\bbefore\s+breakfast\b", "before_breakfast", None),
    (r"\bafter\s+(?:food|meals?|eating)\b", "after_food", None),
    (r"\bbefore\s+(?:food|meals?|eating)\b", "before_food", None),
    (r"\bwith\s+(?:food|meals?)\b", "with_food", None),
    (r"\bwith\s+milk\b", "with_milk", None),
    (r"\bwith\s+water\b", "with_water", None),
    (r"\bin\s+(?:the\s+)?morning\b", "in_morning", None),
    (r"\bin\s+(?:both|each)\s+eyes?\b", "both_eyes", None),
    (r"\bin\s+(?:the\s+)?left\s+eye\b", "left_eye", None),
    (r"\bin\s+(?:the\s+)?right\s+eye\b", "right_eye", None),
    (r"\bfor\s+fever\b|\bwhen\s+(?:you\s+have\s+)?(?:a\s+)?fever\b", "for_fever", None),
    (r"\bfor\s+pain\b", "for_pain", None),
    (r"(\d+)\s+puffs?\s+when\s+breathless", "puffs_breathless", 1),
    (r"(\d+)\s+puffs?(?:\s+each\s+time)?", "puffs", 1),
]
_EYE_KEYS = {"both_eyes", "left_eye", "right_eye"}
_FILLER = {"and", "or", "also", "then", "&", "take", "it"}
_DURATION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(day|week|month)s?\s*$", re.IGNORECASE)


def _plural(forms: dict, n: str) -> str:
    return forms["one" if float(n) == 1 else "other"]


def _cap(text: str, pack: Pack) -> str:
    return text[:1].upper() + text[1:] if pack.capitalise and text else text


def _join(items: list[str], and_word: str) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {and_word} " + items[-1]


def _dose(raw: str, pack: Pack) -> str:
    out = raw
    for canon, rx in _UNIT_WORDS.items():
        if canon in pack.units:
            out = re.sub(rf"\b(?:{rx})\b", pack.units[canon], out, flags=re.IGNORECASE)
    return out


def _frequency(raw: str, spec: FrequencySpec, pack: Pack) -> tuple[str, list[str]]:
    f = pack.freq
    if spec.as_needed:
        return f["as_needed"], []
    if spec.slots:
        if any(v != 1.0 for v in spec.slots.values()):
            # 2-0-1 or half-0-half: the quantity differs per time and the app does not model that.
            return f"{raw}. {f['ask_pharmacist']}", numbers(raw)
        names = [f["slots"][s] for s in ("morning", "afternoon", "night") if s in spec.slots]
        return _cap(_join(names, f["and"]), pack), []
    if spec.interval_hours:
        n = str(spec.interval_hours)
        t = _plural(f["every_hours"], n)
        return t.replace("{n}", n), ([n] if "{n}" in t else [])
    if spec.bedtime:
        return f["bedtime"], []
    n = spec.per_day
    key = {1: "once", 2: "twice", 3: "thrice"}.get(n)
    if key:
        return f[key], []
    return f["n_times"].replace("{n}", str(n)), [str(n)]


def _duration(raw: str | None, pack: Pack) -> tuple[str, list[str]] | None:
    m = _DURATION.match(raw or "")
    if not m:
        return None
    n, unit = m.group(1), m.group(2).lower()
    return _plural(pack.duration[unit], n).replace("{n}", n), [n]


def _notes(instructions: str | None, pack: Pack) -> tuple[list[tuple[str, str]], list[str], str]:
    """Matched phrases as (key, text), their digits, and whatever had no template."""
    rest = instructions or ""
    found: list[tuple[int, str, str, list[str]]] = []
    for pattern, key, group in _NOTE_RULES:
        for m in list(re.finditer(pattern, rest, flags=re.IGNORECASE)):
            n = m.group(group) if group else None
            text = pack.notes[key].replace("{n}", n) if n else pack.notes[key]
            found.append((m.start(), key, text, [n] if n else []))
            rest = rest[:m.start()] + " " * (m.end() - m.start()) + rest[m.end():]
    found.sort()
    leftover_words = [w for w in re.split(r"[\s,;.()\-/]+", rest) if w and w.lower() not in _FILLER]
    leftover = " ".join(leftover_words)
    return [(k, t) for _, k, t, _ in found], [d for *_, ds in found for d in ds], leftover


def _times(times: list[str], pack: Pack, time_format: str) -> tuple[str, list[str]]:
    parts, digits = [], []
    for t in times:
        shown = format_time(t, time_format)
        if pack.period_words:
            clock = shown.split(" ")[0]
            parts.append(f"{pack.periods[period(t)]} {clock}")
            digits += numbers(clock)
        else:
            parts.append(shown)
            digits += numbers(shown)
    return pack.joiner.join(parts), digits


def render(item: MedicationItem, times: list[str], lang: str, *, time_format: str = "12h", patient: str = "") -> Rendered:
    """Write one confirmed item as rows. Raises RealiserError rather than risk a wrong number."""
    if not item.is_usable:
        raise RealiserError("only confirmed or clear items can be written")
    pack = load_pack(lang)
    drug, dose_raw = item.name.value, item.dose.value
    if not drug or not dose_raw:
        raise RealiserError("name and dose are required")
    spec = parse_frequency(item.frequency.value)
    if spec is None:
        raise RealiserError("frequency cannot be understood")

    expected: list[str] = numbers(drug) + numbers(dose_raw)
    rows: list[Row] = []
    L = pack.labels

    rows.append(Row("medicine", L["medicine"], f"{drug} {_dose(dose_raw, pack)}"))

    freq_text, digits = _frequency(item.frequency.value, spec, pack)
    expected += digits
    rows.append(Row("how_often", L["how_often"], freq_text))

    if times and not spec.as_needed:
        text, digits = _times(times, pack, time_format)
        expected += digits
        rows.append(Row("when", L["when"], text))

    dur = _duration(item.duration.value, pack)
    if dur:
        rows.append(Row("how_long", L["how_long"], dur[0]))
        expected += dur[1]
    elif item.duration.value:
        rows.append(Row("how_long", L["how_long"], item.duration.value))  # as written
        expected += numbers(item.duration.value)

    phrases, digits, leftover = _notes(item.instructions.value, pack)
    expected += digits
    keys = {k for k, _ in phrases}
    how = []
    route = (item.route.value or "").lower()
    if route in pack.route and not (keys & _EYE_KEYS):
        how.append(pack.route[route])
    how += [t for _, t in phrases]
    if how:
        rows.append(Row("how_to_take", L["how_to_take"], _cap(pack.joiner.join(how), pack)))
    if leftover:
        rows.append(Row("note", L["note"], leftover))
        expected += numbers(leftover)

    footer = [pack.footer["storage"]]
    if needs_refill(item.duration.value):
        footer.append(pack.footer["refill"])
    footer.append(pack.footer["disclaimer"])

    got = Counter(numbers(" ".join(r.text for r in rows)))
    want = Counter(expected)
    if got != want:
        raise RealiserError(f"digit contract failed in '{lang}': rendered {dict(got)}, expected {dict(want)}")

    greeting = pack.greeting["named"].replace("{patient}", patient) if patient else pack.greeting["plain"]
    return Rendered(lang, pack.reviewed, greeting, rows, footer, untranslated=leftover or None, digits=sorted(expected))
