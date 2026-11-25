"""Train and evaluate the T1 taggers on this laptop.

    python -m src.tagger.train [--n 100000] [--epochs 4]

Writes weights to src/tagger/weights/ (small, committed) and the numbers to outputs/eval/tagger.json.
Test sets, all built from seeds the training never saw:
  seen_clean       new lines, medicine names the models trained on
  unseen_clean     medicine names held out of training entirely
  unseen_noisy     held-out names plus OCR-style slips
  reference_25     the 25 hand-written prescriptions from data/generate_samples.py (typed text),
                   written separately from this generator. Names are in the vocabulary.
Synthetic-to-synthetic scores flatter a model; reference_25 and unseen_noisy are the honest ones.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import time
from pathlib import Path

import torch
from torch import nn

from src.tagger.models import N, BiLstmTagger, CharVocab, HmmTagger, batchify, predict_lstm, save_hmm, save_lstm
from src.tagger.spans import decode, score
from src.tagger.synth import make_lines, split_names

ROOT = Path(__file__).resolve().parents[2]
WEIGHTS = Path(__file__).resolve().parent / "weights"


def reference_25() -> tuple[list[str], list[dict[str, str]]]:
    texts, gold = [], []
    for jf in sorted((ROOT / "data" / "samples").glob("S*.json")):
        truth = json.loads(jf.read_text(encoding="utf-8"))
        lines = [l for l in jf.with_suffix(".txt").read_text(encoding="utf-8").splitlines() if re.match(r"\s*\d+\.\s", l)]
        if len(lines) != len(truth["items"]):
            continue
        for line, it in zip(lines, truth["items"]):
            texts.append(line)
            gold.append({k: v for k, v in (("name", it["name"]), ("dose", it["dose"]), ("frequency", it["frequency"]),
                                           ("duration", it["duration"]), ("instructions", it["instructions"])) if v})
    return texts, gold


def train_lstm(train, val, epochs: int, seed: int = 0) -> tuple[BiLstmTagger, CharVocab, list[dict]]:
    torch.manual_seed(seed)
    rng = random.Random(seed)
    vocab = CharVocab.build([l.text for l in train])
    model = BiLstmTagger(len(vocab.itos))
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3, weight_decay=1e-4)
    steps = epochs * ((len(train) + 511) // 512)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=3e-3, total_steps=steps)
    loss_fn = nn.CrossEntropyLoss(ignore_index=-100)
    history = []
    for ep in range(epochs):
        model.train()
        order = list(range(len(train)))
        rng.shuffle(order)
        t0, total, n = time.perf_counter(), 0.0, 0
        for i in range(0, len(order), 512):
            x, y, lengths = batchify(vocab, [train[j] for j in order[i:i + 512]], unk_dropout=0.02, rng=rng)
            loss = loss_fn(model(x, lengths).reshape(-1, N), y.reshape(-1))
            opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            total, n = total + loss.item(), n + 1
        pred = predict_lstm(model, vocab, [l.text for l in val])
        f = score([decode(l.text, p) for l, p in zip(val, pred)], [l.gold for l in val])["micro_f1"]
        history.append({"epoch": ep + 1, "train_loss": round(total / n, 4), "val_micro_f1": f, "seconds": round(time.perf_counter() - t0, 1)})
        print(history[-1], flush=True)
    return model, vocab, history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100_000)
    ap.add_argument("--epochs", type=int, default=3)
    args = ap.parse_args()

    train_names, held = split_names()
    print(f"{len(train_names)} training names, {len(held)} held out", flush=True)
    train = make_lines(args.n, train_names, seed=1, noise=0.01)
    val = make_lines(4000, train_names, seed=2, noise=0.01)
    sets = {
        "seen_clean": make_lines(5000, train_names, seed=11),
        "unseen_clean": make_lines(5000, held, seed=12),
        "unseen_noisy": make_lines(5000, held, seed=13, noise=0.03),
    }

    t0 = time.perf_counter()
    hmm = HmmTagger().fit(train)
    hmm_s = time.perf_counter() - t0
    model, vocab, history = train_lstm(train, val, args.epochs)

    ref_texts, ref_gold = reference_25()
    results: dict = {"n_train": args.n, "train_names": len(train_names), "held_out_names": len(held), "hmm_fit_seconds": round(hmm_s, 1),
                     "lstm_params": sum(p.numel() for p in model.parameters()), "history": history, "tests": {}}

    def evaluate(name: str, texts: list[str], gold: list[dict]):
        t = time.perf_counter()
        hp = [decode(x, hmm.predict(x)) for x in texts]
        t_h = time.perf_counter() - t
        t = time.perf_counter()
        lp = [decode(x, p) for x, p in zip(texts, predict_lstm(model, vocab, texts))]
        t_l = time.perf_counter() - t
        results["tests"][name] = {"hmm": score(hp, gold), "bilstm": score(lp, gold),
                                  "ms_per_line": {"hmm": round(1000 * t_h / len(texts), 3), "bilstm_batched": round(1000 * t_l / len(texts), 3)}}
        print(name, "HMM", results["tests"][name]["hmm"]["micro_f1"], "BiLSTM", results["tests"][name]["bilstm"]["micro_f1"], flush=True)
        # the lines the neural model gets wrong, kept so the report can say what kind of mistakes they are
        wrong = [{"line": x, "gold": g, "bilstm": p} for x, g, p in zip(texts, gold, lp) if p != g][:12]
        results["tests"][name]["bilstm_errors_sample"] = wrong

    for name, ls in sets.items():
        evaluate(name, [l.text for l in ls], [l.gold for l in ls])
    evaluate("reference_25", ref_texts, ref_gold)

    WEIGHTS.mkdir(parents=True, exist_ok=True)
    save_lstm(WEIGHTS / "t1_bilstm.pt", model, vocab)
    save_hmm(WEIGHTS / "t1_hmm.json", hmm)
    out = ROOT / "outputs" / "eval" / "tagger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
