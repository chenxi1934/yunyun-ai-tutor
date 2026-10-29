"""阶段05五项审查回归：控制模型为显式Mock，文件/数据库/进程操作真实。"""
import json
import stat
import subprocess
import sys

import pytest
from app.agent import Agent
from app.api import create_app
from app.config import Settings
from app.domain import AppError, dumps, sha
from app.storage import Store
from conftest import ScriptedProvider, reply
from fastapi.testclient import TestClient

from backend.tests.integration.test_delivery import decide, draft, prepare, snapshot
from backend.tests.integration.test_delivery import delivery_client as delivery_client


def publish(messages):
    did = json.loads(messages[-1]['content'])['data']['draft_id']
    return reply(('request_publish', {'draft_id': did}), ('read_file', {'path': 'fixture.md'}))


@pytest.mark.parametrize('written', [0, 1, 2])
async def test_process_crash_reconcile_reject_or_accept_and_resume_once(setup_agent, written):
    agent, store, session, root = setup_agent(ScriptedProvider(reply(('propose_patch', {
        'path': 'fixture.md', 'content': 'new-a', 'base_hash': None})), publish))
    before = (root / 'fixture.md').read_text()
    agent.provider.responses[0] = reply(('propose_patch', {'path': 'fixture.md', 'content': 'new-a', 'base_hash': sha(before)}))
    (root / 'fixture.md').chmod(0o600)
    (root / 'second.md').write_text('old-b')
    (root / 'second.md').chmod(0o600)
    run = agent.new_run(session['id'], '修改后请求审批', 0, 'review-crash-0001')
    await agent.run(run['id'])
    assert store.find('approvals', session['id']), [(c['name'], c['result'].get('error')) for c in store.find('calls', session['id'])]
    approval = store.find('approvals', session['id'])[0]
    # 故障夹具：同一待审批调用绑定两文件快照，覆盖多文件提交的中断窗口。
    with store.tx():
        replacement = agent.delivery.prepare(store.get('sessions', session['id']),
            {'fixture.md': 'new-a', 'second.md': 'new-b'}, run_id=run['id'], call_id=approval['call_id'])
        replacement['id'] = approval['id']
        original_id = store.find('approvals', session['id'])[-1]['id']
        orphan = store.get('approvals', original_id)
        orphan['status'] = 'CANCELLED'
        store.put('approvals', orphan)
        store.put('approvals', replacement)
    script = '''import os,sys
from pathlib import Path
from app.agent import Agent
from app.config import Settings
from app.storage import Store
from app.workspaces import Workspace
settings=Settings(_env_file=None,llm_provider='mock',yunyun_mode='pc',yunyun_workspace=Path(sys.argv[1]),yunyun_data_dir=Path(sys.argv[2]))
store=Store(settings.yunyun_data_dir/'state.sqlite3');agent=Agent(settings,store)
original=Workspace.replace; calls=0; stop=int(sys.argv[4])
def crash(self,*args,**kwargs):
 global calls
 if stop==0: os._exit(73)
 original(self,*args,**kwargs);calls+=1
 if calls==stop: os._exit(73)
Workspace.replace=crash
agent.delivery.decide(sys.argv[3],1,True)
'''
    result = subprocess.run([sys.executable, '-c', script, str(root), str(agent.settings.yunyun_data_dir), approval['id'], str(written)])
    assert result.returncode == 73
    db_path = agent.settings.yunyun_data_dir / 'state.sqlite3'
    store.close()
    reopened = Store(db_path)
    try:
        restored = Agent(agent.settings, reopened, ScriptedProvider(reply(content='对账后继续完成。')))
        reopened.recover()
        restored.delivery.recover()
        commit = reopened.find('commits', session['id'])[-1]
        assert commit['status'] == 'INTERRUPTED'
        assert reopened.get('approvals', approval['id'])['status'] == 'INTERRUPTED'
        assert reopened.get('runs', run['id'])['status'] == 'INTERRUPTED'
        assert reopened.get('calls', approval['call_id'])['status'] == 'INTERRUPTED'
        current = reopened.get('sessions', session['id'])
        with pytest.raises(AppError) as error:
            restored.prepare_resume(session['id'], current['revision'])
        assert error.value.code == 'RECOVERY_REQUIRED'
        with reopened.tx(), pytest.raises(AppError) as error:
            restored.delivery.prepare(current, {'new.md': 'cannot bypass'})
        assert error.value.code == 'RECOVERY_REQUIRED'
        other = restored.create_session('owner', session['context'])
        with reopened.tx(), pytest.raises(AppError) as error:
            restored.delivery.prepare(other, {'new.md': 'same real root'})
        assert error.value.code == 'RECOVERY_REQUIRED'
        observed = restored.delivery.inspect_recovery(current, commit['id'])
        assert sum(e['state'] == 'AFTER' for e in observed['entries']) == written
        if written == 1:
            (root / 'second.md').write_text('external change')
            with pytest.raises(AppError) as error:
                restored.delivery.reconcile(current, commit['id'], current['revision'], observed['snapshot_hash'], 'rollback')
            assert error.value.code == 'RECOVERY_CONFLICT'
            assert (root / 'fixture.md').read_text() == 'new-a'
            (root / 'second.md').write_text('old-b')
            observed = restored.delivery.inspect_recovery(current, commit['id'])
        decision = 'accept' if written == 2 else 'rollback' if written else 'reject'
        before_times = {p.name: p.stat().st_mtime_ns for p in root.iterdir()}
        restored.delivery.reconcile(current, commit['id'], current['revision'], observed['snapshot_hash'], decision)
        assert (root / 'fixture.md').read_text() == ('new-a' if written == 2 else before)
        assert (root / 'second.md').read_text() == ('new-b' if written == 2 else 'old-b')
        assert stat.S_IMODE((root / 'fixture.md').stat().st_mode) == 0o600
        assert stat.S_IMODE((root / 'second.md').stat().st_mode) == 0o600
        if written != 1:
            assert before_times == {p.name: p.stat().st_mtime_ns for p in root.iterdir()}
        assert reopened.get('calls', approval['call_id'])['status'] == 'DONE'
        resumed = restored.prepare_resume(session['id'], reopened.get('sessions', session['id'])['revision'])
        await restored.run(resumed['id'])
        assert reopened.get('runs', run['id'])['status'] == 'COMPLETED'
        messages = [m for m in reopened.messages(session['id']) if m.get('tool_call_id') == approval['call_id']]
        assert len(messages) == 1 and messages[0]['role'] == 'tool'
        assert len(reopened.find('commits', session['id'])) == 1
        with pytest.raises(AppError):
            restored.delivery.reconcile(current, commit['id'], reopened.get('sessions', session['id'])['revision'], observed['snapshot_hash'], decision)
    finally:
        reopened.close()


@pytest.mark.parametrize('decision', ['reject', 'approve'])
async def test_model_python_delete_has_same_review_contract(setup_agent, decision):
    agent, store, session, root = setup_agent(ScriptedProvider(reply(('propose_patch', {
        'path': 'remove.py', 'operation': 'delete', 'content': '', 'base_hash': sha('print(1)\n')})), publish))
    target = root / 'remove.py'
    target.write_text('print(1)\n')
    original = target.read_bytes()
    run = agent.new_run(session['id'], '删除旧题目', 0, 'review-delete-0001')
    await agent.run(run['id'])
    assert store.get('runs', run['id'])['status'] == 'WAITING_APPROVAL'
    assert store.find('approvals', session['id']), [(c['name'], c['result'].get('error')) for c in store.find('calls', session['id'])]
    approval = store.find('approvals', session['id'])[0]
    assert approval['status'] == 'PENDING'
    assert target.read_bytes() == original
    agent.delivery.decide(approval['id'], store.get('sessions', session['id'])['revision'], decision == 'approve')
    if decision == 'reject':
        assert target.read_bytes() == original
    else:
        assert not target.exists()


def test_overwrite_restore_permissions_and_conservative_create(delivery_client):
    app, client, sid, root = delivery_client
    target = root / 'lesson.md'
    target.chmod(0o600)
    original = target.read_bytes()
    did = draft(client, sid, 'lesson.md', '私有新教案\n', sha(original.decode())).json()['draft_id']
    a = prepare(client, sid, did).json()['approval']
    assert a['entries'][0]['before_mode'] == a['entries'][0]['content_mode'] == 0o600
    decide(client, sid, a['id'], 'approve')
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    commit = snapshot(client, sid)['commits'][-1]
    r = client.post(f'/api/sessions/{sid}/commits/{commit["id"]}/restore-draft', json={'expected_revision': snapshot(client, sid)['session']['revision']})
    assert r.status_code == 200
    decide(client, sid, r.json()['approval']['id'], 'approve')
    assert target.read_bytes() == original and stat.S_IMODE(target.stat().st_mode) == 0o600
    d = draft(client, sid, 'fresh.md', 'new', None).json()['draft_id']
    a = prepare(client, sid, d).json()['approval']
    decide(client, sid, a['id'], 'approve')
    assert stat.S_IMODE((root / 'fresh.md').stat().st_mode) == 0o600


@pytest.mark.parametrize('size', [540065, 1048576, 1048577])
@pytest.mark.parametrize('bom', [False, True])
def test_raw_json_upload_uses_original_bytes_and_hash(tmp_path, size, bom):
    settings = Settings(_env_file=None, llm_provider='mock', yunyun_mode='web', yunyun_data_dir=tmp_path)
    app = create_app(settings)
    obj = {'facts': [{'type': 'infinite_loop', 'count': 3}], 'padding': ''}
    prefix = b'\xef\xbb\xbf' if bom else b''
    payload_size = size - len(prefix)
    original = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
    obj['padding'] = '\\"汉\n' * ((payload_size - len(original)) // 9)
    raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
    obj['padding'] += 'x' * (payload_size - len(raw))
    raw = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
    raw = prefix + raw
    assert len(raw) == size
    with TestClient(app) as client:
        client.post('/api/client')
        sid = client.post('/api/sessions', json={}).json()['session']['id']
        r = client.post(f'/api/sessions/{sid}/class-profiles/upload?format=json&expected_revision=0', content=raw, headers={'Content-Type': 'application/octet-stream'})
        if size <= 1048576:
            assert r.status_code == 201, r.text
            assert r.json()['profile']['source_hash'] == sha(raw.decode())
            assert snapshot(client, sid)['profiles'][-1]['profile']['source_hash'] == sha(raw.decode())
        else:
            assert r.status_code == 413


def test_recovery_api_owns_exact_revision_and_disk_snapshot(delivery_client, monkeypatch):
    app, client, sid, root = delivery_client
    target = root / 'lesson.md'
    target.chmod(0o600)
    did = draft(client, sid, 'lesson.md', '中断时已写入\n', sha(target.read_bytes().decode())).json()['draft_id']
    approval = prepare(client, sid, did).json()['approval']
    ws_type = type(app.state.agent.workspace(snapshot(client, sid)['session']))
    original = ws_type.replace

    def interrupt_after_write(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise AppError('INJECTED_INTERRUPTION', '合成中断，仅故障注入。', 503)

    monkeypatch.setattr(ws_type, 'replace', interrupt_after_write)
    assert decide(client, sid, approval['id'], 'approve').status_code == 503
    monkeypatch.setattr(ws_type, 'replace', original)
    value = snapshot(client, sid)
    commit = value['commits'][-1]
    assert commit['status'] == 'INTERRUPTED'
    cid = commit['id']
    url = f'/api/sessions/{sid}/commits/{cid}/recovery'
    other = client.post('/api/sessions', json={}).json()['session']['id']
    assert client.get(f'/api/sessions/{other}/commits/{cid}/recovery').status_code == 404
    assert client.get(url, headers={'Cookie': 'yunyun_client=' + 'f' * 64}).status_code == 404
    observed = client.get(url).json()['recovery']
    assert observed['can_accept'] and not observed['can_reject']
    body = {'decision': 'accept', 'snapshot_hash': observed['snapshot_hash'], 'expected_revision': value['session']['revision']}
    assert client.post(url, json={**body, 'expected_revision': 0}).json()['error']['code'] == 'REVISION_CONFLICT'
    assert client.post(url, json={**body, 'snapshot_hash': '0' * 64}).json()['error']['code'] == 'RECOVERY_CONFLICT'
    assert client.post(url, json=body, headers={'Cookie': 'yunyun_client=' + 'f' * 64}).status_code == 404
    target.write_text('教师额外的外部修改\n')
    conflict = client.get(url).json()['recovery']
    assert conflict['entries'][0]['state'] == 'CONFLICT'
    assert not any(conflict[k] for k in ('can_accept', 'can_reject', 'can_rollback'))
    assert client.post(url, json={**body, 'decision': 'rollback', 'snapshot_hash': conflict['snapshot_hash']}).json()['error']['code'] == 'RECOVERY_CONFLICT'
    assert target.read_text() == '教师额外的外部修改\n'
    target.write_text('中断时已写入\n')
    final = client.get(url).json()['recovery']
    before = target.stat().st_mtime_ns
    accepted = client.post(url, json={**body, 'snapshot_hash': final['snapshot_hash']})
    assert accepted.status_code == 200 and accepted.json()['commit']['status'] == 'COMMITTED'
    assert target.stat().st_mtime_ns == before
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert client.post(url, json={**body, 'expected_revision': snapshot(client, sid)['session']['revision']}).json()['error']['code'] == 'RECOVERY_NOT_REQUIRED'
    continued = draft(client, sid, 'continued.md', 'new draft after reconciliation', None)
    assert continued.status_code == 200
    assert prepare(client, sid, continued.json()['draft_id']).json()['approval']['status'] == 'PENDING'


async def test_python_delete_still_blocks_other_unverified_code(setup_agent):
    saved = {}

    def save_delete_id(messages):
        saved['delete_id'] = json.loads(messages[-1]['content'])['data']['draft_id']
        return reply(('propose_patch', {'path': 'failed.py', 'content': 'raise ValueError("bad")', 'base_hash': None}))

    agent, store, session, root = setup_agent(ScriptedProvider(
        reply(('propose_patch', {'path': 'remove.py', 'operation': 'delete', 'content': '', 'base_hash': sha('print(1)\n')})),
        save_delete_id, lambda _: reply(('request_publish', {'draft_id': saved['delete_id']})), reply(content='未验证，停止交付。')))
    (root / 'remove.py').write_text('print(1)\n')
    run = agent.new_run(session['id'], '删除旧代码，但其他新代码尚未通过测试', 0, 'delete-block-other-01')
    await agent.run(run['id'])
    publish_call = next(c for c in store.find('calls', session['id']) if c['name'] == 'request_publish')
    assert publish_call['result']['error']['code'] == 'VERIFICATION_REQUIRED'
    assert not store.find('approvals', session['id'])
    assert (root / 'remove.py').read_text() == 'print(1)\n'


@pytest.mark.parametrize('mode', [0o600, 0o640])
def test_legacy_pending_approval_records_permissions_on_commit(delivery_client, mode):
    app, client, sid, root = delivery_client
    target = root / 'lesson.md'
    target.chmod(mode)
    original = target.read_bytes().decode()
    did = draft(client, sid, 'lesson.md', 'new legacy approval content', sha(original)).json()['draft_id']
    approval = prepare(client, sid, did).json()['approval']
    for entry in approval['entries']:
        for key in ('before_mode', 'base_mode', 'content_mode'):
            entry.pop(key)
    approval['snapshot_hash'] = sha(dumps(approval['entries']))
    with app.state.store.tx():
        app.state.store.put('approvals', approval)
    assert decide(client, sid, approval['id'], 'approve').status_code == 200
    commit = snapshot(client, sid)['commits'][-1]
    assert commit['entries'][0]['before_mode'] == mode
    assert stat.S_IMODE(target.stat().st_mode) == mode
    restored = client.post(f'/api/sessions/{sid}/commits/{commit["id"]}/restore-draft', json={'expected_revision': snapshot(client, sid)['session']['revision']})
    assert restored.status_code == 200
    assert decide(client, sid, restored.json()['approval']['id'], 'approve').status_code == 200
    assert target.read_bytes().decode() == original and stat.S_IMODE(target.stat().st_mode) == mode
