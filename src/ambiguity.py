"""Ambiguity detection (step 5): deterministic rules first, LLM Chain of Thought second.

Rules (always applied): missing required field, low confidence, unparseable
frequency (UNKNOWN_ABBREVIATION), non-standard duration, instructions whose
frequency contradicts the frequency field (CONFLICTING).
LLM CoT may ADD reason codes; it can never clear a rule-based flag.
"""
import re

from src.audit import log_step
from src.extract import prescription_json
from src.llm import LLM, parse_json
from src.prompts import load_prompt
from src.schedule import parse_frequency
from src.schema import ItemStatus, Prescription, ReasonCode
from src.validator import gate_item, wrap_untrusted

_DURATION_RE = re.compile(r"^\s*\d+(\.\d+)?\s*(day|days|week|weeks|month|months)\s*$", re.IGNORECASE)
_VALID = {r.value for r in ReasonCode}


def rule_flags(rx: Prescription) -> Prescription:
    for item in rx.items:
        if item.status == ItemStatus.CONFIRMED:
            continue
        gate_item(item)
        reasons = list(item.reasons)
        freq = item.frequency.value
        if freq and parse_frequency(freq) is None:
            reasons.append(ReasonCode.UNKNOWN_ABBREVIATION)
        dur = item.duration.value
        if dur and not _DURATION_RE.match(dur):
            reasons.append(ReasonCode.UNKNOWN_ABBREVIATION)
        spec_f, spec_i = parse_frequency(freq), parse_frequency(item.instructions.value)
        if spec_f and spec_i and _per_day(spec_f) != _per_day(spec_i):
            reasons.append(ReasonCode.CONFLICTING)
        _set(item, reasons)
    return rx


def llm_flags(rx: Prescription, source_text: str, llm: LLM | None = None) -> tuple[Prescription, str]:
    """Run the CoT prompt. Returns (prescription, raw_output). Reasoning text is discarded."""
    if not rx.items:
        return rx, ""
    llm = llm or LLM()
    prompt = load_prompt("ambiguity_cot")
    system, user = prompt.render(prescription=wrap_untrusted(source_text), extraction=prescription_json(rx))
    res = llm.complete(system, user)
    final = res.text.split("FINAL:")[-1]
    verdict = parse_json(final) or {}
    added = 0
    for v in verdict.get("items", []) if isinstance(verdict, dict) else []:
        try:
            idx = int(v.get("index"))
        except (TypeError, ValueError):
            continue
        if not (0 <= idx < len(rx.items)) or rx.items[idx].status == ItemStatus.CONFIRMED:
            continue
        codes = [ReasonCode(c) for c in v.get("reasons", []) if c in _VALID]
        if v.get("ambiguous") and not codes:
            codes = [ReasonCode.ILLEGIBLE]
        item = rx.items[idx]
        before = len(item.reasons)
        _set(item, list(item.reasons) + codes)
        added += len(item.reasons) - before
    log_step("ambiguity_llm", llm.model_id, source_text, prompt=prompt.id, codes_added=added)
    return rx, res.text


def detect(rx: Prescription, source_text: str, llm: LLM | None = None, use_llm: bool = True) -> Prescription:
    rule_flags(rx)
    if use_llm:
        llm_flags(rx, source_text, llm)
    return rx


def _set(item, reasons):
    uniq = []
    for r in reasons:
        if r not in uniq:
            uniq.append(r)
    item.reasons = uniq
    item.status = ItemStatus.NEEDS_CONFIRMATION if uniq else ItemStatus.CLEAR


def _per_day(spec):
    if spec.as_needed:
        return "prn"
    if spec.interval_hours:
        return 24 // spec.interval_hours
    if spec.slots:
        return len(spec.slots)
    return spec.per_day
