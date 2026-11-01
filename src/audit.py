"""Append-only audit trail. Logs step, model id and a SHA-256 of the input.

Raw prescription text is never written to disk.
"""
import hashlib
import json
import time
import uuid
from pathlib import Path

from src.config import ROOT, load_config

SESSION_ID = uuid.uuid4().hex[:12]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def log_step(step: str, model_id: str | None, input_text: str, **meta) -> dict:
    """meta must not contain raw prescription text; only counts, flags, codes."""
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "session": SESSION_ID,
        "step": step,
        "model": model_id,
        "input_sha256": sha256(input_text),
        **meta,
    }
    path = ROOT / load_config()["audit"]["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_session(session_id: str | None = None) -> list[dict]:
    path = ROOT / load_config()["audit"]["path"]
    if not path.exists():
        return []
    sid = session_id or SESSION_ID
    with open(path, encoding="utf-8") as f:
        return [r for r in map(json.loads, f) if r.get("session") == sid]
