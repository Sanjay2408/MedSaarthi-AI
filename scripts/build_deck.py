"""Build the jury deck (.pptx) with python-pptx. Numbers come from outputs/eval/*.json where they exist.

    python scripts/build_deck.py [--out docs/MedSaarthi_Jury_Deck.pptx]

Palette follows the app: deep teal on a pale sage ground, one amber accent for "needs a check".
Fonts are Cambria for titles and Calibri for text (both ship with Office).
"""
import argparse
import json
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "outputs" / "screens_new"
TEAL, DEEP, SAGE, GROUND, AMBER, INK, MUTED, WHITE = (RGBColor.from_string(c) for c in
                                                       ("0B6B5F", "0A3F38", "D9ECE7", "F1F6F4", "E5A400", "17302B", "4D625C", "FFFFFF"))
W, H = Inches(13.333), Inches(7.5)


def tagger():
    p = ROOT / "outputs" / "eval" / "tagger.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def text(slide, x, y, w, h, s, size=16, bold=False, color=INK, font="Calibri", align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, name=None):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tb.name = name or "text"
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, line in enumerate(s if isinstance(s, list) else [s]):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(6)
        r = p.add_run()
        r.text = line
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, font
        r.font.color.rgb = color
    return tb


def box(slide, x, y, w, h, fill=WHITE, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE, name=None, radius=0.08):
    s = slide.shapes.add_shape(shape, x, y, w, h)
    s.name = name or "box"
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    if line:
        s.line.color.rgb = line
        s.line.width = Pt(1)
    else:
        s.line.fill.background()
    s.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = radius
    return s


def base(prs, title, dark=False):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = DEEP if dark else GROUND
    if title:
        text(s, Inches(0.7), Inches(0.5), Inches(11.9), Inches(0.9), title, 36, True, WHITE if dark else DEEP, "Cambria", name="title")
    return s


def notes(slide, s):
    slide.notes_slide.notes_text_frame.text = s


def stat(slide, x, y, w, big, small, color=TEAL):
    box(slide, x, y, w, Inches(1.9), WHITE, name="stat card")
    text(slide, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5), Inches(0.9), big, 44, True, color, "Cambria", name="stat")
    text(slide, x + Inches(0.25), y + Inches(1.1), w - Inches(0.5), Inches(0.75), small, 14, False, MUTED, name="stat label")


def build(out: Path):
    t = tagger()
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1 title
    s = base(prs, None, dark=True)
    text(s, Inches(0.9), Inches(2.1), Inches(11), Inches(1.3), "MedSaarthi AI", 66, True, WHITE, "Cambria", name="title")
    text(s, Inches(0.9), Inches(3.5), Inches(10.5), Inches(1.2),
         "A guide beside every patient: prescriptions in plain words and in their language, checked by a person before they reach the plan.", 24, False, SAGE)
    text(s, Inches(0.9), Inches(6.2), Inches(11), Inches(0.8),
         ["CS4204 Generative Models and Prompt Engineering  |  B.Sc (Hons) VII Semester  |  RV University", "Team: Sanjay S G, [member 2], [member 3]"], 14, False, SAGE)
    notes(s, "Open with the problem in one sentence, then the rule that runs through the whole project: the language model handles language, code handles anything that must be exact.")

    # 2 problem
    s = base(prs, "Patients misread prescriptions, and models can too")
    stat(s, Inches(0.7), Inches(1.9), Inches(3.7), "22.7%", "of instructions from all three models in a 2026 study could lead to incorrect use (Reis et al., JMIR)")
    stat(s, Inches(4.8), Inches(1.9), Inches(3.7), "4 in 5", "extraction fields right with a one-line prompt; 100% with an engineered prompt on my 25 prescriptions", AMBER)
    stat(s, Inches(8.9), Inches(1.9), Inches(3.7), "0", "wrong items shown as clear after OCR on the same set (a safety gate, not luck)")
    text(s, Inches(0.7), Inches(4.4), Inches(11.9), Inches(2.4),
         ["Handwriting, abbreviations (OD, BD, TDS, 1-0-1), missing doses, and a language the patient reads with difficulty.",
          "In India: many languages, short consultations, and one person managing medicines for a family, in a ward or at home.",
          "Both reference papers conclude that a clinician must confirm the result. So the design makes confirmation a step the software cannot skip."], 18)
    notes(s, "22.7% is from Paper A. The 4-in-5 figure is V1 at 81.7% (147 of 180 fields) against V2 at 100%. All data are synthetic, written by me.")

    # 3 principle
    s = base(prs, "The model writes words; code writes numbers")
    box(s, Inches(0.7), Inches(1.8), Inches(5.8), Inches(4.6), WHITE, name="llm card")
    text(s, Inches(1.0), Inches(2.0), Inches(5.2), Inches(0.5), "The language model", 24, True, TEAL, "Cambria")
    text(s, Inches(1.0), Inches(2.7), Inches(5.2), Inches(3.5),
         ["Reads messy prescription text", "Rewrites in plain words", "Translates free-text notes", "Suggests reasons something is unclear (flags only, never removes one)"], 18)
    box(s, Inches(6.9), Inches(1.8), Inches(5.8), Inches(4.6), TEAL, name="code card")
    text(s, Inches(7.2), Inches(2.0), Inches(5.2), Inches(0.5), "Plain code", 24, True, WHITE, "Cambria")
    text(s, Inches(7.2), Inches(2.7), Inches(5.2), Inches(3.5),
         ["Turns OD / BD / 1-0-1 into clock times", "Writes every dose, time and day count", "Blocks any number that is not in the confirmed data", "Holds missing or low-confidence items for a person"], 18, False, WHITE)
    notes(s, "This is the sentence to remember. Everything that must be exact is deterministic and tested.")

    # 4 pipeline
    s = base(prs, "From photo to plan, with a person in the middle")
    steps = ["Photo or text", "OCR + extraction", "Ground in source", "Safety gate", "Pharmacist or patient confirms", "Schedule by code", "Plan in your language"]
    x0, w, g = 0.7, 1.55, 0.17
    for i, label in enumerate(steps):
        hot = i == 4
        b = box(s, Inches(x0 + i * (w + g)), Inches(2.5), Inches(w), Inches(1.9), AMBER if hot else WHITE, name=f"step {i + 1}")
        text(s, Inches(x0 + i * (w + g) + 0.12), Inches(2.7), Inches(w - 0.24), Inches(1.5), label, 16, True, INK if hot else TEAL, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(0.7), Inches(4.9), Inches(11.9), Inches(1.8),
         ["Anything missing or below 0.80 confidence is held out of the plan until it is confirmed.",
          "Text inside the prescription is data, never instructions; injected lines are not accepted as evidence."], 18)
    notes(s, "Walk the amber step: this is where a pharmacist signs. Their name and time are stored with the item.")

    # 5 structured first
    s = base(prs, "Structured first, language last")
    cd = CategoryChartData()
    cd.categories = ["Template realiser", "gpt-oss-120b (Hindi, Kannada)", "gpt-oss-120b (Tamil, Telugu)"]
    cd.add_series("Seconds", (0.0001, 2, 6.5))
    ch = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.7), Inches(1.7), Inches(6.2), Inches(4.3), cd).chart
    ch.has_legend = False
    ch.plots[0].has_data_labels = True
    ch.plots[0].data_labels.font.size = Pt(14)
    ch.plots[0].data_labels.number_format = '0.0###" s"'
    ch.plots[0].data_labels.number_format_is_linked = False
    ch.plots[0].series[0].format.fill.solid()
    ch.plots[0].series[0].format.fill.fore_color.rgb = TEAL
    ch.category_axis.tick_labels.font.size = Pt(13)
    ch.value_axis.tick_labels.font.size = Pt(12)
    ch.value_axis.has_major_gridlines = False
    ch.has_title = True
    ch.chart_title.text_frame.text = "Seconds to produce the patient wording"
    ch.chart_title.text_frame.paragraphs[0].runs[0].font.size = Pt(16)
    text(s, Inches(7.4), Inches(1.8), Inches(5.3), Inches(4.8),
         ["A JSON language pack holds the sentence frames for each language.",
          "Code writes doses, times and days. The pack loader rejects any string with a digit.",
          "A digit contract checks every card: digits out must equal digits in.",
          "Machine translation is only for free-text notes, through an ordered chain with answer checks.",
          "Packs are drafts until a native speaker signs them, and the app says so."], 17)
    notes(s, "Medians from docs/EVAL.md section 11: one batch of about five sentences for the model, one whole card for the realiser (about 0.1 ms). The models kept every number; their failures were mostly medicine names rewritten in the local script. An earlier translation turned 8 AM and 8 PM into the same word, which is why this exists.")

    # 6 results
    s = base(prs, "Prompt engineering, measured")
    cd = CategoryChartData()
    cd.categories = ["Extraction: field accuracy", "Injection: output unchanged", "Simplification: validator pass"]
    cd.add_series("V1 baseline", (81.7, 0, 12))
    cd.add_series("V2 engineered", (100, 100, 96))
    gf = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(1.7), Inches(7.4), Inches(4.8), cd)
    ch = gf.chart
    ch.has_legend = True
    ch.legend.position = XL_LEGEND_POSITION.BOTTOM
    ch.legend.include_in_layout = False
    ch.legend.font.size = Pt(13)
    for series, color in zip(ch.plots[0].series, (RGBColor.from_string("9AB5AE"), TEAL)):
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = color
    ch.plots[0].has_data_labels = True
    ch.plots[0].data_labels.font.size = Pt(13)
    ch.plots[0].data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    ch.plots[0].data_labels.number_format = '0"%"'
    ch.plots[0].data_labels.number_format_is_linked = False
    ch.value_axis.maximum_scale = 110
    ch.value_axis.has_major_gridlines = False
    ch.value_axis.visible = False
    ch.category_axis.tick_labels.font.size = Pt(13)
    text(s, Inches(8.5), Inches(1.8), Inches(4.2), Inches(4.8),
         ["25 synthetic prescriptions, 30 items, written by me.",
          "V2 = Role-Goal-Constraints, 4 examples, delimiters.",
          "Retrieval over leaflets (V3) did not beat V2 here, as in Paper A.",
          "Evaluation found six bugs in my own code; each was fixed with a test."], 16)
    notes(s, "Numbers are from docs/EVAL.md. Say plainly that the data is small and easy. The injection figure is the share of 7 cases where the raw LLM output was unchanged by the injected instruction.")

    # 7 product
    s = base(prs, "One app for every age, in a hospital or at home")
    # crops of the real screenshots: (file, crop box as fractions of width/height-in-pixels, x, width, caption)
    shots = (("11-phone-plan.png", (0, 0, 1.0, 1.9), 0.7, 2.3, "Phone: your day as tiles"),
             ("13-settings-senior.png", (0, 0, 0.85, 0.70), 3.4, 4.4, "Senior mode: bigger, calmer"),
             ("14-pharmacist-queue.png", (0, 0, 0.95, 0.72), 8.2, 4.4, "Pharmacist queue"))
    tmp = ROOT / "outputs" / "deck_crops"
    tmp.mkdir(parents=True, exist_ok=True)
    for i, (img, (l, t_, r, b), x_in, w_in, cap) in enumerate(shots):
        p = SHOTS / img
        if p.exists():
            im = Image.open(p)
            iw, ih = im.size
            box_px = (int(l * iw), int(t_ * iw), int(r * iw), min(ih, int(b * iw)))  # top and bottom measured against width
            crop_path = tmp / f"crop{i}.png"
            im.crop(box_px).save(crop_path)
            pic = s.shapes.add_picture(str(crop_path), Inches(x_in), Inches(1.55), width=Inches(w_in))
            pic.name = f"screenshot {i + 1}"
        text(s, Inches(x_in), Inches(5.95), Inches(w_in), Inches(0.5), cap, 15, True, TEAL)
    text(s, Inches(0.7), Inches(6.45), Inches(11.9), Inches(0.8),
         "Patient, caregiver (up to 10 profiles) and pharmacist roles. Child, adult and senior registers. 3D pill organizer with a flat fallback. Installable on a phone.", 15, False, MUTED)
    notes(s, "Screenshots are from the automated browser test on synthetic accounts. The 3D organizer is a second view of data the page already shows as text.")

    # 8 trained models
    s = base(prs, "Models trained here: a classical and a neural tagger")
    if t:
        names = ["seen_clean", "unseen_clean", "unseen_noisy", "reference_25"]
        labels = ["New lines, known names", "Unseen medicine names", "Unseen names + OCR noise", "My 25 prescriptions"]
        cd = CategoryChartData()
        cd.categories = labels
        cd.add_series("HMM", [round(100 * t["tests"][n]["hmm"]["micro_f1"], 2) for n in names])
        cd.add_series("BiLSTM", [round(100 * t["tests"][n]["bilstm"]["micro_f1"], 2) for n in names])
        ch = s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(0.7), Inches(1.7), Inches(7.8), Inches(4.8), cd).chart
        ch.has_legend = True
        ch.legend.position = XL_LEGEND_POSITION.BOTTOM
        ch.legend.include_in_layout = False
        ch.legend.font.size = Pt(13)
        for series, color in zip(ch.plots[0].series, (RGBColor.from_string("9AB5AE"), TEAL)):
            series.format.fill.solid()
            series.format.fill.fore_color.rgb = color
        ch.plots[0].has_data_labels = True
        ch.plots[0].data_labels.font.size = Pt(12)
        ch.plots[0].data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
        ch.plots[0].data_labels.number_format = '0.0#"%"'
        ch.plots[0].data_labels.number_format_is_linked = False
        ch.value_axis.minimum_scale = 60
        ch.value_axis.maximum_scale = 105
        ch.value_axis.has_major_gridlines = False
        ch.value_axis.visible = False
        ch.category_axis.tick_labels.font.size = Pt(12)
        note = f"{t['n_train']:,} synthetic training lines; {t['train_names']} medicine names for training, {t['held_out_names']} held out. Field-level micro F1, exact match."
    else:
        note = "Results not yet generated."
    text(s, Inches(8.9), Inches(1.8), Inches(3.8), Inches(4.8),
         [note, "HMM (Module 2): states are labels, Viterbi decoding.", "BiLSTM (Module 3): reads characters, so it copes with OCR slips and unseen names.",
          "Scores on synthetic lines flatter a model. The last group, my 25 hand-written prescriptions, is the honest one, and it is only 30 lines."], 15)
    notes(s, "State the caveat first: this is trained on synthetic lines, not real prescriptions. The unseen-name and noisy sets and the 25 hand-written prescriptions are the fair comparison.")

    # 9 GPU plan
    s = base(prs, "Prepared for a free GPU: LoRA and TrOCR")
    rows = [("T2", "LoRA fine-tune of Qwen2.5-1.5B", "20,000 synthetic prescriptions to JSON; score before and after on 200 held-out names", "Notebook ready, not yet run"),
            ("T3", "TrOCR on handwritten medicine names", "RxHandBD, 5,578 word images; character error rate before and after", "Notebook ready, not yet run")]
    for i, (k, a, b, c) in enumerate(rows):
        y = Inches(1.9 + i * 2.0)
        box(s, Inches(0.7), y, Inches(11.9), Inches(1.7), WHITE, name=f"{k} card")
        text(s, Inches(1.0), y + Inches(0.25), Inches(1.0), Inches(0.8), k, 36, True, TEAL, "Cambria")
        text(s, Inches(2.2), y + Inches(0.2), Inches(6.2), Inches(0.5), a, 20, True, INK)
        text(s, Inches(2.2), y + Inches(0.75), Inches(6.2), Inches(0.9), b, 15, False, MUTED)
        text(s, Inches(9.0), y + Inches(0.55), Inches(3.4), Inches(0.6), c, 16, True, AMBER if "not yet" in c else TEAL, anchor=MSO_ANCHOR.MIDDLE)
    text(s, Inches(0.7), Inches(6.1), Inches(11.9), Inches(0.9),
         "No GPU on this laptop, so these are notebooks for a free Kaggle or Colab T4. The honest claim: fine-tuned on synthetic prescriptions and real handwriting of drug names, never on real prescriptions.", 15, False, MUTED)
    notes(s, "If the notebooks have been run by the time of the jury, replace the amber text with the measured numbers from EVAL.md.")

    # 10 syllabus
    s = base(prs, "Every module of the course shows up in the project")
    mods = [("1", "Foundations", "Discriminative tagger vs generative LLM; probability and temperature"), ("2", "Classical and deep generative", "HMM tagger; why not GAN or VAE"),
            ("3", "Transformers and LLMs", "BiLSTM; gpt-oss, TrOCR, NLLB; LoRA fine-tuning"), ("4", "Prompt engineering", "Persona, RGC, few-shot, chain of thought, injection defence"),
            ("5", "Advanced systems", "RAG, human-in-the-loop instead of an agent, ethics")]
    for i, (n, a, b) in enumerate(mods):
        y = Inches(1.6 + i * 1.05)
        box(s, Inches(0.7), y, Inches(11.9), Inches(0.9), WHITE, name=f"module {n}")
        text(s, Inches(0.95), y + Inches(0.1), Inches(0.7), Inches(0.7), n, 28, True, TEAL, "Cambria", anchor=MSO_ANCHOR.MIDDLE)
        text(s, Inches(1.8), y + Inches(0.1), Inches(3.6), Inches(0.7), a, 18, True, INK, anchor=MSO_ANCHOR.MIDDLE)
        text(s, Inches(5.5), y + Inches(0.1), Inches(7.0), Inches(0.7), b, 15, False, MUTED, anchor=MSO_ANCHOR.MIDDLE)
    notes(s, "Also: 15 lab programs are completed as notebooks with outputs, and the viva bank in docs/VIVA.md maps each module to this project.")

    # 11 ethics
    s = base(prs, "What this is not")
    items = ["Not a medical device, and not tested with patients.", "Synthetic data only; no real prescription was used.",
             "Wording in all ten Indian languages is a draft until a native speaker signs it.", "Photos are never stored; saved plans are encrypted; deleting an account removes everything.",
             "No streaks or points: a missed dose must never feel like a lost game."]
    text(s, Inches(0.7), Inches(1.7), Inches(11.9), Inches(4.8), items, 22)
    notes(s, "Say the limits before the jury asks. They are in the report too.")

    # 12 close
    s = base(prs, None, dark=True)
    text(s, Inches(0.9), Inches(2.4), Inches(11.5), Inches(1.2), "Demo: two screens, six minutes", 48, True, WHITE, "Cambria")
    text(s, Inches(0.9), Inches(3.8), Inches(11.5), Inches(2.0),
         ["A patient on a phone shares an unclear item.", "A pharmacist on the laptop signs it.", "The plan now says who verified it."], 24, False, SAGE)
    text(s, Inches(0.9), Inches(6.4), Inches(11.5), Inches(0.5), "github.com/Sanjay2408/MedSaarthi-AI", 16, False, SAGE)
    notes(s, "Follow the two-screen script in docs/VIVA.md. Fallback: show outputs/eval and docs/EVAL.md.")

    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(out)
    print("wrote", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "MedSaarthi_Jury_Deck.pptx"))
    build(Path(ap.parse_args().out))
