"""Module 3 tests: the connection to Claude, against a stand-in. No real API calls."""

import pytest

from ai_triage.claude_client import ClaudeClient
from ai_triage.prompt import OUTPUT_SCHEMA
from fakes import FakeSDK, api_error, response

ANSWER = {"summary": "s", "result": "CLEAN", "findings": [], "next_checks": [], "unknowns": []}


def client(*replies, **kwargs):
    fake = FakeSDK(*replies)
    return ClaudeClient(model="claude-haiku-5-5", effort="medium", sdk_client=fake, **kwargs), fake


def test_request_uses_the_model_effort_system_prompt_and_exact_answer_format():
    c, fake = client(response(ANSWER))
    c.draft("SYSTEM", "USER")
    [request] = fake.requests
    assert request["model"] == "claude-haiku-5-5"
    assert request["system"] == "SYSTEM"
    assert request["messages"] == [{"role": "user", "content": "USER"}]
    assert request["output_config"] == {"effort": "medium",
                                        "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}}
    assert request["max_tokens"] >= 8000           # room for thinking plus the answer
    assert "temperature" not in request            # Haiku 5.5 rejects non-default sampling settings


def test_answer_is_read_from_the_text_block_not_the_first_block():
    c, _ = client(response(ANSWER))                 # the fake puts a thinking block first
    reply = c.draft("S", "U")
    assert (reply.ok, reply.answer, reply.error) == (True, ANSWER, None)
    assert reply.usage == {"input_tokens": 3000, "output_tokens": 800}
    assert reply.request_id == "req_test"


@pytest.mark.parametrize("kind, reason", [
    ("auth", "API key was refused"),
    ("rate", "rate limit"),
    ("timeout", "timed out"),
    ("connection", "could not reach"),
    ("server", "error 529"),
    ("bad", "error 400"),
])
def test_every_api_failure_becomes_a_clear_reason_instead_of_a_crash(kind, reason):
    c, _ = client(api_error(kind))
    reply = c.draft("S", "U")
    assert reply.ok is False and reply.answer is None
    assert reason in reply.error


@pytest.mark.parametrize("stop_reason, reason", [("refusal", "declined"), ("max_tokens", "cut off")])
def test_declined_or_cut_off_answers_are_not_used(stop_reason, reason):
    c, _ = client(response(ANSWER, stop_reason=stop_reason))
    reply = c.draft("S", "U")
    assert reply.ok is False and reason in reply.error
    assert reply.usage["output_tokens"] == 800      # still counted: it was still paid for


def test_an_answer_that_is_not_json_is_not_used():
    c, _ = client(response(text="Sure! Here is your summary: ..."))
    reply = c.draft("S", "U")
    assert reply.ok is False and "not valid JSON" in reply.error


def test_missing_api_key_never_reaches_the_network(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    reply = ClaudeClient(model="claude-haiku-5-5", effort="medium").draft("S", "U")
    assert reply.ok is False and "ANTHROPIC_API_KEY is not set" in reply.error
    assert reply.usage == {"input_tokens": 0, "output_tokens": 0}
