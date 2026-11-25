"""Write the T2 fine-tuning data. Nothing here is a real prescription.

    python scripts/make_lora_data.py [--n 20000]

data/synth/t2_train.jsonl   N examples, medicine names from the training split only
data/synth/t2_eval.jsonl    500 examples with the HELD-OUT names, used before and after fine-tuning
Both are chat-format JSONL (system, user, assistant). They are git-ignored; this script rebuilds
them from fixed seeds, so the Kaggle notebook can either upload them or regenerate them.
"""
import argparse
from pathlib import Path

from src.tagger.synth import split_names, write_lora_set

OUT = Path(__file__).resolve().parents[1] / "data" / "synth"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000)
    args = ap.parse_args()
    write_lora_set(OUT / "t2_train.jsonl", args.n, seed=7, noise=0.01)
    write_lora_set(OUT / "t2_eval.jsonl", 500, seed=99, noise=0.01, held_out=True)
    train, held = split_names()
    print(f"wrote {args.n} train and 500 eval examples to {OUT} ({len(train)} train names, {len(held)} held-out names)")


if __name__ == "__main__":
    main()
