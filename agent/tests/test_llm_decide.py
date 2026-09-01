"""Tests for the LLM chooser: happy path, retry, and every fallback,
using a stubbed model — no API key or network involved."""

import json

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
