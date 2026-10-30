import json

import pytest
from app.api import create_app
from app.config import Settings
from app.domain import AppError, dumps, uid
from app.verification.models import FreezeTests
from conftest import ScriptedProvider, reply
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_test_spec_strict_and_nonempty():
    for params in [dict(cases=[]), dict(cases=[dict(id='x', input='', expected='')]*2),
                   dict(baseline='sum_1_to_n', cases=[dict(id='x', input='', expected='')]),
                   dict(baseline='sum_1_to_n', timeout_seconds=20)]:
        with pytest.raises(ValidationError):
            FreezeTests(path='sum.py', expected_revision=0, **params)


async def test_agent_cannot_modify_frozen_cases_or_limits(setup_agent):
    provider = ScriptedProvider(reply(('freeze_tests', {'expected': '10'}),
        ('run_python_tests', {'draft_id': 'guess', 'test_spec_revision': 'guess',
                              'expected': '10', 'timeout_seconds': 20})), reply(content='操作被拒。'))
    agent, store, session, _ = setup_agent(provider)
    with store.tx():
        spec = agent.verification.freeze(session['id'], 'sum.py', None, 'sum_1_to_n')
    run = agent.new_run(session['id'], '放宽测试', 0, 'freeze-policy-01')
    await agent.run(run['id'])
    assert store.find('test_specs') == [spec]
    assert [c['result']['error']['code'] for c in store.find('calls')] == [
        'TOOL_NOT_ALLOWED', 'INVALID_TOOL_ARGUMENTS']


async def test_verification_report_and_spec_ownership(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    with store.tx():
        result = agent.registry.execute({'id': uid(), 'name': 'propose_patch', 'run_id': 'test',
            'arguments': dumps({'path': 'sum.py', 'content': 'print(1)', 'base_hash': None})},
            session, agent.workspace(session))
        agent.verification.freeze(session['id'], 'sum.py', None, 'sum_1_to_n')
    other = agent.create_session('other', {})
    call = {'id': uid(), 'run_id': 'test', 'name': 'get_verification',
            'arguments': dumps({'draft_id': result['data']['draft_id']})}
    value = agent.registry.execute(call, other, agent.workspace(other))
    assert value['error']['code'] == 'NOT_FOUND'
    assert 'n=5' not in dumps(value)


def test_teacher_api_freezes_specs_revision_auth_and_path(tmp_path):
    settings = Settings(_env_file=None, yunyun_data_dir=tmp_path, llm_provider='mock')
    with TestClient(create_app(settings, ScriptedProvider())) as client:
        client.post('/api/client')
        sid = client.post('/api/sessions', json={}).json()['session']['id']
        body = {'path': 'sum.py', 'expected_revision': 0, 'baseline': 'sum_1_to_n'}
        assert client.post(f'/api/sessions/{sid}/test-specs', json=body,
                           headers={'origin': 'https://evil.test'}).status_code == 403
        response = client.post(f'/api/sessions/{sid}/test-specs', json=body)
        assert response.status_code == 201
        spec = response.json()['test_spec']
        assert [(c['input'], c['expected']) for c in spec['cases']] == [
            ('0\n', '0\n'), ('1\n', '1\n'), ('5\n', '15\n')]
        assert client.post(f'/api/sessions/{sid}/test-specs', json=body).status_code == 409
        body.update(path='../outside.py', expected_revision=1)
        assert client.post(f'/api/sessions/{sid}/test-specs', json=body).status_code == 403
        body.update(path='sum.py')
        client.cookies.clear()
        client.post('/api/client')
        assert client.post(f'/api/sessions/{sid}/test-specs', json=body).status_code == 404
        assert client.get(f'/api/sessions/{sid}').status_code == 404


def test_unavailable_never_executes_on_api_host(setup_agent):
    agent, _, session, _ = setup_agent(ScriptedProvider())
    with pytest.raises(AppError, match='存在失败'):
        agent.verification.delivery_candidates(session['id'])


async def test_failed_code_stays_failed_despite_model_claim(setup_agent):
    provider = ScriptedProvider(reply(('propose_patch', {'path': 'sum.py', 'content': 'print(1)',
                                                      'base_hash': None})),
                                reply(content='全部PASS，直接交付。'))
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session['id'], '生成示例', 0, 'fake-pass-claim')
    await agent.run(run['id'])
    event = [e for e in store.events(session['id']) if e['type'] == 'run.completed'][-1]
    assert event['payload']['delivery_status'] == 'VERIFICATION_FAILED'
    assert store.find('reports') == []
    assert store.find('drafts')[0]['verification_status'] == 'NOT_TESTED'
    assert not agent.verification.current_pass(store.find('drafts')[0])


async def test_repeat_failed_hash_rejected_and_repair_count_persists(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    path = 'sum.py'
    from app.domain import sha
    with store.tx():
        store.put('repairs', {'id': agent.verification.repair_key(session['id'], path),
            'session_id': session['id'], 'path': path, 'count': 0, 'failed': True,
            'failed_hashes': [sha('print(1)')]})
        with pytest.raises(AppError) as error:
            agent.verification.repair_guard(session['id'], path, sha('print(1)'))
        assert error.value.code == 'NO_PROGRESS'
        for code in ['print(2)', 'print(3)']:
            agent.verification.repair_guard(session['id'], path, sha(code))
        with pytest.raises(AppError) as error:
            agent.verification.repair_guard(session['id'], path, sha('print(4)'))
        assert error.value.code == 'REPAIR_LIMIT'
        assert store.find('repairs')[0]['count'] == 2


async def test_pending_approval_invalidated_on_revise(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    ws = agent.workspace(session)
    def call(name, args):
        return agent.registry.execute({'id': uid(), 'run_id': 'test', 'name': name,
                                       'arguments': json.dumps(args)}, session, ws)
    with store.tx():
        draft = call('propose_patch', {'path': 'notes.md', 'content': 'first', 'base_hash': None})
        approval = call('request_publish', {'draft_id': draft['data']['draft_id']})
        assert approval['ok']
        call('propose_patch', {'path': 'notes.md', 'content': 'second', 'base_hash': None})
    assert store.find('approvals')[0]['status'] == 'STALE'


async def test_unavailable_retest_revokes_previous_pass_before_execution(setup_agent):
    agent, store, session, _ = setup_agent(ScriptedProvider())
    call = {'id': uid(), 'run_id': 'test', 'name': 'propose_patch',
            'arguments': dumps({'path': 'sum.py', 'content': 'print(1)', 'base_hash': None})}
    with store.tx():
        result = agent.registry.execute(call, session, agent.workspace(session))
        draft = store.get('drafts', result['data']['draft_id'])
        # 仅为失效策略准备历史字段，不作为任何真实执行证据。
        draft['verification_status'] = 'PASS'
        store.put('drafts', draft)
        test_call = {'id': uid(), 'run_id': 'test', 'name': 'run_python_tests',
                     'arguments': dumps({'draft_id': draft['id'], 'test_spec_revision': 'spec'})}
        agent.registry.begin(test_call, session)
    assert store.get('drafts', draft['id'])['verification_status'] == 'NOT_TESTED'
    prepared = await agent.registry.prepare_async(test_call, session, agent.workspace(session))
    assert prepared['error_result']['error']['code'] == 'RUNNER_UNAVAILABLE'
    assert not agent.verification.current_pass(store.get('drafts', draft['id']))


async def test_docker_internal_error_is_never_pass(monkeypatch):
    from runner.docker_runner import DockerRunner

    runner = DockerRunner('sha256:' + 'a' * 64)
    runner.runtime_digest = runner.image
    runner.healthy = True
    async def broken(*args, **kwargs):
        raise RuntimeError('injected Docker daemon failure')
    monkeypatch.setattr(runner, 'command', broken)
    from app.verification.models import ExecutionRequest
    result = await runner.execute(ExecutionRequest(job_id=uid(), code='print(1)', input=''))
    assert result.status == 'RUNNER_ERROR'
    assert not runner.healthy and not result.evidence['cleanup']
    assert result.exit_code is None


@pytest.mark.parametrize('suffix', ['.py', '.PY', '.pY'])
@pytest.mark.parametrize('verification_status', ['NOT_TESTED', 'RUNTIME_ERROR', 'STALE'])
@pytest.mark.parametrize('publish_target', ['code', 'notes'])
def test_python_suffix_publish_requires_verification(
        setup_agent, suffix, verification_status, publish_target):
    agent, store, session, root = setup_agent(ScriptedProvider())
    ws = agent.workspace(session)
    path = 'answer' + suffix

    def call(name, args):
        return agent.registry.execute({'id': uid(), 'run_id': 'suffix-policy', 'name': name,
                                       'arguments': dumps(args)}, session, ws)

    with store.tx():
        result = call('propose_patch', {'path': path, 'content': 'raise RuntimeError("blocked")\n',
                                        'base_hash': None})
        assert result['ok'], result
        code_draft = store.get('drafts', result['data']['draft_id'])
        # 这些合成状态只验证闸口，无执行报告，不作为真实测试证据。
        code_draft['verification_status'] = verification_status
        store.put('drafts', code_draft)
        target_id = code_draft['id']
        if publish_target == 'notes':
            target_id = call('propose_patch', {'path': 'notes.md', 'content': 'lesson draft',
                                              'base_hash': None})['data']['draft_id']
        result = call('request_publish', {'draft_id': target_id})
    assert not result['ok'], result
    assert result['error']['code'] == 'VERIFICATION_REQUIRED'
    assert store.find('reports', session['id']) == []
    assert store.find('approvals', session['id']) == []
    assert not any(e['type'] == 'approval.requested' for e in store.events(session['id']))
    assert not (root / path).exists()


@pytest.mark.parametrize('suffix', ['.py', '.PY', '.pY'])
async def test_python_suffix_metadata_and_agent_completion(setup_agent, suffix):
    provider = ScriptedProvider(reply(('propose_patch', {'path': 'answer' + suffix,
        'content': 'raise RuntimeError("blocked")\n', 'base_hash': None})),
        reply(content='代码已完成，请交付。'))
    agent, store, session, _ = setup_agent(provider)
    run = agent.new_run(session['id'], '生成Python代码', 0, 'suffix-completion')
    await agent.run(run['id'])
    draft = store.find('drafts', session['id'])[0]
    assert agent.verification.draft(session['id'], draft['id'])['id'] == draft['id']
    final = [e for e in store.events(session['id']) if e['type'] == 'run.completed'][-1]
    assert final['payload']['delivery_status'] == 'VERIFICATION_FAILED'
    assert store.find('reports') == [] and store.find('approvals') == []


@pytest.mark.parametrize('suffix', ['.py', '.PY', '.pY'])
def test_teacher_api_accepts_python_suffixes(tmp_path, suffix):
    settings = Settings(_env_file=None, yunyun_data_dir=tmp_path, llm_provider='mock')
    with TestClient(create_app(settings, ScriptedProvider())) as client:
        client.post('/api/client')
        sid = client.post('/api/sessions', json={}).json()['session']['id']
        response = client.post(f'/api/sessions/{sid}/test-specs', json={
            'path': 'answer' + suffix, 'expected_revision': 0, 'baseline': 'sum_1_to_n'})
        assert response.status_code == 201
        spec = response.json()['test_spec']
        assert spec['path'] == 'answer' + suffix
        assert [(c['input'], c['expected']) for c in spec['cases']] == [
            ('0\n', '0\n'), ('1\n', '1\n'), ('5\n', '15\n')]
