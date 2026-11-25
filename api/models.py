"""Database tables.

Health data (saved prescriptions, reviewer notes) is stored only as encrypted blobs; the columns
beside them hold structure the server needs for routing and access checks, not medical content.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ROLES = ("patient", "caregiver", "pharmacist")
AGE_BANDS = ("child", "adult", "senior")
RELATIONS = ("self", "parent", "child", "spouse", "other")
CONSENT_VERSION = "2026-11-26"


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(16), default="patient")
    consent_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    profiles: Mapped[list["Profile"]] = relationship(back_populates="user", cascade="all, delete-orphan", order_by="Profile.id")
    sessions: Mapped[list["AuthSession"]] = relationship(cascade="all, delete-orphan")


class Profile(Base):
    """A person the app is set up for. A caregiver has several; each tailors the app to its owner."""
    __tablename__ = "profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(60))
    relation: Mapped[str] = mapped_column(String(10), default="self")
    age_band: Mapped[str] = mapped_column(String(8), default="adult")
    language: Mapped[str] = mapped_column(String(8), default="en")
    time_format: Mapped[str] = mapped_column(String(3), default="12h")
    large_text: Mapped[bool] = mapped_column(Boolean, default=False)
    high_contrast: Mapped[bool] = mapped_column(Boolean, default=False)
    reduce_motion: Mapped[bool] = mapped_column(Boolean, default=False)
    voice_first: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    user: Mapped[User] = relationship(back_populates="profiles")
    plans: Mapped[list["Plan"]] = relationship(back_populates="profile", cascade="all, delete-orphan")


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Plan(Base):
    """A saved prescription. `data_enc` holds the extracted fields, the text read from the paper
    and the verification record, encrypted. The photo itself is never stored."""
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="")
    n_items: Mapped[int] = mapped_column(Integer, default=0)
    data_enc: Mapped[bytes] = mapped_column(LargeBinary)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    profile: Mapped[Profile] = relationship(back_populates="plans")
    reviews: Mapped[list["Review"]] = relationship(back_populates="plan", cascade="all, delete-orphan")


class Review(Base):
    """A request for a pharmacist to check one item of a plan. Made only when the patient shares it."""
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    item_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)  # pending | verified | declined
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    plan: Mapped[Plan] = relationship(back_populates="reviews")
    reviewer: Mapped[User | None] = relationship()
