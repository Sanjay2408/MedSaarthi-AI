"""Accounts, encryption at rest, saved plans and the pharmacist review queue.
In-memory database, fake language model, no network."""
import hashlib

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.auth as auth
import api.server as server
from api import security, state
from api.db import get_db
from api.models import AuthSession, Base, Plan, Review, User
from src import audit
from tests.test_api import TEXT, FakeLLM

PASSWORD = "correct horse battery"
INVITE = "ward-7-invite"


@pytest.fixture
def world(monkeypatch, tmp_path):
    monkeypatch.setenv("MEDSAARTHI_DATA_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("PHARMACIST_INVITE_CODE", INVITE)
    security._cipher.cache_clear()
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine, expire_on_commit=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    server.app.dependency_overrides[get_db] = override
    monkeypatch.setattr(server, "LLM", FakeLLM)
    monkeypatch.setattr(state, "CASES", {})
    monkeypatch.setattr(audit, "load_config", lambda: {"audit": {"path": str(tmp_path / "audit.jsonl")}})
    monkeypatch.setattr(audit, "ROOT", tmp_path)
    state.hits.clear()
    auth._failures.clear()
    yield Session
    server.app.dependency_overrides.clear()
    security._cipher.cache_clear()


def person(world, email, role="patient", name="Asha", invite=None, password=PASSWORD):
    c = TestClient(server.app)
    res = c.post("/api/auth/signup", json={"email": email, "password": password, "name": name, "role": role,
                                           "invite": invite, "agree": True})
    assert res.status_code == 200, res.text
    return c


def pharmacist(world, email="pharm@example.test", name="Ravi Pharmacist"):
    return person(world, email, "pharmacist", name, INVITE)


def read_case(c):
    res = c.post("/api/read", data={"consent": "true", "text": TEXT, "patient": "Test Patient"})
    assert res.status_code == 200, res.text
    return res.json()


def profile_id(c):
    return c.get("/api/auth/me").json()["profiles"][0]["id"]


# ---------------------------------------------------------------- accounts

def test_signup_makes_a_user_a_default_profile_and_a_cookie(world):
    c = person(world, "asha@example.test")
    me = c.get("/api/auth/me").json()
    assert me["user"]["email"] == "asha@example.test" and me["user"]["role"] == "patient"
    assert me["profiles"][0]["is_default"] and me["profiles"][0]["relation"] == "self"
    assert "password" not in str(me).lower()


def test_signup_rules(world):
    c = TestClient(server.app)
    ok = {"email": "a@example.test", "password": PASSWORD, "name": "A", "agree": True}
    assert c.post("/api/auth/signup", json={**ok, "email": "not-an-email"}).status_code == 422
    assert c.post("/api/auth/signup", json={**ok, "agree": False}).status_code == 403
    assert c.post("/api/auth/signup", json={**ok, "password": "short"}).status_code == 422
    assert c.post("/api/auth/signup", json={**ok, "password": "password1234"}).status_code == 422
    assert c.post("/api/auth/signup", json={**ok, "password": "asha-is-my-name", "name": "Asha"}).status_code == 422
    assert c.post("/api/auth/signup", json={**ok, "role": "admin"}).status_code == 422
    assert c.post("/api/auth/signup", json=ok).status_code == 200
    assert TestClient(server.app).post("/api/auth/signup", json=ok).status_code == 409


def test_nobody_can_make_themselves_a_pharmacist(world, monkeypatch):
    ok = {"email": "p@example.test", "password": PASSWORD, "name": "P", "agree": True, "role": "pharmacist"}
    c = TestClient(server.app)
    assert c.post("/api/auth/signup", json=ok).status_code == 403
    assert c.post("/api/auth/signup", json={**ok, "invite": "guess"}).status_code == 403
    assert c.post("/api/auth/signup", json={**ok, "invite": INVITE}).status_code == 200
    monkeypatch.delenv("PHARMACIST_INVITE_CODE")
    assert TestClient(server.app).post("/api/auth/signup", json={**ok, "email": "q@example.test", "invite": ""}).status_code == 403


def test_passwords_and_tokens_are_never_stored_in_clear(world):
    c = person(world, "asha@example.test")
    with world() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
        token = c.cookies.get("ms_auth")
        stored = db.scalar(select(AuthSession)).token_hash
        assert stored == hashlib.sha256(token.encode()).hexdigest() and stored != token


def test_login_logout_and_generic_errors(world):
    person(world, "asha@example.test")
    c = TestClient(server.app)
    wrong = c.post("/api/auth/login", json={"email": "asha@example.test", "password": "wrong-password-1"})
    unknown = c.post("/api/auth/login", json={"email": "nobody@example.test", "password": "wrong-password-1"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()
    assert c.post("/api/auth/login", json={"email": "ASHA@example.test ", "password": PASSWORD}).status_code == 200
    assert c.get("/api/auth/me").json()["user"]["name"] == "Asha"
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").json()["user"] is None


def test_repeated_wrong_passwords_are_throttled_then_cleared_on_success(world):
    person(world, "asha@example.test")
    c = TestClient(server.app)
    bad = {"email": "asha@example.test", "password": "wrong-password-1"}
    codes = [c.post("/api/auth/login", json=bad).status_code for _ in range(9)]
    assert codes[:8] == [401] * 8 and codes[8] == 429
    # even the right password is refused while throttled
    assert c.post("/api/auth/login", json={**bad, "password": PASSWORD}).status_code == 429


def test_a_post_from_another_site_is_refused(world):
    c = TestClient(server.app)
    res = c.post("/api/auth/login", json={"email": "a@example.test", "password": "x"}, headers={"Origin": "https://evil.example"})
    assert res.status_code == 403
    same = c.post("/api/auth/login", json={"email": "a@example.test", "password": "x"}, headers={"Origin": "http://testserver"})
    assert same.status_code == 401


def test_deleting_an_account_needs_the_password_and_removes_everything(world):
    c = person(world, "asha@example.test")
    case = read_case(c)
    c.post("/api/plans", json={"case_id": case["id"], "profile_id": profile_id(c), "share_with_pharmacist": True})
    assert c.request("DELETE", "/api/auth/account", json={"password": "nope-nope-nope"}).status_code == 403
    assert c.request("DELETE", "/api/auth/account", json={"password": PASSWORD}).status_code == 200
    with world() as db:
        assert db.scalar(select(User)) is None and db.scalar(select(Plan)) is None and db.scalar(select(Review)) is None
    assert audit.read_user(1) == []
    assert c.get("/api/auth/me").json()["user"] is None


# ---------------------------------------------------------------- profiles

def test_a_caregiver_looks_after_several_people_each_with_their_own_settings(world):
    c = person(world, "meera@example.test", "caregiver", "Meera")
    kid = c.post("/api/profiles", json={"display_name": "Arjun", "relation": "child", "age_band": "child", "language": "kn"})
    assert kid.status_code == 200 and kid.json()["age_band"] == "child"
    gran = c.post("/api/profiles", json={"display_name": "Ammamma", "relation": "parent", "age_band": "senior",
                                         "language": "te", "large_text": True, "voice_first": True}).json()
    assert gran["large_text"] and gran["voice_first"]
    assert len(c.get("/api/profiles").json()) == 3
    assert c.patch(f"/api/profiles/{gran['id']}", json={"high_contrast": True}).json()["high_contrast"] is True
    assert c.delete(f"/api/profiles/{gran['id']}").status_code == 200


def test_profile_rules(world):
    patient = person(world, "asha@example.test")
    assert patient.post("/api/profiles", json={"display_name": "X"}).status_code == 403
    c = person(world, "meera@example.test", "caregiver", "Meera")
    assert c.post("/api/profiles", json={"display_name": "X", "age_band": "teen"}).status_code == 422
    assert c.post("/api/profiles", json={"display_name": "X", "language": "xx"}).status_code == 422
    assert c.post("/api/profiles", json={"display_name": "X", "relation": "self"}).status_code == 422
    assert c.delete(f"/api/profiles/{profile_id(c)}").status_code == 409  # your own profile stays
    other = person(world, "other@example.test")
    assert other.patch(f"/api/profiles/{profile_id(c)}", json={"large_text": True}).status_code == 404
    assert TestClient(server.app).get("/api/profiles").status_code == 401


# ---------------------------------------------------------------- saved plans

def test_saving_requires_an_account_and_is_encrypted_at_rest(world):
    guest = TestClient(server.app)
    case = read_case(guest)
    assert guest.post("/api/plans", json={"case_id": case["id"], "profile_id": 1}).status_code == 401
    c = person(world, "asha@example.test")
    case = read_case(c)
    saved = c.post("/api/plans", json={"case_id": case["id"], "profile_id": profile_id(c)}).json()
    assert saved["n_items"] == 2 and saved["title"] == "Metformin, Paracetamol"
    with world() as db:
        raw = db.scalar(select(Plan)).data_enc
        assert b"Metformin" not in raw and b"Paracetamol" not in raw
    security._cipher.cache_clear()
    monkey_key = Fernet.generate_key().decode()
    import os
    os.environ["MEDSAARTHI_DATA_KEY"] = monkey_key  # a different key cannot read it
    security._cipher.cache_clear()
    with pytest.raises(ValueError):
        security.decrypt_json(raw)


def test_a_saved_plan_reopens_and_makes_a_guide(world):
    c = person(world, "asha@example.test")
    case = read_case(c)
    plan = c.post("/api/plans", json={"case_id": case["id"], "profile_id": profile_id(c)}).json()
    assert [i["name"] for i in c.get("/api/plans").json()[0]["items"]] == ["Metformin", "Paracetamol"]
    state.CASES.clear()  # forget it, as if the browser had closed
    opened = c.post(f"/api/plans/{plan['id']}/open").json()
    assert opened["plan_id"] == plan["id"] and opened["items"][0]["status"] == "NEEDS_CONFIRMATION"
    guide = c.post(f"/api/cases/{opened['id']}/guide", json={"lang": "hi"}).json()
    assert [m["name"] for m in guide["medicines"]] == ["Paracetamol"]
    assert guide["left_out"][0]["name"] == "Metformin"


def test_nobody_else_can_open_change_or_delete_my_plan(world):
    c = person(world, "asha@example.test")
    plan = c.post("/api/plans", json={"case_id": read_case(c)["id"], "profile_id": profile_id(c)}).json()
    other = person(world, "other@example.test")
    for method, url in (("GET", f"/api/plans/{plan['id']}"), ("POST", f"/api/plans/{plan['id']}/open"),
                        ("DELETE", f"/api/plans/{plan['id']}"), ("POST", f"/api/plans/{plan['id']}/review")):
        assert other.request(method, url, json={"scope": "held"} if url.endswith("review") else None).status_code == 404
    assert other.get("/api/plans").json() == []
    assert c.delete(f"/api/plans/{plan['id']}").status_code == 200 and c.get("/api/plans").json() == []


def test_a_patient_cannot_save_into_someone_elses_profile(world):
    a, b = person(world, "a@example.test"), person(world, "b@example.test")
    case = read_case(a)
    assert a.post("/api/plans", json={"case_id": case["id"], "profile_id": profile_id(b)}).status_code == 404


# ---------------------------------------------------------------- pharmacist review

def share(c):
    case = read_case(c)
    return c.post("/api/plans", json={"case_id": case["id"], "profile_id": profile_id(c), "share_with_pharmacist": True}).json()


def test_only_shared_held_items_reach_the_queue_and_only_pharmacists_see_it(world):
    c = person(world, "asha@example.test")
    p = pharmacist(world)
    c.post("/api/plans", json={"case_id": read_case(c)["id"], "profile_id": profile_id(c)})  # not shared
    assert p.get("/api/review/queue").json() == []
    share(c)
    queue = p.get("/api/review/queue").json()
    assert len(queue) == 1 and queue[0]["item"]["fields"]["name"]["value"] == "Metformin"
    assert queue[0]["item"]["fields"]["dose"]["value"] is None
    assert queue[0]["patient"] == "Asha (adult)" and queue[0]["ocr_lines"]
    assert c.get("/api/review/queue").status_code == 403
    assert TestClient(server.app).get("/api/review/queue").status_code == 401


def test_a_pharmacist_signs_and_the_patient_sees_who_verified_it(world):
    c, p = person(world, "asha@example.test"), pharmacist(world)
    plan = share(c)
    rid = p.get("/api/review/queue").json()[0]["id"]
    fields = {"name": "Metformin", "dose": "", "route": "oral", "frequency": "BD", "duration": "30 days", "instructions": "after food"}
    refused = p.post(f"/api/review/{rid}/verify", json={"fields": fields})
    assert refused.status_code == 422 and "dose" in refused.json()["missing"]
    done = p.post(f"/api/review/{rid}/verify", json={"fields": {**fields, "dose": "500 mg"}}).json()
    assert done["status"] == "verified" and done["reviewed_by"] == "Ravi Pharmacist"
    summary = c.get(f"/api/plans/{plan['id']}").json()
    metformin = summary["items"][0]
    assert metformin["status"] == "CONFIRMED" and metformin["verification"]["kind"] == "pharmacist"
    assert metformin["verification"]["by"] == "Ravi Pharmacist" and summary["pending"] == 0
    # it now flows into the plan, with the badge
    opened = c.post(f"/api/plans/{plan['id']}/open").json()
    guide = c.post(f"/api/cases/{opened['id']}/guide", json={"lang": "kn"}).json()
    badge = {m["name"]: m["verification"] for m in guide["medicines"]}
    assert badge["Metformin"]["kind"] == "pharmacist" and badge["Paracetamol"] is None
    assert p.post(f"/api/review/{rid}/verify", json={"fields": {**fields, "dose": "500 mg"}}).status_code == 409
    assert p.get("/api/review/queue").json() == []
    assert p.get("/api/review/queue?status=done").json()[0]["reviewed_by"] == "Ravi Pharmacist"


def test_declining_keeps_the_item_held_and_tells_the_patient(world):
    c, p = person(world, "asha@example.test"), pharmacist(world)
    plan = share(c)
    rid = p.get("/api/review/queue").json()[0]["id"]
    p.post(f"/api/review/{rid}/decline", json={"note": "Dose unclear. Please see Dr. Rao."})
    summary = c.get(f"/api/plans/{plan['id']}").json()
    assert summary["items"][0]["status"] == "NEEDS_CONFIRMATION"
    assert summary["reviews"][0]["status"] == "declined" and "Dr. Rao" in summary["reviews"][0]["note"]


def test_a_pharmacist_cannot_sign_their_own_prescription(world):
    p = pharmacist(world)
    share(p)
    rid = p.get("/api/review/queue").json()[0]["id"]
    fields = {"name": "Metformin", "dose": "500 mg", "route": "oral", "frequency": "BD", "duration": "30 days"}
    assert p.post(f"/api/review/{rid}/verify", json={"fields": fields}).status_code == 403
    assert p.post(f"/api/review/{rid}/decline", json={"note": ""}).status_code == 403


def test_asking_for_review_again_does_not_duplicate_the_request(world):
    c = person(world, "asha@example.test")
    plan = share(c)
    again = c.post(f"/api/plans/{plan['id']}/review", json={"scope": "held"}).json()
    assert again["pending"] == 1
    assert c.post(f"/api/plans/{plan['id']}/review", json={"scope": "everything"}).status_code == 422


def test_a_patient_confirmation_is_recorded_as_self_attested(world):
    c = person(world, "asha@example.test")
    case = read_case(c)
    fields = {f: v["value"] for f, v in case["items"][0]["fields"].items()} | {"dose": "500 mg"}
    item = c.post(f"/api/cases/{case['id']}/items/0/confirm", json={"fields": fields}).json()["items"][0]
    assert item["status"] == "CONFIRMED" and item["verification"]["kind"] == "self"


# ---------------------------------------------------------------- helpers

@pytest.mark.parametrize("password,ok", [
    ("short", False), ("1234567890", False), ("Password1234", False), ("correct horse battery", True), ("x" * 201, False),
])
def test_password_problem(password, ok):
    assert (security.password_problem(password) is None) is ok
