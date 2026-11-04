"""Translation (step 8) with NLLB-200 (CPU) and two automatic checks.

1. Number check: the multiset of digits in the translation (native digits are
   normalised) must equal that of the English source; otherwise the translation
   is blocked and the English text is shown.
2. Back-translation to English and a similarity score (rapidfuzz token_set_ratio)
   as a rough spot check. This is NOT a substitute for a native-speaker review.

Clock times never go through the translator. NLLB turned "8:00 AM, 8:00 PM" into
"8 o'clock, 8 o'clock", which a patient cannot tell apart, and "20:00" into "20 o'clock".
strip_times removes them from the English and when_line writes them in code, each with
its morning / afternoon / evening / night word in the target language.
"""
import re
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from src.audit import log_step
from src.config import load_config
from src.schedule import PERIODS, format_time, period

NOTE = "Machine translation. Needs review by a qualified translator before real use."
_DIGIT_MAP = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯",
                           "0123456789" * 4)
_NUM_RE = re.compile(r"\d+(?:[.:]\d+)?")

# Standard words, written by hand; part of the native-speaker review in docs/EVAL.md.
WHEN_LABEL = {
    "hi": "दवा लेने का समय",
    "kn": "ಔಷಧಿ ತೆಗೆದುಕೊಳ್ಳುವ ಸಮಯ",
    "ta": "மருந்து எடுக்கும் நேரம்",
    "te": "మందు తీసుకునే సమయం",
}
PERIOD_WORDS = {
    "hi": dict(zip(PERIODS, ("सुबह", "दोपहर", "शाम", "रात"))),
    "kn": dict(zip(PERIODS, ("ಬೆಳಿಗ್ಗೆ", "ಮಧ್ಯಾಹ್ನ", "ಸಂಜೆ", "ರಾತ್ರಿ"))),
    "ta": dict(zip(PERIODS, ("காலை", "மதியம்", "மாலை", "இரவு"))),
    "te": dict(zip(PERIODS, ("ఉదయం", "మధ్యాహ్నం", "సాయంత్రం", "రాత్రి"))),
}
_T = r"\d{1,2}:\d{2}(?:\s?[ap]\.?m\b)?"  # not the sentence's full stop after "PM."
_TIME_RE = re.compile(_T, re.IGNORECASE)
_TIME_LIST_RE = re.compile(rf",?\s*\bat\s+{_T}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+){_T})*", re.IGNORECASE)


def strip_times(text: str) -> str:
    """Remove clock times from English text: 'Take X at 08:00 and 20:00.' -> 'Take X.'"""
    text = _TIME_RE.sub("", _TIME_LIST_RE.sub("", text))
    return re.sub(r" +([.,])", r"\1", text).strip()


def when_line(times: list[str], lang: str, time_format: str = "12h") -> str:
    """Code-built dose times, e.g. 'दवा लेने का समय: सुबह 8:00, रात 8:00'."""
    words = PERIOD_WORDS[lang]
    shown = [f"{words[period(t)]} {format_time(t, time_format).split(' ')[0]}" for t in times]
    return f"{WHEN_LABEL[lang]}: {', '.join(shown)}"


@dataclass
class TranslationResult:
    lang: str
    text: str
    back_translation: str
    similarity: float
    numbers_ok: bool
    blocked: bool
    model_id: str
    english_body: str = ""  # the English that was translated (no clock times)
    body: str = ""          # its translation, the part the number check covers
    when: str = ""          # code-built times line


@lru_cache(maxsize=1)
def _model():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    name = load_config()["translation"]["model"]
    return AutoTokenizer.from_pretrained(name), AutoModelForSeq2SeqLM.from_pretrained(name, use_safetensors=False).eval()


def _codes() -> dict:
    return load_config()["translation"]["languages"]


def split_sentences(text: str) -> list[str]:
    parts = []
    for line in text.splitlines():
        parts += [s.strip() for s in re.split(r"(?<=[.!?।])\s+", line) if s.strip()]
    return parts


def translate_sentences(sentences: list[str], src: str, tgt: str) -> list[str]:
    import torch

    if not sentences:
        return []
    tok, model = _model()
    tok.src_lang = _codes()[src]
    batch = tok(sentences, return_tensors="pt", padding=True, truncation=True, max_length=256)
    with torch.no_grad():
        out = model.generate(**batch, forced_bos_token_id=tok.convert_tokens_to_ids(_codes()[tgt]),
                             max_new_tokens=256, max_length=None, num_beams=4)
    return tok.batch_decode(out, skip_special_tokens=True)


def numbers(text: str) -> list[str]:
    """Digits in the text, with native digits mapped to ASCII and whole-hour times
    reduced to the hour ("08:00" -> "8"), since translations often write "8 o'clock"."""
    text = text.translate(_DIGIT_MAP)
    text = re.sub(r"\b(\d{1,2})(?:\s*:\s*|\.)(\d{2})\b", r"\1:\2", text)  # "08: 00", "8.00" -> "08:00", "8:00"; not "05. 22"
    out = []
    for n in _NUM_RE.findall(text):
        n = re.sub(r":00$", "", n)
        out.append(n.lstrip("0") or "0" if n.isdigit() else n)
    return sorted(out)


def translate(text: str, lang: str, times: list[str] | None = None, time_format: str = "12h") -> TranslationResult:
    model_id = f"hf:{load_config()['translation']['model']}"
    if lang == "en":
        return TranslationResult("en", text, text, 100.0, True, False, model_id, text, text)
    lines = [strip_times(line) for line in text.splitlines() if line.strip()]
    english = "\n".join(lines)
    out_lines, back_all = [], []
    for line in lines:
        target = translate_sentences(split_sentences(line), "en", lang)
        back_all += translate_sentences(target, lang, "en")
        out_lines.append(" ".join(target))
    body, back_text = "\n".join(out_lines), " ".join(back_all)
    when = when_line(times, lang, time_format) if times else ""
    shown = "\n".join(out_lines[:1] + ([when] if when else []) + out_lines[1:])
    nums_ok = numbers(body) == numbers(english)
    sim = fuzz.token_set_ratio(english.lower(), back_text.lower())
    log_step("translate", model_id, english, lang=lang, numbers_ok=nums_ok, back_similarity=round(sim, 1))
    return TranslationResult(lang, shown, back_text, round(sim, 1), nums_ok, not nums_ok, model_id, english, body, when)
