"""Language packs: one JSON file per language, validated when loaded.

A pack holds every word the app writes by itself (labels, parts of the day, frequency phrases,
instruction phrases, the safety footer). Adding a language means adding src/lang/packs/<code>.json
and having a native speaker run `python -m src.lang.review <code>`; no code changes.
"""
import json
import string
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

PACK_DIR = Path(__file__).resolve().parent / "packs"
PLURAL = ("one", "other")
ALLOWED = {"n", "patient"}
REQUIRED = {
    "labels": ["medicine", "how_often", "when", "how_long", "how_to_take", "note"],
    "periods": ["Morning", "Afternoon", "Evening", "Night"],
    "freq": ["once", "twice", "thrice", "n_times", "every_hours", "bedtime", "as_needed", "slots", "and", "ask_pharmacist"],
    "route": ["oral", "eye", "inhalation", "topical"],
    "notes": ["after_food", "before_food", "with_food", "before_breakfast", "hour_before_food", "in_morning",
              "both_eyes", "left_eye", "right_eye", "for_fever", "for_pain", "with_milk", "with_water",
              "puffs", "puffs_breathless"],
    "duration": ["day", "week", "month"],
    "footer": ["storage", "refill", "disclaimer"],
    "greeting": ["named", "plain"],
}


class PackError(ValueError):
    pass


@dataclass
class Pack:
    code: str
    name: str
    native: str
    bcp47: str
    script: str
    mt: dict
    review: dict
    labels: dict
    greeting: dict
    periods: dict
    freq: dict
    route: dict
    notes: dict
    units: dict
    duration: dict
    footer: dict
    period_words: bool = True
    capitalise: bool = False
    joiner: str = ", "
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def reviewed(self) -> bool:
        return self.review.get("status") == "reviewed"


def _placeholders(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def _templates(node, path=""):
    """Yield (path, string) for every string in a nested dict."""
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _templates(v, f"{path}.{k}" if path else k)


def validate(data: dict) -> None:
    code = data.get("code", "?")
    for section, keys in REQUIRED.items():
        if section not in data:
            raise PackError(f"{code}: missing section '{section}'")
        for key in keys:
            if key not in data[section]:
                raise PackError(f"{code}: missing '{section}.{key}'")
    for unit, forms in data["duration"].items():
        if set(forms) != set(PLURAL):
            raise PackError(f"{code}: duration.{unit} needs {PLURAL}")
    for key, forms in data["freq"]["every_hours"].items() if isinstance(data["freq"]["every_hours"], dict) else []:
        if key not in PLURAL:
            raise PackError(f"{code}: freq.every_hours has unexpected form '{key}'")
    for path, text in _templates({k: data[k] for k in REQUIRED}):
        if not text.strip():
            raise PackError(f"{code}: '{path}' is empty")
        bad = _placeholders(text) - ALLOWED
        if bad:
            raise PackError(f"{code}: '{path}' uses unknown placeholder(s) {sorted(bad)}")
        if any(c.isdigit() for c in text):
            raise PackError(f"{code}: '{path}' contains a digit; numbers must come from the data, never the pack")
    if data["review"].get("status") not in ("draft", "reviewed"):
        raise PackError(f"{code}: review.status must be 'draft' or 'reviewed'")
    if data["review"]["status"] == "reviewed" and not data["review"].get("by"):
        raise PackError(f"{code}: a reviewed pack must name its reviewer")


@lru_cache(maxsize=None)
def load_pack(code: str) -> Pack:
    path = PACK_DIR / f"{code}.json"
    if not path.exists():
        raise PackError(f"no language pack for '{code}'")
    data = json.loads(path.read_text(encoding="utf-8"))
    validate(data)
    return Pack(
        code=data["code"], name=data["name"], native=data["native"], bcp47=data["bcp47"], script=data["script"],
        mt=data.get("mt", {}), review=data["review"], labels=data["labels"], greeting=data["greeting"],
        periods=data["periods"], freq=data["freq"], route=data["route"], notes=data["notes"],
        units=data.get("units", {}), duration=data["duration"], footer=data["footer"],
        period_words=data.get("period_words", True), capitalise=data.get("capitalise", False),
        joiner=data.get("joiner", ", "), raw=data)


def has_pack(code: str) -> bool:
    return (PACK_DIR / f"{code}.json").exists()


def available() -> list[dict]:
    """Every pack, with whether a native speaker has signed it off."""
    out = []
    for path in sorted(PACK_DIR.glob("*.json")):
        p = load_pack(path.stem)
        out.append({"code": p.code, "name": p.name, "native": p.native, "bcp47": p.bcp47,
                    "reviewed": p.reviewed, "reviewer": p.review.get("by")})
    return out


def reload() -> None:
    load_pack.cache_clear()
