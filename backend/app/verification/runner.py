"""API 仅使用私有 Unix socket。该模块不导入 Docker，也不执行候选 subprocess。"""
import asyncio
import contextlib
from pathlib import Path

import httpx

from app.domain import AppError
from app.verification.models import ExecutionRequest, ExecutionResult


class RemoteRunner:
    def __init__(self, socket: Path | None, token: str):
        self.socket, self.token = socket, token

    def client(self):
        if not self.socket or not self.token:
            raise AppError('RUNNER_UNAVAILABLE', 'NOT_TESTED：未配置私有隔离 Runner。', 503)
        return httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=str(self.socket)),
                                base_url='http://runner', timeout=10,
                                headers={'Authorization': 'Bearer ' + self.token})

    async def _request(self, method, path, **kwargs):
        try:
            async with self.client() as client:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError, OSError):
            raise AppError('RUNNER_UNAVAILABLE', '隔离执行器不可用；本次没有通过证据。', 503) from None

    async def identity(self):
        value = await self._request('GET', '/identity')
        if not value.get('ready') or not value.get('runtime_digest') or not value.get('runner_policy_hash'):
            raise AppError('RUNNER_UNAVAILABLE', '隔离策略尚未就绪。', 503)
        return value

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            return ExecutionResult.model_validate(await self._request('POST', '/execute',
                                                                       json=request.model_dump()))
        except asyncio.CancelledError:
            # 断连不是可靠的取消协议；显式按原job_id终止并等待完整容器清理。
            with contextlib.suppress(Exception):
                await asyncio.shield(self._request('DELETE', '/execute/' + request.job_id))
            raise
        except ValueError:
            raise AppError('RUNNER_PROTOCOL', '执行器响应不符合协议。', 503) from None
