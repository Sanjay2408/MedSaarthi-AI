"""MedSaarthi AI: Streamlit front end.

Screens: 1 consent -> 2 input -> 3 review & confirm -> 4 preferences -> 5 result.
Run:  streamlit run app/streamlit_app.py
"""
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import audit  # noqa: E402
from src.config import load_config  # noqa: E402
from src.llm import LLM  # noqa: E402
from src.pipeline import explain, read_and_extract  # noqa: E402
from src.render import Prefs, render_html, render_pdf  # noqa: E402
from src.schema import ALL_FIELDS, REQUIRED_FIELDS, FieldValue, ItemStatus  # noqa: E402
from src.translate import NOTE  # noqa: E402

CFG = load_config()
THRESHOLD = CFG["safety"]["confidence_threshold"]
LANGS = {"English": "en", "हिन्दी (Hindi)": "hi", "ಕನ್ನಡ (Kannada)": "kn", "தமிழ் (Tamil)": "ta", "తెలుగు (Telugu)": "te"}
STEPS = ["Consent", "Prescription", "Review", "Preferences", "Result"]

st.set_page_config(page_title="MedSaarthi AI", page_icon="💊", layout="centered")
ss = st.session_state
ss.setdefault("step", 0)
ss.setdefault("prefs", {"lang": "English", "time_format": "24h", "large": False, "contrast": False, "shift": 0})


def go(step: int):
    ss.step = step
    st.rerun()


def style():
    p = ss.prefs
    css = ""
    if p["large"]:
        css += "html, body, [class*='css'], p, li, label, input, textarea {font-size: 1.25rem !important;}"
    if p["contrast"]:
        css += (".stApp {background:#000 !important; color:#fff !important;} "
                ".stApp p, .stApp li, .stApp label, .stApp h1, .stApp h2, .stApp h3 {color:#fff !important;}")
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def conf_badge(c: float) -> str:
    if c >= 0.9:
        return f"🟢 {c:.2f}"
    if c >= THRESHOLD:
        return f"🟡 {c:.2f}"
    return f"🔴 {c:.2f}"


style()
st.title("💊 MedSaarthi AI")
st.caption("Prescription interpretation and medication guidance. **Prototype on synthetic data. "
           + CFG["safety"]["disclaimer"] + "**")
st.progress((ss.step + 1) / len(STEPS), text=f"Step {ss.step + 1} of {len(STEPS)}: {STEPS[ss.step]}")

with st.sidebar:
    st.subheader("Settings")
    model = st.selectbox("Language model (Groq)", [CFG["llm"]["model"]] + CFG["llm"]["alt_models"])
    variant = st.selectbox("Prompt variant", ["v2", "v3", "v1"], format_func={
        "v1": "V1 baseline", "v2": "V2 engineered", "v3": "V3 engineered + leaflet RAG"}.get)
    ocr_mode = st.selectbox("OCR mode", ["auto", "printed", "handwriting"])
    st.divider()
    if st.button("🗑️ Delete my session data"):
        for k in list(ss.keys()):
            del ss[k]
        st.rerun()
    st.caption(f"Audit session id: `{audit.SESSION_ID}`")

llm = LLM(model=model)

# ------------------------------------------------------------------ 1. consent
if ss.step == 0:
    st.header("Before you start")
    st.markdown(
        "- This is a **student prototype**, tested only on **synthetic** prescriptions. It is not a medical device.\n"
        "- It never changes or guesses doses. Unclear items must be confirmed by a pharmacist or doctor.\n"
        "- **Privacy:** images are read on this computer (local OCR). The extracted text is sent to the Groq API "
        "for language processing. Do not enter real patient data.\n"
        "- An audit log stores only step names, model ids and a hash of the input, never the text itself.\n"
        "- Translations are machine-generated and not professionally validated.")
    agree = st.checkbox("I understand and agree to continue.")
    if st.button("Continue", type="primary", disabled=not agree):
        audit.log_step("consent", None, "consent", agreed=True)
        go(1)

# ------------------------------------------------------------------ 2. input
elif ss.step == 1:
    st.header("Add a prescription")
    tab_img, tab_txt, tab_demo = st.tabs(["📷 Upload photo", "⌨️ Type text", "🧪 Synthetic sample"])
    image, text, alias = None, None, None
    with tab_img:
        up = st.file_uploader("Prescription image", type=["png", "jpg", "jpeg"])
        if up:
            st.image(up, use_container_width=True)
            image = up
    with tab_txt:
        typed = st.text_area("Prescription text", height=180,
                             placeholder="Tab. Paracetamol 500 mg TDS x 5 days after food")
        text = typed or None
    with tab_demo:
        samples = sorted(p.stem for p in (ROOT / "data/samples").glob("S*.txt"))
        sid = st.selectbox("Sample", [""] + samples)
        demo_as_image = st.checkbox("Use the image version (runs OCR)")
        if sid:
            if demo_as_image:
                st.image(str(ROOT / f"data/samples/{sid}.png"))
                image = str(ROOT / f"data/samples/{sid}.png")
            else:
                text = (ROOT / f"data/samples/{sid}.txt").read_text(encoding="utf-8")
                st.code(text)
            alias = f"Test Patient {sid[1:]}"
    alias = st.text_input("Patient name for greeting (optional, use a made-up name)", value=alias or "")
    if st.button("Read prescription", type="primary", disabled=not (image or text)):
        with st.spinner("Reading and extracting..."):
            try:
                ss.stage1 = read_and_extract(image=image, text=None if image else text, ocr_mode=ocr_mode,
                                             variant="v1" if variant == "v1" else "v2", llm=llm, patient_alias=alias)
                ss.patient = alias
                go(2)
            except Exception as e:  # show a plain message, keep the app alive
                st.error(f"Could not process this prescription: {e}")

# ------------------------------------------------------------------ 3. review & confirm
elif ss.step == 2:
    s1 = ss.stage1
    st.header("Check what was read")
    if s1.extraction.injection_hits:
        st.warning("⚠️ The prescription contains text that looks like instructions to the AI "
                   f"({'; '.join(s1.extraction.injection_hits)}). It was treated as data and ignored. "
                   "Please check the items carefully.")
    with st.expander(f"Text read from the prescription ({s1.ocr.engine}, mean confidence {s1.ocr.mean_confidence:.2f})",
                     expanded=s1.ocr.engine != "typed"):
        for line in s1.ocr.lines:
            st.markdown(f"{conf_badge(line.confidence)} `{line.text}`")
    items = s1.extraction.prescription.items
    if not items:
        st.error("No medicines were found. Please type the prescription or ask your pharmacist.")
    st.caption("🟢 high confidence · 🟡 acceptable · 🔴 below threshold, needs confirmation")
    for i, it in enumerate(items):
        flagged = it.status == ItemStatus.NEEDS_CONFIRMATION
        title = f"{'⚠️' if flagged else '✅'} {it.name.value or 'Unknown medicine'}"
        with st.expander(title, expanded=flagged):
            if flagged:
                st.error("Needs confirmation: " + ", ".join(r.value for r in it.reasons) +
                         ". This item will not be explained or scheduled until confirmed.")
            cols = st.columns(2)
            edits = {}
            for j, f in enumerate(ALL_FIELDS):
                fv = it.field(f)
                with cols[j % 2]:
                    edits[f] = st.text_input(f"{f.title()}  {conf_badge(fv.confidence) if fv.value else '⬜ missing'}",
                                             value=fv.value or "", key=f"f{i}{f}")
            changed = any((edits[f] or None) != it.field(f).value for f in ALL_FIELDS)
            if flagged or changed:
                ok = st.checkbox("I have checked this item with the prescription and my pharmacist/doctor.", key=f"c{i}")
                missing = [f for f in REQUIRED_FIELDS if not edits[f].strip()]
                if ok and missing:
                    st.warning("Fill in: " + ", ".join(missing) + " (ask your pharmacist; do not guess).")
                if ok and not missing:
                    for f in ALL_FIELDS:
                        setattr(it, f, FieldValue(value=edits[f].strip() or None, confidence=1.0))
                    it.status = ItemStatus.CONFIRMED
                    audit.log_step("human_confirm", None, it.name.value or "", item=i)
                    st.success("Confirmed.")
    pending = sum(1 for it in items if it.status == ItemStatus.NEEDS_CONFIRMATION)
    c1, c2 = st.columns(2)
    if c1.button("← Back"):
        go(1)
    if c2.button("Continue", type="primary", disabled=not items):
        if pending:
            st.info(f"{pending} item(s) still need confirmation and will be left out of the schedule.")
        go(3)

# ------------------------------------------------------------------ 4. preferences
elif ss.step == 3:
    st.header("Your preferences")
    p = ss.prefs
    p["lang"] = st.selectbox("Language", list(LANGS), index=list(LANGS).index(p["lang"]))
    p["time_format"] = st.radio("Time format", ["24h", "12h"], horizontal=True, index=["24h", "12h"].index(p["time_format"]))
    p["large"] = st.toggle("Large text", value=p["large"])
    p["contrast"] = st.toggle("High contrast", value=p["contrast"])
    p["shift"] = st.select_slider("Move all default times (minutes)", options=list(range(-120, 121, 30)), value=p["shift"])
    st.caption("Default times: morning 08:00, afternoon 14:00, night 20:00; 'every 8 hours' starts at 06:00.")
    c1, c2 = st.columns(2)
    if c1.button("← Back"):
        go(2)
    if c2.button("Create my guide", type="primary"):
        with st.spinner("Writing instructions and translating (translation runs on this computer and can take a minute)..."):
            ss.stage2 = explain(ss.stage1.extraction.prescription.items, variant=variant, lang=LANGS[p["lang"]],
                                time_format=p["time_format"], shift_minutes=p["shift"], patient=ss.get("patient", ""),
                                llm=llm)
        go(4)

# ------------------------------------------------------------------ 5. result
elif ss.step == 4:
    s2, p = ss.stage2, ss.prefs
    st.header("Your medicine guide")
    prefs = Prefs(p["time_format"], p["large"], p["contrast"])
    timed = [e for e in s2.schedule if not e.as_needed]
    prn = [e for e in s2.schedule if e.as_needed]
    explanations = []
    for name, simp, tr in s2.explanations:
        with st.container(border=True):
            st.subheader(name)
            if simp.blocked:
                st.warning("The AI wording did not pass the safety check, so the confirmed prescription is shown as written.")
            if tr and not tr.blocked:
                st.markdown(tr.text)
                st.caption(f"{NOTE} Back-translation similarity: {tr.similarity:.0f}/100")
                with st.expander("English"):
                    st.text(simp.final_text)
            else:
                if tr and tr.blocked:
                    st.warning("The translation changed a number, so it was hidden. Showing English.")
                st.text(simp.final_text)
        explanations.append((name, simp.final_text, tr.text if tr and not tr.blocked else None))
    if s2.skipped:
        st.error("Not included (needs confirmation or the frequency could not be read): "
                 + ", ".join(i.name.value or "unknown" for i in s2.skipped))
    st.subheader("Daily schedule")
    from src.render import timeline
    from src.schedule import format_time
    for t, ents in timeline(timed):
        st.markdown(f"**{format_time(t, p['time_format'])}**: " + ", ".join(f"{e.medication} {e.dose}" for e in ents))
    for e in prn:
        st.markdown(f"**Only when needed**: {e.medication} {e.dose}")
    patient = ss.get("patient", "")
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ Schedule (PDF)", render_pdf(timed, prefs, patient, prn), "schedule.pdf", "application/pdf")
    c2.download_button("⬇️ Full guide (HTML, printable)",
                       render_html(timed, prefs, patient, explanations, prn, NOTE if LANGS[p["lang"]] != "en" else None),
                       "guide.html", "text/html")
    st.info(CFG["safety"]["disclaimer"])
    with st.expander("Audit trail for this session (hashes only)"):
        st.dataframe(audit.read_session(), use_container_width=True)
    if st.button("← Change preferences"):
        go(3)
