"""Accounts: sign up, log in, log out, delete.

The `ms_auth` cookie carries a random token; the database keeps only its hash. Login failures are
throttled per address and per email, and an unknown email takes as long as a wrong password so the
response time does not reveal which emails have accounts. Pharmacist accounts cannot be created by
visitors: they need an invite code set by the server owner (a real system would check a registration
number with the State Pharmacy Council).
"""
import os
import re
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api import security
from api.db import get_db
from api.models import CONSENT_VERSION, ROLES, AuthSession, Profile, User, now
from api.state import PUBLIC, client_address, rate_limit
from src import audit
from src.lang import available as lang_available

router = APIRouter(prefix="/api/auth", tags=["auth"])
AUTH_COOKIE = "ms_auth"
SESSION_DAYS = 7
_failures: dict[str, deque] = defaultdict(deque)
_failures_lock = threading.Lock()
MAX_FAILURES, FAILURE_WINDOW_S = 8, 900


def profile_json(p: Profile) -> dict:
    return {"id": p.id, "display_name": p.display_name, "relation": p.relation, "age_band": p.age_band,
            "language": p.language, "time_format": p.time_format, "large_text": p.large_text,
            "high_contrast": p.high_contrast, "reduce_motion": p.reduce_motion, "voice_first": p.voice_first,
            "is_default": p.is_default}


def me_json(user: User | None) -> dict:
    if user is None:
        return {"user": None, "profiles": []}
    return {"user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role,
                     "consent_version": user.consent_version},
            "profiles": [profile_json(p) for p in user.profiles]}


# ---------------------------------------------------------------- dependencies

def current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        return None
    s = db.scalar(select(AuthSession).where(AuthSession.token_hash == security.token_hash(token)))
    if s is None or s.expires_at.replace(tzinfo=s.expires_at.tzinfo or now().tzinfo) < now():
        return None
    return db.get(User, s.user_id)


def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise HTTPException(401, "Please sign in first.")
    return user


def require_role(*roles: str):
    def check(user: User = Depends(require_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Your account can't do that.")
        return user
    return check


# ---------------------------------------------------------------- helpers

def _throttled(keys: list[str]) -> bool:
    t = time.monotonic()
    with _failures_lock:
        for k in keys:
            q = _failures[k]
            while q and t - q[0] > FAILURE_WINDOW_S:
                q.popleft()
        return any(len(_failures[k]) >= MAX_FAILURES for k in keys)


def _record_failure(keys: list[str]) -> None:
    with _failures_lock:
        for k in keys:
            _failures[k].append(time.monotonic())


def _clear_failures(keys: list[str]) -> None:
    with _failures_lock:
        for k in keys:
            _failures.pop(k, None)


def _start_session(db: Session, user: User, response: Response) -> None:
    db.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < now()))
    token = security.new_token()
    db.add(AuthSession(token_hash=security.token_hash(token), user_id=user.id, expires_at=now() + timedelta(days=SESSION_DAYS)))
    db.commit()
    # SameSite=None is needed when the app is shown inside another site's frame (Hugging Face Spaces).
    response.set_cookie(AUTH_COOKIE, token, httponly=True, max_age=SESSION_DAYS * 86400, secure=PUBLIC,
                        samesite="none" if PUBLIC else "lax")


def _clean_name(name: str) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:60]


# ---------------------------------------------------------------- endpoints

class SignupBody(BaseModel):
    email: str
    password: str
    name: str = Field(min_length=1, max_length=60)
    role: str = "patient"
    invite: str | None = None
    agree: bool = False
    language: str = "en"


@router.post("/signup")
def signup(body: SignupBody, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(request, "signup")
    email = body.email.strip().lower()
    name = _clean_name(body.name)
    if not security.EMAIL_RE.match(email):
        raise HTTPException(422, "That doesn't look like an email address.")
    if not name:
        raise HTTPException(422, "Please tell me what to call you.")
    if not body.agree:
        raise HTTPException(403, "Please agree to the privacy notice to make an account.")
    if body.role not in ROLES:
        raise HTTPException(422, "Unknown account type.")
    if body.role == "pharmacist":
        code = os.getenv("PHARMACIST_INVITE_CODE", "")
        if not code:
            raise HTTPException(403, "Pharmacist accounts are made by the server's owner, not by visitors.")
        if not security.same_secret(code, body.invite or ""):
            raise HTTPException(403, "That invite code isn't right.")
    problem = security.password_problem(body.password, email, name)
    if problem:
        raise HTTPException(422, problem)
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "There is already an account with that email. Try signing in.")
    language = body.language if body.language in {p["code"] for p in lang_available()} else "en"
    user = User(email=email, password_hash=security.hash_password(body.password), name=name, role=body.role,
                consent_version=CONSENT_VERSION, consent_at=now())
    user.profiles.append(Profile(display_name=name, relation="self", age_band="adult", language=language, is_default=True))
    db.add(user)
    db.commit()
    _start_session(db, user, response)
    audit.log_step("signup", None, email, user=user.id, role=user.role)
    return me_json(user)


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(body: LoginBody, request: Request, response: Response, db: Session = Depends(get_db)):
    rate_limit(request, "login", window_s=900)
    email = body.email.strip().lower()
    keys = [f"{client_address(request)}|{email}", f"email|{email}"]
    if _throttled(keys):
        raise HTTPException(429, "Too many tries. Please wait 15 minutes, then try again.")
    user = db.scalar(select(User).where(User.email == email))
    ok = security.verify_password(user.password_hash if user else security.DUMMY_HASH, body.password)
    if not (user and ok):
        _record_failure(keys)
        raise HTTPException(401, "That email and password don't match.")
    _clear_failures(keys)
    _start_session(db, user, response)
    audit.log_step("login", None, email, user=user.id)
    return me_json(user)


@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == security.token_hash(token)))
        db.commit()
    response.delete_cookie(AUTH_COOKIE, samesite="none" if PUBLIC else "lax", secure=PUBLIC)
    return {"ok": True}


@router.get("/me")
def me(user: User | None = Depends(current_user)):
    return me_json(user)


class DeleteBody(BaseModel):
    password: str


@router.delete("/account")
def delete_account(body: DeleteBody, response: Response, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Erases the account, its profiles, saved plans, reviews and sessions, and its audit entries."""
    if not security.verify_password(user.password_hash, body.password):
        raise HTTPException(403, "That password isn't right, so nothing was deleted.")
    uid = user.id
    from api.models import Review
    db.execute(delete(Review).where(Review.reviewer_id == uid))
    db.delete(user)
    db.commit()
    audit.purge_user(uid)
    response.delete_cookie(AUTH_COOKIE)
    return {"ok": True}
