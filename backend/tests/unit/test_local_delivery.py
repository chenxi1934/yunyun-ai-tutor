"""本机入口协议测试。合成报告/原生打开替身不作为真实执行证据。"""
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.api import create_app
from app.config import Settings
from app.domain import sha
from fastapi.testclient import TestClient

from backend.tests.unit.test_export_documents import publish, reviewed  # noqa: F401


@pytest.fixture
def local_delivery(reviewed, monkeypatch):  # noqa: F811 - imported pytest fixture
    agent, store, session, root, view = reviewed
    publish(reviewed)
    session = store.get('sessions', session['id'])
    session['owner'] = sha('a' * 64)
    store.put('sessions', session)
    settings = Settings(_env_file=None, **(agent.settings.model_dump() | {'yunyun_local_token': 'local-test'}))
    app = create_app(settings)

    async def identity():
        return {'ready': True, 'runtime_digest': 'SYNTHETIC_PROTOCOL_FIXTURE', 'runner_policy_hash': 'SYNTHETIC'}

    monkeypatch.setattr(app.state.agent.verification.runner, 'identity', identity)
    calls = []
    monkeypatch.setattr('app.delivery_api.subprocess.run', lambda command, **kw:
                        calls.append(command) or SimpleNamespace(returncode=0))
    with TestClient(app, headers={'Authorization': 'Bearer local-test'}) as client:
        client.cookies.set('yunyun_client', 'a' * 64)
        yield client, app.state.agent, session, root, view, calls


def base(session, view):
    return f"/api/sessions/{session['id']}/lessons/{view['lesson_id']}/local-package"


def test_existing_materials_are_located_and_repeated_open_does_not_write(local_delivery):
    client, agent, session, root, view, calls = local_delivery
    endpoint = base(session, view)
    before = {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns)
              for p in root.rglob('*') if p.is_file()}
    original_commits = agent.store.find('commits', session['id'])
    for _ in range(2):
        response = client.get(endpoint)
        assert response.status_code == 200, response.text
        data = response.json()
        assert Path(data['directory']) == root / 'published' / view['lesson_id']
        assert Path(data['entry']).name == '开始阅读.html'
        for target in ['read', 'folder']:
            response = client.post(endpoint + '/open', json={'target': target})
            assert response.status_code == 200, response.text
    assert calls == [["/usr/bin/open", data['entry']], ['/usr/bin/open', '-R', data['entry']]] * 2
    assert agent.store.find('commits', session['id']) == original_commits
    assert before == {p.relative_to(root): (p.read_bytes(), p.stat().st_mtime_ns)
                      for p in root.rglob('*') if p.is_file()}


def test_only_current_owner_and_local_authorized_actions_can_open(local_delivery):
    client, _, session, _, view, calls = local_delivery
    endpoint = base(session, view)
    assert client.post(endpoint + '/open', json={'target': 'read', 'path': '/etc/passwd'}).status_code == 422
    assert client.post(endpoint + '/open', json={'target': 'shell'}).status_code == 422
    assert client.post(endpoint + '/open', json={'target': 'read'}, headers={'Origin': 'https://other.test'}).status_code == 403
    client.headers.pop('Authorization')
    assert client.post(endpoint + '/open', json={'target': 'read'}).status_code == 403
    client.cookies.set('yunyun_client', 'b' * 64)
    assert client.get(endpoint).status_code == 404
    assert not calls


@pytest.mark.parametrize('change', ['modified', 'symlink', 'missing', 'unreviewed', 'uncommitted', 'runner_changed'])
def test_changed_or_unapproved_materials_never_open(local_delivery, change):
    client, agent, session, root, view, calls = local_delivery
    endpoint = base(session, view)
    entry = root / 'published' / view['lesson_id'] / '开始阅读.html'
    if change == 'modified':
        entry.write_text('外部修改')
    elif change == 'symlink':
        entry.unlink()
        entry.symlink_to(root / 'fixture.md')
    elif change == 'missing':
        entry.unlink()
    elif change == 'uncommitted':
        commit = agent.store.find('commits', session['id'])[-1]
        commit['status'] = 'ROLLED_BACK'
        agent.store.put('commits', commit)
    elif change == 'unreviewed':
        review = agent.store.find('education_reviews', session['id'])[-1]
        review['decision'] = 'reject'
        agent.store.put('education_reviews', review)
    else:
        async def changed_identity():
            return {'ready': True, 'runtime_digest': 'CHANGED', 'runner_policy_hash': 'CHANGED'}
        agent.verification.runner.identity = changed_identity
    assert client.get(endpoint).status_code >= 400
    assert client.post(endpoint + '/open', json={'target': 'read'}).status_code >= 400
    assert not calls


def test_web_and_native_open_failure_are_explicit(local_delivery, monkeypatch):
    client, agent, session, _, view, calls = local_delivery
    endpoint = base(session, view)
    agent.settings.yunyun_mode = 'web'
    assert client.get(endpoint).status_code == 403
    assert client.post(endpoint + '/open', json={'target': 'read'}).status_code == 403
    assert not calls
    agent.settings.yunyun_mode = 'pc'
    monkeypatch.setattr('app.delivery_api.subprocess.run', lambda *a, **k: SimpleNamespace(returncode=1))
    response = client.post(endpoint + '/open', json={'target': 'read'})
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'LOCAL_OPEN_FAILED'
