"""Profiles, saved plans and the pharmacist review queue.

Saving is opt-in. A saved plan holds the extracted fields and the text read from the paper,
encrypted; the photo is never stored. A pharmacist sees a plan only when the patient has shared an
item for review, can edit and sign only items still waiting for them, and cannot sign their own.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api import security
from api.auth import profile_json, require_role, require_user
from api.db import get_db
from api.models import AGE_BANDS, RELATIONS, Plan, Profile, Review, User, now
from api.rules import ConfirmationError, apply_confirmation, clean_confirmation, stamp
from api.state import Case, get_case, remember, session_id
from api.views import case_json, item_json
from src import audit
from src.extract import ExtractionResult
from src.lang import available as lang_available
from src.ocr import OCRLine, OCRResult
from src.pipeline import Stage1
from src.schema import MedicationItem, Prescription, Verification

router = APIRouter(prefix="/api", tags=["records"])
MAX_PROFILES = 10


# ---------------------------------------------------------------- profiles

class ProfileBody(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    relation: str = "other"
    age_band: str = "adult"
    language: str = "en"
    time_format: str = "12h"
    large_text: bool = False
    high_contrast: bool = False
    reduce_motion: bool = False
    voice_first: bool = False


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    age_band: str | None = None
    language: str | None = None
    time_format: str | None = None
    large_text: bool | None = None
    high_contrast: bool | None = None
    reduce_motion: bool | None = None
    voice_first: bool | None = None


def _check_profile(values: dict) -> None:
    langs = {p["code"] for p in lang_available()}
    if values.get("age_band") not in (None, *AGE_BANDS):
        raise HTTPException(422, "Age group must be child, adult or senior.")
    if values.get("relation") not in (None, *RELATIONS):
        raise HTTPException(422, "Unknown relation.")
    if values.get("language") not in (None, *langs):
        raise HTTPException(422, "Unknown language.")
    if values.get("time_format") not in (None, "12h", "24h"):
        raise HTTPException(422, "Time format must be 12h or 24h.")


def _own_profile(db: Session, user: User, pid: int) -> Profile:
    p = db.get(Profile, pid)
    if p is None or p.user_id != user.id:
        raise HTTPException(404, "No such profile.")
    return p


@router.get("/profiles")
def list_profiles(user: User = Depends(require_user)):
    return [profile_json(p) for p in user.profiles]


@router.post("/profiles")
def add_profile(body: ProfileBody, user: User = Depends(require_role("caregiver")), db: Session = Depends(get_db)):
    values = body.model_dump()
    _check_profile(values)
    if values["relation"] == "self":
        raise HTTPException(422, "Your own profile already exists.")
    if len(user.profiles) >= MAX_PROFILES:
        raise HTTPException(409, f"You can look after up to {MAX_PROFILES} people.")
    p = Profile(user_id=user.id, **values)
    db.add(p)
    db.commit()
    return profile_json(p)


@router.patch("/profiles/{pid}")
def edit_profile(pid: int, body: ProfilePatch, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = _own_profile(db, user, pid)
    values = body.model_dump(exclude_none=True)
    _check_profile(values)
    for k, v in values.items():
        setattr(p, k, v)
    db.commit()
    return profile_json(p)


@router.delete("/profiles/{pid}")
def remove_profile(pid: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    p = _own_profile(db, user, pid)
    if p.is_default:
        raise HTTPException(409, "Your own profile can't be removed. Delete the account instead.")
    db.delete(p)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- case <-> encrypted blob

def case_to_blob(case: Case) -> dict:
    s1, ex = case.stage1, case.stage1.extraction
    return {"patient": case.patient, "source": ex.prescription.source,
            "ocr": {"engine": s1.ocr.engine, "lines": [{"text": l.text, "confidence": l.confidence} for l in s1.ocr.lines]},
            "injection_hits": ex.injection_hits, "model": ex.model_id, "prompt": ex.prompt_id,
            "items": [it.model_dump(mode="json") for it in ex.prescription.items]}


def blob_to_case(blob: dict, sid: str) -> Case:
    items = [MedicationItem.model_validate(i) for i in blob["items"]]
    rx = Prescription(patient_alias=blob.get("patient") or None, source=blob.get("source", "text"), items=items)
    ocr = OCRResult([OCRLine(l["text"], l["confidence"]) for l in blob["ocr"]["lines"]], blob["ocr"]["engine"])
    ex = ExtractionResult(rx, "", True, False, blob.get("injection_hits", []), blob.get("model", ""), blob.get("prompt", ""), 0.0, [])
    return Case(uuid.uuid4().hex, sid, blob.get("patient", ""), Stage1(ocr, ex))


def _blob(plan: Plan) -> dict:
    try:
        return security.decrypt_json(plan.data_enc)
    except ValueError as e:
        raise HTTPException(500, "This saved plan can't be opened with the server's current key.") from e


def _iso(dt) -> str | None:
    return dt.isoformat(timespec="seconds") if dt else None


def plan_summary(plan: Plan) -> dict:
    blob = _blob(plan)
    items = [MedicationItem.model_validate(i) for i in blob["items"]]
    reviews = []
    for r in sorted(plan.reviews, key=lambda r: (r.item_index, r.id)):
        note = security.decrypt_json(r.note_enc).get("note") if r.note_enc else None
        reviews.append({"id": r.id, "item_index": r.item_index, "status": r.status, "requested_at": _iso(r.requested_at),
                        "reviewed_at": _iso(r.reviewed_at), "reviewer": r.reviewer.name if r.reviewer else None, "note": note})
    return {"id": plan.id, "profile_id": plan.profile_id, "profile_name": plan.profile.display_name, "title": plan.title,
            "created_at": _iso(plan.created_at), "updated_at": _iso(plan.updated_at), "n_items": plan.n_items,
            "items": [{"index": i, "name": it.name.value or "Unknown medicine", "status": it.status.value,
                       "verification": it.verification.model_dump() if it.verification else None} for i, it in enumerate(items)],
            "reviews": reviews, "pending": sum(r["status"] == "pending" for r in reviews)}


def _own_plan(db: Session, user: User, plan_id: str) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None or plan.profile.user_id != user.id:
        raise HTTPException(404, "No such saved plan.")
    return plan


def _request_reviews(db: Session, plan: Plan, scope: str) -> int:
    items = [MedicationItem.model_validate(i) for i in _blob(plan)["items"]]
    waiting = {r.item_index for r in plan.reviews if r.status == "pending"}
    made = 0
    for i, it in enumerate(items):
        wants = (not it.is_usable) if scope == "held" else not (it.verification and it.verification.kind == "pharmacist")
        if wants and i not in waiting:
            db.add(Review(plan_id=plan.id, item_index=i))
            made += 1
    return made


# ---------------------------------------------------------------- plans

class SaveBody(BaseModel):
    case_id: str
    profile_id: int
    title: str = Field(default="", max_length=120)
    share_with_pharmacist: bool = False


@router.post("/plans")
def save_plan(body: SaveBody, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    case = get_case(body.case_id, request)
    profile = _own_profile(db, user, body.profile_id)
    blob = case_to_blob(case)
    names = ", ".join(i["name"]["value"] or "?" for i in blob["items"])
    plan = Plan(profile_id=profile.id, title=(body.title.strip() or names)[:120], n_items=len(blob["items"]),
                data_enc=security.encrypt_json(blob))
    db.add(plan)
    db.flush()
    made = _request_reviews(db, plan, "held") if body.share_with_pharmacist else 0
    db.commit()
    db.refresh(plan)
    audit.log_step("plan_save", None, plan.id, user=user.id, items=plan.n_items, shared=made)
    return plan_summary(plan)


@router.put("/plans/{plan_id}")
def update_plan(plan_id: str, case_id: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    plan = _own_plan(db, user, plan_id)
    blob = case_to_blob(get_case(case_id, request))
    plan.data_enc, plan.n_items = security.encrypt_json(blob), len(blob["items"])
    db.commit()
    return plan_summary(plan)


@router.get("/plans")
def list_plans(profile_id: int | None = None, user: User = Depends(require_user), db: Session = Depends(get_db)):
    ids = [p.id for p in user.profiles if profile_id in (None, p.id)]
    plans = db.scalars(select(Plan).where(Plan.profile_id.in_(ids)).order_by(Plan.created_at.desc()).limit(100)).all() if ids else []
    return [plan_summary(p) for p in plans]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return plan_summary(_own_plan(db, user, plan_id))


@router.post("/plans/{plan_id}/open")
def open_plan(plan_id: str, request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Load a saved plan into memory so the guide, PDF and share endpoints work on it."""
    plan = _own_plan(db, user, plan_id)
    case = blob_to_case(_blob(plan), session_id(request))
    remember(case)
    audit.log_step("plan_open", None, plan.id, user=user.id)
    return {**case_json(case), "plan_id": plan.id, "profile_id": plan.profile_id}


class ReviewRequest(BaseModel):
    scope: str = "held"  # held | all


@router.post("/plans/{plan_id}/review")
def ask_for_review(plan_id: str, body: ReviewRequest, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if body.scope not in ("held", "all"):
        raise HTTPException(422, "Scope must be held or all.")
    plan = _own_plan(db, user, plan_id)
    made = _request_reviews(db, plan, body.scope)
    db.commit()
    db.refresh(plan)
    audit.log_step("review_request", None, plan.id, user=user.id, items=made)
    return plan_summary(plan)


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: str, user: User = Depends(require_user), db: Session = Depends(get_db)):
    db.delete(_own_plan(db, user, plan_id))
    db.commit()
    audit.log_step("plan_delete", None, plan_id, user=user.id)
    return {"ok": True}


# ---------------------------------------------------------------- pharmacist queue

def _review_json(r: Review) -> dict:
    blob = _blob(r.plan)
    item = MedicationItem.model_validate(blob["items"][r.item_index])
    return {"id": r.id, "plan_id": r.plan_id, "item_index": r.item_index, "status": r.status,
            "requested_at": _iso(r.requested_at), "reviewed_at": _iso(r.reviewed_at),
            "patient": f"{r.plan.profile.display_name} ({r.plan.profile.age_band})", "source": blob.get("source"),
            "item": item_json(r.item_index, item), "ocr_lines": blob["ocr"]["lines"],
            "injection_hits": blob.get("injection_hits", []), "reviewed_by": r.reviewer.name if r.reviewer else None}


@router.get("/review/queue")
def queue(status: str = "pending", user: User = Depends(require_role("pharmacist")), db: Session = Depends(get_db)):
    q = select(Review).order_by(Review.requested_at)
    q = q.where(Review.status == "pending") if status == "pending" else q.where(Review.reviewer_id == user.id).order_by(Review.reviewed_at.desc())
    return [_review_json(r) for r in db.scalars(q.limit(100)).all()]


def _pending_review(db: Session, user: User, rid: int) -> Review:
    r = db.get(Review, rid)
    if r is None:
        raise HTTPException(404, "No such review.")
    if r.status != "pending":
        raise HTTPException(409, "This one has already been dealt with.")
    if r.plan.profile.user_id == user.id:
        raise HTTPException(403, "You can't review your own prescription.")
    return r


class VerifyBody(BaseModel):
    fields: dict[str, str | None]


@router.post("/review/{rid}/verify")
def verify(rid: int, body: VerifyBody, user: User = Depends(require_role("pharmacist")), db: Session = Depends(get_db)):
    """The pharmacist's values replace the item's, and their name and time are stored with it."""
    r = _pending_review(db, user, rid)
    try:
        values = clean_confirmation(body.fields)
    except ConfirmationError as e:
        return JSONResponse({"detail": e.detail, "missing": e.missing}, status_code=422)
    blob = _blob(r.plan)
    item = MedicationItem.model_validate(blob["items"][r.item_index])
    apply_confirmation(item, values, Verification(kind="pharmacist", by=user.name, at=stamp()))
    blob["items"][r.item_index] = item.model_dump(mode="json")
    r.plan.data_enc = security.encrypt_json(blob)
    r.status, r.reviewer_id, r.reviewed_at = "verified", user.id, now()
    db.commit()
    audit.log_step("review_verify", None, r.plan_id, user=user.id, item=r.item_index)
    return _review_json(r)


class DeclineBody(BaseModel):
    note: str = Field(default="", max_length=300)


@router.post("/review/{rid}/decline")
def decline(rid: int, body: DeclineBody, user: User = Depends(require_role("pharmacist")), db: Session = Depends(get_db)):
    """The item stays held. The patient is told, in the pharmacist's words, to see someone in person."""
    r = _pending_review(db, user, rid)
    note = body.note.strip() or "Please show this prescription to your doctor or pharmacist in person."
    r.status, r.reviewer_id, r.reviewed_at = "declined", user.id, now()
    r.note_enc = security.encrypt_json({"note": note})
    db.commit()
    audit.log_step("review_decline", None, r.plan_id, user=user.id, item=r.item_index)
    return _review_json(r)
