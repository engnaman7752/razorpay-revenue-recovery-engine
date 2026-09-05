"""Tests for the LLM chooser: happy path, retry, and every fallback,
using a stubbed model — no API key or network involved."""

import json

import pytest

from graph import llm
from graph.llm import DecideLLM, _parse

CANDIDATES = ["schedule_retry_24h", "payment_link", "retry_now"]
CONTEXT = {"diagnosis": "SOFT_DECLINE", "amount_paise": 120000}


def test_parse_plain_json():
    assert _parse('{"action": "retry_now", "reason": "x"}')["action"] == "retry_now"


def test_parse_json_in_code_fence():
    raw = '```json\n{"action": "payment_link", "reason": "y"}\n```'
    assert _parse(raw)["action"] == "payment_link"


def test_parse_garbage_returns_none():
    assert _parse("sorry, I cannot help") is None
    assert _parse("") is None


def test_happy_path_uses_llm_choice():
    llm = DecideLLM(invoke=lambda p: '{"action": "payment_link", "reason": "customer pays via links"}')
    action, reason, mode = llm.choose(CONTEXT, CANDIDATES)
    assert action == "payment_link" and mode == "llm"
    assert reason == "customer pays via links"


def test_bad_reply_then_good_reply_retries_once():
    replies = iter(["not json at all", '{"action": "retry_now", "reason": "ok"}'])
    llm = DecideLLM(invoke=lambda p: next(replies))
    action, _, mode = llm.choose(CONTEXT, CANDIDATES)
    assert action == "retry_now" and mode == "llm_retry"


def test_persistent_bad_replies_fall_back_to_top_ev():
    calls = []
    llm = DecideLLM(invoke=lambda p: calls.append(p) or "garbage")
    action, reason, mode = llm.choose(CONTEXT, CANDIDATES)
    assert action == CANDIDATES[0]          # top-EV candidate
    assert mode == "fallback_parse"
    assert reason == "fallback: LLM parse failure"
    assert len(calls) == 2                  # exactly one retry


def test_hallucinated_action_is_rejected():
    llm = DecideLLM(invoke=lambda p: '{"action": "refund_everything", "reason": "!"}')
    action, _, mode = llm.choose(CONTEXT, CANDIDATES)
    assert action == CANDIDATES[0] and mode == "fallback_parse"


def test_api_error_falls_back():
    def boom(prompt):
        raise ConnectionError("api down")
    llm = DecideLLM(invoke=boom)
    action, reason, mode = llm.choose(CONTEXT, CANDIDATES)
    assert action == CANDIDATES[0] and mode == "fallback_error"
    assert "LLM error" in reason


def test_no_api_key_means_rule_mode():
    llm = DecideLLM()   # no stub, no GOOGLE_API_KEY in test env
    assert not llm.available
    action, _, mode = llm.choose(CONTEXT, CANDIDATES)
    assert action == CANDIDATES[0] and mode == "rule"


# --------------------------------------------- the REST transport (AQ. keys)
def _fake_response(status, payload):
    class R:
        status_code = status
        text = json.dumps(payload)
        def json(self): return payload
    return R()


def test_rest_call_sends_the_header_not_the_query_param(monkeypatch):
    """AQ.-prefixed keys must go in x-goog-api-key. Passing ?key= as well is
    what produces 'Multiple authentication credentials received'."""
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen["headers"] = kwargs.get("headers", {})
        seen["params"] = kwargs.get("params")
        seen["json"] = kwargs.get("json")
        return _fake_response(200, {"candidates": [{"content": {"parts": [
            {"text": '{"action": "payment_link", "reason": "hard decline"}'}]}}]})

    monkeypatch.setattr(llm.httpx, "post", fake_post)
    monkeypatch.setenv("GOOGLE_API_KEY", "AQ.Ab8FAKEKEY")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.6-flash")

    action, reason, mode = llm.DecideLLM().choose(
        {"diagnosis": "HARD_DECLINE"}, ["payment_link", "retry_now"])

    assert (action, mode) == ("payment_link", "llm")
    assert seen["headers"]["x-goog-api-key"] == "AQ.Ab8FAKEKEY"
    assert seen["params"] is None, "must not also send ?key= — that breaks AQ. keys"
    assert "gemini-3.6-flash:generateContent" in seen["url"]
    assert seen["json"]["generationConfig"]["temperature"] == 0


def test_rest_error_keeps_the_reason_in_the_audit_trail(monkeypatch):
    """A bare exception name sent us debugging the wrong thing once. The
    decision_log must carry what Google actually said."""
    monkeypatch.setattr(llm.httpx, "post", lambda url, **kw: _fake_response(
        404, {"error": {"message": "models/gemini-2.5-flash is no longer "
                                   "available to new users."}}))
    monkeypatch.setenv("GOOGLE_API_KEY", "AQ.Ab8FAKEKEY")

    action, reason, mode = llm.DecideLLM().choose(
        {"diagnosis": "HARD_DECLINE"}, ["payment_link", "retry_now"])

    assert mode == "fallback_error"
    assert action == "payment_link", "must still fall back to the top-EV action"
    assert "404" in reason and "no longer available" in reason


def test_llm_can_be_switched_off_for_the_ablation(monkeypatch):
    """Same key, same everything — LLM_ENABLED=false must give the
    deterministic top-EV chooser, so an A/B batch run is attributable."""
    monkeypatch.setenv("GOOGLE_API_KEY", "AQ.Ab8FAKEKEY")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k:
                        pytest.fail("must not call Gemini when LLM_ENABLED=false"))

    action, reason, mode = llm.DecideLLM().choose(CONTEXT, CANDIDATES)
    assert mode == "rule"
    assert action == CANDIDATES[0]


def test_llm_on_by_default_when_a_key_exists(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "AQ.Ab8FAKEKEY")
    monkeypatch.delenv("LLM_ENABLED", raising=False)
    assert llm.DecideLLM().available is True
