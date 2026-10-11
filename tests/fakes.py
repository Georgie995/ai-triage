"""A stand-in for the Anthropic SDK client, so no test ever calls the real API or spends money."""

import json
from types import SimpleNamespace

import anthropic
import httpx2

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def response(answer=None, text=None, stop_reason="end_turn", input_tokens=3000, output_tokens=800):
    """A reply shaped like the SDK's Message: thinking block first, then the JSON text."""
    body = text if text is not None else json.dumps(answer)
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=body)],
        stop_reason=stop_reason, stop_details=None, _request_id="req_test",
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens))


def api_error(kind):
    if kind == "timeout":
        return anthropic.APITimeoutError(request=REQUEST)
    if kind == "connection":
        return anthropic.APIConnectionError(request=REQUEST)
    status = {"auth": 401, "rate": 429, "server": 529, "bad": 400}[kind]
    cls = {"auth": anthropic.AuthenticationError, "rate": anthropic.RateLimitError,
           "server": anthropic.InternalServerError, "bad": anthropic.BadRequestError}[kind]
    return cls(f"error {status}", response=httpx2.Response(status, request=REQUEST), body=None)


class FakeSDK:
    """Replies (or errors) are queued per test. Every request is recorded for inspection."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **request):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
