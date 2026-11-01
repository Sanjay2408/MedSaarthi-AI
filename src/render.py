"""Schedule renderers (step 9): printable PDF (ReportLab) and HTML.

- Icons for morning / afternoon / evening / night drawn as shapes (no emoji fonts needed).
- Large-text and high-contrast modes, 12/24 h time.
- The PDF is English only: ReportLab does not shape Indic scripts correctly (conjuncts
  break), so translated instructions go in the HTML file, which the browser shapes and
  can print to PDF. This limitation is stated in the report.
"""
import html
import io
from dataclasses import dataclass

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from src.config import load_config
from src.schedule import ScheduleEntry, format_time


@dataclass
class Prefs:
    time_format: str = "24h"
    large_text: bool = False
    high_contrast: bool = False


def period(t: str) -> str:
    h = int(t.split(":")[0])
    if 4 <= h < 11:
        return "Morning"
    if 11 <= h < 16:
        return "Afternoon"
    if 16 <= h < 21:
        return "Evening"
    return "Night"


_ICON_COLOUR = {"Morning": "#F2A900", "Afternoon": "#E86A17", "Evening": "#7A5BC7", "Night": "#1F3A93"}


def timeline(entries: list[ScheduleEntry]) -> list[tuple[str, list[ScheduleEntry]]]:
    """Group entries by clock time, sorted through the day."""
    slots: dict[str, list] = {}
    for e in entries:
        for t in e.times:
            slots.setdefault(t, []).append(e)
    return sorted(slots.items())


def _colours(prefs: Prefs):
    if prefs.high_contrast:
        return {"bg": "#000000", "fg": "#FFFFFF", "accent": "#FFD400", "muted": "#FFFFFF", "rule": "#FFFFFF"}
    return {"bg": "#FFFFFF", "fg": "#1A1A1A", "accent": "#0B6E4F", "muted": "#555555", "rule": "#CCCCCC"}


# ---------------------------------------------------------------- PDF

def render_pdf(entries: list[ScheduleEntry], prefs: Prefs, patient: str = "",
               as_needed: list[ScheduleEntry] | None = None) -> bytes:
    c_ = _colours(prefs)
    base = 16 if prefs.large_text else 11
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    font, bold = "Helvetica", "Helvetica-Bold"

    def page_bg():
        pdf.setFillColor(colors.HexColor(c_["bg"]))
        pdf.rect(0, 0, width, height, stroke=0, fill=1)

    page_bg()
    y = height - 20 * mm
    pdf.setFillColor(colors.HexColor(c_["accent"]))
    pdf.setFont(bold, base + 8)
    pdf.drawString(20 * mm, y, "My medicine schedule")
    y -= (base + 8) * 1.4
    pdf.setFillColor(colors.HexColor(c_["fg"]))
    pdf.setFont(font, base)
    if patient:
        pdf.drawString(20 * mm, y, f"For: {patient}")
        y -= base * 1.6

    def need(space):
        nonlocal y
        if y - space < 25 * mm:
            pdf.showPage()
            page_bg()
            y = height - 20 * mm

    for t, items in timeline(entries):
        need(base * 2.2 * (len(items) + 1))
        p = period(t)
        pdf.setFillColor(colors.HexColor(c_["accent"] if prefs.high_contrast else _ICON_COLOUR[p]))
        _icon(pdf, p, 24 * mm, y + base * 0.35, base * 0.8)
        pdf.setFillColor(colors.HexColor(c_["fg"]))
        pdf.setFont(bold, base + 4)
        pdf.drawString(32 * mm, y, f"{format_time(t, prefs.time_format)}   {p}")
        y -= (base + 4) * 1.5
        pdf.setFont(font, base + 2)
        for e in items:
            pdf.rect(32 * mm, y - 1, base, base, stroke=1, fill=0)  # tick box
            pdf.drawString(32 * mm + base * 1.6, y, f"{e.medication}  {e.dose}")
            y -= (base + 2) * 1.6
        pdf.setStrokeColor(colors.HexColor(c_["rule"]))
        pdf.line(20 * mm, y + base * 0.6, width - 20 * mm, y + base * 0.6)
        y -= base * 0.6

    if as_needed:
        need(base * 2.2 * (len(as_needed) + 1))
        pdf.setFont(bold, base + 2)
        pdf.drawString(20 * mm, y, "Only when needed")
        y -= (base + 2) * 1.6
        pdf.setFont(font, base + 1)
        for e in as_needed:
            pdf.drawString(24 * mm, y, f"{e.medication}  {e.dose}")
            y -= (base + 1) * 1.6

    need(base * 4)
    y -= base
    pdf.setFont(bold, base)
    pdf.drawString(20 * mm, y, load_config()["safety"]["disclaimer"])
    y -= base * 1.4
    pdf.setFont(font, base - 2)
    pdf.setFillColor(colors.HexColor(c_["muted"]))
    pdf.drawString(20 * mm, y, "Default times can be moved to fit your day. Ask your pharmacist first.")
    pdf.save()
    return buf.getvalue()


def _icon(pdf, kind: str, x: float, y: float, r: float):
    if kind in ("Morning", "Afternoon"):
        pdf.circle(x, y, r * (0.55 if kind == "Morning" else 0.7), stroke=0, fill=1)
        if kind == "Morning":
            pdf.rect(x - r, y - r * 0.9, 2 * r, r * 0.25, stroke=0, fill=1)  # horizon
    elif kind == "Evening":
        pdf.circle(x, y - r * 0.2, r * 0.6, stroke=0, fill=1)
        pdf.rect(x - r, y - r * 0.9, 2 * r, r * 0.5, stroke=0, fill=1)
    else:  # crescent moon: ring with offset gap
        pdf.circle(x, y, r * 0.65, stroke=0, fill=1)
        pdf.saveState()
        pdf.setFillColor(colors.white)
        pdf.circle(x + r * 0.35, y + r * 0.2, r * 0.55, stroke=0, fill=1)
        pdf.restoreState()


# ---------------------------------------------------------------- HTML

_SVG = {
    "Morning": '<svg viewBox="0 0 24 24" width="1.4em" height="1.4em" aria-hidden="true"><circle cx="12" cy="14" r="5" fill="{c}"/><rect x="2" y="19" width="20" height="2" fill="{c}"/></svg>',
    "Afternoon": '<svg viewBox="0 0 24 24" width="1.4em" height="1.4em" aria-hidden="true"><circle cx="12" cy="12" r="6" fill="{c}"/></svg>',
    "Evening": '<svg viewBox="0 0 24 24" width="1.4em" height="1.4em" aria-hidden="true"><circle cx="12" cy="15" r="6" fill="{c}"/><rect x="2" y="16" width="20" height="6" fill="{bg}"/></svg>',
    "Night": '<svg viewBox="0 0 24 24" width="1.4em" height="1.4em" aria-hidden="true"><path d="M15 3a9 9 0 1 0 6 15A7 7 0 0 1 15 3z" fill="{c}"/></svg>',
}


def render_html(entries: list[ScheduleEntry], prefs: Prefs, patient: str = "",
                explanations: list[tuple[str, str, str | None]] | None = None,
                as_needed: list[ScheduleEntry] | None = None, lang_note: str | None = None) -> str:
    """explanations: (medicine, English text, translated text or None)."""
    c_ = _colours(prefs)
    size = "22px" if prefs.large_text else "16px"
    esc = html.escape
    rows = []
    for t, items in timeline(entries):
        p = period(t)
        icon = _SVG[p].format(c=c_["accent"] if prefs.high_contrast else _ICON_COLOUR[p], bg=c_["bg"])
        meds = "".join(f'<li><span class="box"></span>{esc(e.medication)} &middot; {esc(e.dose)}</li>' for e in items)
        rows.append(f'<section class="slot"><h2>{icon} {esc(format_time(t, prefs.time_format))} '
                    f'<small>{p}</small></h2><ul>{meds}</ul></section>')
    if as_needed:
        meds = "".join(f"<li>{esc(e.medication)} &middot; {esc(e.dose)}</li>" for e in as_needed)
        rows.append(f'<section class="slot"><h2>Only when needed</h2><ul>{meds}</ul></section>')
    expl = ""
    for name, en, tr in explanations or []:
        tr_html = f'<p class="tr">{esc(tr).replace(chr(10), "<br>")}</p>' if tr else ""
        expl += f'<article><h3>{esc(name)}</h3>{tr_html}<p>{esc(en).replace(chr(10), "<br>")}</p></article>'
    note = f'<p class="note">{esc(lang_note)}</p>' if lang_note else ""
    disclaimer = esc(load_config()["safety"]["disclaimer"])
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Medicine schedule</title>
<style>
body{{background:{c_['bg']};color:{c_['fg']};font:{size}/1.5 "Nirmala UI","Noto Sans","Segoe UI",sans-serif;max-width:760px;margin:0 auto;padding:16px}}
h1{{color:{c_['accent']}}} h2{{display:flex;gap:.5em;align-items:center;margin:.4em 0}} small{{color:{c_['muted']};font-weight:normal}}
.slot{{border-bottom:1px solid {c_['rule']};padding:.4em 0}} ul{{list-style:none;padding-left:2em;margin:.2em 0}}
.box{{display:inline-block;width:.9em;height:.9em;border:2px solid {c_['fg']};margin-right:.6em;vertical-align:-.1em}}
article{{border:1px solid {c_['rule']};border-radius:8px;padding:.6em 1em;margin:.8em 0}} .tr{{font-weight:600}}
.note,.disc{{color:{c_['muted']}}} .disc{{font-weight:700;color:{c_['fg']}}}
@media print{{body{{max-width:none}}}}
</style></head><body>
<h1>My medicine schedule</h1>{f'<p>For: {esc(patient)}</p>' if patient else ''}
{''.join(rows)}
{'<h2>How to take your medicines</h2>' + expl if expl else ''}
{note}
<p class="disc">{disclaimer}</p>
<p class="note">Default times can be moved to fit your day. Ask your pharmacist first.</p>
</body></html>"""
