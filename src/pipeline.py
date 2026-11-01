"""End-to-end orchestration used by the Streamlit app and the evaluation.

    input (image or text) -> OCR -> extraction -> ambiguity flags
    -> [human confirms flagged items] -> schedule (code) -> simplify + validator
    -> translate + number check -> render
"""
from dataclasses import dataclass, field

from src.ambiguity import detect
from src.extract import ExtractionResult, extract
from src.llm import LLM
from src.ocr import OCRResult, from_typed_text, ocr_image
from src.schedule import ScheduleEntry, build_schedule, shift_times
from src.simplify import SimplifyResult, simplify
from src.translate import TranslationResult, translate


@dataclass
class Stage1:
    ocr: OCRResult
    extraction: ExtractionResult


@dataclass
class Stage2:
    schedule: list[ScheduleEntry]
    skipped: list
    explanations: list[tuple[str, SimplifyResult, TranslationResult | None]] = field(default_factory=list)


def read_and_extract(image=None, text: str | None = None, ocr_mode: str = "auto", variant: str = "v2",
                     llm: LLM | None = None, patient_alias: str | None = None, use_llm_ambiguity: bool = True) -> Stage1:
    if image is not None:
        ocr, source = ocr_image(image, ocr_mode), "image"
    else:
        ocr, source = from_typed_text(text or ""), "text"
    res = extract(ocr.text, ocr.lines, variant=variant, llm=llm, source=source, patient_alias=patient_alias)
    detect(res.prescription, ocr.text, llm=llm, use_llm=use_llm_ambiguity)
    return Stage1(ocr, res)


def explain(items, variant: str = "v2", lang: str = "en", time_format: str = "24h", shift_minutes: int = 0,
            patient: str = "", llm: LLM | None = None) -> Stage2:
    """Only CLEAR/CONFIRMED items are scheduled and explained (enforced in build_schedule/simplify)."""
    entries, skipped = build_schedule(items)
    for e in entries:
        e.times = shift_times(e.times, shift_minutes)
    out = Stage2(entries, skipped)
    usable = [i for i in items if i.is_usable and i not in skipped]
    for item, entry in zip(usable, entries):
        s = simplify(item, entry.times, variant=variant, patient=patient, time_format=time_format, llm=llm)
        tr = translate(s.final_text, lang) if lang != "en" else None
        out.explanations.append((item.name.value, s, tr))
    return out
