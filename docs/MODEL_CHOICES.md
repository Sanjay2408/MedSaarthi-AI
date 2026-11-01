# Model choices

Hardware: Intel Core i5-11320H, 16 GB RAM, Intel Iris Xe (no CUDA GPU), Windows 11, Python 3.12.
Licence, gating and parameter counts were read from the Hugging Face model cards through `huggingface_hub` on 2026-11-01.

| Task | Chosen | Licence / gating | Size | Runs on | Why |
|---|---|---|---|---|---|
| Extraction, ambiguity CoT, simplification, RAG summary | `openai/gpt-oss-20b` served by Groq | Apache-2.0, open weights, not gated | 20.9 B total params (mixture of experts) | Groq API | Open-weight model on Hugging Face, fast on Groq, temperature 0. Hidden reasoning set to `low`. |
| Optional larger LLM (app dropdown) | `openai/gpt-oss-120b` (Groq) | Apache-2.0 | 116.8 B total params | Groq API | For comparison in the demo. Not used in the evaluation. |
| Printed OCR | EasyOCR (`en`) | Apache-2.0 | small CRAFT detector + CRNN recogniser | CPU | Gives a confidence score for each word, which feeds the safety gate. |
| Handwriting OCR | `microsoft/trocr-base-handwritten` | MIT, not gated | 333 M params | CPU | Reads one line at a time. EasyOCR supplies the line boxes. Confidence is the mean token probability. |
| Translation | `facebook/nllb-200-distilled-600M` | **CC-BY-NC-4.0** (non-commercial), not gated | 600 M params | CPU | Covers hi, kn, ta and te. Installs easily on Windows and runs on CPU. Its non-commercial licence suits a course project but not a product. |
| Embeddings (RAG) | `BAAI/bge-m3` | MIT, not gated | about 568 M params | CPU | The same embedding model that Paper B (de Jesus et al. 2025) used. |

## Considered but not used

| Model | Reason |
|---|---|
| `meta-llama/Llama-3.2-3B-Instruct` | Gated (manual approval). On CPU only it would run at a few tokens per second, too slow to evaluate 25 samples × 3 variants. |
| `Qwen/Qwen2.5-7B-Instruct` (4-bit) | Needs a CUDA GPU for bitsandbytes 4-bit; this laptop has none. |
| Groq-hosted Llama 3.x (named in the project brief) | **No longer offered** by the Groq account on 2026-11-01. The API returned only gpt-oss-20b/120b, qwen3.8-27b, allam-2-7b, Whisper and prompt-guard models. gpt-oss-20b is the closest open-weight replacement. |
| `ai4bharat/indictrans2-en-indic-1B` | Probably better Indic quality, but it is gated (accept terms), larger (1.1 B), and needs IndicTransToolkit, which is hard to install on Windows. Kept as `translation.alt_model` in `config.yaml`. |
| `Qwen/Qwen2.5-VL-3B-Instruct` (photo to JSON in one step) | 3.75 B params. Too slow on CPU for a fair comparison, so not attempted. Listed as future work. |
| `d4data/biomedical-ner-all` (sanity NER) | Optional in the brief. Source grounding (`src/extract.py`) already catches values that are not in the text. |

## Consequences to state honestly
- The papers used Llama 3.1 8B and ChatGPT-4.0. This project uses gpt-oss-20b, so the numbers are not directly comparable to theirs.
- The LLM runs in the cloud (Groq), so the extracted prescription text leaves the device. The consent screen says so. A fully local deployment would need a GPU or a much smaller model.
- `local` backend in `config.yaml` (`Qwen/Qwen2.5-1.5B-Instruct` via Transformers) exists for offline use but was not evaluated.
