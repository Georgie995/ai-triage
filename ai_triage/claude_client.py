"""Module 3: the ONLY code that talks to the network, through the official Anthropic SDK.

Every way a request can go wrong becomes a plain reason (ModelReply.error) instead of a crash,
so the caller can fall back to a code-written note.
"""

import json
import os
from dataclasses import dataclass, field

import anthropic

from .prompt import OUTPUT_SCHEMA

MAX_TOKENS = 16000  # Haiku 5.5 thinks before answering, and thinking counts towards this limit


@dataclass
class ModelReply:
    ok: bool
    answer: dict | None
    error: str | None
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    request_id: str | None = None


class ClaudeClient:
    def __init__(self, model, effort, timeout=60, sdk_client=None):
        self.model, self.effort = model, effort
        self._timeout = timeout
        self._sdk = sdk_client  # tests pass a stand-in here; otherwise created on first use

    def draft(self, system_prompt, user_message):
        if self._sdk is None:
            if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
                return ModelReply(False, None, "ANTHROPIC_API_KEY is not set")
            # The SDK retries connection errors, 429 and 5xx twice by itself, with backoff.
            self._sdk = anthropic.Anthropic(timeout=self._timeout, max_retries=2)
        try:
            response = self._sdk.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
                # No temperature: Haiku 5.5 rejects non-default sampling settings.
                output_config={"effort": self.effort,
                               "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            )
        except anthropic.AuthenticationError:
            return ModelReply(False, None, "the API key was refused (check ANTHROPIC_API_KEY)")
        except anthropic.RateLimitError:
            return ModelReply(False, None, "rate limit reached; try again later")
        except anthropic.APITimeoutError:
            return ModelReply(False, None, f"the request timed out after {self._timeout} seconds")
        except anthropic.APIConnectionError:
            return ModelReply(False, None, "could not reach the Anthropic API (network problem)")
        except anthropic.APIStatusError as error:
            return ModelReply(False, None, f"the API returned error {error.status_code}")

        usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens}
        request_id = getattr(response, "_request_id", None)
        if response.stop_reason == "refusal":
            return ModelReply(False, None, "the model declined this request", usage, request_id)
        if response.stop_reason == "max_tokens":
            return ModelReply(False, None, "the answer was cut off (max_tokens reached)", usage, request_id)

        # Read the answer by type: a reply can start with "thinking" blocks before the text.
        text = next((block.text for block in response.content if block.type == "text"), None)
        try:
            answer = json.loads(text) if text is not None else None
        except ValueError:
            answer = None
        if answer is None:
            return ModelReply(False, None, "the answer was not valid JSON", usage, request_id)
        return ModelReply(True, answer, None, usage, request_id)
