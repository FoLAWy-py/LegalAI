"""Verification's own model-call code (P2): a minimal OpenAI-compatible chat client returning JSON text."""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from legalai_verification.config import VerificationModelConfig

PHASE_B_TEMPERATURE = 0.0
"""P7: model checks are deterministic-as-possible; changing this requires an ADR."""

_RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class ModelCallError(Exception):
    """The model could not be called or returned an unusable response. Callers map it to CHECK_ERROR."""


@runtime_checkable
class JsonChatModel(Protocol):
    """What Phase B needs from a model: one system prompt + one user message in, raw JSON text out."""

    @property
    def model_id(self) -> str: ...

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        """Return the model's reply text. Raise `ModelCallError` on any transport or protocol failure."""
        ...


@dataclass(frozen=True)
class HttpRequest:
    url: str
    headers: dict[str, str]
    body: bytes
    timeout_seconds: float


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes


HttpTransport = Callable[[HttpRequest], HttpResponse]
"""Sends one POST. Returns any HTTP status as a response; raises `OSError` on network failure."""


def urllib_transport(request: HttpRequest) -> HttpResponse:
    """Default transport using the standard library (no third-party HTTP dependency)."""
    req = urllib.request.Request(request.url, data=request.body, headers=request.headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=request.timeout_seconds) as resp:
            return HttpResponse(status=int(resp.status), body=resp.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(status=exc.code, body=exc.read())


class _Message(BaseModel):
    model_config = ConfigDict(extra="ignore")
    content: str | None = None


class _Choice(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: _Message
    finish_reason: str | None = None


class _Completion(BaseModel):
    model_config = ConfigDict(extra="ignore")
    choices: list[_Choice] = Field(min_length=1)


class OpenAICompatibleChatModel:
    """Calls `{base_url}/chat/completions` with temperature 0 and JSON-object response format.

    Guarantees: returns the content of the single completed choice; raises `ModelCallError` for
    network errors (after `max_retries` retries on transient failures), non-200 responses, truncated
    output (`finish_reason` other than `stop`), or a response that does not match the API shape.
    It never reads environment variables; everything comes from the injected config.
    """

    def __init__(
        self,
        config: VerificationModelConfig,
        *,
        transport: HttpTransport = urllib_transport,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._config = config
        self._transport = transport
        self._sleep = sleep

    def __repr__(self) -> str:
        return f"OpenAICompatibleChatModel(base_url={self._config.base_url!r}, model={self._config.model!r})"

    @property
    def model_id(self) -> str:
        return self._config.model

    def complete_json(self, system_prompt: str, user_content: str) -> str:
        cfg = self._config
        payload = {
            "model": cfg.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": PHASE_B_TEMPERATURE,
            "max_tokens": cfg.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        request = HttpRequest(
            url=f"{cfg.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg.api_key.get_secret_value()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout_seconds=cfg.timeout_seconds,
        )
        response = self._send_with_retries(request)
        return self._extract_content(response)

    def _send_with_retries(self, request: HttpRequest) -> HttpResponse:
        attempts = 1 + self._config.max_retries
        last_problem = "no attempt made"
        for attempt in range(attempts):
            if attempt:
                self._sleep(min(2.0**attempt, 30.0))
            try:
                response = self._transport(request)
            except OSError as exc:
                last_problem = f"network error: {type(exc).__name__}"
                continue
            if response.status == 200:
                return response
            last_problem = f"HTTP {response.status}"
            if response.status not in _RETRYABLE_STATUS:
                break
        raise ModelCallError(f"model call failed after {attempts} attempt(s): {last_problem}")

    @staticmethod
    def _extract_content(response: HttpResponse) -> str:
        try:
            completion = _Completion.model_validate_json(response.body)
        except ValidationError as exc:
            raise ModelCallError(f"response is not a chat completion ({exc.error_count()} error(s))") from exc
        choice = completion.choices[0]
        if choice.finish_reason != "stop":
            raise ModelCallError(f"incomplete model output (finish_reason={choice.finish_reason!r})")
        if choice.message.content is None:
            raise ModelCallError("model returned no content")
        return choice.message.content
