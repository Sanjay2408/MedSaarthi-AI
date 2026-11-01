"""OCR (step 3): image -> text lines with per-line confidence.

printed:     EasyOCR word boxes grouped into lines; line confidence = mean word confidence.
handwriting: EasyOCR finds line boxes, TrOCR (microsoft/trocr-base-handwritten) reads each
             line crop; confidence = mean token probability from the decoder.
auto:        printed first; if mean confidence < 0.6, also run handwriting and keep the
             result with the higher mean confidence.
Typed text bypasses OCR with confidence 1.0.
"""
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image


@dataclass
class OCRLine:
    text: str
    confidence: float
    bbox: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass
class OCRResult:
    lines: list[OCRLine] = field(default_factory=list)
    engine: str = ""

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def mean_confidence(self) -> float:
        return float(np.mean([l.confidence for l in self.lines])) if self.lines else 0.0


@lru_cache(maxsize=1)
def _easyocr():
    import easyocr

    return easyocr.Reader(["en"], gpu=False, verbose=False)


@lru_cache(maxsize=1)
def _trocr():
    from transformers import TrOCRProcessor, VisionEncoderDecoderModel

    name = "microsoft/trocr-base-handwritten"
    return TrOCRProcessor.from_pretrained(name), VisionEncoderDecoderModel.from_pretrained(name).eval()


def _load(image) -> Image.Image:
    return image.convert("RGB") if isinstance(image, Image.Image) else Image.open(image).convert("RGB")


def _group_lines(dets) -> list[list]:
    """Group EasyOCR word detections into lines by vertical centre."""
    dets = sorted(dets, key=lambda d: (np.mean([p[1] for p in d[0]]), d[0][0][0]))
    def centre(d):
        return float(np.mean([p[1] for p in d[0]]))

    lines, current = [], []
    for d in dets:
        ys = [p[1] for p in d[0]]
        if current and abs(centre(d) - np.mean([centre(c) for c in current])) > max(12, 0.6 * (max(ys) - min(ys))):
            lines.append(current)
            current = []
        current.append(d)
    if current:
        lines.append(current)
    return [sorted(l, key=lambda d: d[0][0][0]) for l in lines]


def _bbox(words) -> tuple[int, int, int, int]:
    xs = [p[0] for w in words for p in w[0]]
    ys = [p[1] for w in words for p in w[0]]
    return int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))


def ocr_printed(image) -> OCRResult:
    img = _load(image)
    dets = _easyocr().readtext(np.array(img), detail=1, paragraph=False)
    lines = []
    for words in _group_lines(dets):
        text = " ".join(w[1] for w in words)
        conf = float(np.mean([w[2] for w in words]))
        lines.append(OCRLine(text, round(conf, 3), _bbox(words)))
    return OCRResult(lines, "easyocr")


def ocr_handwriting(image) -> OCRResult:
    import torch

    img = _load(image)
    processor, model = _trocr()
    boxes = [l.bbox for l in ocr_printed(img).lines]
    lines = []
    for x0, y0, x1, y1 in boxes:
        crop = img.crop((max(0, x0 - 8), max(0, y0 - 6), x1 + 8, y1 + 6))
        pixel_values = processor(images=crop, return_tensors="pt").pixel_values
        with torch.no_grad():
            out = model.generate(pixel_values, max_new_tokens=64, output_scores=True,
                                 return_dict_in_generate=True)
        text = processor.batch_decode(out.sequences, skip_special_tokens=True)[0].strip()
        scores = model.compute_transition_scores(out.sequences, out.scores, normalize_logits=True)
        conf = float(torch.exp(scores).mean()) if scores.numel() else 0.0
        lines.append(OCRLine(text, round(conf, 3), (x0, y0, x1, y1)))
    return OCRResult(lines, "easyocr-detect+trocr")


def ocr_image(image, mode: str = "auto") -> OCRResult:
    if mode == "printed":
        return ocr_printed(image)
    if mode == "handwriting":
        return ocr_handwriting(image)
    printed = ocr_printed(image)
    if printed.mean_confidence >= 0.6:
        return printed
    hand = ocr_handwriting(image)
    return hand if hand.mean_confidence > printed.mean_confidence else printed


def from_typed_text(text: str) -> OCRResult:
    return OCRResult([OCRLine(l, 1.0) for l in text.splitlines() if l.strip()], "typed")
