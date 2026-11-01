"""Structured extraction: prescription text -> Prescription (step 4).

V1 = one-line zero-shot prompt (baseline). V2 = RGC + few-shot + delimiters.
After the LLM, deterministic code:
  - repairs/validates JSON against the Pydantic schema (one LLM retry if unparseable)
  - grounds each field in the source text: a value that cannot be found in the
    OCR/typed text gets low confidence, so hallucinated values are flagged
  - applies the safety gate (src.validator.gate_item)
"""
import json
import time
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from src.audit import log_step
from src.llm import LLM, parse_json
from src.prompts import load_prompt
from src.schema import ALL_FIELDS, FieldValue, MedicationItem, Prescription
from src.validator import detect_injection, gate_item, wrap_untrusted

GROUNDING_MIN = 85  # partial_ratio needed to count a value as present in the source


@dataclass
class OCRLineLike:
    text: str
    confidence: float


@dataclass
class ExtractionResult:
    prescription: Prescription
    raw_output: str
    parsed_ok: bool
    repaired: bool
    injection_hits: list[str]
    model_id: str
    prompt_id: str
    latency_s: float
    ungrounded: list[str] = field(default_factory=list)


def extract(text: str, ocr_lines: list | None = None, variant: str = "v2", llm: LLM | None = None,
            source: str = "text", patient_alias: str | None = None) -> ExtractionResult:
    llm = llm or LLM()
    prompt = load_prompt(f"extract_{variant}")
    payload = wrap_untrusted(text) if variant != "v1" else text
    system, user = prompt.render(prescription=payload)
    start = time.perf_counter()
    res = llm.complete(system, user, json_mode=True)
    data = parse_json(res.text)
    repaired = False
    if not _valid_shape(data):
        repaired = True
        res2 = llm.complete(system, user + "\n\nReturn valid JSON only: {\"medications\": [...]}", json_mode=True)
        data = parse_json(res2.text)
    latency = res.latency_s if not repaired else time.perf_counter() - start

    lines = ocr_lines or [OCRLineLike(line, 1.0) for line in text.splitlines() if line.strip()]
    items, ungrounded = [], []
    for med in (data or {}).get("medications", []) if _valid_shape(data) else []:
        item, missing = _to_item(med, lines)
        ungrounded += missing
        items.append(gate_item(item))
    rx = Prescription(patient_alias=patient_alias, source=source, items=items)
    hits = detect_injection(text)
    log_step("extract", llm.model_id, text, prompt=prompt.id, n_items=len(items),
             parsed_ok=_valid_shape(data), repaired=repaired, injection_hits=len(hits))
    return ExtractionResult(rx, res.text, _valid_shape(data), repaired, hits, llm.model_id,
                            prompt.id, latency, ungrounded)


def _valid_shape(data) -> bool:
    return isinstance(data, dict) and isinstance(data.get("medications"), list)


def _clean(v):
    if v is None:
        return None
    v = str(v).strip()
    return None if v.lower() in ("", "null", "none", "n/a", "unknown") else v


def _to_item(med: dict, lines: list) -> tuple[MedicationItem, list[str]]:
    """Attach a confidence to every field from the source line it was found in."""
    values = {f: _clean(med.get(f)) if isinstance(med, dict) else None for f in ALL_FIELDS}
    name_conf = 1.0
    fields, ungrounded = {}, []
    for f in ALL_FIELDS:
        v = values[f]
        if v is None:
            fields[f] = FieldValue(value=None, confidence=1.0)
            continue
        if f == "route":  # route is derived from the dosage form, not copied
            continue
        score, conf = _best_line(v, lines)
        if score < GROUNDING_MIN:
            ungrounded.append(f"{f}={v}")
            conf = min(conf, 0.5)
        fields[f] = FieldValue(value=v, confidence=round(conf, 3))
        if f == "name":
            name_conf = conf
    fields["route"] = FieldValue(value=values["route"], confidence=round(name_conf, 3))
    return MedicationItem(**fields), ungrounded


def _best_line(value: str, lines: list) -> tuple[float, float]:
    best_score, best_conf = 0.0, 0.0
    for line in lines:
        s = fuzz.partial_ratio(value.lower(), line.text.lower())
        if s > best_score or (s == best_score and line.confidence > best_conf):
            best_score, best_conf = s, line.confidence
    return best_score, best_conf


def prescription_json(rx: Prescription) -> str:
    return json.dumps([{f: it.field(f).value for f in ALL_FIELDS} for it in rx.items], ensure_ascii=False)
