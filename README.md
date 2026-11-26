# MedSaarthi AI

**Prescriptions in plain words and in the patient's own language, with a pharmacist in the loop.**
CS4204 Generative Models and Prompt Engineering, mini project (CIE-3), RV University.

> Student prototype tested on **synthetic data only**. It is not clinically validated, has not been tested with patients, and is not a medical device. Every output says: *Not medical advice. Confirm with your pharmacist or doctor.*

## What it does
1. Reads a prescription from a photo (local OCR) or typed text, and extracts each medicine's name, dose, route, frequency, duration and instructions with a confidence for every field.
2. Holds anything missing, unclear or low-confidence out of the plan. Nothing is guessed. A patient can share a held item with a pharmacist, who edits it and signs it.
3. Writes the plan in the patient's language from a **language pack**: code writes every dose, time and day count, so a number can never be mistranslated. English plus ten Indian languages (Hindi, Kannada, Tamil, Telugu, Bengali, Marathi, Gujarati, Malayalam, Punjabi, Odia). Every Indian-language pack is an **unreviewed draft** and the app says so.
4. Gives a day plan to tick, a printable PDF and HTML guide that say who checked each medicine, calendar reminders (.ics) and a FHIR R4 export.
5. Accounts for patients, caregivers (up to 10 family profiles) and invite-only pharmacists. Each profile has an age group (child, adult, senior), language, clock, text size, contrast and motion settings. The app installs on a phone and has a 3D pill organizer that falls back to flat tiles.

```
photo/text -> OCR -> extraction LLM (RGC + 4-shot, delimiters) -> grounding in the source -> safety gate
           -> ambiguity rules + LLM chain of thought -> [patient or pharmacist confirms held items]
           -> schedule (Python) -> template realiser in the patient's language -> digit contract
           -> plan, PDF, HTML, .ics, FHIR
```

## Safety rules enforced in code
| Rule | Where |
|---|---|
| A missing field or confidence below 0.80 holds the item; held items are never explained or scheduled | `src/validator.py::gate_item`, `src/schedule.py` |
| A value not found in the source text gets low confidence and is held | `src/extract.py::_to_item` |
| Prescription text is data: delimiters, injection detector, injected lines never count as evidence | `src/validator.py`, `src/extract.py` |
| Dose times come from Python, never from a model | `src/schedule.py` |
| Patient wording is written from a language pack; the digits out must equal the digits in, on every render | `src/lang/realiser.py` |
| A pack string with a digit or an unknown placeholder is rejected; a pack marked reviewed must name its reviewer | `src/lang/pack.py` |
| Machine translation is used only for free text, through an ordered chain, and every answer is checked | `src/mt.py` |
| Passwords hashed with Argon2id; saved plans encrypted at rest; photos never stored; one-click account deletion | `api/security.py`, `api/models.py`, `api/auth.py` |
| Pharmacist accounts need an invite code; nobody can review their own prescription | `api/auth.py`, `api/records.py` |
| The audit log stores a SHA-256 of each input, never raw text | `src/audit.py` |

## Setup (Windows, Python 3.12, Node 22+, CPU only)
```bash
python -m venv .venv
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install -r requirements.txt
npm --prefix web install
npm --prefix web run build
```
Create `.env` in the project root (it is git-ignored):
```
GROQ_API_KEY=<your key from console.groq.com>
PHARMACIST_INVITE_CODE=<any secret you choose; give it only to pharmacists>
# optional: SARVAM_API_KEY, COHERE_API_KEY (lab programs), MEDSAARTHI_DATA_KEY (otherwise a local dev key is created)
```
Optional, to avoid waiting on the first run (about 6 GB): `.venv/Scripts/python scripts/warm_models.py`.

## Run
```bash
.venv/Scripts/python -m uvicorn api.server:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000. For the two-screen demo, `python scripts/seed_demo.py` creates three local demo accounts (patient, caregiver, pharmacist); see `docs/VIVA.md`.

## Tests
```bash
.venv/Scripts/python -m pytest -q
```
End-to-end in a real browser (start a server first; the pharmacist round trip needs the same invite code in both places):
```bash
.venv/Scripts/python tests/e2e_web.py outputs/screens_new
```

## Training and evaluation
| Command | What it does |
|---|---|
| `python -m src.eval.run_eval` | Extraction, OCR, ambiguity, injection, simplification and translation evaluation on the 25 reference prescriptions |
| `python -m src.eval.lang_bench` | Translation providers: checks, latency, back-translation |
| `python -m src.tagger.train` | Trains the T1 HMM and BiLSTM taggers on 100,000 synthetic lines (about 20 minutes on CPU) |
| `python scripts/make_lora_data.py` | Writes the T2 fine-tuning data (20,000 synthetic prescriptions) |
| `notebooks/t2_lora_qwen.ipynb`, `notebooks/t3_trocr_rxhandbd.ipynb` | LoRA and TrOCR fine-tuning for a free Kaggle or Colab GPU (written, not yet run) |
| `python -m src.lang.review <code>` | Prints a pack beside the English for a native speaker; `--sign "Name"` records their review |

Results and their limits are in [docs/EVAL.md](docs/EVAL.md).

## Course deliverables
| Deliverable | How to build it |
|---|---|
| Lab manual (15 programs, run with outputs) | `python labs/build_labs.py`, then `python labs/build_manual.py --name "..." --usn "..."` |
| Project report in the course template | `python scripts/build_report_docx.py --name "..." --usn "..."` (text in `docs/report_sections.md`) |
| Jury deck | `python scripts/build_deck.py` writes `docs/MedSaarthi_Jury_Deck.pptx` |
| Report figures | `python scripts/make_figures.py` |
| Viva bank and demo script | [docs/VIVA.md](docs/VIVA.md) |

## Repository map
| Path | Contents |
|---|---|
| `src/` | Pipeline: schema, OCR, extraction, ambiguity, schedule, simplification, RAG, rendering, audit |
| `src/lang/` | Language packs (`packs/*.json`), the template realiser, digit handling, review tool |
| `src/mt.py`, `src/translate.py` | Translation provider chain and answer checks |
| `src/tagger/` | T1: synthetic line generator, HMM and BiLSTM taggers, training, weights |
| `api/` | FastAPI server, accounts, database models, plans and pharmacist review |
| `web/` | React + TypeScript app with Three.js scenes; installable |
| `labs/` | The 15 lab programs as notebooks, and their builders |
| `notebooks/` | Evaluation tables; T2 and T3 GPU notebooks |
| `data/` | 25 synthetic reference prescriptions and their generator; synthetic leaflets |
| `docs/` | Report, evaluation, prompts, design, model choices, viva bank, deck, figures |
| `Dockerfile`, `scripts/deploy_space.py` | Hosting on Hugging Face Spaces |
