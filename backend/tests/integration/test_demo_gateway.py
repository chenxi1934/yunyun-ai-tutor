"""演示代理协议与边界。显式桩只作协议测试；真实模型/隔离器另验。"""
import asyncio

import httpx
import pytest
from app.api import create_app
from app.config import Settings
from app.demo_gateway import DemoProvider, DemoRunner, gateway_url
from app.domain import ModelReply, uid
from app.tools import schemas
from conftest import ScriptedProvider
from fastapi.testclient import TestClient


@pytest.fixture
def demo(tmp_path):
    provider = ScriptedProvider(ModelReply(content='TEST_MOCK_PROTOCOL', input_tokens=12,
        output_tokens=2, model='TEST_MOCK', request_id='synthetic-protocol'))
    app = create_app(Settings(_env_file=None, llm_provider='mock', demo_gateway_enabled=True,
        yunyun_data_dir=tmp_path, yunyun_hosts='testserver,localhost,127.0.0.1,gateway.test'), provider)
    class UnexecutedRunner:
        async def identity(self):
            return {'ready': True, 'runtime_digest': 'SYNTHETIC_IDENTITY_NOT_EXECUTION',
                    'runner_policy_hash': 'SYNTHETIC', 'active_jobs': ['private-job-not-for-public']}
        async def execute(self, request):
            raise AssertionError('协议边界测试不能执行候选代码')
    app.state.agent.verification.runner = UnexecutedRunner()
    return app, provider


def test_gateway_disabled_by_default_and_existing_session_auth_unchanged(tmp_path):
    with TestClient(create_app(Settings(_env_file=None, llm_provider='mock', yunyun_data_dir=tmp_path))) as c:
        assert c.get('/api/demo/status').status_code == 404
        assert not any(getattr(route, 'path', '') == '/api/demo/model' for route in c.app.routes)
        assert c.post('/api/demo/model', json={}).status_code == 405  # 现有静态文件挂载的默认行为
        assert c.get('/api/sessions').status_code == 401


def test_public_status_excludes_secrets_and_job_ids_and_model_remains_protocol(demo):
    app, provider = demo
    with TestClient(app) as c:
        value = c.get('/api/demo/status')
        assert value.status_code == 200 and value.json()['mock'] is True
        assert 'active_jobs' not in value.json() and 'token' not in value.text.lower()
        response = c.post('/api/demo/model', json={'messages': [{'role': 'user', 'content': 'protocol fixture'}], 'tools': schemas()})
        assert response.status_code == 200 and response.json()['content'] == 'TEST_MOCK_PROTOCOL'
        assert len(provider.requests) == 1
        assert c.get('/api/sessions').status_code == 401
        assert c.post('/api/local-workspace/dialog').status_code == 403


@pytest.mark.parametrize('payload', [
    {'messages': [{'role': 'user', 'content': 'x'}], 'tools': []},
    {'messages': [{'role': 'bad', 'content': 'x'}], 'tools': schemas()},
    {'messages': [{'role': 'user', 'content': 'x'}], 'tools': schemas(), 'api_key': 'forbidden'},
])
def test_model_schema_role_extra_fields_are_rejected_before_provider(demo, payload):
    app, provider = demo
    with TestClient(app) as c:
        assert c.post('/api/demo/model', json=payload).status_code in {409, 422}
        assert not provider.requests


@pytest.mark.parametrize('extra', [{'command': 'sh'}, {'path': '/etc/passwd'}, {'expected': 'fake-pass'}, {'timeout_seconds': 999}])
def test_execute_cannot_accept_shell_files_expected_or_limits(demo, extra):
    app, _ = demo
    with TestClient(app) as c:
        r = c.post('/api/demo/execute', json={'job_id': uid(), 'code': 'print(1)', 'input': '', **extra})
        assert r.status_code == 422


def test_chunked_body_bound_and_global_model_rate_limit(demo):
    app, provider = demo
    with TestClient(app) as c:
        assert c.post('/api/demo/model', content=iter([b'x' * 131072] * 3)).status_code == 413
        for _ in range(29):
            assert c.post('/api/demo/model', json={}).status_code == 422
        assert c.post('/api/demo/model', json={}).status_code == 429
        assert not provider.requests


@pytest.mark.parametrize('url', ['http://example.com', 'https://user:password@example.com', 'https://example.com/?token=x'])
def test_client_requires_safe_url_without_credentials(url):
    with pytest.raises(ValueError):
        gateway_url(url)


async def test_thin_model_and_identity_clients_use_only_gateway_without_credentials(demo):
    app, _ = demo
    transport = httpx.ASGITransport(app=app)
    model = DemoProvider('https://gateway.test', transport)
    reply = await model.complete([{'role': 'user', 'content': 'protocol'}], schemas())
    assert reply.request_id == 'synthetic-protocol' and reply.model == 'TEST_MOCK'
    runner = DemoRunner('https://gateway.test', transport)
    assert (await runner.identity())['runtime_digest'] == 'SYNTHETIC_IDENTITY_NOT_EXECUTION'


async def test_busy_model_request_is_rejected_without_second_provider_call(demo):
    app, provider = demo
    entered, release = asyncio.Event(), asyncio.Event()
    async def slow(messages, tools):
        entered.set()
        await release.wait()
        return ModelReply(content='TEST_MOCK_SLOW', input_tokens=1, output_tokens=1, model='TEST_MOCK')
    provider.complete = slow
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='https://gateway.test') as c:
        body = {'messages': [{'role': 'user', 'content': 'x'}], 'tools': schemas()}
        first = asyncio.create_task(c.post('/api/demo/model', json=body))
        await asyncio.wait_for(entered.wait(), 3)
        assert (await c.post('/api/demo/model', json=body)).status_code == 429
        release.set()
        assert (await first).status_code == 200
