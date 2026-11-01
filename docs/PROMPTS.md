# Prompt catalogue

All prompts are versioned files in `src/prompts/`. They load into LangChain `ChatPromptTemplate`s through `src/prompts/__init__.py::load_prompt`. Each header records the technique, the reason for it and a changelog. Temperature is 0 for every call (`config.yaml`).

| File | Course technique(s) | Used in | Notes |
|---|---|---|---|
| `extract_v1.prompt` | Zero-shot baseline | Comparative experiment (V1) | One line, no role, no delimiters |
| `extract_v2.prompt` | **RGC** (Role / Goal / Constraints), **few-shot** (4 examples), delimiters against **prompt injection** | Extraction | The examples use drugs that are not in the test set, so they cannot leak answers. One example is noisy OCR, one is ambiguous, and one contains an embedded request the model must ignore. |
| `ambiguity_cot.prompt` | **Chain of Thought** with hidden reasoning and a structured verdict | Ambiguity detection | Code keeps only the JSON after `FINAL:`. The LLM can add reason codes but never remove the rule-based ones. |
| `simplify_v1.prompt` | Zero-shot baseline | Comparative experiment (V1) | Mirrors Model 1 in Paper B |
| `simplify_v2.prompt` | **Persona pattern**, **style/tone/content control** (grade-6 level, imperative voice, length cap, route wording), one-shot example | Simplification V2, and V3 with leaflet context | Rules adapted from Paper B's 18-rule prompt |
| `rag_summary.prompt` | **RAG** context compression ("Extract and summarize dosage") | V3 | Copies Paper B's two-step RAG |

## Root prompt and multi-part structure
Every engineered prompt has the same parts: a system part (role or persona, goal, numbered constraints, examples) and a user part that holds only data, inside labelled slots (`PATIENT:`, `CONFIRMED DATA:`, `SCHEDULE:`, `LEAFLET NOTES:`). This separation lets code control which facts the model sees. The validator then checks that the model used only those facts.

## Controlling style, tone and content
| Control | How |
|---|---|
| Reading level | "grade 6 reading level, sentences of at most 15 words"; measured with textstat Flesch-Kincaid grade |
| Voice | Imperative verbs; "Do not begin with 'Start taking'" (a failure reported in Paper B) |
| Length | "At most 70 words"; word count measured |
| Content | "Use ONLY the facts in CONFIRMED DATA and SCHEDULE"; enforced afterwards by `validate_output` |
| Language | Generated in English, translated by NLLB-200; numbers checked after translation |
| Safety lines | Never generated; appended by `append_fixed_lines` |

## Prompt-injection defence (defence in depth)
1. The prompt puts the text between `<<<PRESCRIPTION_DATA>>>` delimiters and says it is untrusted data (V2 rule 11).
2. `wrap_untrusted` removes forged delimiters from the input before wrapping it.
3. `detect_injection` matches 12 regex patterns and shows a warning in the app.
4. Lines that look like injected instructions are not accepted as evidence for a value (source grounding), so a value the attacker wrote ends up flagged.
5. The validator blocks any number not in the confirmed data. Confirmation is a human step.

The evaluation results for each layer are in [EVAL.md](EVAL.md#4-prompt-injection).

## Example outputs
Real outputs from the evaluation run (model `openai/gpt-oss-20b`, temperature 0) are listed in [EVAL.md](EVAL.md#example-outputs).
