"""Fill the course's project-report template (.docx) from docs/report_sections.md.

    python scripts/build_report_docx.py --name "Student Name" --usn "RVU..." [--template PATH] [--out PATH]

The template's cover page, headings and styles are kept. Each section's text is read from
docs/report_sections.md (H2 headings that match the template's headings) and inserted under the
matching heading. Tiny markdown: paragraphs, "- " bullets, "1. " numbers, pipe tables, ![caption](path),
**bold**, `code`. Run it once per team member; only Name and USN differ.
"""
import argparse
import re
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TEMPLATE = Path.home() / "Downloads" / "CS_4204_Genrative_models_and_Prompt_Enginnering-final project report templete.docx"
SECTIONS = ROOT / "docs" / "report_sections.md"

# template heading text -> heading in report_sections.md
MAP = {
    "Introduction and Motivation": "Introduction and Motivation",
    "Problem statement": "Problem statement",
    "Methodology:": "Methodology",
    "Dataset details": "Dataset details",
    "Model Architecture": "Model Architecture",
    "Workflow/Pipeline": "Workflow/Pipeline",
    "Results": "Results",
    "Github link for code": "Github link for code",
}


def parse_sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip()
            out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def add_runs(par, text: str, size: Pt | None = None):
    for part in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not part:
            continue
        if part.startswith("**"):
            r = par.add_run(part[2:-2])
            r.bold = True
        elif part.startswith("`"):
            r = par.add_run(part[1:-1])
            r.font.name = "Consolas"
            r._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
        else:
            r = par.add_run(part)
        if size:
            r.font.size = size


class Filler:
    def __init__(self, d: docx.Document, anchor):
        self.d, self.anchor = d, anchor

    def _place(self, element):
        self.anchor.addnext(element)
        self.anchor = element

    def par(self, text: str, bold_all=False, indent=0.0, align=None, size=Pt(11)):
        p = self.d.add_paragraph(style="Body Text")
        p.paragraph_format.space_after = Pt(6)
        if indent:
            p.paragraph_format.left_indent = Inches(indent)
        if align:
            p.alignment = align
        add_runs(p, f"**{text}**" if bold_all else text, size)
        self._place(p._p)
        return p

    def table(self, rows: list[list[str]]):
        t = self.d.add_table(rows=len(rows), cols=len(rows[0]))
        borders = OxmlElement("w:tblBorders")  # the template has no table style, so draw thin grey borders directly
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            e = OxmlElement(f"w:{edge}")
            for k, v in (("w:val", "single"), ("w:sz", "4"), ("w:space", "0"), ("w:color", "9AA5A1")):
                e.set(qn(k), v)
            borders.append(e)
        t._tbl.tblPr.append(borders)
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                c = t.cell(i, j)
                c.text = ""
                add_runs(c.paragraphs[0], f"**{cell}**" if i == 0 else cell, Pt(9.5))
        self._place(t._tbl)
        self.par("", size=Pt(4))

    def image(self, path: Path, caption: str):
        self.d.add_picture(str(path), width=Inches(5.8))
        pic = self.d.paragraphs[-1]
        pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self._place(pic._p)
        if caption:
            c = self.par(caption, align=WD_ALIGN_PARAGRAPH.CENTER, size=Pt(9.5))
            for r in c.runs:
                r.italic = True

    def render(self, lines: list[str]):
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line.strip():
                i += 1
            elif line.startswith("```"):
                i += 1
                while i < len(lines) and not lines[i].startswith("```"):
                    p = self.par("", indent=0.3, size=Pt(9))
                    r = p.add_run(lines[i].rstrip())
                    r.font.name, r.font.size = "Consolas", Pt(9)
                    p.paragraph_format.space_after = Pt(0)
                    i += 1
                i += 1
            elif line.startswith("### "):
                self.par(line[4:], bold_all=True, size=Pt(12))
                i += 1
            elif line.startswith("|"):
                block = []
                while i < len(lines) and lines[i].startswith("|"):
                    block.append(lines[i])
                    i += 1
                rows = [[c.strip() for c in b.strip().strip("|").split("|")] for b in block if not re.match(r"^\|[\s:|-]+\|$", b)]
                self.table(rows)
            elif m := re.match(r"!\[(.*?)\]\((.*?)\)", line):
                path = ROOT / m.group(2)
                if path.exists():
                    self.image(path, m.group(1))
                else:
                    self.par(f"[missing figure: {m.group(2)}]")
                i += 1
            elif re.match(r"^(-|\d+\.) ", line):
                marker = "• " if line.startswith("-") else line.split(" ", 1)[0] + " "
                self.par(marker + re.sub(r"^(-|\d+\.) ", "", line), indent=0.3)
                i += 1
            else:
                para = [line]
                i += 1
                while i < len(lines) and lines[i].strip() and not re.match(r"^(\||### |- |\d+\. |!\[)", lines[i]):
                    para.append(lines[i].rstrip())
                    i += 1
                self.par(" ".join(para))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--usn", required=True)
    ap.add_argument("--title", default="MedSaarthi AI: Intelligent Prescription Interpretation and Multilingual Medication Guidance")
    ap.add_argument("--template", default=str(DEFAULT_TEMPLATE))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    d = docx.Document(a.template)
    sections = parse_sections(SECTIONS.read_text(encoding="utf-8"))
    paras = list(d.paragraphs)

    def fill_label(label: str, value: str):
        for p in paras:
            if p.text.strip().startswith(label):
                r = p.add_run(" " + value)
                r.bold = False
                r.font.size = p.runs[0].font.size
                return
        raise SystemExit(f"template has no '{label}' line")

    fill_label("Name:", a.name)
    fill_label("USN:", a.usn)
    fill_label("Project Title:", a.title)

    for p in paras:
        key = MAP.get(p.text.strip())
        if key is None:
            continue
        if key not in sections:
            raise SystemExit(f"docs/report_sections.md has no section '{key}'")
        Filler(d, p._p).render(sections[key])

    out = Path(a.out) if a.out else ROOT / "docs" / f"MedSaarthi_Report_{re.sub(r'[^A-Za-z0-9]+', '_', a.name)}.docx"
    d.save(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
