# MedSaarthi AI: master plan for the jury

Written Thursday 26 November 2026. The jury is next week (Monday 30 November to Friday 4 December; the exact day is not known to me). That leaves **four working days: Thu 26, Fri 27, Sat 28, Sun 29.** Work happens on the git branch `jury-upgrade`, so `main` stays a demo-ready fallback until the new version has passed its tests.

## 1. What the course requires

From `CS4204-Course outline.docx`. Total = 70 (CIE) + 70 (SEE).

| Component | Marks | What it is | State | Who |
|---|---|---|---|---|
| CIE1 MOOC | 5 | Course certificate, submitted by the due date | **Unknown** | You |
| CIE1 Quiz | 15 | 15 MCQs | Presumably done | n/a |
| CIE2 Theory | 25 | Pen and paper | Presumably done | n/a |
| CIE3 Mini project and demonstration | 20 | 4 criteria x 5: problem, prompt design, implementation, documentation and ethics (rubric in the outline) | Built; being upgraded | Me |
| CIE3 Lab manual | 5 | 15 lab programs (word vectors, PCA/t-SNE, Word2Vec, prompt enrichment, Hugging Face pipelines, LangChain + Cohere, Pydantic parser, IPC chatbot) | **Not started** | Me (you supply a Cohere key) |
| **SEE Jury** | **70** | Oral exam; the outline gives no format, so I assume questions on **all five modules** plus the project | Prep covers the project only | Me + you |
| Project report | in CIE3 | Fixed template: name, USN, title, introduction and motivation, problem statement, methodology, dataset details, model architecture, workflow/pipeline, results, GitHub link | `docs/REPORT.md` exists but is **not in the template** | Me (one .docx per student) |
| Slide deck | in CIE3 | 11 slides in `MedSaarthi_AI_Presentation.pdf` | **Stale** (see 2) | Me |

The team is Prajan K (1RVU23BSC100), Sachin S (1RVU23BSC124) and Sanjay SG (1RVU23BSC128). Every member must be able to answer questions on every part. Nothing below helps if you cannot explain it.

## 2. Gaps in the current project

Honest list, against the rubric and the jury.

1. **The deck is out of date.** It still says Streamlit (slides 4, 7, 10), 64 tests (now 93), no authentication, and "no model training". The Streamlit app no longer exists.
2. **"No training or fine-tuning" is a weak line for this course.** Module 3 covers pretraining vs fine-tuning and CO2 is about training concepts. A jury will ask. Fix: real training runs with before and after numbers (section 5).
3. **The "pharmacist confirmed" button is self-attested.** Anyone can tick it. A hospital use case needs a real pharmacist role with a sign-off recorded (section 6).
4. **No accounts, database or login.** Plans vanish when the browser closes.
5. **Translation is not real time.** NLLB on this laptop takes 20 to 30 seconds per medicine. A hosted API takes about a second (to be measured, section 4).
6. **Modules 1 to 3 and 5 have no project link.** HMMs, GANs, VAEs, LSTM and agents will be asked about. Prepared answers and one bridge experiment are in section 7.
7. **The lab manual does not exist.**
8. **Evidence is thin where it matters most:** 25 synthetic prescriptions, no real handwriting, no human ratings, no native-speaker review. The report states this. The upgrade must not hide it.

## 3. "Syntax for any language": the answer

The current design writes English with an LLM and then machine-translates it. That is why Hindi once lost the difference between 8 AM and 8 PM. Translating safety-critical sentences is the wrong tool.

**Structured first, language last.**

```
prescription -> structured plan (language-neutral JSON, checked by code)
             -> per-language template realiser (deterministic, instant)
             -> machine translation only for free text with no template
```

- A **language pack** is one JSON file per language: names for parts of the day, unit words, sentence templates with slots (`{drug} {dose} {frequency} {times} {days}`), and the plural and ordering rules. **Adding a language means adding a file and having a native speaker read about 30 short strings.** No code changes.
- The realiser fills slots from the confirmed structured data, so numbers and times cannot be altered by a model. A test renders every language from the same input and asserts the digits match.
- Drug names stay in Latin script by default (safer to match the box), with an optional transliteration column that a native speaker reviews.
- **Fallback ladder for text with no template** (for example an unusual "extra note"): glossary phrase, then hosted translation API, then local model. Each step keeps the digit check, and anything machine-made is labelled as such.
- Result: any language with a pack answers in **milliseconds**, offline, with no quality risk on doses and times. That meets "real time" better than any API.

Ship: Hindi, Kannada, Tamil, Telugu (reviewed by you) plus Bengali, Marathi, Gujarati, Malayalam, Punjabi, Odia as **drafts clearly labelled "not reviewed"**. A language is only presented as supported when a native speaker has signed off its pack.

## 4. Real-time translation and your keys

I read "KPA keys" as **API keys**, and "ordered" as the **order they are tried in** (fallback chain). **Please confirm or correct this.**

Planned chain, tried in order, each with a timeout and the same digit and drug-name checks:

| Order | Provider | Needs | Notes |
|---|---|---|---|
| 1 | Language pack (templates) | nothing | Instant. Handles all safety-critical sentences |
| 2 | Groq-hosted model (`gpt-oss-120b`, `qwen3.8-27b`) | `GROQ_API_KEY` (have it) | Free-text fallback. **Quality for Kannada, Tamil, Telugu is unmeasured; I will measure it** |
| 3 | Sarvam Translate / Mayura API | a Sarvam key | 11 languages. Priced at 20 rupees per 10,000 characters; new accounts get 100 rupees of credit per the current docs |
| 4 | Bhashini (government) | a registered, approved key | 22 languages. Needs approval, which may take days |
| 5 | Local NLLB-200 on CPU | nothing | Slow (20 to 30 s) but private and offline |

Measured on the actual keys and recorded in `docs/EVAL.md`: latency (median, p95), digit fidelity, drug-name preservation, and back-translation similarity. **I cannot score true translation quality for Dravidian languages without a native speaker.** The numbers will say so.

## 5. Data and models

### Verified candidates (licences read from the Hugging Face API or the pages, 26 Nov 2026)

| Item | Use | Licence and access | Verdict |
|---|---|---|---|
| A-Z Medicine Dataset of India (Kaggle, about 254,000 medicines: name, manufacturer, composition, pack) | Realistic drug names and strengths for synthetic data | **No licence shown** on the HF mirrors; the Kaggle page must be checked | Use as private vocabulary only. **Do not redistribute or commit the file.** Cite it |
| India's National List of Essential Medicines 2022 | Clean, defensible drug list | Government publication (to verify) | Preferred backbone of the vocabulary |
| RxHandBD and Doctor's Handwritten Prescription BD (Mendeley, 5,578 and 4,680 word images of medicine names) | **Real handwriting** to fine-tune TrOCR | Licence field not shown by search; HF mirror `lance-format/handwriting-ocr` is **ODbL** | Usable with attribution. Check the Mendeley licence |
| BPCC (about 230 million pairs; CC0 for the mined part, CC-BY-4.0 for human seed data) | Translation training and testing | Gated, auto-approved after you accept terms on Hugging Face | Needs your HF login |
| IN22-Gen (Indian translation benchmark) | Standard translation test | CC-BY-4.0, gated auto | Needs your HF login |
| MedMCQA (194,000 Indian medical entrance questions) | Medical-domain evaluation of language models | Apache-2.0, open | Context only. MedSaarthi gives no medical advice, so this is not core |
| Real prescriptions | the ideal | **Not available.** Privacy and consent rules block it | Say so plainly |

### "Best models in the country": candidates to evaluate

| Model | From | Licence and access | Role |
|---|---|---|---|
| IndicTrans2 (1B and 200M distilled) | AI4Bharat, IIT Madras | MIT, gated auto | Translation baseline for 22 languages |
| Sarvam Translate (4.3B) | Sarvam AI | **GPL-3.0**, open | Translation. Copyleft: fine for coursework, flag for any product |
| Sarvam API (Mayura / Translate V1) | Sarvam AI | Paid per character, small free credit | Real-time translation |
| Sarvam 30B and 105B, Sarvam-M (24B) | Sarvam AI | Apache-2.0 | Too large to run here; API or comparison only |
| Param2 17B | BharatGen | Announced Feb 2026; weights and licence unconfirmed | Mention only |
| IndicConformer 600M (speech to text), Indic Parler-TTS (text to speech) | AI4Bharat | MIT and Apache-2.0, gated | Voice for readers who cannot read well (stretch) |
| IndicPage-OCR, Chitrapathak-2, Sarvam Vision 2.1 | IIIT-H, Krutrim, Sarvam | research / API | Prescriptions are mostly written in English letters, so Indic OCR matters less. **Kannada coverage is unclear** |
| NLLB-200 600M | Meta | CC-BY-NC | Current local fallback |

I will **not** claim any of these is "the best". The benchmark will rank them on my test set, and a ranking on 60 sentences is a small-sample result.

### Training that is actually possible

This laptop has **no GPU** (16 GB RAM, Intel Iris Xe), so large fine-tuning cannot run here. The plan separates what runs locally from what needs a free GPU.

| # | Training | Data | Where | Honest claim |
|---|---|---|---|---|
| T1 | **BiLSTM tagger** (and an HMM baseline) that labels each token as drug, dose, frequency or duration | **100,000 synthetic prescription lines** built from the drug vocabulary, many abbreviations, typos and OCR-style noise | **This laptop, minutes** | A small trained model that works offline. This also keeps prescription text on the device, which matters for hospitals. Evaluated on a separately written test set, because synthetic-to-synthetic scores look better than reality |
| T2 | **LoRA fine-tune of Qwen2.5-1.5B-Instruct** (Apache-2.0) for prescription-to-JSON | 20,000 of the same examples | **Free Kaggle or Colab GPU.** I prepare the notebook; you press run (about an hour) | Before and after against the prompt-only `gpt-oss-20b` baseline |
| T3 | **TrOCR fine-tune** on real doctor handwriting | RxHandBD, 5,578 word images | Free Kaggle or Colab GPU | Character error rate before and after on writers not seen in training |

Everything is called what it is: fine-tuning on **synthetic prescriptions and real handwriting of drug names**. It is not training on real prescriptions.

## 6. Product upgrade

**One sentence for the design:** *on this page, the patient's own day becomes a 3D pill organizer.* A pill box with Morning, Noon, Evening and Night lids is an object every age group already understands.

**Accounts and database**
- SQLite now, Postgres by changing one setting (so a hosted database can be used). SQLAlchemy models: user, profile, plan, review, audit.
- Passwords hashed with Argon2id; server-side sessions in an `HttpOnly` cookie; Origin check on every state-changing request.
- Plans and extracted fields **encrypted at rest** (Fernet, key outside the database). Saving is **opt-in**; the default stays "forgotten when you close the page". The consent text changes to match.
- Delete my account and all data, in one click.

**Roles** (this is the hospital and home story)

| Role | Does |
|---|---|
| Patient | Reads, checks, gets a plan, ticks doses |
| Caregiver | Manages several profiles (a parent, a child), each with its own language and accessibility |
| Pharmacist or nurse | Sees a **review queue** of held items, edits and **signs**. The signature, name and time are stored and printed on the plan |

Plans show **"verified by pharmacist X"** or **"checked by you, not yet by a pharmacist"**. Today's self-attested button becomes the second kind.

**Tailored to each person.** A profile has an age mode and the app changes with it:

| Mode | Changes |
|---|---|
| Child (a guardian manages it) | Bouncier Saarthi, simple words, no scores |
| Adult | Default |
| Senior | Largest type, highest contrast, slow motion, voice read-out offered first, fewest choices |
| Any | Reduced motion switches the 3D scene to flat tiles. **All dose text stays real text** in the page, never only inside the 3D scene |

**Mobile first.** An installable web app (PWA) with the plan cached for offline use, camera capture for the photo, and add-to-home-screen. **Reminders** as a calendar file with alarms (works on every phone, no push server). **Share the plan on WhatsApp.** Export as a **FHIR MedicationRequest** bundle, the standard hospitals and India's health-record scheme use. A real Android APK (Capacitor) is optional and needs Android Studio, which this machine does not have.

**3D.** Three.js through React Three Fiber, loaded only when needed. Saarthi reacts to state (thinking, careful, happy). The organizer lids open on tap and a capsule drops in when a dose is ticked. A sun and moon arc follows the device clock. Fallback to flat tiles when WebGL is missing, the device is weak, or motion is reduced. Performance on cheap phones will be measured, not assumed.

## 7. Jury preparation (70 marks)

- **Viva bank for all five modules**, each answer tied back to MedSaarthi: HMM (a tagger baseline), autoencoders and VAEs (augmenting handwriting), GANs (why they are not used here), RNN, LSTM, GRU, attention and the Transformer (what `gpt-oss`, TrOCR and NLLB are), pretraining vs fine-tuning (T1 to T3), multimodal models, the prompt techniques, RAG (and why it did not help), agents, bias and deepfakes.
- **Module 2 bridge:** an HMM tagger trained on the same synthetic data, compared with the BiLSTM. It costs little and gives you a concrete classical-vs-neural answer.
- Two-screen demo script: patient on a phone, pharmacist on the laptop.
- Five-minute fallback if the network or Groq fails.

## 8. Schedule (four working days)

| Day | Build | Output |
|---|---|---|
| **Thu 26** | This plan; language packs and realiser; provider chain and measured benchmark; database, login and roles in the API, with tests | Backend that can be demoed with `curl` |
| **Fri 27** | Mobile-first app: login, profiles, age modes, pharmacist queue, 3D organizer and Saarthi, PWA, reminders, share | Two-device demo |
| **Sat 28** | Synthetic data generator; T1 trained here; T2 and T3 notebooks ready for Kaggle; model benchmark; lab manual programs run and written up | Real trained model, numbers in `EVAL.md` |
| **Sun 29** | Report .docx per student; new deck; viva bank; demo video; **feature freeze at noon**; rehearsal | Everything submit-ready |

If time runs short, cut in this order: Android APK, voice, drafted languages beyond the four, the 3D lids animation (keep flat tiles), T3. **Never cut:** report, deck, viva bank, lab manual, a stable demo.

## 9. Review: risks and what I will not claim

1. **Scope.** Four days is tight for this list. I rank by marks and demo value, and the branch keeps `main` safe.
2. **Health data in a database raises the stakes.** Encryption, opt-in saving, deletion and synthetic-only data are required, and India's Digital Personal Data Protection Act 2023 applies to real use. This remains a student prototype.
3. **Do not claim "trained on a large dataset of prescriptions".** The truthful sentence is "fine-tuned on 20,000 synthetic prescriptions built from real Indian medicine names, and on 5,578 real handwritten word images".
4. **Synthetic-to-synthetic scores flatter the model.** Test sets are written separately and the hand-specified 25 stay the reference.
5. **Licences.** The Indian medicine dataset has no stated licence; Sarvam Translate is GPL-3.0; NLLB is non-commercial. Fine for coursework, and noted in the report.
6. **"Best in the country" is a claim I can only test narrowly.** The benchmark will say what it measured.
7. **A friendly 3D interface can over-reassure.** The disclaimer, the pharmacist step and calm wording stay.
8. **Nothing here has been tested with patients.** The report must keep saying so.

## 10. What I need from you

1. **Which keys do you have?** Only Groq today. Optional: Sarvam, Bhashini, Cohere (the lab manual needs one, free trial), a Hugging Face token (for IndicTrans2 and the gated datasets).
2. **The jury date and format**, and whether it is individual or the whole team.
3. **Whether the MOOC certificate and CIE1/CIE2 are done.**
4. **A free Kaggle account** to run T2 and T3 (about two hours, you only press run).
5. **A native-speaker read** of the language packs (Kannada is likely one of your team's strengths; Hindi, Tamil and Telugu need a classmate).

Sources: [Indian medicine dataset (Kaggle mirror)](https://baselight.app/u/kaggle/dataset/shudhanshusingh_az_medicine_dataset_of_india) · [Doctor's Handwritten Prescription BD](https://data.mendeley.com/datasets/zjjtptvn6f) · [RxHandBD](https://data.mendeley.com/datasets/dsb5r6vskg) · [IndicTrans2 and BPCC](https://github.com/AI4Bharat/IndicTrans2) · [Sarvam pricing](https://docs.sarvam.ai/api/getting-started/pricing) · [Sarvam translation](https://www.sarvam.ai/apis/translation) · [Bhashini onboarding](https://bhashini.gitbook.io/bhashini-apis/pre-requisites-and-onboarding) · [Sarvam 30B and 105B](https://www.sarvam.ai/blogs/sarvam-30b-105b) · [IndicPage-OCR](https://cvit.iiit.ac.in/images/ConferencePapers/2026_01/IndicPage-OCR.pdf) · [Sarvam Vision 2.1](https://www.sarvam.ai/blogs/sarvam-vision-2-1)
