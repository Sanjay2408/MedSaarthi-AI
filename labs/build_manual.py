"""Assemble the lab manual (.docx) from the executed notebooks lab01..lab15.

    python labs/build_manual.py --name "Student Name" --usn "RVU..." [--out docs/MedSaarthi_Lab_Manual.docx]

For each program: aim, theory, code, output (text and figures) and observations, exactly as the
notebook produced them. Notebooks are never edited here, so the manual cannot disagree with them.
"""
import argparse
import base64
import io
import re
from pathlib import Path

import docx
import nbformat
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NOISE = re.compile(r"downloaded|it/s\]|\bwarn", re.I)


def clean(text: str, limit: int = 2600) -> str:
    lines = [l for l in text.replace("\r", "\n").splitlines() if l.strip() and not NOISE.search(l)]
    out = "\n".join(lines)
    return out if len(out) <= limit else out[:limit] + "\n... (output shortened; the notebook has the full text)"


def code_par(d, src: str, size=8.5):
    p = d.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.15)
    p.paragraph_format.space_after = Pt(6)
    r = p.add_run(src)
    r.font.name, r.font.size = "Consolas", Pt(size)
    r.font.color.rgb = RGBColor(0x17, 0x30, 0x2B)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--usn", required=True)
    ap.add_argument("--out", default=str(ROOT / "docs" / "MedSaarthi_Lab_Manual.docx"))
    a = ap.parse_args()

    d = docx.Document()
    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(11)
    for s in d.sections:
        s.left_margin = s.right_margin = Inches(0.9)
    t = d.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = t.add_run("CS4204 Generative Models and Prompt Engineering\nLab Manual")
    r.bold, r.font.size = True, Pt(22)
    sub = d.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run(f"B.Sc (Hons) VII Semester, RV University\nName: {a.name}    USN: {a.usn}").font.size = Pt(13)
    d.add_paragraph("Each program below was run as a Jupyter notebook (labs/labNN.ipynb in the project repository). "
                    "The code, output and figures are what the notebook produced. Programs that call a language model "
                    "state which one ran: the manual names Cohere, but no Cohere key was available, so Groq was used.")
    d.add_page_break()

    found = 0
    for n in range(1, 16):
        path = HERE / f"lab{n:02d}.ipynb"
        if not path.exists():
            d.add_heading(f"Program {n}", 1)
            d.add_paragraph("[notebook not yet run]")
            continue
        nb = nbformat.read(path, 4)
        found += 1
        head = nb.cells[0].source
        m = re.match(r"# Program (\d+): (.*?)\n\n\*\*Aim\.\*\* (.*?)\n\n\*\*Theory\.\*\* (.*)", head, re.S)
        d.add_heading(f"Program {m.group(1)}: {m.group(2)}", 1)
        for label, body in (("Aim", m.group(3)), ("Theory", m.group(4))):
            p = d.add_paragraph()
            p.add_run(label + ". ").bold = True
            p.add_run(body)
        d.add_paragraph().add_run("Code and output").bold = True
        for c in nb.cells[2:-1]:
            if c.cell_type != "code":
                continue
            code_par(d, c.source.strip())
            for o in c.get("outputs", []):
                if o.output_type == "stream":
                    txt = clean(o.text)
                    if txt:
                        p = d.add_paragraph()
                        p.paragraph_format.left_indent = Inches(0.15)
                        rr = p.add_run(txt)
                        rr.font.name, rr.font.size = "Consolas", Pt(8.5)
                        rr.font.color.rgb = RGBColor(0x0A, 0x4A, 0x41)
                elif o.output_type in ("display_data", "execute_result"):
                    png = o.get("data", {}).get("image/png")
                    if png:
                        d.add_picture(io.BytesIO(base64.b64decode(png)), width=Inches(6.2))
                    elif "text/plain" in o.get("data", {}) and o.output_type == "execute_result":
                        code_par(d, clean(o["data"]["text/plain"]), 8.5)
                elif o.output_type == "error":
                    p = d.add_paragraph()
                    p.add_run(f"[error: {o.ename}: {o.evalue}]").bold = True
        obs = nb.cells[-1].source.replace("## Observations\n\n", "")
        p = d.add_paragraph()
        p.add_run("Observations. ").bold = True
        p.add_run(obs)
        d.add_page_break()

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    d.save(a.out)
    print(f"wrote {a.out} ({found} of 15 notebooks included)")


if __name__ == "__main__":
    main()
