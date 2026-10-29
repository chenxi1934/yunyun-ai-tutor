import json

import pytest
from app.api import create_app
from app.config import Settings
from fastapi.testclient import TestClient


@pytest.fixture
def education_client(tmp_path):
    app = create_app(Settings(_env_file=None, llm_provider='mock', yunyun_mode='web',
                              yunyun_data_dir=tmp_path))
    with TestClient(app) as client:
        client.post('/api/client')
        sid = client.post('/api/sessions', json={}).json()['session']['id']
        yield app, client, sid


def test_upload_parse_generate_modify_view_and_owner(education_client):
    app, client, sid = education_client
    base = f'/api/sessions/{sid}'
    r = client.post(base + '/class-profiles/upload?format=csv&expected_revision=0',
                    content='type,count,name\nnot_submitted,5,合成姓名\ninfinite_loop,3,合成姓名\n',
                    headers={'Content-Type': 'text/csv'})
    assert r.status_code == 201, r.text
    assert '合成姓名' not in json.dumps(r.json(), ensure_ascii=False)
    context = client.get(base + '/education-context').json()
    r = client.post(base + '/lessons', json={'profile_id': context['profile']['id'], 'profile_revision': 1,
                    'base_revision': 0, 'plan': context['suggested_plan']})
    assert r.status_code == 201, r.text
    view = r.json()['lesson']
    lid = view['lesson_id']
    code = view['plan']['examples'][0]
    blocked = client.post(base + f'/lessons/{lid}/reviews', json={'expected_revision': 1,
        'item_id': code['id'], 'decision': 'accept', 'note': '未测试不能接受'})
    assert blocked.status_code == 409 and blocked.json()['error']['code'] == 'VERIFICATION_REQUIRED'
    r = client.post(base + f'/lessons/{lid}/verify', json={'expected_revision': 1})
    assert r.status_code == 503
    doc = client.get(base + f'/lessons/{lid}').json()
    assert doc['attempts'][0]['error']['code'] == 'RUNNER_UNAVAILABLE'
    assert client.get(base + f'/lessons/{lid}/export').status_code == 409
    document = client.get(base + f'/lessons/{lid}/json')
    assert document.status_code == 200 and not document.json()['delivery_ready']
    segment = view['plan']['segments'][0]
    modified = {**segment, 'activity': segment['activity'] + '教师核对实际提交情况。'}
    r = client.patch(base + f'/lessons/{lid}/items', json={'expected_revision': 1,
        'item_id': segment['id'], 'replacement': modified, 'reason': '细化环节'})
    assert r.status_code == 200 and r.json()['lesson']['revision'] == 2
    assert r.json()['lesson']['bindings'] == view['bindings']
    doc = client.get(base + f'/lessons/{lid}').json()
    assert len(doc['history']) == 2
    assert len(app.state.agent.workspace(app.state.store.get('sessions', sid)).list_files()) == 7
    cookies = dict(client.cookies)
    client.cookies.clear()
    client.post('/api/client')
    assert client.get(base + f'/lessons/{lid}').status_code == 404
    assert client.post(base + '/class-profiles', json={'format': 'text', 'content': '1人未交', 'expected_revision': 0}).status_code == 404
    client.cookies.clear()
    client.cookies.update(cookies)


@pytest.mark.parametrize('format,content,expected', [
    ('json', '{"facts":[{"type":"boundary_error","count":8}]}', 201),
    ('json', '{bad json}', 422),
    ('csv', b'\xff\xfe', 422),
    ('text', '5人未交', 422),
    ('csv', b'a' * 1048577, 413),
])
def test_file_upload_format_encoding_limits(education_client, format, content, expected):
    _, client, sid = education_client
    r = client.post(f'/api/sessions/{sid}/class-profiles/upload?format={format}&expected_revision=0', content=content)
    assert r.status_code == expected, r.text


def test_profile_conflict_cannot_overwrite_and_stage_is_explicit(education_client):
    app, client, sid = education_client
    body = {'format': 'text', 'content': '5人未交、3人死循环', 'expected_revision': 0}
    assert client.post(f'/api/sessions/{sid}/class-profiles', json=body).status_code == 201
    assert client.post(f'/api/sessions/{sid}/class-profiles', json=body).status_code == 409
    profiles = app.state.store.find('class_profiles', sid)
    assert len(profiles) == 1 and profiles[0]['profile']['stage'] == '初中'
    u = client.post('/api/sessions', json={'stage': '大学', 'grade': '大一'}).json()['session']['id']
    assert client.post(f'/api/sessions/{u}/class-profiles', json=body).status_code == 201
    context = client.get(f'/api/sessions/{u}/education-context').json()
    assert context['suggested_plan']['stage'] == '大学'
    assert context['suggested_plan']['exercises'][2]['task_id'] == 'primes'
