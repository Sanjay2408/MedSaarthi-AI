"""API tests: the safety rules hold on the server, whatever the browser sends. No network."""
import json

import pytest
from fastapi.testclient import TestClient

import api.server as server
from src.llm import LLMResult

EXTRACTED = {"medications": [
    {"name": "Metformin", "dose": None, "route": "oral", "frequency": "BD", "duration": "30 days", "instructions": "after food"},
    {"name": "Paracetamol", "dose": "500 mg", "route": "oral", "frequency": "TDS", "duration": "5 days", "instructions": None},
]}
TEXT = "Rx\n1. Tab. Metformin BD x 30 days after food\n2. Tab. Paracetamol 500 mg TDS x 5 days"


class FakeLLM:
    model_id = "fake:test"

    def __init__(self, *a, **k):
        pass

    def complete(self, system, user, json_mode=False):
        if "PRESCRIPTION_DATA" in system and "transcriber" in system:
            text = json.dumps(EXTRACTED)
        elif "FINAL:" in system:
            text = 'FINAL: {"items": []}'
        else:
            text = "Take Paracetamol 500 mg three times a day, at 8:00 AM, 2:00 PM and 8:00 PM, for 5 days."
        return LLMResult(text, self.model_id, 0.0)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "LLM", FakeLLM)
    monkeypatch.setattr(server, "CASES", {})
    server._hits.clear()
    return TestClient(server.app)


def read(client, **extra):
    data = {"consent": "true", "text": TEXT, "patient": "Test Patient 01", **extra}
    res = client.post("/api/read", data=data)
    assert res.status_code == 200, res.text
    return res.json()


def test_consent_is_required(client):
    assert client.post("/api/read", data={"text": TEXT}).status_code == 403


def test_empty_input_is_rejected(client):
    assert client.post("/api/read", data={"consent": "true", "text": "  "}).status_code == 422


def test_non_image_upload_is_rejected(client):
    res = client.post("/api/read", data={"consent": "true"}, files={"file": ("x.png", b"not an image", "image/png")})
    assert res.status_code == 422


def test_sample_ids_cannot_escape_the_folder(client):
    assert client.get("/api/samples/..%2F..%2Fconfig").status_code == 404
    assert client.get("/api/samples/S99").status_code == 404


def test_missing_dose_is_held_and_left_out_of_the_guide(client):
    case = read(client)
    held, ready = case["items"]
    assert held["status"] == "NEEDS_CONFIRMATION" and held["fields"]["dose"]["value"] is None
    assert ready["status"] == "CLEAR"
    guide = client.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"}).json()
    assert [m["name"] for m in guide["medicines"]] == ["Paracetamol"]
    assert guide["left_out"][0]["name"] == "Metformin"
    assert [t["at"] for t in guide["schedule"][0]["times"]] == ["08:00", "14:00", "20:00"]


def test_confirm_cannot_skip_a_required_field(client):
    case = read(client)
    fields = {f: v["value"] for f, v in case["items"][0]["fields"].items()}
    res = client.post(f"/api/cases/{case['id']}/items/0/confirm", json={"fields": fields})
    assert res.status_code == 422 and "dose" in res.json()["missing"]
    fields["dose"] = "tablet"  # no amount
    res = client.post(f"/api/cases/{case['id']}/items/0/confirm", json={"fields": fields})
    assert res.status_code == 422 and "dose amount" in res.json()["missing"]


def test_confirm_rejects_a_frequency_that_cannot_be_scheduled(client):
    case = read(client)
    fields = {f: v["value"] for f, v in case["items"][0]["fields"].items()} | {"dose": "500 mg", "frequency": "sometimes"}
    assert client.post(f"/api/cases/{case['id']}/items/0/confirm", json={"fields": fields}).status_code == 422


def test_confirm_with_all_fields_makes_item_usable(client):
    case = read(client)
    fields = {f: v["value"] for f, v in case["items"][0]["fields"].items()} | {"dose": "500 mg"}
    res = client.post(f"/api/cases/{case['id']}/items/0/confirm", json={"fields": fields})
    assert res.status_code == 200 and res.json()["items"][0]["status"] == "CONFIRMED"


def test_guide_needs_a_usable_item(client, monkeypatch):
    monkeypatch.setitem(EXTRACTED, "medications", EXTRACTED["medications"][:1])
    case = read(client)
    assert client.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"}).status_code == 409


def test_guide_rejects_bad_preferences(client):
    case = read(client)
    url = f"/api/cases/{case['id']}/guide"
    assert client.post(url, json={"lang": "xx"}).status_code == 422
    assert client.post(url, json={"shift_minutes": 7}).status_code == 422
    assert client.post(url, json={"time_format": "9h"}).status_code == 422


def test_downloads_and_deletion(client):
    case = read(client)
    assert client.get(f"/api/cases/{case['id']}/schedule.pdf").status_code == 409
    client.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"})
    pdf = client.get(f"/api/cases/{case['id']}/schedule.pdf?large=true&contrast=true")
    assert pdf.content.startswith(b"%PDF")
    html = client.get(f"/api/cases/{case['id']}/guide.html")
    assert "Not medical advice" in html.text and "8:00 AM" in html.text
    assert client.delete("/api/session").json()["removed"] == 1
    assert client.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"}).status_code == 404


def test_audit_never_contains_prescription_text(client):
    read(client)
    rows = json.dumps(client.get("/api/audit").json()["rows"])
    assert "Metformin" not in rows and "Paracetamol" not in rows


def test_one_browser_cannot_touch_another_browsers_case(client):
    case = read(client)
    other = TestClient(server.app)
    other.get("/api/audit")
    assert other.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"}).status_code == 404
    assert other.get(f"/api/cases/{case['id']}/schedule.pdf").status_code == 404
    assert other.get("/api/audit").json()["rows"] == []
    assert other.delete("/api/session").json()["removed"] == 0
    assert client.post(f"/api/cases/{case['id']}/guide", json={"lang": "en"}).status_code == 200


def test_typed_prescriptions_never_reach_the_disk_cache(client, monkeypatch):
    flags = []
    monkeypatch.setattr(server, "LLM", lambda model=None, use_cache=True: (flags.append(use_cache), FakeLLM())[1])
    read(client)
    assert flags and not any(flags)
    flags.clear()
    client.post("/api/read", data={"consent": "true", "sample_id": "S01"})
    assert flags and all(flags)


def test_reads_are_rate_limited_per_address(client, monkeypatch):
    monkeypatch.setitem(server.LIMITS, "read", 2)
    read(client)
    read(client)
    assert client.post("/api/read", data={"consent": "true", "text": TEXT}).status_code == 429


def test_oversized_text_is_refused(client):
    assert client.post("/api/read", data={"consent": "true", "text": "x" * 6000}).status_code == 413


def test_item_explains_frequency_codes_in_words(client):
    case = read(client)
    assert case["items"][0]["frequency_plain"] == "Twice a day"
    assert case["items"][1]["frequency_plain"] == "3 times a day"
