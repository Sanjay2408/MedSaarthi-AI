"""End-to-end orchestration used by the web API and the evaluation.

    input (image or text) -> OCR -> extraction -> ambiguity flags
    -> [a person confirms flagged items] -> schedule (code) -> simplify + validator (English, LLM)
    -> card in the chosen language (language pack, code) -> render
"""
from dataclasses import dataclass, field

from src.ambiguity import detect
from src.extract import ExtractionResult, extract
from src.lang import RealiserError, Rendered, has_pack, render
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
class Explanation:
    """Everything shown for one medicine.

    simplify  the English sentences written by the LLM and checked by the validator
    card_en   the same facts as labelled rows, built by code from the confirmed fields
    local     the card in the chosen language, from a language pack (no translator involved)
    mt        machine translation, only when the language has no pack or the card could not be built
    """
    name: str
    simplify: SimplifyResult
    card_en: Rendered | None = None
    local: Rendered | None = None
    mt: TranslationResult | None = None

    @property
    def translated_text(self) -> str | None:
        if self.local:
            return self.local.text
        return self.mt.text if self.mt and not self.mt.blocked else None


@dataclass
class Stage2:
    schedule: list[ScheduleEntry]
    skipped: list
    explanations: list[Explanation] = field(default_factory=list)


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
        card_en = _card(item, entry.times, "en", time_format, patient)
        local = mt = None
        if lang != "en":
            # Safety-critical content comes from the pack, never from a translator. Machine
            # translation is the fallback for a language with no pack, or a card that failed its check.
            local = _card(item, entry.times, lang, time_format, patient) if has_pack(lang) else None
            if local is None:
                mt = translate(s.final_text, lang, entry.times, time_format, keep=(item.name.value,))
        out.explanations.append(Explanation(item.name.value, s, card_en, local, mt))
    return out


def _card(item, times, lang, time_format, patient) -> Rendered | None:
    try:
        return render(item, times, lang, time_format=time_format, patient=patient)
    except RealiserError:
        return None
