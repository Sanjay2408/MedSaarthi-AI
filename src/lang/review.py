"""Native-speaker review of a language pack.

    python -m src.lang.review ta                 show every phrase next to the English one
    python -m src.lang.review ta --out ta.txt    the same, written to a file to send to a reviewer
    python -m src.lang.review ta --sign "Name"   mark the pack reviewed by that person, today

Sign only after a person who reads the language has checked every line and the corrections are
in the JSON file. The app then stops labelling that language "draft wording". The signature is a
claim about a real review: never sign on someone's behalf.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from src.lang.pack import PACK_DIR, REQUIRED, PackError, reload, validate


def _flat(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from _flat(v, f"{path}.{k}" if path else k)


def sheet(code: str, pack_dir: Path = PACK_DIR) -> str:
    """Every phrase with its English meaning, one block each."""
    data = json.loads((pack_dir / f"{code}.json").read_text(encoding="utf-8"))
    english = json.loads((PACK_DIR / "en.json").read_text(encoding="utf-8"))
    sections = [*REQUIRED, "units"]
    ref = dict(_flat({k: english.get(k, {}) for k in sections}))
    status = data["review"]["status"]
    out = [f"{data['name']} ({data['native']}): {status}",
           "Check each line: is it natural, polite and impossible to misread? {n} is a number, {patient} is a name.", ""]
    for path, text in _flat({k: data.get(k, {}) for k in sections}):
        out += [path, f"  English: {ref.get(path, '(no English line)')}", f"  {data['name']}: {text}", ""]
    return "\n".join(out)


def sign(code: str, reviewer: str, pack_dir: Path = PACK_DIR, today: date | None = None) -> dict:
    reviewer = reviewer.strip()
    if code == "en":
        raise PackError("English is the source text and is not signed here")
    if len(reviewer) < 2:
        raise PackError("give the reviewer's name")
    path = pack_dir / f"{code}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["review"] = {**data["review"], "status": "reviewed", "by": reviewer, "on": (today or date.today()).isoformat()}
    validate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reload()
    return data["review"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("code")
    ap.add_argument("--out", help="write the review sheet to this file")
    ap.add_argument("--sign", metavar="NAME", help="record that NAME has reviewed this pack")
    args = ap.parse_args()
    if not (PACK_DIR / f"{args.code}.json").exists():
        sys.exit(f"no language pack for '{args.code}'")
    if args.sign:
        review = sign(args.code, args.sign)
        print(f"{args.code}: reviewed by {review['by']} on {review['on']}")
        return
    text = sheet(args.code)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print("wrote", args.out)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()
