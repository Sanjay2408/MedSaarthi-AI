"""MedSaarthi AI: HTTP API and web app host.

    python -m uvicorn api.server:app --port 8000      # after: npm --prefix web run build

The safety rules stay on the server. The browser sends what a person typed and that they
confirmed it; it can never mark an item safe on its own, and a confirmed item must still
have every required field and a dose with an amount (api/rules.py). Cases live in memory only
and belong to one browser; saving to an account is opt-in and encrypted (api/records.py).
Prescription text is never written to disk (the LLM disk cache is used for synthetic samples only).

Each browser gets its own session cookie: it can see and delete only its own cases and audit
rows. Reads and guides are rate limited per address, because they spend the owner's Groq quota.
State-changing requests that carry an Origin header must come from this site.
"""
import io
import json
import re
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel

from api import state
from api.auth import router as auth_router
from api.db import init_db
from api.records import router as records_router
from api.rules import ConfirmationError, apply_confirmation, clean_confirmation, stamp
from api.views import REASON_TEXT, case_json
from src import audit
from datetime import date

from src.config import ROOT, load_config
from src.fhir import bundle as fhir_bundle
from src.ics import build_ics, course_days
from src.lang import available as lang_available
from src.llm import LLM
from src.pipeline import explain, read_and_extract
from src.render import Prefs, render_html, render_pdf
from src.schedule import format_time, period
from src.schema import Verification
from src.translate import NOTE

CFG = load_config()
SAMPLES = ROOT / "data" / "samples"
DIST = ROOT / "web" / "dist"
MAX_UPLOAD = 10 * 1024 * 1024
MAX_TEXT = 5000
CATEGORY_LABELS = {"clean": "Clean print", "degraded": "Degraded scan", "ambiguous": "Unclear or missing",
                   "injection": "Injected text"}


@asynccontextmanager
async def lifespan(_app):
    init_db()
    yield


app = FastAPI(title="MedSaarthi AI", docs_url=None, redoc_url=None, lifespan=lifespan)
app.include_router(auth_router)
app.include_router(records_router)
_translate_lock = threading.Lock()  # NLLB's tokenizer holds per-call state


@app.middleware("http")
async def same_origin(request: Request, call_next):
    """Refuse a state-changing API call whose Origin is another site. SameSite cookies already
    stop most of these; this covers the cases they don't (for example a framed app)."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
        if origin and urlparse(origin).netloc != host:
            return JSONResponse({"detail": "That request came from another site, so it was refused."}, status_code=403)
    return await call_next(request)


@app.middleware("http")
async def session_cookie(request: Request, call_next):
    sid = request.cookies.get(state.COOKIE, "")
    fresh = not state.SESSION_RE.fullmatch(sid)
    if fresh:
        sid = uuid.uuid4().hex
    request.state.session = sid
    response = await call_next(request)
    if fresh and request.url.path.startswith("/api/"):
        # Spaces embeds the app in a frame on another site, which needs SameSite=None.
        response.set_cookie(state.COOKIE, sid, httponly=True, max_age=86400, secure=state.PUBLIC,
                            samesite="none" if state.PUBLIC else "lax")
    return response


def _llm(model: str | None, cache: bool = False) -> LLM:
    allowed = [CFG["llm"]["model"], *CFG["llm"]["alt_models"]]
    if model and model not in allowed:
        raise HTTPException(422, "Unknown language model.")
    return LLM(model=model or None, use_cache=cache)


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
    sid = state.session_id(request)
    if not consent:
        raise HTTPException(403, "Please agree to the notice before reading a prescription.")
    if variant not in ("v1", "v2", "v3"):
        raise HTTPException(422, "Unknown prompt variant.")
    if ocr_mode not in ("auto", "printed", "handwriting"):
        raise HTTPException(422, "Unknown OCR mode.")
    if text and len(text) > MAX_TEXT:
        raise HTTPException(413, "That's longer than a prescription. Please keep it under 5,000 characters.")
    state.rate_limit(request, "read")
    if sid not in state.consented:
        audit.log_step("consent", None, "consent", agreed=True)
        state.consented.add(sid)

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
    case = state.Case(uuid.uuid4().hex, sid, patient.strip(), stage1, image=raw, cacheable=is_sample)
    state.remember(case)
    return case_json(case)


@app.get("/api/cases/{case_id}/image")
def case_image(case_id: str, request: Request):
    case = state.get_case(case_id, request)
    if case.image is None:
        raise HTTPException(404, "This prescription was typed.")
    return Response(case.image, media_type="application/octet-stream")


# ------------------------------------------------------------------ confirm

class Confirmation(BaseModel):
    fields: dict[str, str | None]


@app.post("/api/cases/{case_id}/items/{index}/confirm")
def confirm(case_id: str, index: int, body: Confirmation, request: Request):
    """The patient says a pharmacist or doctor checked this item. Never fills a gap for them.
    Recorded as self-attested; only a signed-in pharmacist's review is recorded as verified."""
    case = state.get_case(case_id, request)
    items = case.stage1.extraction.prescription.items
    if not 0 <= index < len(items):
        raise HTTPException(404, "No such item.")
    try:
        values = clean_confirmation(body.fields)
    except ConfirmationError as e:
        return JSONResponse({"detail": e.detail, "missing": e.missing}, status_code=422)
    apply_confirmation(items[index], values, Verification(kind="self", at=stamp()))
    case.guides.clear()
    audit.log_step("human_confirm", None, values["name"], item=index)
    return case_json(case)


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
        "verification": ex.verification,
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
    case = state.get_case(case_id, request)
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
        state.rate_limit(request, "guide")

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


def _render_prefs(case: state.Case, large: bool, contrast: bool) -> Prefs:
    return Prefs(case.last_prefs.get("time_format", "12h"), large, contrast)


def _split(entries):
    return [e for e in entries if not e.as_needed], [e for e in entries if e.as_needed]


@app.get("/api/cases/{case_id}/schedule.pdf")
def schedule_pdf(case_id: str, request: Request, large: bool = False, contrast: bool = False, inline: bool = False):
    case = state.get_case(case_id, request)
    if case.last_guide is None:
        raise HTTPException(409, "Write the guide first.")
    timed, prn = _split(case.last_guide.schedule)
    checks = [(ex.name, ex.verification) for ex in case.last_guide.explanations]
    pdf = render_pdf(timed, _render_prefs(case, large, contrast), case.patient, prn, checks)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'{"inline" if inline else "attachment"}; filename="medicine-schedule.pdf"'})


@app.get("/api/cases/{case_id}/guide.html")
def guide_html(case_id: str, request: Request, large: bool = False, contrast: bool = False, download: bool = True):
    case = state.get_case(case_id, request)
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
    page = render_html(timed, _render_prefs(case, large, contrast), case.patient, medicines, prn, note,
                       checks=[(ex.name, ex.verification) for ex in exps])
    headers = {"Content-Disposition": 'attachment; filename="medicine-guide.html"'} if download else {}
    return HTMLResponse(page, headers=headers)


@app.get("/api/cases/{case_id}/reminders.ics")
def reminders(case_id: str, request: Request):
    """A calendar file with an alarm at every dose time, for as many days as the course lasts."""
    case = state.get_case(case_id, request)
    if case.last_guide is None:
        raise HTTPException(409, "Write the guide first.")
    by_name = {it.name.value: it for it in case.stage1.extraction.prescription.items}
    cards = {ex.name: ex.card_en for ex in case.last_guide.explanations}
    entries = []
    for e in case.last_guide.schedule:
        if e.as_needed or not e.times:
            continue
        item, card = by_name.get(e.medication), cards.get(e.medication)
        how = card.row("how_to_take") if card else None
        entries.append({"medicine": e.medication, "dose": e.dose, "times": e.times,
                        "days": course_days(item.duration.value) if item else None, "how": how.text if how else ""})
    return Response(build_ics(entries, date.today()), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="medicine-reminders.ics"'})


@app.get("/api/cases/{case_id}/plan.fhir.json")
def fhir_export(case_id: str, request: Request):
    """The confirmed items as FHIR R4 MedicationRequests. Draft unless a pharmacist verified them."""
    case = state.get_case(case_id, request)
    data = fhir_bundle(case.stage1.extraction.prescription.items, case.patient)
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/fhir+json",
                    headers={"Content-Disposition": 'attachment; filename="medicine-plan.fhir.json"'})


# ------------------------------------------------------------------ audit and deletion

@app.get("/api/audit")
def audit_log(request: Request):
    sid = state.session_id(request)
    return {"session": sid[:12], "rows": audit.read_session(sid)}


@app.delete("/api/session")
def delete_session(request: Request):
    """Forget this browser's cases and start it a new audit session. Others are untouched."""
    sid = state.session_id(request)
    mine = [k for k, c in state.CASES.items() if c.session == sid]
    for k in mine:
        del state.CASES[k]
    state.consented.discard(sid)
    response = JSONResponse({"removed": len(mine)})
    response.delete_cookie(state.COOKIE)
    return response


# ------------------------------------------------------------------ web app

if (DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", include_in_schema=False)
def web_app(path: str):
    if path.startswith("api/"):
        raise HTTPException(404, "No such endpoint.")
    # Files in the build root (service worker, manifest, icons). Resolved and kept inside DIST.
    if path and "/" not in path:
        target = (DIST / path).resolve()
        if target.parent == DIST.resolve() and target.is_file() and target.name != "index.html":
            headers = {"Cache-Control": "no-cache"} if target.name == "sw.js" else None
            return FileResponse(target, headers=headers)
    index = DIST / "index.html"
    if not index.exists():
        return HTMLResponse("<p>The web app is not built yet. Run <code>npm --prefix web install</code> and "
                            "<code>npm --prefix web run build</code>.</p>", status_code=503)
    return FileResponse(index)
