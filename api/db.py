"""Database engine and session. SQLite by default; set DATABASE_URL for Postgres (for example a
hosted free-tier database) with no other change. Requires `pip install psycopg[binary]` for Postgres."""
import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.models import Base
from src.config import ROOT


def make_engine(url: str | None = None):
    url = url or os.getenv("DATABASE_URL") or f"sqlite:///{(ROOT / 'data' / 'medsaarthi.db').as_posix()}"
    if url.startswith("postgres://"):  # some hosts still hand out the old scheme
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=args, pool_pre_ping=True)


engine = make_engine()
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
