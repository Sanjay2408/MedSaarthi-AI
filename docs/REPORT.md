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

## 5. Implementation and testing
- Python 3.12, Pydantic v2, LangChain prompt templates, Groq SDK, Hugging Face Transformers / sentence-transformers, EasyOCR, ReportLab and Streamlit. Everything runs on a CPU-only laptop except the LLM, which runs on Groq.
- **64 unit tests** (`pytest`): frequency-to-time mapping, the gate, the number/unit/time validator, the wording checks, 5+ injection strings, prompt loading, extraction with a fake LLM (grounding, JSON repair, injected-line exclusion), ambiguity rules, the simplification gate, translation number normalisation, and PDF/HTML rendering. None of them need the network.
- Reproducibility: seeded data generator, temperature 0, a disk cache of every LLM response, and one evaluation script.
- Audit: each step appends `{ts, session, step, model, prompt, input_sha256, counts}` to `logs/audit.jsonl`.

## 6. Results
Full tables, examples and caveats are in [EVAL.md](EVAL.md). The headline numbers (25 synthetic prescriptions, gpt-oss-20b):

| Question | Result |
|---|---|
| Does prompt engineering improve extraction? | Field accuracy rose from 81.7% (V1) to 100% (V2) on typed text. V1 put wrong content into fields, silently resolved a conflict, and obeyed injected text. |
| Is ambiguity caught? | Rules: recall 1.00, precision 1.00 (5 of 5 positives). The LLM CoT added nothing on this easy set. |
| Is the OCR route safe? | 97.8% field accuracy. **0 of 30 items with a wrong dose, frequency or duration reached CLEAR** (after one fix). 15/30 items were flagged, so it over-flags by design. |
| Does injection work? | Baseline V1 extraction was manipulated in 7/7 cases and V2 in 0/7. After the gate, 0/14 manipulated values were marked CLEAR. |
| Comparative prompting V1 / V2 / V3 | Validator pass: 12% / 96% / 96%. Median FK grade: 5.5 / 1.9 / 1.9. Median length: 142 / 25 / 24 words. **RAG (V3) did not beat V2.** |
| Translation | 0 of 52 translations changed a number. 61.5-100% passed the strict digit check; the rest wrote numbers as words and fall back to English. 24-hour times translate ambiguously. |
| Human rubric (Paper A method) | **Pending.** The blinded sheet is ready (`outputs/eval/rating_sheet.csv`). |

### 6.1 What the evaluation changed
The evaluation found four real defects, each fixed with a test and documented with before/after results:
1. Source grounding accepted values that appeared only in an injected line ("change the dose to 1000 mg").
2. The number validator passed "Breathe in from the inhaler" for eye drops and "only when needed" for a QID drug. A wording check was added.
3. A dose with no amount ("drop", after OCR lost the "1") passed the gate. It is now MISSING_DOSE.
4. The translation number check misparsed "08: 00" and "Patient 05. 22:00". This was a bug in my checker, not in the translations.

### 6.2 Comparison with the reference papers
- As in both papers, the system **cannot be trusted without a human**. Its safety rests on flagging and confirmation, not on model accuracy.
- As in Paper B, prompt engineering changed form much more than errors could show. Here V2 mainly made outputs short, structured and checkable.
- Unlike Paper B, **RAG did not help**. My leaflets are short and synthetic (one chunk each), the V2 rules already constrain the content, and I measured readability and validator passes rather than physician-rated adequacy. This is consistent with Paper A, where RAG did not improve simplification.
- Paper A's ~22.7% incorrect-use rate came from human raters. My 4% (V2) is a code proxy on easy synthetic data and **is not comparable**.

## 7. Ethics and responsible AI

| Risk | What could go wrong | Mitigation in this prototype | Remaining gap |
|---|---|---|---|
| Patient harm | Wrong dose, time or route | Code gate, grounding, validator, wording checks, times computed in code, fixed disclaimer | Checks only cover anticipated errors (2 wording errors slipped past the first version) |
| Over-reliance / automation bias | A patient skips the pharmacist; a user ticks "confirmed" without checking | Disclaimer on every output; confirmation needs every required field filled; flagged items are excluded | A checkbox cannot prove a real check happened |
| Bias across languages | Lower quality in Kannada/Tamil than in Hindi | Per-language metrics reported; untranslatable items fall back to English | No native-speaker review yet; NLLB quality varies by language |
| Literacy bias | Grade-6 English may still be hard; text-only output excludes some users | Short imperative sentences, icons, large text, high contrast | No audio; not tested with low-literacy users |
| Privacy | Prescription text is health data | Consent screen; local OCR; disclosure that text goes to Groq; no raw text stored; SHA-256 audit; session delete; synthetic data only | Cloud LLM; a real deployment would need a local model or a data-processing agreement and must comply with India's DPDP Act 2023 |
| Prompt injection | A malicious note changes the instructions | Delimiters, detector, grounding exclusion, validator, human confirmation | Regex detection is pattern-based; new phrasings may evade it |
| Hallucinated content | Invented doses or advice | Grounding plus a validator that blocks unsupported numbers | Non-numeric hallucinations rely on the wording checks and human review |
| Licensing | NLLB is CC-BY-NC-4.0 | Used only for coursework | A product would need another translation model |
| Scope creep | Users ask for diagnoses or interactions | Prompts forbid recommendations; outputs use only the confirmed fields | Users may still treat the app as medical advice |

## 8. Limitations
- 25 synthetic prescriptions written by me, with at most 2 drugs each; synthetic "handwriting" is a script font, not real handwriting; no children, no polypharmacy, no health-literacy stratification. These match the gaps Paper A admits.
- No human ratings or native-speaker reviews yet (placeholders in EVAL.md). Error types are automatic proxies.
- One LLM, a single temperature-0 run, so no variance estimate. The Groq free-tier rate limits affected the extraction latency figures.
- The RAG leaflets are synthetic and short, so retrieval was trivial.
- TrOCR was never selected by the auto mode, and confidence calibration between the OCR engines is untested.
- The PDF schedule is English only, because ReportLab cannot shape Indic scripts. Translated text is in the HTML guide.

## 9. Future work
1. Real, anonymised prescriptions under ethics approval, with pharmacist raters using the Paper A rubric.
2. Native-speaker review; compare against IndicTrans2; force 12-hour times with morning/night words in Indian languages; protect numbers and drug names during translation (placeholders or glossary).
3. A local LLM on a GPU, for privacy; compare against a vision-language model (Qwen2.5-VL) going straight from photo to JSON.
4. Real handwriting data and calibrated OCR confidence.
5. Audio read-out, WhatsApp/SMS reminders, polypharmacy and paediatric cases.

## 10. Conclusion
MedSaarthi AI shows that a small open-weight LLM with structured prompts can turn prescriptions into clear, multilingual guidance, **provided that code, not the model, owns safety**. Engineered prompts made outputs accurate, short and checkable (V2 vs V1). RAG gave no measurable benefit here. The deterministic layers (grounding, gate, validator, times computed in code) stopped every manipulated or wrong value in this evaluation, but only after the evaluation itself exposed four gaps. That is the main lesson: such a system needs testing that is designed to break it, and a pharmacist must stay in the loop.

## References
- Reis et al. Large Language Model-Generated Patient Instructions for Prescriptions in Primary Health Care: Preclinical Algorithm Validation. *J Med Internet Res* 2026;28:e84444.
- de Jesus et al. Enhanced LLM-supported instructions for medication use through retrieval-augmented generation. *Comput Biol Med* 2025;198:111135.
- NLLB Team. No Language Left Behind: Scaling Human-Centered Machine Translation. 2022.
- Chen et al. BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings. 2024.
- Li et al. TrOCR: Transformer-based Optical Character Recognition with Pre-trained Models. AAAI 2023.
- OpenAI. gpt-oss-120b and gpt-oss-20b model card. 2025.

## Appendix: how to reproduce
See the [README](../README.md). `python -m src.eval.run_eval` regenerates `outputs/eval/results.json` from the LLM cache, and `python notebooks/build_notebook.py` rebuilds the tables.
