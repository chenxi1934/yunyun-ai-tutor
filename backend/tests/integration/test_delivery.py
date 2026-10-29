import json

import pytest
from app.api import create_app
from app.config import Settings
from app.domain import AppError, sha
from app.storage import Store
from fastapi.testclient import TestClient


@pytest.fixture
def delivery_client(tmp_path):
    root = tmp_path / 'teacher'
    root.mkdir()
    (root / 'lesson.md').write_text('原有正式教案\r\n', newline='')
    settings = Settings(_env_file=None, llm_provider='mock', yunyun_mode='pc',
                        yunyun_local_token='test-local-token', yunyun_workspace=root,
                        yunyun_data_dir=tmp_path / 'data')
    app = create_app(settings)
    with TestClient(app, headers={'Authorization': 'Bearer test-local-token'}) as client:
        client.post('/api/client')
        session = client.post('/api/sessions', json={}).json()['session']
        yield app, client, session['id'], root


def snapshot(client, sid):
    return client.get(f'/api/sessions/{sid}').json()


def draft(client, sid, path, content, base_hash, operation='write'):
    return client.post(f'/api/sessions/{sid}/drafts', json={'path': path, 'content': content,
        'base_hash': base_hash, 'operation': operation,
        'expected_revision': snapshot(client, sid)['session']['revision']})


def prepare(client, sid, did):
    return client.post(f'/api/sessions/{sid}/publish-draft', json={'draft_id': did,
        'expected_revision': snapshot(client, sid)['session']['revision']})


def decide(client, sid, aid, decision):
    return client.post(f'/api/approvals/{aid}/decision', json={'decision': decision,
        'expected_revision': snapshot(client, sid)['session']['revision']})


def test_reject_overwrite_then_commit_delete_restore_and_restart(delivery_client):
    app, client, sid, root = delivery_client
    before = (root / 'lesson.md').read_bytes()
    d = draft(client, sid, 'lesson.md', '新教案\n', sha(before.decode())).json()['draft_id']
    a = prepare(client, sid, d).json()['approval']
    assert a['entries'][0]['base_hash'] == sha(before.decode())
    assert '-原有正式教案' in a['entries'][0]['diff']
    assert decide(client, sid, a['id'], 'reject').status_code == 200
    assert (root / 'lesson.md').read_bytes() == before
    a = prepare(client, sid, d).json()['approval']
    assert decide(client, sid, a['id'], 'approve').status_code == 200
    assert (root / 'lesson.md').read_bytes() == '新教案\n'.encode()
    # 重复确认不重复落盘或添加提交日志。
    assert decide(client, sid, a['id'], 'approve').status_code == 200
    assert len(snapshot(client, sid)['commits']) == 1
    deletion = draft(client, sid, 'lesson.md', '', sha('新教案\n'), 'delete').json()['draft_id']
    a = prepare(client, sid, deletion).json()['approval']
    decide(client, sid, a['id'], 'reject')
    assert (root / 'lesson.md').read_text() == '新教案\n'
    a = prepare(client, sid, deletion).json()['approval']
    decide(client, sid, a['id'], 'approve')
    assert not (root / 'lesson.md').exists()
    commit = snapshot(client, sid)['commits'][-1]
    r = client.post(f'/api/sessions/{sid}/commits/{commit["id"]}/restore-draft', json={
        'expected_revision': snapshot(client, sid)['session']['revision']})
    assert r.status_code == 200, r.text
    a = r.json()['approval']
    assert not (root / 'lesson.md').exists()
    decide(client, sid, a['id'], 'approve')
    assert (root / 'lesson.md').read_text() == '新教案\n'
    reopened = Store(app.state.agent.settings.yunyun_data_dir / 'state.sqlite3')
    reopened.recover()
    assert len(reopened.find('commits', sid)) == 3
    assert reopened.get('sessions', sid)['workspace_id'] == snapshot(client, sid)['session']['workspace_id']
    reopened.close()


def test_conflict_stale_draft_symlink_and_unauthorized_never_overwrite(delivery_client, tmp_path):
    _, client, sid, root = delivery_client
    d = draft(client, sid, 'lesson.md', '拟覆盖', sha('原有正式教案\r\n')).json()['draft_id']
    a = prepare(client, sid, d).json()['approval']
    (root / 'lesson.md').write_text('用户并发修改')
    assert decide(client, sid, a['id'], 'approve').status_code == 409
    assert (root / 'lesson.md').read_text() == '用户并发修改'
    outside = tmp_path / 'outside'
    outside.mkdir()
    (root / 'link').symlink_to(outside, target_is_directory=True)
    assert draft(client, sid, 'link/x.md', '逃逸', None).status_code == 409
    assert not (outside / 'x.md').exists()
    d = draft(client, sid, 'fresh.md', 'v1', None).json()['draft_id']
    a = prepare(client, sid, d).json()['approval']
    draft(client, sid, 'fresh.md', 'v2', None)
    assert decide(client, sid, a['id'], 'approve').status_code == 409
    assert not (root / 'fresh.md').exists()
    client.headers.pop('Authorization')
    assert client.post('/api/local-workspace/dialog').status_code == 403
    assert draft(client, sid, 'unauthorized.md', 'x', None).status_code == 403


def test_interrupt_after_partial_commit_never_replays_and_restore_is_reviewed(delivery_client, monkeypatch):
    app, client, sid, root = delivery_client
    agent, store = app.state.agent, app.state.store
    session = store.get('sessions', sid)
    with store.tx():
        approval = agent.delivery.prepare(session, {'one.md': 'one', 'two.md': 'two'})
    ws_class = type(agent.workspace(session))
    original = ws_class.replace
    def fail_second(self, path, content, expected_hash, **kwargs):
        if path == 'two.md':
            raise AppError('INJECTED_FAILURE', '模拟第二文件写入失败', 409)
        return original(self, path, content, expected_hash, **kwargs)
    monkeypatch.setattr(ws_class, 'replace', fail_second)
    with pytest.raises(AppError):
        agent.delivery.decide(approval['id'], 0, True)
    assert (root / 'one.md').read_text() == 'one'
    assert not (root / 'two.md').exists()
    assert store.find('commits', sid)[0]['status'] == 'INTERRUPTED'
    store.recover()
    assert store.get('approvals', approval['id'])['status'] == 'INTERRUPTED'
    assert not (root / 'two.md').exists()
    with pytest.raises(AppError):
        agent.delivery.decide(approval['id'], 0, True)
    monkeypatch.setattr(ws_class, 'replace', original)
    commit = store.find('commits', sid)[0]
    with store.tx(), pytest.raises(AppError, match='先对账恢复'):
        agent.delivery.restore(store.get('sessions', sid), commit)
    observed = agent.delivery.inspect_recovery(session, commit['id'])
    assert [e['state'] for e in observed['entries']] == ['AFTER', 'BEFORE']
    assert (root / 'one.md').exists()
    agent.delivery.reconcile(session, commit['id'], store.get('sessions', sid)['revision'],
                             observed['snapshot_hash'], 'rollback')
    assert not (root / 'one.md').exists()


def test_web_never_opens_local_directory(tmp_path):
    app = create_app(Settings(_env_file=None, llm_provider='mock', yunyun_data_dir=tmp_path))
    with TestClient(app) as client:
        client.post('/api/client')
        assert client.post('/api/local-workspace/dialog').status_code == 403
        sid = client.post('/api/sessions', json={}).json()['session']['id']
        state = snapshot(client, sid)
        assert 'root' not in json.dumps(state)
        assert len(client.get(f'/api/workspaces/{state["session"]["workspace_id"]}/files').json()['files']) == 7
