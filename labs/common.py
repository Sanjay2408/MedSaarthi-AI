"""Shared setup for the 15 lab programs (CS4204). Import with: from common import *"""
import os
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
OUT = HERE / "out"
DATA = HERE / "data"
OUT.mkdir(exist_ok=True)
DATA.mkdir(exist_ok=True)
os.environ.setdefault("GENSIM_DATA_DIR", str(DATA / "gensim"))
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def get_llm(temperature: float = 0.0):
    """Cohere when COHERE_API_KEY is set (what the course manual asks for), otherwise Groq.
    Returns (chat_model, label) so every notebook says which one produced its output."""
    if os.getenv("COHERE_API_KEY"):
        from langchain_cohere import ChatCohere

        return ChatCohere(model="command-a-03-2025", temperature=temperature), "Cohere command-a-03-2025"
    from langchain_groq import ChatGroq

    return ChatGroq(model="openai/gpt-oss-20b", temperature=temperature, max_retries=5), "Groq openai/gpt-oss-20b (no Cohere key available)"


def ask(llm, prompt: str) -> str:
    """One question, plain text back."""
    return llm.invoke(prompt).content.strip()
