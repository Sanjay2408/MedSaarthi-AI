"""MedSaarthi AI: HTTP API and web app host (replaces the Streamlit front end).

    python -m uvicorn api.server:app --port 8000      # after: npm --prefix web run build

The safety rules stay on the server. The browser sends what a person typed and that they
confirmed it; it can never mark an item safe on its own, and a confirmed item must still
have every required field and a dose with an amount. Cases live in memory only: prescription
text is never written to disk (the LLM disk cache is used for the synthetic samples only).

Each browser gets its own session cookie: it can see and delete only its own cases and audit
rows. Reads and guides are rate limited per address, because they spend the owner's Groq quota.
"""
import io
import json
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from src import audit
from src.config import ROOT, load_config
from src.lang import available as lang_available
from src.llm import LLM
from src.pipeline import Stage1, Stage2, explain, read_and_extract
from src.render import Prefs, render_html, render_pdf
from src.schedule import format_time, parse_frequency, period, plain_frequency
from src.schema import ALL_FIELDS, REQUIRED_FIELDS, FieldValue, ItemStatus, ReasonCode
from src.translate import NOTE
from src.validator import extract_quantities, gate_item

CFG = load_config()
SAMPLES = ROOT / "data" / "samples"
DIST = ROOT / "web" / "dist"
MAX_UPLOAD = 10 * 1024 * 1024
MAX_TEXT = 5000
MAX_CASES = 200
PUBLIC = os.getenv("MEDSAARTHI_PUBLIC") == "1"
LIMITS = {"read": int(os.getenv("READS_PER_HOUR", "30")), "guide": int(os.getenv("GUIDES_PER_HOUR", "60"))}
COOKIE = "ms_session"
CATEGORY_LABELS = {"clean": "Clean print", "degraded": "Degraded scan", "ambiguous": "Unclear or missing",
                   "injection": "Injected text"}
REASON_TEXT = {
    ReasonCode.ILLEGIBLE: "I couldn't read part of this clearly.",
    ReasonCode.MISSING_NAME: "I can't find the medicine's name.",
    ReasonCode.MISSING_DOSE: "I can't find how much to take.",
    ReasonCode.MISSING_FREQUENCY: "I can't find how often to take it.",
    ReasonCode.MISSING_DURATION: "I can't find how many days to take it for.",
    ReasonCode.UNKNOWN_ABBREVIATION: "This short form is new to me, so I won't guess what it means.",
    ReasonCode.LOW_OCR_CONFIDENCE: "The photo isn't sharp enough here for me to be sure.",
    ReasonCode.CONFLICTING: "Two parts of the prescription seem to say different things.",
}

app = FastAPI(title="MedSaarthi AI", docs_url=None, redoc_url=None)
_translate_lock = threading.Lock()  # NLLB's tokenizer holds per-call state


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
_consented: set[str] = set()
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_hits_lock = threading.Lock()


def _session(request: Request) -> str:
    """Runs inside each endpoint's thread, so audit rows land in this browser's log."""
    sid = request.state.session
    audit.use_session(sid)
    return sid


@app.middleware("http")
async def session_cookie(request: Request, call_next):
    sid = request.cookies.get(COOKIE, "")
    fresh = not re.fullmatch(r"[0-9a-f]{32}", sid)
    if fresh:
        sid = uuid.uuid4().hex
    request.state.session = sid
    response = await call_next(request)
    if fresh and request.url.path.startswith("/api/"):
        # Spaces embeds the app in a frame on another site, which needs SameSite=None.
        response.set_cookie(COOKIE, sid, httponly=True, max_age=86400, secure=PUBLIC, samesite="none" if PUBLIC else "lax")
    return response


def _rate_limit(request: Request, bucket: str) -> None:
    forwarded = request.headers.get("x-forwarded-for", "")
    who = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    with _hits_lock:
        hits = _hits[(who, bucket)]
        while hits and now - hits[0] > 3600:
            hits.popleft()
        if len(hits) >= LIMITS[bucket]:
            raise HTTPException(429, "That's a lot of requests for this demo. Please try again in a little while.")
        hits.append(now)


def _llm(model: str | None, cache: bool = False) -> LLM:
    allowed = [CFG["llm"]["model"], *CFG["llm"]["alt_models"]]
    if model and model not in allowed:
        raise HTTPException(422, "Unknown language model.")
    return LLM(model=model or None, use_cache=cache)


def _case(case_id: str, request: Request) -> Case:
    case = CASES.get(case_id)
    if case is None or case.session != _session(request):
        raise HTTPException(404, "This prescription is no longer in memory. Please add it again.")
    return case


def _item_json(index: int, item) -> dict:
    return {
        "index": index,
        "status": item.status.value,
        "usable": item.is_usable,
        "reasons": [{"code": r.value, "text": REASON_TEXT[r]} for r in item.reasons],
        "fields": {f: {"value": item.field(f).value, "confidence": item.field(f).confidence} for f in ALL_FIELDS},
        "frequency_plain": plain_frequency(item.frequency.value),
    }


def _case_json(case: Case) -> dict:
    s1, ex = case.stage1, case.stage1.extraction
    return {
        "id": case.id,
        "patient": case.patient,
        "source": ex.prescription.source,
        "has_image": case.image is not None,
        "ocr": {"engine": s1.ocr.engine, "mean_confidence": round(s1.ocr.mean_confidence, 3),
                "lines": [{"text": l.text, "confidence": l.confidence} for l in s1.ocr.lines]},
        "injection_hits": ex.injection_hits,
        "model": ex.model_id,
        "prompt": ex.prompt_id,
        "threshold": CFG["safety"]["confidence_threshold"],
        "items": [_item_json(i, it) for i, it in enumerate(ex.prescription.items)],
    }


def _run(fn):
    """Turn model and network failures into one plain sentence for the block that failed."""
    try:
        return fn()
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "GROQ_API_KEY" in msg or "401" in msg or "invalid_api_key" in msg.lower():
            detail = "The language service rejected the API key. Check GROQ_API_KEY in .env."
        elif "rate limit" in msg.lower() or "quota" in msg.lower():
            detail = "The language service is at its rate limit. Try again in a minute."
        else:
            detail = f"Processing failed: {type(e).__name__}."
        raise HTTPException(502, detail) from e


# ------------------------------------------------------------------ reference data

@app.get("/api/config")
def config():
    return {
        "models": [CFG["llm"]["model"], *CFG["llm"]["alt_models"]],
        "variants": [{"id": "v2", "label": "Engineered prompt"}, {"id": "v3", "label": "Engineered + leaflet RAG"},
                     {"id": "v1", "label": "Baseline prompt (for comparison)"}],
        "ocr_modes": ["auto", "printed", "handwriting"],
        "languages": [{k: p[k] for k in ("code", "name", "native", "reviewed")} for p in lang_available()],
        "threshold": CFG["safety"]["confidence_threshold"],
        "disclaimer": CFG["safety"]["disclaimer"],
    }


@app.get("/api/samples")
def samples():
    index = json.loads((SAMPLES / "index.json").read_text(encoding="utf-8"))
    return [{**s, "label": CATEGORY_LABELS[s["category"]]} for s in index]


def _sample_path(sample_id: str, ext: str) -> Path:
    if not re.fullmatch(r"S\d{2}", sample_id):
        raise HTTPException(404, "No such sample.")
    path = SAMPLES / f"{sample_id}.{ext}"
    if not path.exists():
        raise HTTPException(404, "No such sample.")
    return path


@app.get("/api/samples/{sample_id}")
def sample(sample_id: str):
    return {"id": sample_id, "text": _sample_path(sample_id, "txt").read_text(encoding="utf-8"),
            "patient": f"Test Patient {sample_id[1:]}"}


@app.get("/api/samples/{sample_id}/image")
def sample_image(sample_id: str):
    return FileResponse(_sample_path(sample_id, "png"), media_type="image/png")


# ------------------------------------------------------------------ read

@app.post("/api/read")
def read(request: Request, consent: bool = Form(False), text: str | None = Form(None), sample_id: str | None = Form(None),
         use_image: bool = Form(False), patient: str = Form(""), variant: str = Form("v2"),
         model: str | None = Form(None), ocr_mode: str = Form("auto"), file: UploadFile | None = File(None)):
    sid = _session(request)
    if not consent:
        raise HTTPException(403, "Please agree to the notice before reading a prescription.")
    if variant not in ("v1", "v2", "v3"):
        raise HTTPException(422, "Unknown prompt variant.")
    if ocr_mode not in ("auto", "printed", "handwriting"):
        raise HTTPException(422, "Unknown OCR mode.")
    if text and len(text) > MAX_TEXT:
        raise HTTPException(413, "That's longer than a prescription. Please keep it under 5,000 characters.")
    _rate_limit(request, "read")
    if sid not in _consented:
        audit.log_step("consent", None, "consent", agreed=True)
        _consented.add(sid)

    is_sample = bool(sample_id) and not (file is not None and file.filename)
    raw: bytes | None = None
    if file is not None and file.filename:
        raw = file.file.read(MAX_UPLOAD + 1)
        if len(raw) > MAX_UPLOAD:
            raise HTTPException(413, "That image is larger than 10 MB.")
    elif sample_id and use_image:
        raw = _sample_path(sample_id, "png").read_bytes()
    elif sample_id:
        text = _sample_path(sample_id, "txt").read_text(encoding="utf-8")

    image = None
    if raw is not None:
        try:
            image = Image.open(io.BytesIO(raw))
            image.load()
        except (UnidentifiedImageError, OSError) as e:
            raise HTTPException(422, "That file could not be opened as an image. Use PNG or JPEG.") from e
    elif not (text and text.strip()):
        raise HTTPException(422, "Add a photo, type the prescription or choose a sample.")

    extract_variant = "v1" if variant == "v1" else "v2"  # V3 only changes the explanation step
    stage1 = _run(lambda: read_and_extract(image=image, text=None if image is not None else text, ocr_mode=ocr_mode,
                                           variant=extract_variant, llm=_llm(model, cache=is_sample), patient_alias=patient))
    case = Case(uuid.uuid4().hex, sid, patient.strip(), stage1, image=raw, cacheable=is_sample)
    CASES[case.id] = case
    while len(CASES) > MAX_CASES:
        CASES.pop(next(iter(CASES)))
    return _case_json(case)


@app.get("/api/cases/{case_id}/image")
def case_image(case_id: str, request: Request):
    case = _case(case_id, request)
    if case.image is None:
        raise HTTPException(404, "This prescription was typed.")
    return Response(case.image, media_type="application/octet-stream")


# ------------------------------------------------------------------ confirm

class Confirmation(BaseModel):
    fields: dict[str, str | None]


@app.post("/api/cases/{case_id}/items/{index}/confirm")
def confirm(case_id: str, index: int, body: Confirmation, request: Request):
    """A person checked this item with a pharmacist or doctor. Never fills a gap for them."""
    case = _case(case_id, request)
    items = case.stage1.extraction.prescription.items
    if not 0 <= index < len(items):
        raise HTTPException(404, "No such item.")
    values = {f: (body.fields.get(f) or "").strip() or None for f in ALL_FIELDS}
    missing = [f for f in REQUIRED_FIELDS if not values[f]]
    if values["dose"] and not extract_quantities(values["dose"]):
        missing.append("dose amount")
    if missing:
        return JSONResponse({"detail": "Still needed: " + ", ".join(missing) + ". Please ask your pharmacist rather than guessing.",
                             "missing": missing}, status_code=422)
    if parse_frequency(values["frequency"]) is None:
        return JSONResponse({"detail": "I can't turn this into dose times. Write it the way your pharmacist "
                                       "says it, like twice a day, 1-0-1 or every 8 hours.", "missing": ["frequency"]}, status_code=422)
    item = items[index]
    for f in ALL_FIELDS:
        setattr(item, f, FieldValue(value=values[f], confidence=1.0))
    item.reasons = []
    item.status = ItemStatus.CONFIRMED
    case.guides.clear()
    audit.log_step("human_confirm", None, values["name"], item=index)
    return _case_json(case)


# ------------------------------------------------------------------ guide

class GuideRequest(BaseModel):
    lang: str = "en"
    time_format: str = "12h"
    shift_minutes: int = 0
    variant: str = "v2"
    model: str | None = None


def _dose_slots(entries, time_format: str) -> list[dict]:
    return [{"medicine": e.medication, "dose": e.dose, "as_needed": e.as_needed,
             "times": [{"at": t, "label": format_time(t, time_format), "period": period(t)} for t in e.times]}
            for e in entries]


DRAFT_NOTE = "Wording written from a fixed template. A native speaker has not reviewed this language yet."


def _template_note(r) -> str:
    if r.reviewed:
        return "Wording written from a fixed template that a native speaker has reviewed."
    return DRAFT_NOTE


def _medicine_payload(ex) -> dict:
    """One medicine as the app shows it. `translation.tier` says how the words were produced:
    "template" (language pack, numbers written by code) or "mt" (machine translation, checked)."""
    payload = {
        "name": ex.name,
        "english": ex.simplify.final_text,
        "blocked": ex.simplify.blocked,
        "model": ex.simplify.model_id,
        "prompt": ex.simplify.prompt_id,
        "card": ex.card_en.as_dict() if ex.card_en else None,
        "translation": None,
    }
    if ex.local:
        payload["translation"] = {**ex.local.as_dict(), "tier": "template", "blocked": False, "numbers_ok": True,
                                  "text": ex.local.text, "when": ex.local.when, "note": _template_note(ex.local),
                                  "provider": "template"}
    elif ex.mt:
        mt = ex.mt
        payload["translation"] = {"lang": mt.lang, "tier": "mt", "reviewed": False, "blocked": mt.blocked,
                                  "numbers_ok": mt.numbers_ok, "text": None if mt.blocked else mt.text,
                                  "when": mt.when, "note": NOTE, "provider": mt.provider, "rows": [], "footer": [],
                                  "greeting": "", "untranslated": None}
    return payload


@app.post("/api/cases/{case_id}/guide")
def guide(case_id: str, body: GuideRequest, request: Request):
    case = _case(case_id, request)
    if body.lang not in {p["code"] for p in lang_available()}:
        raise HTTPException(422, "Unknown language.")
    if body.time_format not in ("12h", "24h"):
        raise HTTPException(422, "Unknown time format.")
    if body.variant not in ("v1", "v2", "v3"):
        raise HTTPException(422, "Unknown prompt variant.")
    if abs(body.shift_minutes) > 720 or body.shift_minutes % 30:
        raise HTTPException(422, "Times move in steps of 30 minutes, by up to 12 hours.")
    items = case.stage1.extraction.prescription.items
    if not any(i.is_usable for i in items):
        raise HTTPException(409, "Nothing is ready yet. Check at least one medicine first.")

    key = (body.lang, body.time_format, body.shift_minutes, body.variant, body.model)
    if key in case.guides:
        stage2, payload = case.guides[key]
    else:
        _rate_limit(request, "guide")

        def work():
            with _translate_lock:
                return explain(items, variant=body.variant, lang=body.lang, time_format=body.time_format,
                               shift_minutes=body.shift_minutes, patient=case.patient, llm=_llm(body.model, cache=case.cacheable))
        stage2 = _run(work)
        payload = {
            "case_id": case.id,
            "patient": case.patient,
            "prefs": body.model_dump(),
            "schedule": _dose_slots(stage2.schedule, body.time_format),
            "medicines": [_medicine_payload(ex) for ex in stage2.explanations],
            "left_out": [{
                "name": i.name.value or "Unknown medicine",
                "reason": " ".join(REASON_TEXT[r] for r in i.reasons) or
                          "The frequency could not be turned into dose times.",
            } for i in stage2.skipped],
            "disclaimer": CFG["safety"]["disclaimer"],
        }
        case.guides[key] = (stage2, payload)
    case.last_guide, case.last_prefs, case.last_payload = stage2, body.model_dump(), payload
    return payload


def _render_prefs(case: Case, large: bool, contrast: bool) -> Prefs:
    return Prefs(case.last_prefs.get("time_format", "12h"), large, contrast)


def _split(entries):
    return [e for e in entries if not e.as_needed], [e for e in entries if e.as_needed]


@app.get("/api/cases/{case_id}/schedule.pdf")
def schedule_pdf(case_id: str, request: Request, large: bool = False, contrast: bool = False, inline: bool = False):
    case = _case(case_id, request)
    if case.last_guide is None:
        raise HTTPException(409, "Write the guide first.")
    timed, prn = _split(case.last_guide.schedule)
    pdf = render_pdf(timed, _render_prefs(case, large, contrast), case.patient, prn)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="medicine-schedule.pdf"'})


@app.get("/api/cases/{case_id}/guide.html")
def guide_html(case_id: str, request: Request, large: bool = False, contrast: bool = False, download: bool = True):
    case = _case(case_id, request)
    if case.last_guide is None:
        raise HTTPException(409, "Write the guide first.")
    timed, prn = _split(case.last_guide.schedule)
    exps = case.last_guide.explanations
    medicines = [(ex.name, ex.simplify.final_text, ex.translated_text) for ex in exps]
    note = None
    if any(ex.mt and not ex.mt.blocked for ex in exps):
        note = NOTE
    elif any(ex.local for ex in exps):
        note = " ".join(sorted({_template_note(ex.local) for ex in exps if ex.local}))
    page = render_html(timed, _render_prefs(case, large, contrast), case.patient, medicines, prn, note)
    headers = {"Content-Disposition": 'attachment; filename="medicine-guide.html"'} if download else {}
    return HTMLResponse(page, headers=headers)


# ------------------------------------------------------------------ audit and deletion

@app.get("/api/audit")
def audit_log(request: Request):
    sid = _session(request)
    return {"session": sid[:12], "rows": audit.read_session(sid)}


@app.delete("/api/session")
def delete_session(request: Request):
    """Forget this browser's cases and start it a new audit session. Others are untouched."""
    sid = _session(request)
    mine = [k for k, c in CASES.items() if c.session == sid]
    for k in mine:
        del CASES[k]
    _consented.discard(sid)
    response = JSONResponse({"removed": len(mine)})
    response.delete_cookie(COOKIE)
    return response


# ------------------------------------------------------------------ web app

if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def web_app(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "No such endpoint.")
    index = DIST / "index.html"
    if not index.exists():
        return HTMLResponse("<p>The web app is not built yet. Run <code>npm --prefix web install</code> and "
                            "<code>npm --prefix web run build</code>.</p>", status_code=503)
    return FileResponse(index)
