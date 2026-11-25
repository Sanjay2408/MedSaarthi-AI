"""Process-level state shared by the API modules: cases held in memory, sessions, rate limits.

A "case" is a prescription being worked on. It lives in memory only and belongs to one browser
(the `ms_session` cookie). Saving it to an account is a separate, opt-in step (api/records.py).
"""
import os
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field

from fastapi import HTTPException, Request

from src import audit
from src.pipeline import Stage1, Stage2

PUBLIC = os.getenv("MEDSAARTHI_PUBLIC") == "1"
COOKIE = "ms_session"
MAX_CASES = 200
LIMITS = {"read": int(os.getenv("READS_PER_HOUR", "30")), "guide": int(os.getenv("GUIDES_PER_HOUR", "60")),
          "signup": 10, "login": 20}


@dataclass
class Case:
    id: str
    session: str
    patient: str
    stage1: Stage1
    image: bytes | None = None
    cacheable: bool = False  # True only for synthetic samples
    guides: dict = field(default_factory=dict)
    last_guide: Stage2 | None = None
    last_prefs: dict = field(default_factory=dict)
    last_payload: dict = field(default_factory=dict)


CASES: dict[str, Case] = {}
consented: set[str] = set()
hits: dict[tuple[str, str], deque] = defaultdict(deque)
hits_lock = threading.Lock()


def session_id(request: Request) -> str:
    """Runs inside each endpoint's thread, so audit rows land in this browser's log."""
    sid = request.state.session
    audit.use_session(sid)
    return sid


def get_case(case_id: str, request: Request) -> Case:
    case = CASES.get(case_id)
    if case is None or case.session != session_id(request):
        raise HTTPException(404, "This prescription is no longer in memory. Please add it again.")
    return case


def client_address(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def rate_limit(request: Request, bucket: str, window_s: int = 3600, key: str = "") -> None:
    now = time.monotonic()
    with hits_lock:
        q = hits[(client_address(request) + key, bucket)]
        while q and now - q[0] > window_s:
            q.popleft()
        if len(q) >= LIMITS[bucket]:
            raise HTTPException(429, "That's a lot of requests for this demo. Please try again in a little while.")
        q.append(now)


def remember(case: Case) -> None:
    CASES[case.id] = case
    while len(CASES) > MAX_CASES:
        CASES.pop(next(iter(CASES)))


SESSION_RE = re.compile(r"[0-9a-f]{32}")
