"""Passwords, session tokens and encryption at rest.

- Passwords: Argon2id (the OWASP first choice), never stored or logged in clear.
- Session tokens: 256 random bits; only a SHA-256 of the token is stored, so a copy of the
  database cannot be used to sign in as someone.
- Health data (saved prescriptions) is encrypted with Fernet (AES-128-CBC + HMAC) before it
  reaches the database. The key lives in MEDSAARTHI_DATA_KEY, never in the database. Several
  comma-separated keys are accepted so a key can be rotated: the first encrypts, all decrypt.
  In development a key file is created under data/ (git-ignored). When MEDSAARTHI_PUBLIC=1 a
  missing key is a hard error: a public server must not invent its own.
"""
import hashlib
import json
import os
import re
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from src.config import ROOT

_hasher = PasswordHasher()
DUMMY_HASH = _hasher.hash("this is only used to spend the same time on unknown emails")
_COMMON = {"password", "passw0rd", "1234567890", "qwertyuiop", "medsaarthi", "iloveyou123", "letmein123", "welcome123"}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def password_problem(password: str, email: str = "", name: str = "") -> str | None:
    """Length and obvious-guess checks only (NIST 800-63B): no forced symbols, no expiry."""
    if len(password) < 10:
        return "Please use at least 10 characters. A few random words work well."
    if len(password) > 200:
        return "That password is too long."
    low = password.lower()
    if low in _COMMON or low.strip("0123456789") in _COMMON:
        return "That password is too easy to guess."
    for part in (email.split("@")[0], name):
        if part and len(part) >= 4 and part.lower() in low:
            return "Please don't put your name or email in your password."
    return None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same_secret(a: str, b: str) -> bool:
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@lru_cache(maxsize=1)
def _cipher() -> MultiFernet:
    raw = os.getenv("MEDSAARTHI_DATA_KEY", "").strip()
    if not raw:
        if os.getenv("MEDSAARTHI_PUBLIC") == "1":
            raise RuntimeError("MEDSAARTHI_DATA_KEY is required when MEDSAARTHI_PUBLIC=1. "
                               "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        path = ROOT / "data" / ".dev_data_key"
        if not path.exists():
            path.write_text(Fernet.generate_key().decode(), encoding="utf-8")
        raw = path.read_text(encoding="utf-8").strip()
    return MultiFernet([Fernet(k.strip().encode()) for k in raw.split(",") if k.strip()])


def encrypt_json(obj) -> bytes:
    return _cipher().encrypt(json.dumps(obj, ensure_ascii=False).encode("utf-8"))


def decrypt_json(blob: bytes):
    try:
        return json.loads(_cipher().decrypt(blob).decode("utf-8"))
    except InvalidToken as e:
        raise ValueError("stored data could not be decrypted (wrong or rotated-out key)") from e


EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")
