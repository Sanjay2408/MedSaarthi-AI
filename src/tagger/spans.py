"""Turning per-character labels into field text, and scoring it. Shared by both models and the
generator so that the gold answer and the prediction are read off the same way."""
from __future__ import annotations

from src.tagger.synth import FIELD_OF, LABELS

FIELDS = list(FIELD_OF.values())  # name, dose, frequency, duration, instructions


def decode(text: str, labels: list[int]) -> dict[str, str]:
    """Group neighbouring non-space characters with one label (spaces between them are kept).
    If a field appears more than once, the longest run wins."""
    out: dict[str, str] = {}
    run_label, start, end = None, 0, 0

    def close():
        if run_label is not None and LABELS[run_label] in FIELD_OF:
            field = FIELD_OF[LABELS[run_label]]
            piece = text[start:end + 1].strip()
            if piece and (field not in out or len(piece) > len(out[field])):
                out[field] = piece

    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        if labels[i] != run_label:
            close()
            run_label, start = labels[i], i
        end = i
    close()
    return out


def norm(s: str | None) -> str:
    return " ".join((s or "").lower().split())


def score(pred: list[dict[str, str]], gold: list[dict[str, str]]) -> dict:
    """Exact-match precision, recall and F1 per field, micro over fields, and whole-line accuracy."""
    stats = {f: [0, 0, 0] for f in FIELDS}  # tp, fp, fn
    exact = 0
    for p, g in zip(pred, gold):
        ok = True
        for f in FIELDS:
            pv, gv = norm(p.get(f)), norm(g.get(f))
            if pv and pv == gv:
                stats[f][0] += 1
            else:
                if pv:
                    stats[f][1] += 1
                if gv:
                    stats[f][2] += 1
            ok &= pv == gv
        exact += ok
    res: dict = {}
    tp = fp = fn = 0
    for f, (a, b, c) in stats.items():
        pr = a / (a + b) if a + b else 1.0
        rc = a / (a + c) if a + c else 1.0
        res[f] = {"precision": round(pr, 4), "recall": round(rc, 4), "f1": round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0}
        tp, fp, fn = tp + a, fp + b, fn + c
    pr, rc = tp / (tp + fp) if tp + fp else 1.0, tp / (tp + fn) if tp + fn else 1.0
    res["micro_f1"] = round(2 * pr * rc / (pr + rc), 4) if pr + rc else 0.0
    res["line_exact"] = round(exact / max(1, len(gold)), 4)
    res["n_lines"] = len(gold)
    return res
