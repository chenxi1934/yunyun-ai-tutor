import json
from typing import Protocol

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.domain import AppError, ModelReply, ToolCall, uid


class Provider(Protocol):
    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply: ...


class BailianProvider:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings, self.transport = settings, transport

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        key = self.settings.dashscope_api_key.get_secret_value()
        if not key:
            raise AppError("API_KEY_MISSING", "未配置百炼密钥，请在本地 .env 配置后重启服务。", 503)
        try:
            async with httpx.AsyncClient(timeout=self.settings.model_timeout_seconds,
                                         transport=self.transport) as client:
                response = await client.post(
                    self.settings.dashscope_base_url.rstrip("/") + "/chat/completions",
                    headers={"Authorization": "Bearer " + key},
                    json={"model": self.settings.llm_model, "messages": messages,
                          "tools": tools, "tool_choice": "auto", "stream": False,
                          "enable_thinking": False},
                )
        except httpx.TimeoutException:
            raise AppError("PROVIDER_TIMEOUT", "模型请求超时，实际用量未知，请稍后重试。",
                           503, True) from None
        except httpx.RequestError:
            raise AppError("PROVIDER_UNAVAILABLE", "无法连接模型服务，请检查网络和服务地址。",
                           503, True) from None
        errors = {401: ("PROVIDER_AUTH", "百炼鉴权失败，请检查密钥和地域。"),
                  403: ("PROVIDER_FORBIDDEN", "账户没有该模型或业务空间权限。"),
                  429: ("PROVIDER_RATE_LIMIT", "模型服务限流，稍后可重试。")}
        if response.status_code in errors:
            code, message = errors[response.status_code]
            raise AppError(code, message, 503, response.status_code == 429)
        if response.status_code >= 400:
            # 不转发厂商原始 body，避免将 Key、服务内部信息写进会话/日志。
            raise AppError("PROVIDER_HTTP_ERROR",
                           f"模型服务返回 HTTP {response.status_code}，请检查模型和工具配置。",
                           503, response.status_code >= 500)
        data = None
        try:
            data = response.json()
            choice = data["choices"][0]
            msg, usage = choice["message"], data["usage"]
            calls = [ToolCall(id=c["id"], name=c["function"]["name"],
                              arguments=c["function"]["arguments"])
                     for c in msg.get("tool_calls", [])]
            reply = ModelReply(content=msg.get("content"), tool_calls=calls,
                               finish_reason=choice["finish_reason"],
                               input_tokens=usage["prompt_tokens"],
                               output_tokens=usage["completion_tokens"],
                               model=data["model"], request_id=data.get("id"))
            if reply.finish_reason in {"length", "content_filter"}:
                raise AppError("PROVIDER_TRUNCATED", "模型输出被截断或拦截，本轮没有执行其工具。", 503)
            if reply.finish_reason not in {"stop", "tool_calls"}:
                raise ValueError("unsupported finish reason")
            if not reply.tool_calls and (reply.finish_reason == "tool_calls" or not reply.content):
                raise ValueError("missing content or tools")
            if len({c.id for c in reply.tool_calls}) != len(reply.tool_calls):
                raise ValueError("duplicate call ids")
            return reply
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            diagnostic = {"reason": str(error) if type(error) is ValueError else type(error).__name__,
                          "response_fields": sorted(data) if isinstance(data, dict) else [],
                          "validation_fields": [e["loc"] for e in error.errors(include_input=False)]
                          if isinstance(error, ValidationError) else []}
            raise AppError("PROVIDER_PROTOCOL", "模型响应缺少有效工具协议或用量，未执行任何操作。",
                           503, details=diagnostic) from None


class MockProvider:
    """仅用于离线演示，固定选择读工具；不满足真实 API 验收。"""

    async def complete(self, messages: list[dict], tools: list[dict]) -> ModelReply:
        start = max(i for i, msg in enumerate(messages) if msg["role"] == "user")
        results = [json.loads(msg["content"]) for msg in messages[start:]
                   if msg["role"] == "tool"]
        calls = []
        content = "MOCK_LLM：离线演示完成。仅展示工具流程，未验证代码或生成正式教案。"
        if not results:
            calls = [ToolCall(id=uid(), name="list_files", arguments="{}")]
        elif len(results) == 1 and results[0]["ok"] and results[0]["data"]["files"]:
            path = results[0]["data"]["files"][0]["path"]
            calls = [ToolCall(id=uid(), name="read_file", arguments=json.dumps({"path": path}))]
        return ModelReply(content=content if not calls else None, tool_calls=calls,
                          finish_reason="tool_calls" if calls else "stop",
                          input_tokens=0, output_tokens=0, model="MOCK_LLM")


def create_provider(settings: Settings) -> Provider:
    if settings.yunyun_mode == 'pc' and settings.desktop_gateway_url:
        from app.demo_gateway import DemoProvider
        return DemoProvider(settings.desktop_gateway_url)
    return MockProvider() if settings.llm_provider == "mock" else BailianProvider(settings)
