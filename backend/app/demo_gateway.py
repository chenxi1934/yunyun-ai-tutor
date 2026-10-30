"""可选演示代理：仅模型推理和受限Python执行，无文件/审批/主机管理能力。"""
import asyncio
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

import httpx
from fastapi import Request
from pydantic import Field, ValidationError

from app.domain import AppError, ModelReply, StrictModel, dumps
from app.tools import schemas
from app.verification.models import ExecutionRequest, ExecutionResult


class ModelRequest(StrictModel):
    messages: list[dict] = Field(min_length=1, max_length=400)
    tools: list[dict] = Field(max_length=40)


def gateway_url(value):
    parsed = urlsplit(value)
    secure = parsed.scheme == 'https' or (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'})
    if (not secure or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise ValueError('演示服务必须是无凭据的HTTPS地址。')
    return value.rstrip('/')


class DemoClient:
    def __init__(self, url, transport=None):
        self.url, self.transport = gateway_url(url), transport

    async def request(self, method, path, body=None, timeout=65):
        try:
            async with httpx.AsyncClient(base_url=self.url, transport=self.transport, timeout=timeout,
                                         follow_redirects=False) as client:
                response = await client.request(method, '/api/demo/' + path, json=body)
            if response.status_code >= 400:
                raise AppError('DEMO_SERVICE_BUSY' if response.status_code == 429 else 'DEMO_SERVICE_ERROR',
                               '演示服务繁忙，请稍后重试。' if response.status_code == 429 else
                               '演示服务暂不可用；没有产生通过证据，请检查网络或联系演示者。', 503, True)
            return response.json()
        except (httpx.HTTPError, ValueError):
            raise AppError('DEMO_SERVICE_UNAVAILABLE', '无法连接演示服务，请检查网络和HTTPS地址。', 503, True) from None


class DemoProvider(DemoClient):
    async def complete(self, messages, tools):
        value = await self.request('POST', 'model', {'messages': messages, 'tools': tools})
        try:
            return ModelReply.model_validate(value)
        except ValidationError:
            raise AppError('PROVIDER_PROTOCOL', '演示服务返回的模型协议无效，未执行工具。', 503) from None


class DemoRunner(DemoClient):
    async def identity(self):
        value = await self.request('GET', 'status', timeout=10)
        if not value.get('ready') or not value.get('runtime_digest') or not value.get('runner_policy_hash'):
            raise AppError('RUNNER_UNAVAILABLE', '演示隔离执行器尚未就绪。', 503)
        return value

    async def execute(self, request):
        try:
            return ExecutionResult.model_validate(await self.request('POST', 'execute', request.model_dump(), timeout=10))
        except ValidationError:
            raise AppError('RUNNER_PROTOCOL', '演示执行器返回协议无效，没有通过证据。', 503) from None


def register_demo_gateway(app, agent, execution_lock):
    if agent.settings.yunyun_mode != 'web' or not agent.settings.demo_gateway_enabled:
        return
    calls = defaultdict(deque)
    model_lock = asyncio.Lock()

    def limit(kind, maximum):
        queue, current = calls[kind], time.monotonic()
        while queue and queue[0] <= current - 60:
            queue.popleft()
        if len(queue) >= maximum:
            raise AppError('DEMO_RATE_LIMIT', '演示请求过于频繁，请稍后重试。', 429, True)
        queue.append(current)

    async def body(request, schema):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > 262144:
                raise AppError('REQUEST_TOO_LARGE', '演示请求上限为256 KiB。', 413)
        try:
            return schema.model_validate_json(data)
        except ValidationError:
            raise AppError('INVALID_REQUEST', '演示请求不符合受限协议。', 422) from None

    @app.get('/api/demo/status')
    async def status():
        limit('status', 600)
        identity = await agent.verification.runner.identity()
        settings = agent.settings
        return {key: identity[key] for key in ('ready', 'runtime_digest', 'runner_policy_hash')} | {
            'provider': settings.llm_provider, 'model': settings.llm_model,
            'mock': settings.llm_provider == 'mock',
            'model_ready': settings.llm_provider == 'mock' or bool(settings.dashscope_api_key.get_secret_value())}

    @app.post('/api/demo/model')
    async def model(request: Request):
        limit('model', 30)
        value = await body(request, ModelRequest)
        if dumps(value.tools) != dumps(schemas()):
            raise AppError('TOOL_SCHEMA_MISMATCH', '桌面工具协议与服务器版本不一致，请更新启动包。', 409)
        if any(m.get('role') not in {'system', 'user', 'assistant', 'tool'} for m in value.messages):
            raise AppError('INVALID_REQUEST', '消息角色无效。', 422)
        if model_lock.locked():
            raise AppError('DEMO_BUSY', '演示模型正忙，请稍后重试。', 429, True)
        async with model_lock:
            try:
                reply = await asyncio.wait_for(agent.provider.complete(value.messages, value.tools), 65)
            except TimeoutError:
                raise AppError('PROVIDER_TIMEOUT', '演示模型请求超时，用量未知，请稍后重试。', 503, True) from None
            return reply.model_dump()

    @app.post('/api/demo/execute')
    async def execute(request: Request):
        limit('execute', 240)
        value = await body(request, ExecutionRequest)
        if execution_lock.locked():
            raise AppError('DEMO_BUSY', '执行器正在处理备课，请稍后重试。', 429, True)
        async with execution_lock:
            task = asyncio.create_task(agent.verification.runner.execute(value))
            try:
                deadline = time.monotonic() + 10
                while not task.done():
                    if await request.is_disconnected() or time.monotonic() > deadline:
                        raise AppError('RUNNER_INTERRUPTED', '执行连接中断或超时，没有通过证据。', 503)
                    await asyncio.sleep(.05)
                return (await task).model_dump()
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
