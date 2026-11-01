"""Translation (step 8) with NLLB-200 (CPU) and two automatic checks.

1. Number check: the multiset of digits in the translation (native digits are
   normalised) must equal that of the English source; otherwise the translation
   is blocked and the English text is shown.
2. Back-translation to English and a similarity score (rapidfuzz token_set_ratio)
   as a rough spot check. This is NOT a substitute for a native-speaker review.
"""
import re
from dataclasses import dataclass
from functools import lru_cache

from rapidfuzz import fuzz

from src.audit import log_step
from src.config import load_config

NOTE = "Machine translation. Needs review by a qualified translator before real use."
_DIGIT_MAP = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯௦௧௨௩௪௫௬௭௮௯౦౧౨౩౪౫౬౭౮౯",
                           "0123456789" * 4)
_NUM_RE = re.compile(r"\d+(?:[.:]\d+)?")


@dataclass
class TranslationResult:
    lang: str
    text: str
    back_translation: str
    similarity: float
    numbers_ok: bool
    blocked: bool
    model_id: str


@lru_cache(maxsize=1)
def _model():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    name = load_config()["translation"]["model"]
    return AutoTokenizer.from_pretrained(name), AutoModelForSeq2SeqLM.from_pretrained(name).eval()


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
                             max_new_tokens=256, num_beams=4)
    return tok.batch_decode(out, skip_special_tokens=True)


def numbers(text: str) -> list[str]:
    return sorted(_NUM_RE.findall(text.translate(_DIGIT_MAP)))


def translate(text: str, lang: str) -> TranslationResult:
    model_id = f"hf:{load_config()['translation']['model']}"
    if lang == "en":
        return TranslationResult("en", text, text, 100.0, True, False, model_id)
    sents = split_sentences(text)
    target = translate_sentences(sents, "en", lang)
    back = translate_sentences(target, lang, "en")
    tgt_text, back_text = " ".join(target), " ".join(back)
    nums_ok = numbers(tgt_text) == numbers(text)
    sim = fuzz.token_set_ratio(text.lower(), back_text.lower())
    log_step("translate", model_id, text, lang=lang, numbers_ok=nums_ok, back_similarity=round(sim, 1))
    return TranslationResult(lang, tgt_text, back_text, round(sim, 1), nums_ok, not nums_ok, model_id)
