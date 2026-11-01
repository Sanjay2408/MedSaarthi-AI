"""RAG over patient leaflets (step 6), following de Jesus et al. 2025:

1. fetch the leaflet for the prescribed drug on demand (local data/leaflets/)
2. chunk: chunk_size 2900, chunk_overlap 2100 (their best setting)
3. embed with BGE-M3, retrieve top-2 chunks for "How should I use this medicine?"
4. summarise with "Extract and summarize dosage" BEFORE adding to the generation prompt

Leaflets here are synthetic and short, so most produce 1-2 chunks; noted in the report.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rapidfuzz import fuzz, process

from src.audit import log_step
from src.config import ROOT, load_config
from src.llm import LLM
from src.prompts import load_prompt

LEAFLET_DIR = ROOT / "data" / "leaflets"


@dataclass
class RAGResult:
    drug: str
    leaflet: str | None
    chunks: list[str]
    scores: list[float]
    summary: str | None


def find_leaflet(drug: str | None) -> Path | None:
    if not drug:
        return None
    files = {p.stem: p for p in LEAFLET_DIR.glob("*.md")}
    match = process.extractOne(drug.lower(), list(files), scorer=fuzz.ratio)
    return files[match[0]] if match and match[1] >= 80 else None


def chunk(text: str) -> list[str]:
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    cfg = load_config()["rag"]
    splitter = RecursiveCharacterTextSplitter(chunk_size=cfg["chunk_size"], chunk_overlap=cfg["chunk_overlap"])
    return splitter.split_text(text)


@lru_cache(maxsize=1)
def _embedder():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(load_config()["rag"]["embedding_model"], device="cpu")


def retrieve(chunks: list[str], query: str, k: int) -> tuple[list[str], list[float]]:
    model = _embedder()
    q = model.encode([query], normalize_embeddings=True)
    c = model.encode(chunks, normalize_embeddings=True)
    sims = (c @ q.T).ravel()
    order = sims.argsort()[::-1][:k]
    return [chunks[i] for i in order], [round(float(sims[i]), 4) for i in order]


_SUMMARY_CACHE: dict[tuple[str, str], RAGResult] = {}


def leaflet_context(drug: str | None, llm: LLM | None = None) -> RAGResult:
    llm = llm or LLM()
    key = ((drug or "").lower(), llm.model_id)
    if key in _SUMMARY_CACHE:
        return _SUMMARY_CACHE[key]
    path = find_leaflet(drug)
    if path is None:
        result = RAGResult(drug or "", None, [], [], None)
    else:
        cfg = load_config()["rag"]
        chunks, scores = retrieve(chunk(path.read_text(encoding="utf-8")), cfg["query"], cfg["top_k"])
        system, user = load_prompt("rag_summary").render(drug=drug, chunks="\n---\n".join(chunks))
        summary = llm.complete(system, user).text.strip()
        log_step("rag_summary", llm.model_id, "".join(chunks), leaflet=path.name, n_chunks=len(chunks))
        result = RAGResult(drug, path.name, chunks, scores, summary)
    _SUMMARY_CACHE[key] = result
    return result
