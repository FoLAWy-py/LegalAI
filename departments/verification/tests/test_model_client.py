"""OpenAI-compatible client: request shape (temperature 0, JSON mode, injected model id), strict errors."""

import json

import pytest
from pydantic import ValidationError

from legalai_verification import (
    JsonChatModel,
    ModelCallError,
    OpenAICompatibleChatModel,
    VerificationModelConfig,
)
from legalai_verification.model_client import HttpRequest, HttpResponse

KEY = "zz-test-key-not-real"


def _config(**kw: object) -> VerificationModelConfig:
    args: dict[str, object] = {
        "base_url": "https://llm.example.invalid/v1/openai/",
        "api_key": KEY,
        "model": "zz-verifier-model",
        "max_retries": 2,
    }
    args.update(kw)
    return VerificationModelConfig.model_validate(args)


def _completion(content: str | None, finish_reason: str | None = "stop") -> bytes:
    return json.dumps(
        {
            "id": "x",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": finish_reason,
                }
            ],
        }
    ).encode()


class FakeTransport:
    def __init__(self, *responses: HttpResponse | OSError) -> None:
        self.responses = list(responses)
        self.requests: list[HttpRequest] = []

    def __call__(self, request: HttpRequest) -> HttpResponse:
        self.requests.append(request)
        nxt = self.responses.pop(0)
        if isinstance(nxt, OSError):
            raise nxt
        return nxt


def _client(transport: FakeTransport, **kw: object) -> OpenAICompatibleChatModel:
    return OpenAICompatibleChatModel(_config(**kw), transport=transport, sleep=lambda _s: None)


def test_request_shape() -> None:
    transport = FakeTransport(HttpResponse(200, _completion('{"verdict": "unsupported"}')))
    client = _client(transport)
    assert isinstance(client, JsonChatModel)
    assert client.model_id == "zz-verifier-model"
    assert client.complete_json("SYSTEM", "用户内容：“引号”") == '{"verdict": "unsupported"}'
    (req,) = transport.requests
    assert req.url == "https://llm.example.invalid/v1/openai/chat/completions"
    assert req.headers["Authorization"] == f"Bearer {KEY}"
    body = json.loads(req.body.decode("utf-8"))
    assert body["model"] == "zz-verifier-model"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"] == [
        {"role": "system", "content": "SYSTEM"},
        {"role": "user", "content": "用户内容：“引号”"},
    ]


def test_retries_transient_failures_then_succeeds() -> None:
    transport = FakeTransport(
        TimeoutError("slow"), HttpResponse(503, b"busy"), HttpResponse(200, _completion("{}"))
    )
    assert _client(transport).complete_json("s", "u") == "{}"
    assert len(transport.requests) == 3


def test_gives_up_after_max_retries() -> None:
    transport = FakeTransport(HttpResponse(429, b""), HttpResponse(429, b""), HttpResponse(429, b""))
    with pytest.raises(ModelCallError, match="3 attempt"):
        _client(transport).complete_json("s", "u")


def test_non_retryable_status_fails_immediately() -> None:
    transport = FakeTransport(HttpResponse(401, b"unauthorized"), HttpResponse(200, _completion("{}")))
    with pytest.raises(ModelCallError, match="HTTP 401"):
        _client(transport).complete_json("s", "u")
    assert len(transport.requests) == 1


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"{}",
        json.dumps({"choices": []}).encode(),
        _completion(None),
        _completion('{"verdict": "supp', finish_reason="length"),
        _completion("{}", finish_reason=None),
    ],
    ids=["not_json", "no_choices_key", "empty_choices", "null_content", "truncated", "no_finish_reason"],
)
def test_unusable_response_is_model_call_error(body: bytes) -> None:
    with pytest.raises(ModelCallError):
        _client(FakeTransport(HttpResponse(200, body))).complete_json("s", "u")


def test_error_messages_and_repr_never_contain_the_key() -> None:
    transport = FakeTransport(HttpResponse(500, KEY.encode()), HttpResponse(500, b""), HttpResponse(500, b""))
    client = _client(transport)
    with pytest.raises(ModelCallError) as info:
        client.complete_json("s", "u")
    assert KEY not in str(info.value)
    assert KEY not in repr(client)
    assert KEY not in repr(_config())


@pytest.mark.parametrize(
    "override",
    [
        {"base_url": "http://llm.example.invalid/v1"},
        {"api_key": "   "},
        {"model": ""},
        {"timeout_seconds": 0},
        {"unknown": 1},
    ],
)
def test_config_validation(override: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _config(**override)
