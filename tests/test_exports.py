"""Calendar reminders and FHIR export."""
import json
import re
from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

import api.server as server
from api import state
from src.fhir import bundle, dose_quantity, timing
from src.ics import build_ics, course_days
from src.schema import FieldValue, ItemStatus, MedicationItem, Verification
from tests.test_api import TEXT, FakeLLM

NOW = datetime(2026, 11, 30, 9, 0, tzinfo=timezone.utc)


def make(name="Paracetamol", dose="500 mg", route="oral", frequency="TDS", duration="5 days", instructions="after food", verified=None):
    vals = dict(name=name, dose=dose, route=route, frequency=frequency, duration=duration, instructions=instructions)
    item = MedicationItem(**{k: FieldValue(value=v, confidence=1.0) for k, v in vals.items()})
    item.status = ItemStatus.CONFIRMED
    item.verification = verified
    return item


@pytest.mark.parametrize("text,days", [("5 days", 5), ("2 weeks", 14), ("1 month", 30), ("continue", None), (None, None), ("999 days", 365)])
def test_course_days(text, days):
    assert course_days(text) == days


def test_ics_has_one_alarmed_daily_event_per_dose_time():
    entries = [{"medicine": "Paracetamol", "dose": "500 mg", "times": ["08:00", "14:00", "20:00"], "days": 5, "how": "Swallow with water, after food"}]
    ics = build_ics(entries, date(2026, 11, 30), NOW)
    assert ics.startswith("BEGIN:VCALENDAR\r\n") and ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == ics.count("END:VEVENT") == 3 and ics.count("BEGIN:VALARM") == 3
    assert re.findall(r"DTSTART:(\d{8}T\d{6})", ics) == ["20261130T080000", "20261130T140000", "20261130T200000"]
    assert ics.count("RRULE:FREQ=DAILY;COUNT=5") == 3
    assert "SUMMARY:Take Paracetamol 500 mg" in ics and "TRIGGER:PT0M" in ics
    assert "\n" not in ics.replace("\r\n", "")  # only CRLF line endings


def test_ics_escapes_special_characters_and_folds_long_lines():
    entries = [{"medicine": "A, B; C", "dose": "1 tab", "times": ["08:00"], "days": 3, "how": "x" * 200 + " ಕನ್ನಡ"}]
    ics = build_ics(entries, date(2026, 11, 30), NOW)
    assert "SUMMARY:Take A\\, B\\; C 1 tab" in ics
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))
    assert "ಕನ್ನಡ" in ics.replace("\r\n ", "")


def test_open_ended_courses_get_a_month_and_as_needed_gets_nothing():
    open_ended = build_ics([{"medicine": "X", "dose": "1 mg", "times": ["22:00"], "days": None, "how": ""}], date(2026, 11, 30), NOW)
    assert "COUNT=30" in open_ended
    assert "BEGIN:VEVENT" not in build_ics([{"medicine": "X", "dose": "1 mg", "times": [], "days": 3, "how": ""}], date(2026, 11, 30), NOW)


def test_late_dose_end_time_rolls_into_the_next_hour_correctly():
    ics = build_ics([{"medicine": "X", "dose": "1 mg", "times": ["23:55"], "days": 1, "how": ""}], date(2026, 11, 30), NOW)
    assert "DTEND:20261201T000500" in ics


# ---------------------------------------------------------------- FHIR

def test_dose_quantity_uses_ucum_and_keeps_unit_words():
    assert dose_quantity("500 mg") == {"value": 500.0, "unit": "mg", "system": "http://unitsofmeasure.org", "code": "mg"}
    assert dose_quantity("100 mcg")["code"] == "ug"
    assert dose_quantity("1 drop") == {"value": 1.0, "unit": "drop"}
    assert dose_quantity("some") is None


@pytest.mark.parametrize("freq,expect", [
    ("TDS", {"frequency": 3, "period": 1, "periodUnit": "d"}),
    ("every 8 hours", {"frequency": 1, "period": 8, "periodUnit": "h"}),
    ("1-0-1", {"frequency": 2, "period": 1, "periodUnit": "d", "when": ["MORN", "NIGHT"]}),
    ("HS", {"frequency": 1, "period": 1, "periodUnit": "d", "when": ["HS"]}),
])
def test_timing(freq, expect):
    assert timing(freq)["timing"]["repeat"] == expect


def test_as_needed_and_unparseable_frequencies():
    assert timing("SOS") == {"asNeededBoolean": True}
    assert timing("as directed") == {}


def test_a_self_checked_item_is_a_draft_and_a_pharmacist_verified_one_is_active():
    mine = make()
    signed = make("Metformin", verified=Verification(kind="pharmacist", by="Ravi", at="2026-11-30T09:00:00+00:00"))
    held = make("Held")
    held.status = ItemStatus.NEEDS_CONFIRMATION
    b = bundle([mine, signed, held], "Asha", NOW)
    assert b["resourceType"] == "Bundle" and len(b["entry"]) == 2  # a held item is never exported
    by = {e["resource"]["medicationCodeableConcept"]["text"]: e["resource"] for e in b["entry"]}
    assert by["Paracetamol"]["status"] == "draft" and "NOT verified" in by["Paracetamol"]["note"][0]["text"]
    assert by["Metformin"]["status"] == "active" and "Ravi" in by["Metformin"]["note"][0]["text"]
    assert by["Paracetamol"]["dispenseRequest"]["expectedSupplyDuration"]["value"] == 5
    assert by["Paracetamol"]["dosageInstruction"][0]["doseAndRate"][0]["doseQuantity"]["value"] == 500.0
    assert all(r["intent"] == "plan" for r in by.values())


# ---------------------------------------------------------------- endpoints

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "LLM", FakeLLM)
    monkeypatch.setattr(state, "CASES", {})
    state.hits.clear()
    return TestClient(server.app)


def test_reminders_and_fhir_endpoints(client):
    case = client.post("/api/read", data={"consent": "true", "text": TEXT, "patient": "Test Patient"}).json()
    assert client.get(f"/api/cases/{case['id']}/reminders.ics").status_code == 409  # no guide yet
    client.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"})
    res = client.get(f"/api/cases/{case['id']}/reminders.ics")
    assert res.headers["content-type"].startswith("text/calendar")
    assert res.text.count("BEGIN:VEVENT") == 3 and "COUNT=5" in res.text and "Metformin" not in res.text  # held item excluded
    fhir = client.get(f"/api/cases/{case['id']}/plan.fhir.json")
    data = json.loads(fhir.text)
    assert [e["resource"]["medicationCodeableConcept"]["text"] for e in data["entry"]] == ["Paracetamol"]
    assert data["entry"][0]["resource"]["status"] == "draft"
    assert client.get("/api/cases/nope/reminders.ics").status_code == 404
