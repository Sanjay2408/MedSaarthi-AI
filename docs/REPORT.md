# MedSaarthi AI: A Generative AI System for Intelligent Prescription Interpretation and Multilingual Medication Guidance

CS4204 Generative Models and Prompt Engineering · Mini project (CIE-3) · RV University, Bengaluru
Author: Sanjay S G (Sanjay2408) · Instructors: Dr. Baishali Garai, Dr. Sachin Somra

> Prototype tested on 25 synthetic prescriptions. Not clinically validated, not a medical device.

## 1. Problem and requirements

### 1.1 Problem
Patients often cannot read a prescription: handwriting, abbreviations (OD, BD, TDS, 1-0-1, SOS), missing durations, and instructions in a language they do not read well. Misunderstanding leads to wrong doses, missed doses and early stopping. In India the problem is made worse by linguistic diversity and short consultations.

### 1.2 Objectives
1. Extract medication name, dose, route, frequency, duration and instructions from a photo or typed text, with a confidence score for each field.
2. Detect ambiguous or missing items and send them to a pharmacist or doctor for confirmation. Never fill gaps.
3. Rewrite confirmed items as plain-language instructions (grade-6 reading level).
4. Translate them into Hindi, Kannada, Tamil and Telugu.
5. Produce a printable daily schedule with accessibility options (large text, high contrast, 12/24 h).
6. Protect privacy (consent, local OCR, hash-only audit) and resist prompt injection.

### 1.3 Scope
In scope: adult outpatient prescriptions of 1-2 oral, eye or inhaled medicines; English prescriptions; synthetic data.
Out of scope: dose checking, interactions, diagnosis, recommendations, children, polypharmacy, real patient data.

### 1.4 Why GenAI
Prescriptions vary in layout, abbreviation and noise, so a fixed parser generalises poorly, and an LLM with good prompts handles that variety. Plain-language rewriting and translation are generative tasks by nature. Everything that must be exact (times, number checks, gating) stays in deterministic code. The design principle is **LLM for language, code for safety**.

## 2. Related work

**Paper A**, Reis et al., *JMIR* 2026;28:e84444. 62 primary-care professionals ran 198 blinded evaluations of instructions from ChatGPT-4.0, Llama3.1-8B and Llama3.1-8B with RAG. Median weighted scores were 88.4, 66.5 and 79.9 (P=.003), with RAG similar to ChatGPT-4.0. ChatGPT-4.0 simplified language better (7.05 vs 5.44, P<.001). About 22.7% of outputs from **all three** models could lead to incorrect use, and hallucination ranged from 9.1% to 13.6%. Conclusion: validation by the prescriber is mandatory.
*Taken from it:* the 5-criterion positive/negative Likert rubric with weights 2/1.5/1.5/1/1 normalised to 0-100, the 4-type error taxonomy, mandatory human confirmation, and an honest list of limitations.

**Paper B**, de Jesus et al., *Comput Biol Med* 2025;198:111135. 83 prescriptions, 357 physician evaluations, three Llama 3.1 8B variants. RAG over patient leaflets raised adequacy (median 93 → 94 → 100) and clarity (90 → 92 → 95). Error type 1 fell from 37.3% to 16.9%. Prompt engineering alone did not significantly reduce errors.
*Taken from it:* the three-variant comparative design (baseline, engineered, engineered + RAG); the RAG pipeline (2900/2100 chunks, BGE-M3, top-2 for "How should I use this medicine?", "Extract and summarize dosage" before generation); persona and imperative rules, including avoiding "Start taking..."; and fixed safety text added by code.

## 3. System design

```
image ──► OCR (EasyOCR; TrOCR for handwriting) ──┐
text  ───────────────────────────────────────────┴► extraction LLM (RGC + 4-shot, delimiters)
   ► JSON repair + Pydantic schema ► source grounding (confidence per field)
   ► safety gate (missing / conf < 0.80) ► ambiguity rules ► LLM CoT (adds flags only)
   ► HUMAN CONFIRMATION of flagged items
   ► schedule (Python) ► simplification LLM (persona; V3 + leaflet RAG) ► validator gate
   ► fixed safety lines (code) ► NLLB translation + number check + back-translation
   ► PDF / HTML schedule ► audit log (hashes only)
```

### 3.1 Components
| Module | Role | Key decision |
|---|---|---|
| `schema.py` | Pydantic v2 model | Each field is `{value, confidence}`; a missing value is `None`, never a default |
| `ocr.py` | EasyOCR word boxes grouped into lines; TrOCR per line for handwriting | Per-line confidence feeds the field confidence |
| `extract.py` | LLM to JSON, repair and one retry, schema | **Source grounding**: a field value must fuzzy-match (≥ 85) a non-injected source line, or its confidence drops to ≤ 0.5 and the item is flagged |
| `ambiguity.py` | Rules (missing, low confidence, unknown abbreviation, non-standard duration, instruction vs frequency conflict), then CoT | The LLM may only add reason codes |
| `schedule.py` | Frequency to default times | OD 08:00; BD 08:00/20:00; TDS 08:00/14:00/20:00; QID 06/12/18/22; HS 22:00; q8h from 06:00; 1-0-1 slots; SOS has no fixed time; anything unknown is flagged |
| `simplify.py` | V1/V2/V3 | Validator blocks the output on any number, unit or time mismatch, or a missing dose; a code template is shown instead |
| `translate.py` | NLLB-200 600M on CPU | Digits (including native digits) must be preserved, otherwise English is shown |
| `render.py` | ReportLab PDF and HTML | Indic text only in HTML, because ReportLab does not shape Indic scripts |
| `audit.py` | JSONL | SHA-256 of the input, step, model id and prompt version; no raw text |
| `app/streamlit_app.py` | 5 screens | Consent, input, review/confirm (confidence colours, editable), preferences, result and downloads |

### 3.2 Models
LLM: `openai/gpt-oss-20b` on Groq (Apache-2.0 open weights), temperature 0, reasoning effort low and hidden. Groq no longer served the Llama 3.x models named in the brief. OCR: EasyOCR and `microsoft/trocr-base-handwritten`. Translation: `facebook/nllb-200-distilled-600M`. Embeddings: `BAAI/bge-m3`. Full reasoning, licences and rejected options are in [MODEL_CHOICES.md](MODEL_CHOICES.md).

## 4. Prompt engineering
The full catalogue is in [PROMPTS.md](PROMPTS.md). Summary:

| Technique (syllabus) | Where |
|---|---|
| RGC (Role/Goal/Constraints) | `extract_v2`: transcriber role, JSON-only goal, 11 constraints |
| Few-shot | `extract_v2`: 4 examples (clean, noisy OCR, missing dose, embedded request) with drugs that are not in the test set |
| Chain of Thought | `ambiguity_cot`: hidden `<reasoning>`, then a `FINAL:` JSON verdict with fixed reason codes |
| Persona pattern | `simplify_v2`: community pharmacist in India |
| Controlling style, tone and content | Grade 6, 15-word sentences, imperative, ≤ 70 words, route wording, facts only from the data slots |
| Root prompt / complex multi-part prompt | System part = rules and examples; user part = labelled data slots |
| External knowledge (RAG) | `rag_summary` + V3 context |
| Comparative prompting | V1 vs V2 (extraction), V1 vs V2 vs V3 (simplification) on identical inputs |
| Prompt injection | Delimiters, forged-delimiter removal, regex detector, grounding exclusion, validator |
| LangChain prompt templates | All prompts load as `ChatPromptTemplate` |
| Hugging Face pipelines | TrOCR, NLLB, BGE-M3 through Transformers / sentence-transformers |

<!-- RESULTS -->
