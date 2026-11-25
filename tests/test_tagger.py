"""The synthetic generator, the span decoder and the scorer. These are fast and need no trained weights."""
import json
import random

from src.tagger.models import HmmTagger, shape, token_labels, tokens
from src.tagger.spans import FIELDS, decode, norm, score
from src.tagger.synth import ALL_NAMES, L2I, LABELS, make_line, make_lines, split_names, write_lora_set


def test_name_split_is_disjoint_and_stable():
    train, held = split_names()
    assert not set(train) & set(held)
    assert set(train) | set(held) == set(ALL_NAMES)
    assert 0.15 < len(held) / len(ALL_NAMES) < 0.30
    assert split_names() == (train, held)


def test_labels_cover_every_character_and_decode_matches_gold():
    train, _ = split_names()
    for ln in make_lines(500, train, seed=5, noise=0.02):
        assert len(ln.labels) == len(ln.text)
        assert decode(ln.text, ln.labels) == ln.gold
        assert "name" in ln.gold  # every line has a medicine


def test_duration_connector_is_not_part_of_the_span():
    train, _ = split_names()
    seen = [ln.gold["duration"] for ln in make_lines(800, train, seed=6) if "duration" in ln.gold]
    assert seen and not any(d.lower().startswith(("x ", "for ")) for d in seen)


def test_missing_fields_stay_missing():
    train, _ = split_names()
    lines = make_lines(2000, train, seed=7)
    assert any("dose" not in l.gold for l in lines)
    assert any("duration" not in l.gold for l in lines)  # a field the paper does not state is never invented


def test_noise_changes_text_but_keeps_labels_aligned():
    train, _ = split_names()
    clean = make_lines(300, train, seed=8)
    noisy = make_lines(300, train, seed=8, noise=0.05)
    assert any(a.text != b.text for a, b in zip(clean, noisy))
    assert all(len(b.labels) == len(b.text) for b in noisy)


def test_held_out_names_never_appear_in_training_lines():
    train, held = split_names()
    text = " ".join(l.text.lower() for l in make_lines(3000, train, seed=9))
    leaked = [n for n in held if f" {n.lower()} " in f" {text} "]
    assert not leaked


def test_decode_longest_run_and_spaces():
    text = "Tab. Paracetamol 500 mg TDS"
    labels = [L2I["FORM"]] * 4 + [0] + [L2I["NAME"]] * 11 + [0] + [L2I["DOSE"]] * 6 + [0] + [L2I["FREQ"]] * 3
    assert decode(text, labels) == {"name": "Paracetamol", "dose": "500 mg", "frequency": "TDS"}


def test_score_counts_wrong_value_as_both_miss_and_false_alarm():
    gold = [{"name": "A", "dose": "5 mg"}]
    perfect = score(gold, gold)
    assert perfect["micro_f1"] == 1.0 and perfect["line_exact"] == 1.0
    wrong = score([{"name": "A", "dose": "50 mg"}], gold)
    assert wrong["dose"]["precision"] == 0.0 and wrong["dose"]["recall"] == 0.0
    assert wrong["line_exact"] == 0.0
    extra = score([{"name": "A", "dose": "5 mg", "duration": "3 days"}], gold)  # invented field lowers precision
    assert extra["duration"]["precision"] == 0.0 and extra["line_exact"] == 0.0
    assert norm("  After   FOOD ") == "after food"


def test_tokeniser_splits_letters_and_digits():
    assert [t for t, _, _ in tokens("500mg x5 1-0-1")] == ["500", "mg", "x", "5", "1", "-", "0", "-", "1"]
    assert shape("Paracetamol") == "SHAPE:Xx" and shape("500") == "SHAPE:0" and shape("TDS") == "SHAPE:X"


def test_hmm_learns_a_small_corpus_and_handles_an_unseen_name():
    train, held = split_names()
    hmm = HmmTagger(min_count=3).fit(make_lines(4000, train, seed=1))
    line = make_line(random.Random(3), held)
    pred = decode(line.text, hmm.predict(line.text))
    assert pred.get("name") == line.gold["name"]  # the shape of a word, not memory, identified it
    assert len(token_labels(line)) == len(tokens(line.text))
    assert hmm.predict("") == []


def test_lora_set_is_valid_chat_json_and_uses_the_right_names(tmp_path):
    train, held = split_names()
    write_lora_set(tmp_path / "t.jsonl", 40, seed=1)
    write_lora_set(tmp_path / "e.jsonl", 40, seed=2, held_out=True)
    for fname, pool in (("t.jsonl", train), ("e.jsonl", held)):
        rows = [json.loads(l) for l in (tmp_path / fname).read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 40
        low = {n.lower() for n in pool}
        for r in rows:
            roles = [m["role"] for m in r["messages"]]
            assert roles == ["system", "user", "assistant"]
            meds = json.loads(r["messages"][2]["content"])["medications"]
            assert meds and set(meds[0]) == {"name", "dose", "route", "frequency", "duration", "instructions"}
            assert len(low) > 40 and all(m["name"] for m in meds)
            assert "<<<PRESCRIPTION_DATA>>>" in r["messages"][1]["content"]
    assert set(FIELDS) == {"name", "dose", "frequency", "duration", "instructions"} and "O" in LABELS
