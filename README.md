# MedSaarthi AI

**A Generative AI system for prescription interpretation and multilingual medication guidance.**
CS4204 Generative Models and Prompt Engineering, mini project (CIE-3), RV University.

> Student prototype tested on **synthetic data only**. It is not clinically validated and is not a medical device. Every output says: *Not medical advice. Confirm with your pharmacist or doctor.*

## What it does
1. Reads a prescription from a photo (local OCR) or typed text.
2. Extracts medication name, dose, route, frequency, duration and instructions as JSON, with a confidence score for every field.
3. Flags ambiguous or missing items for a pharmacist or doctor to confirm. Flagged items are never explained or scheduled.
4. Turns confirmed items into plain-language instructions. A code validator checks every number, unit and time against the confirmed data.
5. Translates the instructions into Hindi, Kannada, Tamil or Telugu, with a number check and a back-translation spot check.
6. Builds a daily schedule in code (never by the LLM) as a downloadable PDF or printable HTML, with large-text, high-contrast and 12/24 h options.

```
image/text -> OCR (EasyOCR / TrOCR) -> extraction (LLM, RGC + few-shot) -> source grounding + safety gate
           -> ambiguity (rules + LLM CoT) -> [human confirmation] -> schedule (Python)
           -> simplification (persona; V3 adds leaflet RAG with BGE-M3) -> validator gate -> fixed safety lines
           -> translation (NLLB-200) + number check -> PDF / HTML
```

## Safety rules enforced in code
| Rule | Where |
|---|---|
| Missing field or confidence < 0.80 sets status `NEEDS_CONFIRMATION`; such items are never simplified or scheduled | `src/validator.py::gate_item`, `src/schedule.py::build_schedule`, `src/simplify.py` |
| A value not found in the source text (hallucination) gets low confidence and is flagged | `src/extract.py::_to_item` |
| Every number, unit and time in the output must match the confirmed data, or the output is blocked | `src/validator.py::validate_output` |
| Route wording (e.g. no "inhaler" for eye drops) and "as needed" wording must match the prescription | `src/validator.py::check_semantics` |
| Dose times come from Python, not the LLM | `src/schedule.py` |
| Prescription text is untrusted data: wrapped in delimiters, injection patterns detected, injected lines never count as evidence | `src/validator.py`, `src/extract.py` |
| Disclaimer, storage line and refill line are appended by code | `src/simplify.py::append_fixed_lines` |
| The audit log stores a SHA-256 of each input, never raw text | `src/audit.py` |
| Clock times never pass through the translator; code writes them with morning/night words | `src/translate.py::when_line` |
| Each browser sees only its own cases and log; typed prescriptions never reach the disk cache; requests are rate limited | `api/server.py` |

## See it
A recording of the whole flow is in [docs/demo.mp4](docs/demo.mp4), with stills in [docs/screenshots/](docs/screenshots/). Run the app and open http://127.0.0.1:8000.

## Setup (Windows, Python 3.12, Node 22+, CPU only)
```bash
python -m venv .venv
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -r requirements.txt
```
Create a `.env` file in the project root (it is git-ignored) containing:
```
GROQ_API_KEY=<your key from console.groq.com>
```
Node 22 or newer is needed to build the web app. The first run downloads about 6 GB of models (EasyOCR, TrOCR, NLLB-200, BGE-M3).

## Run
```bash
.venv/Scripts/python data/generate_samples.py
```
```bash
.venv/Scripts/python -m pytest -q
```
```bash
npm --prefix web install
```
```bash
npm --prefix web run build
```
```bash
.venv/Scripts/python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```
```bash
.venv/Scripts/python -m src.eval.run_eval
```

## Repository map
| Path | Contents |
|---|---|
| `src/schema.py` | Pydantic v2 data model with per-field confidence and reason codes |
| `src/validator.py` | Safety gate, number/unit/time validator, injection detector |
| `src/schedule.py` | Frequency parser and default dose times |
| `src/ocr.py` | EasyOCR (printed) and TrOCR (handwriting) with per-line confidence |
| `src/extract.py` | LLM extraction, JSON repair, source grounding |
| `src/ambiguity.py` | Rule-based flags plus LLM chain-of-thought verdict |
| `src/rag.py` | Leaflet retrieval (2900/2100 chunks, BGE-M3, top-2) and the "Extract and summarize dosage" step |
| `src/simplify.py` | Plain-language V1/V2/V3 with the validator gate |
| `src/translate.py` | NLLB-200 translation with number check and back-translation |
| `src/render.py` | PDF and HTML schedule |
| `src/prompts/*.prompt` | Versioned prompts; each header names the technique and the reason for it |
| `api/server.py` | FastAPI: read, confirm, guide, downloads, audit. Safety rules are enforced here, not in the browser |
| `web/` | React + TypeScript web app for patients: add, check together, your plan, your privacy |
| `Dockerfile`, `scripts/deploy_space.py` | Hosting on Hugging Face Spaces |
| `tests/e2e_web.py` | Real-browser test of the full flow, measuring text contrast on every screen in both modes |
| `scripts/record_demo.py` | Records `docs/demo.mp4` and `docs/screenshots/` from a real Chrome window |
| `src/eval/run_eval.py` | Evaluation; writes `outputs/eval/` |
| `notebooks/eval.ipynb` | Results tables built from `outputs/eval/results.json` |
| `data/` | Synthetic sample generator, 25 samples, 11 synthetic leaflets |
| `docs/` | Report, evaluation, prompts, model choices, viva prep |

## Documents
- [docs/REPORT.md](docs/REPORT.md): full project report
- [docs/EVAL.md](docs/EVAL.md): evaluation results and human-rating placeholders
- [docs/PROMPTS.md](docs/PROMPTS.md): prompt catalogue with example outputs
- [docs/DESIGN.md](docs/DESIGN.md): designing for an anxious patient, and what was left out on purpose
- [docs/MODEL_CHOICES.md](docs/MODEL_CHOICES.md): models, licences, hardware fit
- [docs/VIVA.md](docs/VIVA.md): likely viva questions and a 5-minute demo script
