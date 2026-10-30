import hashlib
import json

import pytest
from app.api import create_app
from app.config import Settings
from app.education.profiles import parse_profile
from fastapi.testclient import TestClient


@pytest.fixture
def uat_client(tmp_path):
    app = create_app(Settings(_env_file=None, llm_provider='mock', yunyun_mode='web',
                              yunyun_data_dir=tmp_path))
    with TestClient(app) as client:
        client.post('/api/client')
        sid = client.post('/api/sessions', json={}).json()['session']['id']
        yield app, client, f'/api/sessions/{sid}'


@pytest.mark.parametrize('format', ['csv', 'json'])
def test_downloadable_synthetic_templates_can_be_uploaded(uat_client, format):
    _, client, base = uat_client
    template = client.get(f'/api/class-profile-templates/{format}')
    assert template.status_code == 200
    assert 'attachment;' in template.headers['content-disposition']
    profile = parse_profile(template.content.decode('utf-8-sig'), format, '初中', '初二')
    assert profile.class_size == 40 and len(profile.facts) == 2
    result = client.post(base + f'/class-profiles/upload?format={format}&expected_revision=0',
                         content=template.content)
    assert result.status_code == 201, result.text
    saved = result.json()['profile']
    assert saved['source_hash'] == hashlib.sha256(template.content).hexdigest()
    assert saved['sources'][0]['origin'] == 'upload'


def test_upload_supplements_and_conflicts_do_not_replace_saved_profile(uat_client):
    app, client, base = uat_client
    assert client.post(base + '/class-profiles', json={'format': 'text', 'content': '5人未交',
        'expected_revision': 0}).status_code == 201
    template = client.get('/api/class-profile-templates/csv')
    result = client.post(base + '/class-profiles/upload?format=csv&expected_revision=1&mode=supplement',
                         content=template.content)
    assert result.status_code == 201, result.text
    profile = result.json()['profile']
    assert profile['class_size'] == 40 and len(profile['facts']) == 2
    assert all(f['denominator'] == 40 for f in profile['facts'])
    data = {'format': 'text', 'content': '8人边界错误', 'mode': 'supplement', 'expected_revision': 2}
    result = client.post(base + '/class-profiles', json=data)
    assert result.status_code == 201, result.text
    assert len(result.json()['profile']['facts']) == 3
    data.update(content='9人边界错误', expected_revision=3)
    conflict = client.post(base + '/class-profiles', json=data)
    assert conflict.status_code == 409 and conflict.json()['error']['code'] == 'CLASS_PROFILE_CONFLICT'
    assert client.get(base).json()['session']['revision'] == 3
    unchanged = client.get(base + '/education-context').json()['profile']
    assert next(f for f in unchanged['facts'] if f['type'] == 'boundary_error')['count'] == 8
    data.update(content='2人未交', mode='replace')
    replaced = client.post(base + '/class-profiles', json=data)
    assert replaced.status_code == 201, replaced.text
    assert [f['count'] for f in replaced.json()['profile']['facts']] == [2]
    assert len(app.state.store.find('class_profiles', base.split('/')[-1])) == 4


def test_rejected_item_survives_refresh_and_restore_is_a_new_pending_version(uat_client):
    _, client, base = uat_client
    client.post(base + '/class-profiles', json={'format': 'text', 'content': '5人未交、3人死循环',
                                              'expected_revision': 0})
    context = client.get(base + '/education-context').json()
    proposed = client.post(base + '/lessons', json={'profile_id': context['profile']['id'],
        'profile_revision': 1, 'base_revision': 0, 'plan': context['suggested_plan']})
    assert proposed.status_code == 201, proposed.text
    lesson = proposed.json()['lesson']
    path = base + f'/lessons/{lesson["lesson_id"]}'
    old_item = lesson['plan']['overview'][0]
    body = {'expected_revision': 1, 'item_id': old_item['id'], 'decision': 'reject',
            'note': '合成审核：需增加可执行的课堂活动'}
    rejected = client.post(path + '/reviews', json=body)
    assert rejected.status_code == 200, rejected.text
    loaded = client.get(path).json()
    assert loaded['lesson']['items'][old_item['id']]['review_status'] == 'REJECTED'
    assert loaded['lesson']['items'][old_item['id']]['review_note'] == body['note']
    assert loaded['lesson']['plan']['overview'][0] == old_item
    assert not loaded['lesson']['delivery_ready']
    assert client.get(path + '/export').status_code == 409
    modified = {**old_item, 'content': old_item['content'] + '\n增加出口反馈。'}
    revised = client.patch(path + '/items', json={'expected_revision': 1, 'item_id': old_item['id'],
        'replacement': modified, 'reason': '合成修订'})
    assert revised.status_code == 200, revised.text
    restored = client.patch(path + '/items', json={'expected_revision': 2, 'item_id': old_item['id'],
        'replacement': old_item, 'reason': '合成回退'})
    assert restored.status_code == 200, restored.text
    current = client.get(path).json()
    assert current['lesson']['revision'] == 3
    assert current['lesson']['items'][old_item['id']]['review_status'] == 'PENDING'
    assert current['lesson']['bindings'] == lesson['bindings']
    assert len(current['history']) == 3 and current['reviews'][0]['decision'] == 'reject'


def test_message_records_explicit_observations_and_retry_is_idempotent(uat_client):
    app, client, base = uat_client
    data = {'content': '全班40人，5人未交、3人while死循环，请备一节循环课。',
            'expected_revision': 0, 'idempotency_key': 'uat-request-0001'}
    response = client.post(base + '/messages', json=data)
    assert response.status_code == 202, response.text
    retry = client.post(base + '/messages', json=data)
    assert retry.status_code == 202 and retry.json()['run_id'] == response.json()['run_id']
    profile = client.get(base + '/education-context').json()['profile']
    assert {f['type']: f['count'] for f in profile['facts']} == {'not_submitted': 5, 'infinite_loop': 3}
    assert profile['sources'][0]['origin'] == 'request'
    assert len(app.state.store.find('class_profiles', base.split('/')[-1])) == 1
    assert 'student_id' not in json.dumps(profile)
    client.post(f'/api/runs/{response.json()["run_id"]}/cancel')


def test_context_only_profile_can_be_supplemented_without_inventing_counts(uat_client):
    _, client, base = uat_client
    initial = client.post(base + '/class-profiles', json={'format': 'text',
        'content': '全班40人，刚学完条件语句。', 'expected_revision': 0})
    assert initial.status_code == 201, initial.text
    assert initial.json()['profile']['facts'] == []
    supplemented = client.post(base + '/class-profiles', json={'format': 'text',
        'content': '5人未交', 'mode': 'supplement', 'expected_revision': 1})
    assert supplemented.status_code == 201, supplemented.text
    profile = supplemented.json()['profile']
    assert profile['class_size'] == 40 and profile['prior_knowledge'] == ['条件语句']
    assert profile['facts'][0]['count'] == 5 and profile['facts'][0]['denominator'] == 40
