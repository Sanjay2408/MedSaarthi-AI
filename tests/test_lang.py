"""Language packs and the template realiser. No network, no models."""
import copy
import dataclasses
import json
from pathlib import Path

import pytest

import src.lang.realiser as realiser
from src.lang import PackError, RealiserError, available, load_pack, render
from src.lang.pack import PACK_DIR, validate
from src.schedule import default_times, needs_refill, parse_frequency
from src.schema import FieldValue, ItemStatus, MedicationItem

ROOT = Path(__file__).resolve().parent.parent
CODES = [p.stem for p in sorted(PACK_DIR.glob("*.json"))]
NON_EN = [c for c in CODES if c != "en"]


def make(name="Paracetamol", dose="500 mg", route="oral", frequency="TDS", duration="5 days", instructions="after food"):
    vals = dict(name=name, dose=dose, route=route, frequency=frequency, duration=duration, instructions=instructions)
    item = MedicationItem(**{k: FieldValue(value=v, confidence=1.0) for k, v in vals.items()})
    item.status = ItemStatus.CONFIRMED
    return item


def times_for(item):
    return default_times(parse_frequency(item.frequency.value))


def sample_items():
    for p in sorted((ROOT / "data" / "samples").glob("S*.json")):
        truth = json.loads(p.read_text(encoding="utf-8"))
        for t in truth["items"]:
            if t["expect_flag"] or t["dose"] is None or t["frequency"] in (None, "QOD?"):
                continue
            yield pytest.param(t, id=f"{truth['id']}-{t['name']}")


def test_expected_packs_exist():
    assert {"en", "hi", "kn", "ta", "te"} <= set(CODES)


@pytest.mark.parametrize("code", CODES)
def test_every_pack_validates_and_is_honest_about_review(code):
    pack = load_pack(code)
    assert pack.code == code
    if code != "en":
        assert not pack.reviewed and pack.review["by"] is None, "no pack may claim a review nobody did"


def test_pack_with_a_digit_is_rejected():
    data = json.loads((PACK_DIR / "hi.json").read_text(encoding="utf-8"))
    data["footer"]["storage"] += " 5"
    with pytest.raises(PackError, match="digit"):
        validate(data)


def test_pack_with_unknown_placeholder_is_rejected():
    data = json.loads((PACK_DIR / "hi.json").read_text(encoding="utf-8"))
    data["labels"]["medicine"] = "दवा {drug}"
    with pytest.raises(PackError, match="placeholder"):
        validate(data)


def test_pack_missing_a_key_is_rejected():
    data = json.loads((PACK_DIR / "kn.json").read_text(encoding="utf-8"))
    del data["notes"]["after_food"]
    with pytest.raises(PackError, match="after_food"):
        validate(data)


def test_reviewed_pack_must_name_its_reviewer():
    data = json.loads((PACK_DIR / "ta.json").read_text(encoding="utf-8"))
    data["review"] = {"status": "reviewed", "by": None, "on": None}
    with pytest.raises(PackError, match="reviewer"):
        validate(data)


@pytest.mark.parametrize("fmt", ["12h", "24h"])
@pytest.mark.parametrize("code", CODES)
@pytest.mark.parametrize("truth", list(sample_items()))
def test_every_sample_renders_in_every_language(truth, code, fmt):
    item = make(**{k: truth[k] for k in ("name", "dose", "route", "frequency", "duration", "instructions")})
    out = render(item, times_for(item), code, time_format=fmt, patient="Test Patient 07")
    assert out.row("medicine").text.startswith(truth["name"])
    assert "{" not in out.text and "}" not in out.text
    spec = parse_frequency(truth["frequency"])
    assert (out.row("when") is None) == (spec.as_needed or not times_for(item))
    assert out.footer[-1] == load_pack(code).footer["disclaimer"]


def test_hindi_keeps_8am_and_8pm_apart():
    """The bug that started this: translation wrote '8 o'clock, 2 o'clock and 8 o'clock'."""
    out = render(make(), ["08:00", "14:00", "20:00"], "hi", time_format="12h")
    assert out.row("when").text == "सुबह 8:00, दोपहर 2:00, रात 8:00"


def test_hindi_golden_card():
    out = render(make(), ["08:00", "14:00", "20:00"], "hi", patient="राम")
    assert out.greeting == "नमस्कार राम।"
    assert [(r.key, r.text) for r in out.rows] == [
        ("medicine", "Paracetamol 500 mg"),
        ("how_often", "दिन में तीन बार"),
        ("when", "सुबह 8:00, दोपहर 2:00, रात 8:00"),
        ("how_long", "5 दिन"),
        ("how_to_take", "पानी के साथ निगल लें, खाने के बाद"),
    ]
    assert len(out.footer) == 2  # storage and disclaimer, no refill line for 5 days


def test_kannada_plural_forms():
    one = render(make(duration="1 day"), ["08:00", "14:00", "20:00"], "kn")
    many = render(make(duration="5 days"), ["08:00", "14:00", "20:00"], "kn")
    assert one.row("how_long").text == "1 ದಿನ"
    assert many.row("how_long").text == "5 ದಿನಗಳು"


def test_24_hour_clock():
    out = render(make(), ["08:00", "14:00", "20:00"], "te", time_format="24h")
    assert out.row("when").text == "ఉదయం 08:00, మధ్యాహ్నం 14:00, రాత్రి 20:00"


def test_english_card_uses_am_pm_without_period_words():
    out = render(make(), ["08:00", "20:00"], "en", time_format="12h")
    assert out.row("when").text == "8:00 AM, 8:00 PM"
    assert out.row("how_often").text == "Three times a day"


def test_eye_drops_in_both_eyes_replace_the_generic_route():
    item = make("Moxifloxacin", "1 drop", "eye", "QID", "5 days", "in both eyes")
    out = render(item, times_for(item), "hi")
    assert out.row("how_to_take").text == "दोनों आँखों में डालें"
    assert out.row("medicine").text == "Moxifloxacin 1 बूँद"
    assert out.row("how_often").text == "दिन में 4 बार"


def test_inhaler_puffs_are_taken_from_the_data_not_the_pack():
    item = make("Salbutamol", "100 mcg", "inhalation", "SOS", "30 days", "2 puffs when breathless")
    out = render(item, [], "ta")
    assert out.row("when") is None
    assert out.row("how_often").text == "தேவைப்படும்போது மட்டும்"
    assert "2" in out.row("how_to_take").text and "பஃப்" in out.row("how_to_take").text
    assert len(out.footer) == 3  # 30 days adds the refill line


def test_changing_per_slot_quantities_are_written_as_prescribed_and_flagged():
    item = make(frequency="2-0-1")
    out = render(item, ["08:00", "20:00"], "hi")
    assert out.row("how_often").text.startswith("2-0-1.")
    assert "फ़ार्मासिस्ट" in out.row("how_often").text


def test_interval_dosing():
    item = make("Ibuprofen", "400 mg", frequency="every 8 hours")
    out = render(item, ["06:00", "14:00", "22:00"], "kn")
    assert out.row("how_often").text == "ಪ್ರತಿ 8 ಗಂಟೆಗೆ"


def test_free_text_with_no_template_is_kept_as_written_and_reported():
    item = make(instructions="after food, avoid direct sunlight")
    out = render(item, ["08:00", "14:00", "20:00"], "hi")
    assert out.untranslated == "avoid direct sunlight"
    assert out.row("note").text == "avoid direct sunlight"
    assert "खाने के बाद" in out.row("how_to_take").text


def test_a_number_inside_unmatched_text_is_still_counted():
    item = make(instructions="2 hours before food")
    out = render(item, ["08:00", "14:00", "20:00"], "hi")
    assert "2" in out.row("note").text


def test_unusable_item_is_refused():
    item = make()
    item.status = ItemStatus.NEEDS_CONFIRMATION
    with pytest.raises(RealiserError):
        render(item, [], "hi")


def test_unparseable_frequency_is_refused():
    with pytest.raises(RealiserError, match="frequency"):
        render(make(frequency="as directed"), [], "hi")


def test_digit_contract_catches_a_pack_that_drops_the_number(monkeypatch):
    pack = load_pack("hi")
    broken = copy.deepcopy(pack.duration)
    broken["day"]["other"] = "कुछ दिन"  # forgot {n}
    monkeypatch.setattr(realiser, "load_pack", lambda code: dataclasses.replace(pack, duration=broken))
    with pytest.raises(RealiserError, match="digit contract"):
        render(make(), ["08:00", "14:00", "20:00"], "hi")


def test_drug_name_with_digits_is_part_of_the_contract():
    out = render(make("Vitamin B12", "1 tablet", frequency="OD"), ["08:00"], "hi")
    assert out.row("medicine").text == "Vitamin B12 1 गोली"


def test_available_lists_review_state():
    info = {p["code"]: p for p in available()}
    assert info["en"]["reviewed"] is True
    assert info["hi"]["reviewed"] is False and info["hi"]["native"] == "हिन्दी"


@pytest.mark.parametrize("duration,expected", [
    ("5 days", False), ("29 days", False), ("30 days", True), ("2 weeks", False), ("1 month", True),
    ("continue", True), ("ongoing", True), (None, False),
])
def test_needs_refill(duration, expected):
    assert needs_refill(duration) is expected
