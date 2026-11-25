"""Benchmark of translation providers on medication-instruction text.

    python -m src.eval.lang_bench --n 12 --langs hi,kn,ta,te \
        --providers groq:openai/gpt-oss-120b,groq:openai/gpt-oss-20b,groq:qwen/qwen3.8-27b,nllb

Results append to outputs/eval/lang_bench.json after every call, so an interrupted run resumes.

What it measures, per provider and language:
  latency      seconds per request of up to 5 lines, model time only (rate-limit sleeps excluded)
  checked      share of lines that pass src.mt.check: right script, same numbers, drug name kept
  chrF         back-translation to English by gpt-oss-120b, scored against the original. This is a
               PROXY: a fluent wrong translation can back-translate well, and the back-translator is
               itself a model. It is not a quality score. Native-speaker rating is the real measure.
The template realiser is timed as the reference: it needs no provider and cannot change a number.
"""
import argparse
import json
import statistics
import time
from pathlib import Path

from sacrebleu.metrics import CHRF

from src.config import ROOT
from src.lang import render
from src.mt import GroqMT, NLLBMT, SarvamMT, check, lang_info
from src.translate import strip_times

OUT = ROOT / "outputs" / "eval" / "lang_bench.json"
BATCH = 5


def test_lines(n: int) -> list[dict]:
    """The English the translator would really see: instruction lines from the V2 evaluation."""
    rows = json.loads((ROOT / "outputs" / "eval" / "results.json").read_text(encoding="utf-8"))["simplify"]["rows"]
    seen, lines = set(), []
    for r in rows:
        if r["variant"] != "v2":
            continue
        for raw in r["final_text"].splitlines():
            text = strip_times(raw)
            if text and text not in seen and not text.startswith(("Keep this", "Not medical")):
                seen.add(text)
                lines.append({"text": text, "drug": r["drug"]})
        if len(lines) >= n:
            break
    return lines[:n] + [{"text": "Keep this medicine in a cool, dry place, out of the reach of children.", "drug": ""},
                        {"text": "Not medical advice. Confirm with your pharmacist or doctor.", "drug": ""}]


def make_provider(spec: str):
    if spec.startswith("groq:"):
        return GroqMT(spec.split(":", 1)[1])
    return {"nllb": NLLBMT, "sarvam": SarvamMT}[spec]()


def load() -> list[dict]:
    return json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else []


def save(records: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")


def run(n: int, langs: list[str], providers: list[str]) -> None:
    lines = test_lines(n)
    records = load()
    done = {(r["provider"], r["lang"], r["batch"]) for r in records}
    backtranslator = GroqMT("openai/gpt-oss-120b")
    chrf = CHRF()
    for spec in providers:
        provider = make_provider(spec)
        if not provider.available():
            print(f"skip {spec}: no key")
            continue
        for lang in langs:
            for b in range(0, len(lines), BATCH):
                batch = lines[b:b + BATCH]
                key = (spec, lang, b // BATCH)
                if key in done:
                    continue
                texts = [x["text"] for x in batch]
                start = time.perf_counter()
                error, out = None, []
                try:
                    out = provider.translate(texts, lang)
                except Exception as e:  # noqa: BLE001
                    error = f"{type(e).__name__}: {str(e)[:120]}"
                wall = time.perf_counter() - start
                latency = getattr(provider, "last_latency_s", 0.0) or wall
                per_line = []
                problems = check(texts, out, lang) if not error else ["error"]
                for i, (src, o) in enumerate(zip(texts, out)):
                    p = check([src], [o], lang, (batch[i]["drug"],) if batch[i]["drug"] else ())
                    per_line.append({"source": src, "output": o, "problems": p})
                back = []
                if out and not error:
                    try:
                        back = backtranslator.translate(out, "en", src=lang)
                        for pl, bt in zip(per_line, back):
                            pl["back"] = bt
                            pl["chrf"] = round(chrf.sentence_score(bt, [pl["source"]]).score, 1)
                    except Exception as e:  # noqa: BLE001
                        print("  back-translation failed:", type(e).__name__)
                records.append({"provider": spec, "lang": lang, "batch": b // BATCH, "lines": len(texts), "latency_s": round(latency, 2),
                                "wall_s": round(wall, 2), "error": error, "batch_problems": problems, "per_line": per_line})
                save(records)
                ok = sum(not x["problems"] for x in per_line)
                print(f"{spec:32s} {lang} batch {b // BATCH}: {latency:5.1f}s  {ok}/{len(texts)} lines pass  {error or ''}", flush=True)


def summarise(records: list[dict] | None = None) -> dict:
    records = records if records is not None else load()
    out = {}
    for spec in sorted({r["provider"] for r in records}):
        for lang in sorted({r["lang"] for r in records if r["provider"] == spec}):
            rs = [r for r in records if r["provider"] == spec and r["lang"] == lang]
            lines = [x for r in rs for x in r["per_line"]]
            if not lines:
                continue
            lat = [r["latency_s"] for r in rs if not r["error"]]
            scores = [x["chrf"] for x in lines if "chrf" in x]
            out.setdefault(spec, {})[lang] = {
                "lines": len(lines),
                "checked_pct": round(100 * sum(not x["problems"] for x in lines) / len(lines), 1),
                "numbers_ok_pct": round(100 * sum(not any("numbers" in p for p in x["problems"]) for x in lines) / len(lines), 1),
                "script_ok_pct": round(100 * sum(not any("not written" in p for p in x["problems"]) for x in lines) / len(lines), 1),
                # Policy, not corruption: the app shows the drug name as printed on the box. A model that
                # transliterates "Paracetamol" into Devanagari fails this but may still be correct.
                "drug_kept_latin_pct": round(100 * sum(not any("drug name" in p for p in x["problems"]) for x in lines) / len(lines), 1),
                "median_latency_s": round(statistics.median(lat), 2) if lat else None,
                "max_latency_s": max(lat) if lat else None,
                "median_chrf_back": round(statistics.median(scores), 1) if scores else None,
                "errors": sum(1 for r in rs if r["error"]),
            }
    return out


def realiser_timing() -> dict:
    """The template path: time to write a full card in every pack, from the 25 sample items."""
    from tests.test_lang import make, times_for, sample_items  # reuse the sample loader

    items = [p.values[0] for p in sample_items()]
    ms = {}
    for code in ("hi", "kn", "ta", "te"):
        t = []
        for truth in items:
            item = make(**{k: truth[k] for k in ("name", "dose", "route", "frequency", "duration", "instructions")})
            s = time.perf_counter()
            render(item, times_for(item), code)
            t.append((time.perf_counter() - s) * 1000)
        ms[code] = {"cards": len(t), "median_ms": round(statistics.median(t), 3), "max_ms": round(max(t), 3)}
    return ms


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--langs", default="hi,kn,ta,te")
    ap.add_argument("--providers", default="groq:openai/gpt-oss-120b,groq:openai/gpt-oss-20b,groq:qwen/qwen3.8-27b")
    ap.add_argument("--summary", action="store_true")
    a = ap.parse_args()
    if not a.summary:
        run(a.n, a.langs.split(","), a.providers.split(","))
    print(json.dumps({"summary": summarise(), "realiser": realiser_timing()}, ensure_ascii=False, indent=1))
