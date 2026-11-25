"""Free-text translation with checks, for text that has no template.

The safety-critical content of a plan (dose, frequency, times, duration) is written by
src/lang/realiser.py, not translated. This module handles what is left: an unusual extra note,
or a language that has no pack yet. It strips clock times first (a translator once turned
"8:00 AM, 8:00 PM" into "8 o'clock, 8 o'clock"), runs the ordered provider chain in src/mt.py,
and re-checks the numbers. Machine output is always labelled as machine output.
"""
import re
from dataclasses import dataclass, field

from src.audit import log_step
from src.lang.digits import numbers  # noqa: F401  re-exported: tests and callers import it from here
from src.lang.pack import has_pack, load_pack
from src.mt import MTUnavailable, translate_chain, translate_sentences  # noqa: F401
from src.schedule import PERIODS, format_time, period

NOTE = "Machine translation. Needs review by a qualified translator before real use."
_T = r"\d{1,2}:\d{2}(?:\s?[ap]\.?m\b)?"  # not the sentence's full stop after "PM."
_TIME_RE = re.compile(_T, re.IGNORECASE)
_TIME_LIST_RE = re.compile(rf",?\s*\bat\s+{_T}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+){_T})*", re.IGNORECASE)


def strip_times(text: str) -> str:
    """Remove clock times from English text: 'Take X at 08:00 and 20:00.' -> 'Take X.'"""
    text = _TIME_RE.sub("", _TIME_LIST_RE.sub("", text))
    return re.sub(r" +([.,])", r"\1", text).strip()


def when_line(times: list[str], lang: str, time_format: str = "12h") -> str:
    """Code-built dose times with the part of the day in words, from the language pack."""
    pack = load_pack(lang if has_pack(lang) else "en")
    use_words = pack.period_words or not has_pack(lang)
    parts = []
    for t in times:
        clock = format_time(t, time_format)
        if use_words:
            words = pack.periods[period(t)] if pack.period_words else period(t)
            parts.append(f"{words} {clock.split(' ')[0]}")
        else:
            parts.append(clock)
    return f"{pack.labels['when']}: {pack.joiner.join(parts)}"


@dataclass
class TranslationResult:
    lang: str
    text: str
    numbers_ok: bool
    blocked: bool
    model_id: str
    english_body: str = ""      # the English that was translated (no clock times)
    body: str = ""              # its translation, the part the number check covers
    when: str = ""              # code-built times line
    provider: str = ""
    latency_s: float = 0.0
    attempts: list[dict] = field(default_factory=list)


def translate(text: str, lang: str, times: list[str] | None = None, time_format: str = "12h",
              keep: tuple[str, ...] = (), order: list[str] | None = None) -> TranslationResult:
    if lang == "en":
        return TranslationResult("en", text, True, False, "none", text, text, provider="none")
    lines = [strip_times(line) for line in text.splitlines() if line.strip()]
    english = "\n".join(lines)
    when = when_line(times, lang, time_format) if times else ""
    try:
        res = translate_chain(lines, lang, keep=keep, order=order)
    except MTUnavailable as e:
        log_step("translate", None, english, lang=lang, provider="none", blocked=True)
        return TranslationResult(lang, english, False, True, "none", english, "", when, "none", 0.0, e.attempts)
    body = "\n".join(res.texts)
    shown = "\n".join(res.texts[:1] + ([when] if when else []) + res.texts[1:])
    ok = numbers(body) == numbers(english)
    log_step("translate", res.provider, english, lang=lang, provider=res.provider, seconds=round(res.latency_s, 2), numbers_ok=ok)
    return TranslationResult(lang, shown, ok, not ok, res.provider, english, body, when, res.provider, res.latency_s, res.attempts)
