"""Figures for the report: cropped app screenshots and the tagger comparison chart.

    python scripts/make_figures.py

Screenshots come from the automated browser test (python tests/e2e_web.py outputs/screens_new) on
synthetic accounts. The chart reads outputs/eval/tagger.json. Output goes to docs/figures/ (committed).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "outputs" / "screens_new"
OUT = ROOT / "docs" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

CROPS = {  # file -> (name, right fraction of width, bottom as a fraction of width)
    "11-phone-plan.png": ("app_phone_plan.png", 1.0, 1.9),
    "13-settings-senior.png": ("app_settings.png", 0.85, 0.70),
    "14-pharmacist-queue.png": ("app_pharmacist_queue.png", 0.95, 0.72),
    "5-plan-hindi.png": ("app_plan_hindi.png", 1.0, 1.1),
}
for src, (name, r, b) in CROPS.items():
    p = SHOTS / src
    if p.exists():
        im = Image.open(p)
        w, h = im.size
        im.crop((0, 0, int(r * w), min(h, int(b * w)))).save(OUT / name)
        print("wrote", name)

t = json.loads((ROOT / "outputs" / "eval" / "tagger.json").read_text(encoding="utf-8"))["tests"]
names = ["seen_clean", "unseen_clean", "unseen_noisy", "reference_25"]
labels = ["New lines,\nknown names", "Unseen\nmedicine names", "Unseen names\n+ OCR noise", "25 hand-written\nprescriptions (30 lines)"]
fig, ax = plt.subplots(figsize=(8, 3.6))
x = range(len(names))
hm = [100 * t[n]["hmm"]["micro_f1"] for n in names]
bl = [100 * t[n]["bilstm"]["micro_f1"] for n in names]
ax.bar([i - 0.2 for i in x], hm, 0.4, label="HMM", color="#9AB5AE")
ax.bar([i + 0.2 for i in x], bl, 0.4, label="BiLSTM", color="#0B6B5F")
for i, (a, b) in enumerate(zip(hm, bl)):
    ax.text(i - 0.2, a + 0.4, f"{a:.1f}", ha="center", fontsize=8)
    ax.text(i + 0.2, b + 0.4, f"{b:.1f}", ha="center", fontsize=8)
ax.set_xticks(list(x), labels, fontsize=8)
ax.set_ylim(80, 103)
ax.set_ylabel("Field F1 (%)")
ax.legend(frameon=False, loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.22))
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.set_title("T1 taggers on four test sets (axis starts at 80%)", fontsize=10)
plt.tight_layout()
plt.savefig(OUT / "tagger_f1.png", dpi=170)
print("wrote tagger_f1.png")
