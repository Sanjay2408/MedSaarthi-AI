"""Loads versioned prompt files into LangChain ChatPromptTemplates.

File format (src/prompts/<name>.prompt):
    # header lines: id, version, technique, why
    === SYSTEM ===
    ...system template...
    === USER ===
    ...user template with {variables}...
Literal braces in templates are doubled ({{ }}), as in Python f-strings.
"""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

PROMPT_DIR = Path(__file__).resolve().parent


@dataclass
class Prompt:
    name: str
    meta: dict
    template: ChatPromptTemplate

    def render(self, **kwargs) -> tuple[str, str]:
        """Return (system, user) strings."""
        msgs = self.template.format_messages(**kwargs)
        return msgs[0].content, msgs[1].content

    @property
    def id(self) -> str:
        return f"{self.meta.get('id', self.name)}@{self.meta.get('version', '?')}"


@lru_cache(maxsize=None)
def load_prompt(name: str) -> Prompt:
    raw = (PROMPT_DIR / f"{name}.prompt").read_text(encoding="utf-8")
    header, rest = raw.split("=== SYSTEM ===", 1)
    system, user = rest.split("=== USER ===", 1)
    meta = {}
    for line in header.splitlines():
        line = line.lstrip("# ").strip()
        if ":" in line:
            k, v = line.split(":", 1)
            meta.setdefault(k.strip().lower(), v.strip())
    template = ChatPromptTemplate.from_messages([("system", system.strip()), ("human", user.strip())])
    return Prompt(name, meta, template)
