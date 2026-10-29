import json

import httpx
import pytest
from app.config import Settings
from app.domain import AppError
from app.providers import BailianProvider
from app.tools import schemas
from pydantic import SecretStr


def settings():
    return Settings(_env_file=None, dashscope_api_key=SecretStr("unit-test-placeholder"))


async def test_native_protocol_and_usage():
    async def handler(request):
        payload = json.loads(request.content)
        assert payload["enable_thinking"] is False
        assert payload["tools"] == schemas() and payload["stream"] is False
        return httpx.Response(200, json={"id": "request-1", "model": "qwen3.8-max", "usage": {
            "prompt_tokens": 20, "completion_tokens": 10}, "choices": [{"finish_reason": "tool_calls", "message": {
                "content": None, "tool_calls": [{"id": "native-call-1", "type": "function", "function": {
                    "name": "read_file", "arguments": '{"path":"fixture.md"}'}}]}}]})

    provider = BailianProvider(settings(), httpx.MockTransport(handler))
    result = await provider.complete([{"role": "user", "content": "读取"}], schemas(), 100)
    assert result.tool_calls[0].id == "native-call-1"
    assert result.input_tokens == 20 and result.request_id == "request-1"


@pytest.mark.parametrize("status,code,retry", [(401, "PROVIDER_AUTH", False), (403, "PROVIDER_FORBIDDEN", False),
                                               (429, "PROVIDER_RATE_LIMIT", True), (500, "PROVIDER_HTTP_ERROR", True)])
async def test_provider_http_errors_are_redacted(status, code, retry):
    provider = BailianProvider(settings(), httpx.MockTransport(lambda _: httpx.Response(status, text="sensitive-body")))
    with pytest.raises(AppError) as error:
        await provider.complete([], schemas(), 100)
    assert error.value.code == code and error.value.retryable is retry
    assert "sensitive-body" not in error.value.message


async def test_missing_key_and_invalid_protocol():
    provider = BailianProvider(Settings(_env_file=None))
    with pytest.raises(AppError) as error:
        await provider.complete([], schemas(), 100)
    assert error.value.code == "API_KEY_MISSING"
    provider = BailianProvider(settings(), httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": []})))
    with pytest.raises(AppError) as error:
        await provider.complete([], schemas(), 100)
    assert error.value.code == "PROVIDER_PROTOCOL"


async def test_timeout_identified():
    def timeout(request):
        raise httpx.ReadTimeout("do not expose", request=request)
    provider = BailianProvider(settings(), httpx.MockTransport(timeout))
    with pytest.raises(AppError) as error:
        await provider.complete([], schemas(), 100)
    assert error.value.code == "PROVIDER_TIMEOUT"
