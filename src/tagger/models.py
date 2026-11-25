"""Two taggers for one prescription line, so the classical and the neural answer can be compared.

HmmTagger   hidden Markov model over tokens, Viterbi decoding (Module 2 of the syllabus).
            Words it has not seen are described by their shape (Xxxx, 0, x), which is how it
            still recognises a medicine name it was never trained on.
BiLstmTagger  character-level bidirectional LSTM (Module 3). Reading characters, not words, is
            what lets it cope with OCR slips and unseen names.
Both return one label id per character, so they are scored by the same code.
"""
from __future__ import annotations

import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import torch
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence

from src.tagger.synth import LABELS, Line

TOKEN = re.compile(r"\d+|[A-Za-z]+|[^\sA-Za-z\d]")
N = len(LABELS)


def tokens(text: str) -> list[tuple[str, int, int]]:
    return [(m.group(), m.start(), m.end()) for m in TOKEN.finditer(text)]


def shape(tok: str) -> str:
    if tok.isdigit():
        return "SHAPE:0"
    if tok.isalpha():
        return "SHAPE:X" if tok.isupper() and len(tok) > 1 else "SHAPE:Xx" if tok[0].isupper() else "SHAPE:x"
    return "SHAPE:" + tok


def token_labels(line: Line) -> list[int]:
    out = []
    for _, a, b in tokens(line.text):
        c = Counter(l for ch, l in zip(line.text[a:b], line.labels[a:b]) if not ch.isspace())
        out.append(c.most_common(1)[0][0] if c else 0)
    return out


class HmmTagger:
    def __init__(self, min_count: int = 5, k: float = 0.02):
        self.min_count, self.k = min_count, k
        self.vocab: set[str] = set()
        self.emit: list[dict[str, float]] = []
        self.trans: list[list[float]] = []
        self.start: list[float] = []

    def fit(self, lines: list[Line], seed: int = 0, shape_dropout: float = 0.2) -> "HmmTagger":
        rng = random.Random(seed)
        counts = Counter(t.lower() for ln in lines for t, _, _ in tokens(ln.text))
        self.vocab = {w for w, c in counts.items() if c >= self.min_count}
        em = [Counter() for _ in range(N)]
        tr = [[0.0] * N for _ in range(N)]
        st = [0.0] * N
        for ln in lines:
            toks, labs = tokens(ln.text), token_labels(ln)
            prev = None
            for (t, _, _), lb in zip(toks, labs):
                sym = t.lower() if t.lower() in self.vocab else shape(t)
                # a share of names are shown only by shape, so the model learns what an unknown name looks like
                if lb == 2 and rng.random() < shape_dropout:
                    sym = shape(t)
                em[lb][sym] += 1
                if prev is None:
                    st[lb] += 1
                else:
                    tr[prev][lb] += 1
                prev = lb
        symbols = {s for c in em for s in c} | {"SHAPE:Xx", "SHAPE:x", "SHAPE:X", "SHAPE:0"}
        V = len(symbols)
        self.emit = []
        for c in em:
            total = sum(c.values()) + self.k * V
            self.emit.append({s: math.log((c[s] + self.k) / total) for s in symbols})
        self.trans = [[math.log((tr[i][j] + self.k) / (sum(tr[i]) + self.k * N)) for j in range(N)] for i in range(N)]
        self.start = [math.log((st[i] + self.k) / (sum(st) + self.k * N)) for i in range(N)]
        return self

    def _sym(self, tok: str) -> str:
        low = tok.lower()
        return low if low in self.vocab and low in self.emit[0] else shape(tok)

    def predict(self, text: str) -> list[int]:
        toks = tokens(text)
        out = [0] * len(text)
        if not toks:
            return out
        syms = [self._sym(t) for t, _, _ in toks]
        floor = math.log(self.k / 1e6)
        delta = [[self.start[s] + self.emit[s].get(syms[0], floor) for s in range(N)]]
        back: list[list[int]] = []
        for t in range(1, len(toks)):
            row, bp = [], []
            for s in range(N):
                best = max(range(N), key=lambda p: delta[-1][p] + self.trans[p][s])
                row.append(delta[-1][best] + self.trans[best][s] + self.emit[s].get(syms[t], floor))
                bp.append(best)
            delta.append(row)
            back.append(bp)
        path = [max(range(N), key=lambda s: delta[-1][s])]
        for bp in reversed(back):
            path.append(bp[path[-1]])
        path.reverse()
        for (_, a, b), lb in zip(toks, path):
            out[a:b] = [lb] * (b - a)
        # a space between two characters of one field belongs to that field
        for i, ch in enumerate(text):
            if ch.isspace() and 0 < i < len(text) - 1 and out[i - 1] == out[i + 1]:
                out[i] = out[i - 1]
        return out


# ------------------------------------------------------------------ neural

class BiLstmTagger(nn.Module):
    def __init__(self, vocab_size: int, emb: int = 48, hidden: int = 64, layers: int = 2, dropout: float = 0.2):
        super().__init__()
        self.emb = nn.Embedding(vocab_size, emb, padding_idx=0)
        self.rnn = nn.LSTM(emb, hidden, num_layers=layers, bidirectional=True, batch_first=True, dropout=dropout)
        self.drop = nn.Dropout(dropout)
        self.out = nn.Linear(2 * hidden, N)

    def forward(self, x: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        packed = pack_padded_sequence(self.emb(x), lengths.cpu(), batch_first=True, enforce_sorted=False)
        h, _ = self.rnn(packed)
        h, _ = pad_packed_sequence(h, batch_first=True, total_length=x.shape[1])
        return self.out(self.drop(h))


class CharVocab:
    def __init__(self, chars: list[str]):
        self.itos = ["<pad>", "<unk>"] + chars
        self.stoi = {c: i for i, c in enumerate(self.itos)}

    @classmethod
    def build(cls, texts: list[str], min_count: int = 3) -> "CharVocab":
        c = Counter(ch for t in texts for ch in t)
        return cls(sorted(ch for ch, n in c.items() if n >= min_count))

    def encode(self, text: str) -> list[int]:
        return [self.stoi.get(ch, 1) for ch in text]


def batchify(vocab: CharVocab, lines: list[Line], unk_dropout: float = 0.0, rng: random.Random | None = None):
    enc = [vocab.encode(l.text) for l in lines]
    if unk_dropout and rng:
        enc = [[1 if rng.random() < unk_dropout else c for c in e] for e in enc]
    n = max(len(e) for e in enc)
    x = torch.zeros(len(enc), n, dtype=torch.long)
    y = torch.full((len(enc), n), -100, dtype=torch.long)
    lengths = torch.tensor([len(e) for e in enc])
    for i, (e, l) in enumerate(zip(enc, lines)):
        x[i, :len(e)] = torch.tensor(e)
        y[i, :len(e)] = torch.tensor(l.labels)
    return x, y, lengths


@torch.no_grad()
def predict_lstm(model: BiLstmTagger, vocab: CharVocab, texts: list[str], batch: int = 512) -> list[list[int]]:
    model.eval()
    out: list[list[int]] = []
    for i in range(0, len(texts), batch):
        chunk = [Line(t, [0] * len(t), {}) for t in texts[i:i + batch]]
        x, _, lengths = batchify(vocab, chunk)
        pred = model(x, lengths).argmax(-1)
        out += [pred[j, :len(t)].tolist() for j, t in enumerate(texts[i:i + batch])]
    return out


def save_lstm(path: Path, model: BiLstmTagger, vocab: CharVocab):
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state": model.state_dict(), "chars": vocab.itos[2:], "labels": LABELS,
                "shape": {"vocab": model.emb.num_embeddings, "emb": model.emb.embedding_dim, "hidden": model.rnn.hidden_size,
                          "layers": model.rnn.num_layers}}, path)


def load_lstm(path: Path) -> tuple[BiLstmTagger, CharVocab]:
    blob = torch.load(path, map_location="cpu", weights_only=True)
    s = blob["shape"]
    model = BiLstmTagger(s["vocab"], s["emb"], s["hidden"], s["layers"])
    model.load_state_dict(blob["state"])
    model.eval()
    return model, CharVocab(blob["chars"])


def save_hmm(path: Path, hmm: HmmTagger):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"vocab": sorted(hmm.vocab), "emit": hmm.emit, "trans": hmm.trans, "start": hmm.start,
                                "k": hmm.k, "min_count": hmm.min_count}), encoding="utf-8")


def load_hmm(path: Path) -> HmmTagger:
    d = json.loads(path.read_text(encoding="utf-8"))
    h = HmmTagger(d["min_count"], d["k"])
    h.vocab, h.emit, h.trans, h.start = set(d["vocab"]), d["emit"], d["trans"], d["start"]
    return h
