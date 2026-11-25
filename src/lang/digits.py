"""Digit extraction shared by the realiser, the translation checks and the tests.

Native numerals (Devanagari, Kannada, Tamil, Telugu) are mapped to ASCII, spaced or dotted clock
times ("08: 00", "8.00") are tightened, and whole-hour times reduce to the hour ("08:00" -> "8")
because some translators write "8 o'clock".
"""
import re

DIGIT_MAP = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯০১২৩৪৫৬৭৮৯૦૧૨૩૪૫૬૭૮૯൦൧൨൩൪൫൬൭൮൯",
                           "0123456789" * 7)
_NUM_RE = re.compile(r"\d+(?:[.:]\d+)?")
_CLOCK_RE = re.compile(r"\b(\d{1,2})(?:\s*:\s*|\.)(\d{2})\b")


def numbers(text: str) -> list[str]:
    """Sorted list of the numbers in `text`, comparable across languages."""
    text = text.translate(DIGIT_MAP)
    text = _CLOCK_RE.sub(r"\1:\2", text)  # "08: 00", "8.00" -> "08:00", "8:00"; not "05. 22"
    out = []
    for n in _NUM_RE.findall(text):
        n = re.sub(r":00$", "", n)
        out.append(n.lstrip("0") or "0" if n.isdigit() else n)
    return sorted(out)
