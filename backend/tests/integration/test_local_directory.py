"""本地路径选择边界，不执行模型/Runner。"""
import pytest
from app.api import create_app
from app.config import Settings
from fastapi.testclient import TestClient


@pytest.fixture
def local(tmp_path):
    original, selected = tmp_path / 'original', tmp_path / 'selected'
    original.mkdir()
    selected.mkdir()
    settings = Settings(_env_file=None, llm_provider='mock', yunyun_mode='pc',
        yunyun_local_token='synthetic-token', yunyun_workspace=original,
        yunyun_data_dir=tmp_path / 'data')
    app = create_app(settings)
    with TestClient(app, headers={'Authorization': 'Bearer synthetic-token'}) as client:
        client.post('/api/client')
        yield app, client, original, selected


def test_select_changes_only_future_session_and_never_writes_teacher_files(local):
    app, client, original, selected = local
    first = client.post('/api/sessions', json={}).json()['session']
    response = client.post('/api/local-workspace/select', json={'path': str(selected)})
    assert response.status_code == 200 and response.json()['workspace_name'] == 'selected'
    second = client.post('/api/sessions', json={}).json()['session']
    assert app.state.agent.workspace(first).root == original
    assert app.state.agent.workspace(second).root == selected
    assert list(original.iterdir()) == list(selected.iterdir()) == []


@pytest.mark.parametrize('invalid', ['relative', 'missing', 'file', 'link', 'data', 'ancestor'])
def test_invalid_directory_does_not_change_selected_workspace(local, invalid):
    app, client, original, selected = local
    value = selected.parent / 'does-not-exist'
    if invalid == 'relative':
        value = '.'
    elif invalid == 'file':
        value = selected.parent / 'file.txt'
        value.write_text('fixture')
    elif invalid == 'link':
        value = selected.parent / 'link'
        value.symlink_to(selected, target_is_directory=True)
    elif invalid == 'data':
        value = app.state.agent.settings.yunyun_data_dir
    elif invalid == 'ancestor':
        value = selected.parent
    response = client.post('/api/local-workspace/select', json={'path': str(value)})
    assert response.status_code in {403, 409, 422}
    assert app.state.agent.settings.yunyun_workspace == original


def test_local_directory_requires_local_authorization_and_same_origin(local):
    app, client, _, selected = local
    body = {'path': str(selected)}
    assert client.post('/api/local-workspace/select', json={**body, 'command': 'open'}).status_code == 422
    assert client.post('/api/local-workspace/select', json=body, headers={'Origin': 'https://other.test'}).status_code == 403
    client.headers.pop('Authorization')
    assert client.post('/api/local-workspace/select', json=body).status_code == 403
    app.state.agent.settings.yunyun_mode = 'web'
    assert client.post('/api/local-workspace/select', json=body).status_code == 403
