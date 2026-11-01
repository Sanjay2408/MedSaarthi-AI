"""Builds and executes notebooks/eval.ipynb from outputs/eval/results.json.

    python notebooks/build_notebook.py
"""
from pathlib import Path

import nbformat
from nbconvert.preprocessors import ExecutePreprocessor

HERE = Path(__file__).resolve().parent

cells = [
    ("md", "# MedSaarthi AI: evaluation results\n\nAll tables are computed from `outputs/eval/results.json`, "
           "which `python -m src.eval.run_eval` writes. Synthetic data only (25 prescriptions). "
           "Human rubric scores are not included here; see `docs/EVAL.md`."),
    ("code", "import json, pandas as pd\nfrom pathlib import Path\n"
             "R = json.loads(Path('../outputs/eval/results.json').read_text(encoding='utf-8'))\n"
             "print('LLM:', R['model'])"),
    ("md", "## 1. Extraction: field accuracy (typed text), V1 baseline vs V2 engineered"),
    ("code", "pd.DataFrame({v: {**R['extract'][v]['per_field_pct'], 'overall': R['extract'][v]['overall_pct'],\n"
             "  'JSON parsed (of 25)': R['extract'][v]['json_parsed'], 'extra items': R['extract'][v]['extra_items']}\n"
             "  for v in ('v1', 'v2')})"),
    ("md", "## 2. OCR pipeline (image to V2 extraction)"),
    ("code", "pd.DataFrame(R['ocr']['by_category']).T"),
    ("code", "pd.DataFrame(R['ocr']['cases'])[['id','category','engine','mean_conf','cer','fields_correct','fields_total','items_flagged','ocr_s']]"),
    ("md", "## 3. Ambiguity detection (30 ground-truth items, 5 should be flagged)"),
    ("code", "pd.DataFrame({m: {k: R['ambiguity'][m][k] for k in ('tp','fp','fn','tn','precision','recall')} for m in R['ambiguity']})"),
    ("md", "## 4. Prompt injection"),
    ("code", "inj = pd.DataFrame(R['injection'])[['injection','variant','detected_by_code','llm_output_unchanged','safe_after_gate']]\n"
             "inj.groupby('variant')[['detected_by_code','llm_output_unchanged','safe_after_gate']].sum()"),
    ("code", "inj"),
    ("md", "## 5. Simplification: V1 baseline, V2 engineered, V3 engineered + RAG"),
    ("code", "S = R['simplify']['summary']\n"
             "pd.DataFrame({v: {k: S[v][k] for k in ('n','validator_pass_pct','median_fk_grade','median_words','median_latency_s','items_with_any_error')} for v in S})"),
    ("code", "pd.DataFrame({v: S[v]['taxonomy_counts'] for v in S}).fillna(0).astype(int)"),
    ("code", "rows = pd.DataFrame(R['simplify']['rows'])\nrows[rows.blocked][['id','drug','variant','errors']]"),
    ("md", "## 6. Translation (V2 outputs of clean samples)"),
    ("code", "pd.DataFrame(R['translate']['summary']).T if 'translate' in R else 'not run'"),
]

nb = nbformat.v4.new_notebook()
nb.cells = [nbformat.v4.new_markdown_cell(src) if kind == "md" else nbformat.v4.new_code_cell(src) for kind, src in cells]
ExecutePreprocessor(timeout=120, kernel_name="python3").preprocess(nb, {"metadata": {"path": str(HERE)}})
(HERE / "eval.ipynb").write_text(nbformat.writes(nb), encoding="utf-8")
print("wrote", HERE / "eval.ipynb")
