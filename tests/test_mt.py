"""The ordered provider chain and its answer checks. Providers are faked; nothing touches the network."""
import pytest

import src.mt as mt
from src.mt import MTUnavailable, check, script_ratio, translate_chain


class Fake:
    def __init__(self, name, out=None, available=True, error=None):
        self.name, self._out, self._available, self._error = name, out, available, error
        self.calls = 0

    def available(self):
        return self._available

    def translate(self, texts, lang, src="en"):
        self.calls += 1
        if self._error:
            raise self._error
        return self._out(texts) if callable(self._out) else self._out


@pytest.fixture
def providers(monkeypatch):
    def install(**fakes):
        monkeypatch.setattr(mt, "PROVIDERS", {k: (lambda f=f: f) for k, f in fakes.items()})
    return install


GOOD = lambda texts: ["आपको यह दवा डॉक्टर के बताए अनुसार लेनी है " + t for t in texts]  # noqa: E731  mostly Devanagari, numbers kept


def test_script_ratio_ignores_latin_drug_names_but_catches_english():
    assert script_ratio("Paracetamol 500 mg दिन में तीन बार", "Devanagari") > 0.3
    assert script_ratio("Take it twice a day", "Devanagari") == 0.0


def test_check_accepts_a_faithful_translation():
    assert check(["Take 5 days"], ["5 दिन लें"], "hi") == []


def test_check_rejects_changed_numbers_wrong_script_and_lost_drug_names():
    assert "numbers changed" in check(["Take 5 days"], ["6 दिन लें"], "hi")[0]
    assert "not written in" in check(["Take it daily"], ["Take it daily"], "hi")[0]
    assert "drug name lost" in check(["Take Metformin"], ["दवा लें"], "hi", keep=("Metformin",))[0]
    assert "expected 2 lines" in check(["a", "b"], ["x"], "hi")[0]


def test_chain_skips_providers_without_keys_and_uses_the_next(providers):
    a, b = Fake("a", available=False), Fake("b", GOOD)
    providers(a=a, b=b)
    res = translate_chain(["Take 5 days"], "hi", order=["a", "b"])
    assert res.provider == "b" and a.calls == 0
    assert [x["status"] for x in res.attempts] == ["no key", "ok"]


def test_chain_moves_on_after_an_error(providers):
    providers(a=Fake("a", error=TimeoutError()), b=Fake("b", GOOD))
    res = translate_chain(["Take 5 days"], "hi", order=["a", "b"])
    assert res.provider == "b" and res.attempts[0]["status"] == "error: TimeoutError"


def test_chain_moves_on_when_numbers_change(providers):
    providers(a=Fake("a", lambda t: ["६ दिन"]), b=Fake("b", GOOD))
    res = translate_chain(["Take 5 days"], "hi", order=["a", "b"])
    assert res.provider == "b" and res.attempts[0]["status"] == "failed check"


def test_chain_raises_with_the_attempts_when_nothing_passes(providers):
    providers(a=Fake("a", available=False), b=Fake("b", lambda t: ["wrong"]))
    with pytest.raises(MTUnavailable) as e:
        translate_chain(["Take 5 days"], "hi", order=["a", "b"])
    assert [x["status"] for x in e.value.attempts] == ["no key", "failed check"]


def test_english_needs_no_provider():
    assert translate_chain(["Take it"], "en").texts == ["Take it"]


def test_unknown_language_is_rejected():
    with pytest.raises(KeyError):
        mt.lang_info("xx")


def test_sarvam_without_a_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert mt.SarvamMT().available() is False
