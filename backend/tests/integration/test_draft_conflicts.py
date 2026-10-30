import pytest
from app.domain import sha

from backend.tests.integration.test_delivery import decide, draft, prepare, snapshot
from backend.tests.integration.test_delivery import delivery_client as delivery_client


@pytest.mark.parametrize('mode', ['modified', 'created', 'deleted'])
def test_conflict_identifies_file_and_latest_comparison_without_writing(delivery_client, mode):
    _, client, sid, root = delivery_client
    path = root / ('new.md' if mode == 'created' else 'lesson.md')
    before = path.read_bytes().decode() if path.exists() else None
    did = draft(client, sid, path.name, '保留的候选教案\n', sha(before) if before is not None else None).json()['draft_id']
    if mode == 'deleted':
        path.unlink()
        current = None
    else:
        current = '后来保存的正式版本\n'
        path.write_text(current)
    revision = snapshot(client, sid)['session']['revision']
    response = prepare(client, sid, did)
    assert response.status_code == 409
    error = response.json()['error']
    assert path.name in error['message']
    assert error['details']['kind'] == 'FILE_DRAFT_CONFLICT'
    assert error['details']['reason'] == mode
    assert error['details']['draft_id'] == did
    assert error['details']['current_file'] == {'path': path.name, 'content': current or '',
                                               'hash': sha(current) if current is not None else None}
    assert '+保留的候选教案' in error['details']['diff']
    state = snapshot(client, sid)
    assert not state['approvals'] and not state['commits']
    assert state['session']['revision'] == revision
    assert (path.read_bytes().decode() if path.exists() else None) == current


def test_publishing_the_same_written_draft_explains_no_change(delivery_client):
    _, client, sid, root = delivery_client
    did = draft(client, sid, 'lesson.md', '新教案\n', sha((root / 'lesson.md').read_bytes().decode())).json()['draft_id']
    approval = prepare(client, sid, did).json()['approval']
    assert decide(client, sid, approval['id'], 'approve').status_code == 200
    response = prepare(client, sid, did)
    assert response.status_code == 409
    error = response.json()['error']
    assert error['code'] == 'DRAFT_ALREADY_CURRENT'
    assert error['details']['reason'] == 'already_current'
    assert '无需' in error['message'] and 'lesson.md' in error['message']
    state = snapshot(client, sid)
    assert len(state['commits']) == len(state['approvals']) == 1


def test_refresh_base_keeps_candidate_and_history_requires_new_review(delivery_client):
    _, client, sid, root = delivery_client
    original = (root / 'lesson.md').read_bytes().decode()
    did = draft(client, sid, 'lesson.md', '候选内容\n', sha(original)).json()['draft_id']
    current = '教师后来保存的内容\n'
    (root / 'lesson.md').write_text(current)
    revision = snapshot(client, sid)['session']['revision']
    response = client.post(f'/api/sessions/{sid}/refresh-draft', json={'draft_id': did,
        'expected_revision': revision, 'current_hash': sha(current)})
    assert response.status_code == 200, response.text
    new_id = response.json()['draft_id']
    state = snapshot(client, sid)
    assert new_id != did and len(state['drafts']) == 2
    old, new = state['drafts']
    assert old['base_hash'] == sha(original) and old['content'] == new['content'] == '候选内容\n'
    assert new['base_hash'] == sha(current) and new['parent_id'] == did
    assert '-教师后来保存的内容' in new['diff'] and '+候选内容' in new['diff']
    assert new['verification_status'] == 'NOT_TESTED'
    assert not state['approvals'] and not state['commits']
    assert (root / 'lesson.md').read_bytes().decode() == current
    approval = prepare(client, sid, new_id).json()['approval']
    assert decide(client, sid, approval['id'], 'reject').status_code == 200
    assert (root / 'lesson.md').read_bytes().decode() == current


def test_refresh_base_rechecks_disk_and_session_revision(delivery_client):
    _, client, sid, root = delivery_client
    did = draft(client, sid, 'lesson.md', '候选\n', sha((root / 'lesson.md').read_bytes().decode())).json()['draft_id']
    (root / 'lesson.md').write_text('第一份外部修改\n')
    checked_hash = sha((root / 'lesson.md').read_bytes().decode())
    revision = snapshot(client, sid)['session']['revision']
    (root / 'lesson.md').write_text('之后再次修改\n')
    body = {'draft_id': did, 'expected_revision': revision, 'current_hash': checked_hash}
    response = client.post(f'/api/sessions/{sid}/refresh-draft', json=body)
    assert response.status_code == 409
    assert response.json()['error']['details']['current_file']['hash'] == sha('之后再次修改\n')
    assert len(snapshot(client, sid)['drafts']) == 1
    body.update(current_hash=sha('之后再次修改\n'), expected_revision=revision - 1)
    assert client.post(f'/api/sessions/{sid}/refresh-draft', json=body).status_code == 409
    assert (root / 'lesson.md').read_bytes().decode() == '之后再次修改\n'


def test_refresh_deletion_keeps_delete_intent_and_missing_file_needs_no_repeat(delivery_client):
    _, client, sid, root = delivery_client
    did = draft(client, sid, 'lesson.md', '', sha((root / 'lesson.md').read_bytes().decode()), 'delete').json()['draft_id']
    (root / 'lesson.md').write_text('新的正式内容\n')
    revision = snapshot(client, sid)['session']['revision']
    response = client.post(f'/api/sessions/{sid}/refresh-draft', json={'draft_id': did,
        'expected_revision': revision, 'current_hash': sha('新的正式内容\n')})
    assert response.status_code == 200
    new = snapshot(client, sid)['drafts'][-1]
    assert new['operation'] == 'delete' and new['content'] == ''
    assert (root / 'lesson.md').exists()
    (root / 'lesson.md').unlink()
    no_change = prepare(client, sid, new['id'])
    assert no_change.json()['error']['code'] == 'DRAFT_ALREADY_CURRENT'


def test_refresh_cannot_use_other_sessions_draft_or_replace_newer_candidate(delivery_client):
    _, client, sid, root = delivery_client
    current = (root / 'lesson.md').read_bytes().decode()
    did = draft(client, sid, 'lesson.md', '旧候选\n', sha(current)).json()['draft_id']
    other = client.post('/api/sessions', json={}).json()['session']['id']
    response = client.post(f'/api/sessions/{other}/refresh-draft', json={'draft_id': did,
        'expected_revision': 0, 'current_hash': sha(current)})
    assert response.status_code == 404 and 'details' not in response.json()['error']
    newer = draft(client, sid, 'lesson.md', '新的候选\n', sha(current)).json()['draft_id']
    response = client.post(f'/api/sessions/{sid}/refresh-draft', json={'draft_id': did,
        'expected_revision': snapshot(client, sid)['session']['revision'], 'current_hash': sha(current)})
    assert response.status_code == 409 and response.json()['error']['code'] == 'STALE_DRAFT'
    assert snapshot(client, sid)['drafts'][-1]['id'] == newer
    assert (root / 'lesson.md').read_bytes().decode() == current


def test_refresh_does_not_follow_symlink(delivery_client, tmp_path):
    _, client, sid, root = delivery_client
    did = draft(client, sid, 'lesson.md', '候选\n', sha((root / 'lesson.md').read_bytes().decode())).json()['draft_id']
    outside = tmp_path / 'outside.md'
    outside.write_text('外部文件\n')
    (root / 'lesson.md').unlink()
    (root / 'lesson.md').symlink_to(outside)
    response = client.post(f'/api/sessions/{sid}/refresh-draft', json={'draft_id': did,
        'expected_revision': snapshot(client, sid)['session']['revision'], 'current_hash': sha('外部文件\n')})
    assert response.status_code == 403
    assert outside.read_text() == '外部文件\n' and len(snapshot(client, sid)['drafts']) == 1


def test_refresh_teaching_code_cannot_bypass_item_revision_and_verification(delivery_client):
    _, client, sid, root = delivery_client
    base = f'/api/sessions/{sid}'
    client.post(base + '/class-profiles', json={'format': 'text', 'content': '5人未交', 'expected_revision': 0})
    context = client.get(base + '/education-context').json()
    proposed = client.post(base + '/lessons', json={'profile_id': context['profile']['id'],
        'profile_revision': 1, 'base_revision': 0, 'plan': context['suggested_plan']}).json()['lesson']
    state = snapshot(client, sid)
    item_id = proposed['plan']['examples'][0]['id']
    did = proposed['items'][item_id]['draft_id']
    value = next(item for item in state['drafts'] if item['id'] == did)
    path = root / value['path']
    path.parent.mkdir(parents=True)
    path.write_text('# 正式文件已出现\n')
    response = client.post(base + '/refresh-draft', json={'draft_id': did,
        'expected_revision': state['session']['revision'], 'current_hash': sha(path.read_text())})
    assert response.status_code == 409 and response.json()['error']['code'] == 'EDUCATION_ITEM_REQUIRED'
    after = snapshot(client, sid)
    assert len(after['drafts']) == 5 and not after['approvals']
    assert all(not info.get('current_pass', False) for info in after['lessons'][-1]['items'].values())
