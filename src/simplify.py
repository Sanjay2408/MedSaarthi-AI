"""Plain-language explanation (step 7) with a deterministic validator gate.

V1 baseline, V2 persona + style rules, V3 = V2 + RAG leaflet summary.
Only CLEAR/CONFIRMED items reach this step. If the validator finds any number,
unit or time that is not in the confirmed data, the LLM text is BLOCKED and a
code-generated template (built only from the confirmed fields) is shown instead.
Fixed safety lines are appended by code, never by the LLM (as in Paper B).
"""
import json
import re
from dataclasses import dataclass, field

from src.audit import log_step
from src.config import load_config
from src.llm import LLM
from src.prompts import load_prompt
from src.rag import leaflet_context
from src.schedule import format_time, parse_frequency
from src.schema import ALL_FIELDS, MedicationItem
from src.validator import validate_output

STORAGE_LINE = "Keep this medicine in a cool, dry place, out of the reach of children."
REFILL_LINE = "Before this medicine runs out, visit your health centre for a new prescription."
_LONG_TERM = re.compile(r"continue|ongoing|long[- ]term|till review|until review|lifelong", re.IGNORECASE)

V3_RULE = ("12. LEAFLET NOTES may give one practical how-to-take tip (for example swallow whole). "
           "Never take numbers, doses or times from LEAFLET NOTES.")


@dataclass
class SimplifyResult:
    variant: str
    llm_text: str
    final_text: str  # what the patient sees (LLM text or safe template) + fixed lines
    blocked: bool
    errors: list[str] = field(default_factory=list)
    model_id: str = ""
    prompt_id: str = ""
    latency_s: float = 0.0
    rag_summary: str | None = None


def simplify(item: MedicationItem, times: list[str], variant: str = "v2", patient: str = "",
             time_format: str = "24h", llm: LLM | None = None) -> SimplifyResult:
    if not item.is_usable:
        raise ValueError("item must be CLEAR or CONFIRMED before simplification")
    llm = llm or LLM()
    item_json = json.dumps({f: item.field(f).value for f in ALL_FIELDS}, ensure_ascii=False)
    shown_times = [format_time(t, time_format) for t in times]
    times_txt = ", ".join(shown_times) if shown_times else "only when needed"

    rag_summary = None
    if variant == "v1":
        prompt = load_prompt("simplify_v1")
        system, user = prompt.render(item=item_json, times=times_txt)
    else:
        prompt = load_prompt("simplify_v2")
        extra_rules, context = "", ""
        if variant == "v3":
            rag = leaflet_context(item.name.value, llm)
            rag_summary = rag.summary
            if rag.summary:
                extra_rules, context = V3_RULE, f"LEAFLET NOTES: {rag.summary}"
        system, user = prompt.render(patient=patient or "Patient", item=item_json, times=times_txt,
                                     extra_rules=extra_rules, context=context)

    res = llm.complete(system, user)
    text = res.text.strip()
    check = validate_output(text, item, allowed_times=times, ignore_phrases=[patient])
    body = text if check.passed else safe_template(item, shown_times, patient)
    final = append_fixed_lines(body, item)
    log_step("simplify", llm.model_id, item_json, prompt=prompt.id, variant=variant,
             blocked=not check.passed, n_errors=len(check.errors))
    pid = prompt.id + ("+rag" if variant == "v3" else "")
    return SimplifyResult(variant, text, final, not check.passed, check.errors, llm.model_id, pid,
                          res.latency_s, rag_summary)


def safe_template(item: MedicationItem, times: list[str], patient: str = "") -> str:
    """Deterministic fallback built only from confirmed fields."""
    v = {f: item.field(f).value for f in ALL_FIELDS}
    spec = parse_frequency(v["frequency"])
    when = "only when needed" if spec and spec.as_needed else (
        f"at {', '.join(times)}" if times else f"as written: {v['frequency']}")
    parts = [f"Hello {patient}." if patient else "",
             f"Take {v['name']} {v['dose']} {when}.",
             f"Continue for {v['duration']}." if v["duration"] else "",
             f"Note: {v['instructions']}." if v["instructions"] else "",
             "(The AI explanation did not pass the safety check, so the confirmed prescription is shown as written.)"]
    return " ".join(p for p in parts if p)


def append_fixed_lines(text: str, item: MedicationItem) -> str:
    lines = [text, STORAGE_LINE]
    dur = item.duration.value or ""
    m = re.match(r"\s*(\d+)\s*(day|week|month)", dur, re.IGNORECASE)
    long_course = m and ((m.group(2).lower() == "day" and int(m.group(1)) >= 30) or m.group(2).lower() == "month")
    if _LONG_TERM.search(dur) or long_course:
        lines.append(REFILL_LINE)
    lines.append(load_config()["safety"]["disclaimer"])
    return "\n".join(lines)
