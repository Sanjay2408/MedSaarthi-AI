"""End-to-end check of the web app in a real browser. Needs the server running on :8000.

    python tests/e2e_web.py [screenshot_dir]

Walks the injection sample through add, check and plan in Hindi, checks that morning and night
stay apart, then measures the contrast of every piece of text on every screen in normal and
high-contrast mode (WCAG AA, 4.5:1), which is the check that would have caught the unreadable
sidebar in the old Streamlit app. Exits non-zero on any failure.
"""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:8000"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else None
failures: list[str] = []
CHECK_TITLE = re.compile("double-check|what I found")

CONTRAST_JS = """
() => {
  const parse = c => { const m = c.match(/[\\d.]+/g).map(Number); return {r:m[0],g:m[1],b:m[2],a:m[3]===undefined?1:m[3]}; };
  const over = (top, under) => ({r:top.r*top.a+under.r*(1-top.a), g:top.g*top.a+under.g*(1-top.a), b:top.b*top.a+under.b*(1-top.a), a:1});
  const lum = ({r,g,b}) => { const f = v => { v/=255; return v<=.03928? v/12.92 : Math.pow((v+.055)/1.055,2.4); };
    return .2126*f(r)+.7152*f(g)+.0722*f(b); };
  const bgOf = el => { const layers=[]; for (let e=el; e; e=e.parentElement) { const c=parse(getComputedStyle(e).backgroundColor);
      if (c.a>0) { layers.push(c); if (c.a>.99) break; } }
    let out={r:255,g:255,b:255,a:1}; for (const l of layers.reverse()) out=over(l,out); return out; };
  const out = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const text = walker.currentNode.textContent.trim(); if (!text) continue;
    const el = walker.currentNode.parentElement; const s = getComputedStyle(el);
    if (s.visibility==='hidden'||s.display==='none'||el.closest('option,script,style,.sr-only')) continue;
    const r = el.getBoundingClientRect(); if (r.width<2||r.height<2) continue;
    const fg=parse(s.color), bg=bgOf(el); const a=lum(fg), b=lum(bg);
    const ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    if (ratio<4.5) out.push({text:text.slice(0,50),ratio:+ratio.toFixed(2),color:s.color,bg:`rgb(${Math.round(bg.r)},${Math.round(bg.g)},${Math.round(bg.b)})`});
  }
  return out;
}
"""
TAP_JS = """
() => [...document.querySelectorAll('button,a,select,input:not([type=file]):not([type=checkbox]),summary')].filter(e => {
  const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && r.height < 36 && !e.closest('.segmented.small'); })
  .map(e => (e.innerText || e.getAttribute('aria-label') || e.type).slice(0, 30) + ' ' + Math.round(e.getBoundingClientRect().height))
"""


def check(ok: bool, what: str):
    print(("PASS " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def audit(page, name: str):
    bad = page.evaluate(CONTRAST_JS)
    over = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
    check(not bad, f"{name}: all text at 4.5:1 or better" + (f" -> {bad[:4]}" if bad else ""))
    check(not over, f"{name}: no sideways scroll")
    if OUT:
        OUT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=OUT / f"{name}.png", full_page=True)


def both_modes(page, name: str):
    page.wait_for_timeout(350)  # let colour transitions finish before measuring
    audit(page, name)
    page.get_by_role("switch", name="High contrast").click()
    page.wait_for_timeout(350)
    audit(page, f"{name}-contrast")
    page.get_by_role("switch", name="High contrast").click()
    page.wait_for_timeout(350)


def run(page):
    errors: list[str] = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="networkidle")
    read_btn = page.get_by_role("button", name="Read my prescription")
    check(read_btn.is_disabled(), "cannot start before agreeing to the notice")
    both_modes(page, "1-start")

    page.get_by_label("I understand and agree").check()
    read_btn.click()
    page.locator(".says h1", has_text=CHECK_TITLE).wait_for(timeout=180000)
    check(page.get_by_text("I found a note that isn't meant for you").is_visible(), "injection note is shown in calm words")
    dose = page.locator("#item-0-dose")
    value = dose.input_value() if dose.evaluate("e => e.tagName") == "INPUT" else dose.inner_text()
    check(value == "500 mg", "dose stayed 500 mg despite 'double the dose'")
    both_modes(page, "2-check-injection")

    page.get_by_text("How sure am I about each line?").click()
    check(page.get_by_text("Ignored", exact=True).first.is_visible(), "injected line is marked as ignored")

    if page.get_by_role("button", name="My pharmacist confirmed this").count():
        page.get_by_role("button", name="My pharmacist confirmed this").first.click()
        page.get_by_text("Checked", exact=True).wait_for()
    page.get_by_role("button", name="See my plan").click()
    page.locator(".dose-time").first.wait_for(timeout=180000)
    check(page.locator(".dose-time").all_inner_texts() == ["8:00 AM", "2:00 PM", "8:00 PM"], "plan shows 8:00 AM, 2:00 PM, 8:00 PM")
    check(page.locator(".tile-morning .dose-time").inner_text() == "8:00 AM" and page.locator(".tile-night .dose-time").inner_text() == "8:00 PM",
          "8 AM sits in the morning tile and 8 PM in the night tile")
    both_modes(page, "3-plan-english")

    ticks = page.get_by_role("checkbox", name="8:00 AM")
    ticks.click()
    page.wait_for_timeout(200)
    check(ticks.get_attribute("aria-checked") == "true" and page.get_by_text("Today: 1 of 3").is_visible(), "ticking a dose counts 1 of 3")
    ticks.click()
    page.wait_for_timeout(200)
    check(page.get_by_text("Today: 0 of 3").is_visible(), "a tick can be undone")
    for t in ("8:00 AM", "2:00 PM", "8:00 PM"):
        page.get_by_role("checkbox", name=t).click()
    page.wait_for_timeout(200)
    check(page.get_by_role("heading", name="That's everything for today").is_visible(), "finishing the day gets one calm line")
    body = page.locator("main").inner_text().lower()
    check(not any(w in body for w in ("streak", "points", "badge")), "no streaks, points or badges")
    both_modes(page, "4-plan-all-done")

    with page.expect_download() as dl:
        page.get_by_role("link", name="Print my plan").click()
    check(dl.value.suggested_filename == "medicine-schedule.pdf", "schedule PDF downloads")

    page.get_by_label("Language").select_option("hi")
    page.locator(".guide-text[lang=hi]").wait_for(timeout=300000)
    hindi = page.locator(".guide-text[lang=hi]").first.inner_text()
    print("  Hindi guide:", " | ".join(x for x in hindi.split("\n") if x))
    check("सुबह 8:00" in hindi and "रात 8:00" in hindi, "Hindi says morning 8:00 and night 8:00, so they cannot be confused")
    check(page.locator(".tile-night h3").inner_text() == "रात", "tile labels switch to Hindi")
    check(page.get_by_text("Machine translation").first.is_visible(), "machine-translation note is shown")
    both_modes(page, "5-plan-hindi")

    page.get_by_role("button", name="Your privacy").click()
    page.get_by_role("cell", name="Translated").first.wait_for()
    check("Paracetamol" not in page.locator("main").inner_text(), "privacy log holds no prescription text")
    both_modes(page, "6-privacy")
    page.get_by_role("button", name="Back to my plan").click()

    # the missing-dose path: held, cannot be confirmed empty, then confirmed with a value
    page.get_by_role("button", name="Add prescription").click()
    page.get_by_role("radio", name="Something is missing").click()
    page.get_by_role("button", name="As text").click()
    page.get_by_role("button", name="Read my prescription").click()
    page.get_by_role("heading", name="double-check Metformin").wait_for(timeout=120000)
    check(page.get_by_text("Let's check this one").is_visible(), "missing dose is held in calm words")
    check(page.get_by_text("You haven't done anything wrong").is_visible(), "the patient is reassured it isn't their fault")
    check(page.locator("#item-0-dose").input_value() == "", "missing dose is left empty, not guessed")
    check(page.get_by_role("button", name="Waiting for your pharmacist's check").is_disabled(), "plan waits until something is checked")
    both_modes(page, "7-check-missing-dose")
    page.get_by_role("button", name="My pharmacist confirmed this").click()
    page.get_by_text("Still needed: dose").wait_for()
    check(True, "confirming with an empty dose is refused")
    page.locator("#item-0-dose").fill("500 mg")
    page.get_by_role("button", name="My pharmacist confirmed this").click()
    page.get_by_text("Checked", exact=True).wait_for()
    check(True, "confirming with a dose succeeds")

    page.get_by_role("switch", name="Bigger text").click()
    both_modes(page, "8-check-bigger-text")
    page.get_by_role("switch", name="Bigger text").click()
    check(not errors, f"no JavaScript errors {errors[:2] if errors else ''}")


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
    run(ctx.new_page())
    phone = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    page = phone.new_page()
    page.goto(URL, wait_until="networkidle")
    both_modes(page, "9-phone-start")
    small = page.evaluate(TAP_JS)
    check(not small, f"phone: touch targets are big enough {small[:5] if small else ''}")
    page.get_by_label("I understand and agree").check()
    page.get_by_role("button", name="As text").click()
    page.get_by_role("button", name="Read my prescription").click()
    page.locator(".says h1", has_text=CHECK_TITLE).wait_for(timeout=180000)
    both_modes(page, "10-phone-check")
    if page.get_by_role("button", name="My pharmacist confirmed this").count():
        page.get_by_role("button", name="My pharmacist confirmed this").first.click()
        page.get_by_text("Checked", exact=True).wait_for()
    page.get_by_role("button", name="See my plan").click()
    page.locator(".dose-time").first.wait_for(timeout=180000)
    both_modes(page, "11-phone-plan")
    browser.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
