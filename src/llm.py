"""Thin LLM client: Groq (default) or a local Hugging Face model.

- temperature 0 for reproducibility
- disk cache keyed by (model, messages) so evaluation reruns cost no tokens
- retries with back-off on rate limits (Groq free tier)
"""
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.config import ROOT, load_config

load_dotenv(ROOT / ".env")
CACHE_DIR = ROOT / ".cache" / "llm"


@dataclass
class LLMResult:
    text: str
    model_id: str
    latency_s: float
    cached: bool = False


class LLM:
    def __init__(self, model: str | None = None, backend: str | None = None, use_cache: bool = True):
        cfg = load_config()["llm"]
        self.backend = backend or cfg["backend"]
        self.model = model or (cfg["model"] if self.backend == "groq" else cfg["local_model"])
        self.temperature = cfg["temperature"]
        self.max_tokens = cfg["max_tokens"]
        self.use_cache = use_cache
        self._client = None
        self._local = None

    @property
    def model_id(self) -> str:
        return f"{self.backend}:{self.model}"

    def complete(self, system: str, user: str, json_mode: bool = False) -> LLMResult:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        key = hashlib.sha256(json.dumps([self.model_id, messages, json_mode]).encode()).hexdigest()
        cache_file = CACHE_DIR / f"{key}.json"
        if self.use_cache and cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            return LLMResult(data["text"], self.model_id, data["latency_s"], cached=True)

        start = time.perf_counter()
        text = self._groq(messages, json_mode) if self.backend == "groq" else self._hf(messages)
        latency = time.perf_counter() - start
        if self.use_cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"text": text, "latency_s": latency}), encoding="utf-8")
        return LLMResult(text, self.model_id, latency)

    def _groq(self, messages, json_mode) -> str:
        from groq import BadRequestError, Groq, RateLimitError

        if self._client is None:
            if not os.getenv("GROQ_API_KEY"):
                raise RuntimeError("GROQ_API_KEY missing: add it to .env")
            self._client = Groq()
        kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
        effort = load_config()["llm"].get("reasoning_effort")
        if effort and ("gpt-oss" in self.model or "qwen" in self.model):
            kwargs.update(reasoning_effort=effort, include_reasoning=False)
        for attempt in range(8):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model, messages=messages, temperature=self.temperature,
                    max_tokens=self.max_tokens, seed=0, **kwargs)
                return resp.choices[0].message.content or ""
            except BadRequestError as e:
                # json_mode can fail validation on malformed output; caller repairs/retries
                if json_mode and "json" in str(e).lower():
                    return ""
                raise
            except RateLimitError as e:
                wait = _retry_after(e) or min(60, 5 * 2 ** attempt)
                time.sleep(wait)
        raise RuntimeError("Groq rate limit: retries exhausted")

    def _hf(self, messages) -> str:
        from transformers import pipeline

        if self._local is None:
            self._local = pipeline("text-generation", model=self.model, device=-1)
        out = self._local(messages, max_new_tokens=self.max_tokens, do_sample=False)
        return out[0]["generated_text"][-1]["content"]


def _retry_after(err) -> float | None:
    try:
        hdr = err.response.headers.get("retry-after")
        if hdr:
            return float(hdr) + 1
    except Exception:
        pass
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(err))
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2)) + 1
    return None


def parse_json(text: str) -> dict | list | None:
    """Lenient JSON parsing: strips code fences/prose, fixes trailing commas."""
    if not text:
        return None
    t = re.sub(r"```(?:json)?", "", text).strip()
    start = min([i for i in (t.find("{"), t.find("[")) if i != -1], default=-1)
    if start == -1:
        return None
    end = max(t.rfind("}"), t.rfind("]"))
    candidate = t[start:end + 1]
    for attempt in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None
