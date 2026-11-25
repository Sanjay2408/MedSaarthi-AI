"""Machine-translation providers, tried in a configured order.

Used ONLY for text that has no template: an unusual "extra note", or a language with no pack yet.
Doses, times and durations never come through here (see src/lang/realiser.py).

Every provider answer is checked before it is accepted: same number of lines, the right script,
the same numbers, and every drug name still present. A provider that fails a check, times out or
has no key is skipped and the next one is tried; the attempts are returned so the app and the
benchmark can show what happened.

    config.yaml  translation.providers: [sarvam, groq, nllb]

Sarvam's request format is from its public docs (POST /translate, `api-subscription-key` header);
it has NOT been run here because no Sarvam key was available. Bhashini needs an approved key and
a pipeline-config handshake and is not implemented.
"""
import concurrent.futures as cf
import json
import os
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache

from src.config import load_config
from src.lang.digits import numbers
from src.llm import LLM, parse_json

# code -> display name, script, NLLB code, Sarvam code. These are the languages Sarvam's Mayura
# model lists; NLLB covers the same ten.
LANGS = {
    "en": ("English", "Latin", "eng_Latn", "en-IN"),
    "hi": ("Hindi", "Devanagari", "hin_Deva", "hi-IN"),
    "bn": ("Bengali", "Bengali", "ben_Beng", "bn-IN"),
    "gu": ("Gujarati", "Gujarati", "guj_Gujr", "gu-IN"),
    "kn": ("Kannada", "Kannada", "kan_Knda", "kn-IN"),
    "ml": ("Malayalam", "Malayalam", "mal_Mlym", "ml-IN"),
    "mr": ("Marathi", "Devanagari", "mar_Deva", "mr-IN"),
    "od": ("Odia", "Odia", "ory_Orya", "od-IN"),
    "pa": ("Punjabi", "Gurmukhi", "pan_Guru", "pa-IN"),
    "ta": ("Tamil", "Tamil", "tam_Taml", "ta-IN"),
    "te": ("Telugu", "Telugu", "tel_Telu", "te-IN"),
}
_RANGES = {"Devanagari": (0x0900, 0x097F), "Bengali": (0x0980, 0x09FF), "Gurmukhi": (0x0A00, 0x0A7F),
           "Gujarati": (0x0A80, 0x0AFF), "Odia": (0x0B00, 0x0B7F), "Tamil": (0x0B80, 0x0BFF),
           "Telugu": (0x0C00, 0x0C7F), "Kannada": (0x0C80, 0x0CFF), "Malayalam": (0x0D00, 0x0D7F)}


def lang_info(code: str) -> dict:
    if code not in LANGS:
        raise KeyError(f"unsupported language '{code}'")
    name, script, nllb, sarvam = LANGS[code]
    return {"code": code, "name": name, "script": script, "nllb": nllb, "sarvam": sarvam}


def script_ratio(text: str, script: str) -> float:
    """Share of letters written in `script` (Latin drug names are expected, so this is not 1.0)."""
    letters = [c for c in text if c.isalpha()]
    if not letters or script not in _RANGES:
        return 1.0
    lo, hi = _RANGES[script]
    return sum(lo <= ord(c) <= hi for c in letters) / len(letters)


class MTUnavailable(RuntimeError):
    def __init__(self, attempts):
        super().__init__("no translation provider produced a checked answer")
        self.attempts = attempts


@dataclass
class MTResult:
    texts: list[str]
    provider: str
    latency_s: float
    attempts: list[dict] = field(default_factory=list)


def check(sources: list[str], outputs: list[str], lang: str, keep: tuple[str, ...] = ()) -> list[str]:
    """Problems with a provider's answer; an empty list means it can be used."""
    if len(outputs) != len(sources):
        return [f"expected {len(sources)} lines, got {len(outputs)}"]
    script = lang_info(lang)["script"]
    problems = []
    for src, out in zip(sources, outputs):
        if not out or not out.strip():
            problems.append("empty line")
        elif script != "Latin" and any(c.isalpha() for c in src) and script_ratio(out, script) < 0.3:
            problems.append(f"not written in {script}: {out[:30]!r}")
        elif numbers(src) != numbers(out):
            problems.append(f"numbers changed: {numbers(src)} -> {numbers(out)}")
        else:
            lost = [k for k in keep if k.lower() in src.lower() and k.lower() not in out.lower()]
            if lost:
                problems.append(f"drug name lost: {lost}")
    return problems


# ---------------------------------------------------------------- providers

class SarvamMT:
    name = "sarvam"
    URL = "https://api.sarvam.ai/translate"

    def available(self) -> bool:
        return bool(os.getenv("SARVAM_API_KEY"))

    def translate(self, texts: list[str], lang: str, src: str = "en") -> list[str]:
        import httpx

        cfg = load_config()["translation"]
        headers = {"api-subscription-key": os.environ["SARVAM_API_KEY"], "Content-Type": "application/json"}

        def one(text: str) -> str:
            body = {"input": text, "source_language_code": lang_info(src)["sarvam"],
                    "target_language_code": lang_info(lang)["sarvam"], "model": cfg.get("sarvam_model", "sarvam-translate:v1")}
            r = httpx.post(self.URL, headers=headers, json=body, timeout=cfg.get("timeout_s", 20))
            r.raise_for_status()
            return r.json()["translated_text"]

        with cf.ThreadPoolExecutor(max_workers=min(6, len(texts))) as pool:
            return list(pool.map(one, texts))


class GroqMT:
    name = "groq"

    def __init__(self, model: str | None = None):
        self.model = model
        self.last_latency_s = 0.0  # model time only, without rate-limit sleeps (the benchmark reads this)

    def available(self) -> bool:
        return bool(os.getenv("GROQ_API_KEY"))

    def translate(self, texts: list[str], lang: str, src: str = "en") -> list[str]:
        cfg = load_config()["translation"]
        a, b = lang_info(src), lang_info(lang)
        system = (f"You translate short patient medication instructions from {a['name']} into {b['name']} "
                  f"({b['script']} script). Keep every number, time, drug name and unit exactly as written, using "
                  "digits 0-9. Do not add, remove or reword any medical content. Reply with JSON only: "
                  '{"translations": ["...", "..."]} with exactly one translation per input line, in the same order.')
        res = LLM(model=self.model or cfg.get("groq_model"), use_cache=False).complete(
            system, json.dumps({"lines": texts}, ensure_ascii=False), json_mode=True)
        self.last_latency_s = res.latency_s
        data = parse_json(res.text)
        out = data.get("translations") if isinstance(data, dict) else None
        if not isinstance(out, list):
            raise ValueError("model did not return a translations list")
        return [str(x) for x in out]


@lru_cache(maxsize=1)
def _nllb():
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    name = load_config()["translation"]["model"]
    return AutoTokenizer.from_pretrained(name), AutoModelForSeq2SeqLM.from_pretrained(name, use_safetensors=False).eval()


def translate_sentences(sentences: list[str], src: str, tgt: str) -> list[str]:
    """Local NLLB-200 on CPU, either direction (also used for back-translation in the benchmark)."""
    import torch

    if not sentences:
        return []
    tok, model = _nllb()
    tok.src_lang = lang_info(src)["nllb"]
    batch = tok(sentences, return_tensors="pt", padding=True, truncation=True, max_length=256)
    with torch.no_grad():
        out = model.generate(**batch, forced_bos_token_id=tok.convert_tokens_to_ids(lang_info(tgt)["nllb"]),
                             max_new_tokens=256, max_length=None, num_beams=4)
    return tok.batch_decode(out, skip_special_tokens=True)


class NLLBMT:
    name = "nllb"

    def available(self) -> bool:
        return True

    def translate(self, texts: list[str], lang: str, src: str = "en") -> list[str]:
        return translate_sentences(texts, src, lang)


PROVIDERS = {"sarvam": SarvamMT, "groq": GroqMT, "nllb": NLLBMT}


def translate_chain(texts: list[str], lang: str, keep: tuple[str, ...] = (), order: list[str] | None = None) -> MTResult:
    """First provider in `order` whose answer passes `check`. Raises MTUnavailable if none does."""
    if lang == "en":
        return MTResult(list(texts), "none", 0.0)
    order = order or load_config()["translation"].get("providers", ["groq", "nllb"])
    attempts: list[dict] = []
    for key in order:
        provider = PROVIDERS[key]()
        if not provider.available():
            attempts.append({"provider": key, "status": "no key"})
            continue
        start = time.perf_counter()
        try:
            out = provider.translate(texts, lang)
        except Exception as e:  # noqa: BLE001  any network or model failure just moves to the next provider
            attempts.append({"provider": key, "status": f"error: {type(e).__name__}", "seconds": round(time.perf_counter() - start, 2)})
            continue
        took = time.perf_counter() - start
        problems = check(texts, out, lang, keep)
        if problems:
            attempts.append({"provider": key, "status": "failed check", "problems": problems[:3], "seconds": round(took, 2)})
            continue
        attempts.append({"provider": key, "status": "ok", "seconds": round(took, 2)})
        return MTResult(out, key, took, attempts)
    raise MTUnavailable(attempts)
