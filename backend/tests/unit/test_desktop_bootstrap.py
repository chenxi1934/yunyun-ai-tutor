"""启动器配置/版本/失败回归；不伪造模型或Runner执行证据。"""
import argparse
import importlib.util
import json
import socket
import sys
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('desktop_bootstrap', Path(__file__).resolve().parents[3] / 'scripts/desktop_bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)


def args(root, **changes):
    return argparse.Namespace(workspace=root / 'teacher', runner_ssh=None, **changes)


@pytest.fixture
def config_root(tmp_path, monkeypatch):
    for name in ['DASHSCOPE_API_KEY', 'RUNNER_SOCKET', 'RUNNER_TOKEN', 'LLM_PROVIDER', 'YUNYUN_DATA_DIR']:
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def frontend(root):
    (root / 'frontend/src').mkdir(parents=True)
    (root / 'frontend/dist').mkdir()
    for name in ['package.json', 'package-lock.json', 'index.html', 'vite.config.ts', 'tsconfig.json']:
        (root / 'frontend' / name).write_text('fixture')
    (root / 'frontend/src/App.tsx').write_text('source')
    (root / 'frontend/dist/index.html').write_text('built HTML')
    marker = root / 'desktop-build.json'
    marker.write_text(json.dumps(bootstrap.frontend_manifest(root)))
    return marker


def test_prebuilt_ui_is_reused_and_source_or_asset_changes_invalidate(tmp_path, monkeypatch):
    marker = frontend(tmp_path)
    monkeypatch.setattr(bootstrap.subprocess, 'run', lambda *a, **k: pytest.fail('不应构建已校验的界面'))
    bootstrap.ensure_frontend(tmp_path)
    assert bootstrap.frontend_ready(tmp_path, marker)
    (tmp_path / 'frontend/dist/index.html').write_text('tampered')
    assert not bootstrap.frontend_ready(tmp_path, marker)
    marker = frontend_manifest_reset(tmp_path)
    (tmp_path / 'frontend/src/App.tsx').write_text('new source')
    assert not bootstrap.frontend_ready(tmp_path, marker)


def frontend_manifest_reset(root):
    path = root / 'desktop-build.json'
    path.write_text(json.dumps(bootstrap.frontend_manifest(root)))
    return path


def test_missing_model_key_noninteractive_is_actionable_and_does_not_write(config_root, monkeypatch):
    monkeypatch.setattr(bootstrap.sys.stdin, 'isatty', lambda: False)
    with pytest.raises(RuntimeError, match='缺少模型Key'):
        bootstrap.configuration(config_root, args(config_root))
    assert not (config_root / '.env').exists()
    assert not (config_root / '.runtime/desktop-settings.json').exists()


def test_first_configuration_saves_key_privately_and_preserves_existing_settings(config_root, monkeypatch):
    path = config_root / '.env'
    path.write_text('LLM_MODEL=qwen3.8-max\n# 原配置注释\nDASHSCOPE_API_KEY=\n')
    monkeypatch.setattr(bootstrap.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(bootstrap.getpass, 'getpass', lambda _: 'synthetic-local-fixture-key')
    monkeypatch.setattr(bootstrap, 'prompt', lambda *a: 'teacher@example.test')
    settings, workspace, target = bootstrap.configuration(config_root, args(config_root))
    assert settings.dashscope_api_key.get_secret_value() == 'synthetic-local-fixture-key'
    assert '# 原配置注释' in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert target == 'teacher@example.test' and workspace == (config_root / 'teacher')
    assert 'synthetic-local-fixture-key' not in (config_root / '.runtime/desktop-settings.json').read_text()
    before = path.read_bytes()
    bootstrap.configuration(config_root, args(config_root))
    assert path.read_bytes() == before


@pytest.mark.parametrize('target', ['-oProxyCommand=bad', 'root@host command', 'root@host;touch x'])
def test_invalid_ssh_target_cannot_become_command_arguments(config_root, monkeypatch, target):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'synthetic-test-key')
    value = args(config_root)
    value.runner_ssh = target
    with pytest.raises(RuntimeError, match='SSH连接名称不合法'):
        bootstrap.configuration(config_root, value)


def test_direct_runner_environment_needs_no_ssh_credentials(config_root, monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'synthetic-test-key')
    monkeypatch.setenv('RUNNER_SOCKET', '/tmp/synthetic-not-executed.sock')
    monkeypatch.setenv('RUNNER_TOKEN', 'synthetic-test-token')
    _, _, target = bootstrap.configuration(config_root, args(config_root))
    assert target is None  # 只检查选择逻辑，不表示执行器已就绪。


def test_symlink_workspace_is_not_selected(config_root, monkeypatch):
    monkeypatch.setenv('DASHSCOPE_API_KEY', 'synthetic-test-key')
    (config_root / 'real').mkdir()
    (config_root / 'teacher').symlink_to(config_root / 'real')
    with pytest.raises(RuntimeError, match='符号链接'):
        bootstrap.configuration(config_root, args(config_root))


def test_occupied_port_fails_before_configuration_and_preserves_service(config_root, monkeypatch, capsys):
    monkeypatch.setattr(bootstrap, 'ROOT', config_root)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        monkeypatch.setattr(sys, 'argv', ['desktop_bootstrap.py', '--port', str(port)])
        assert bootstrap.main() == 2
        assert '被占用' in capsys.readouterr().err
        assert listener.getsockname()[1] == port
    assert not (config_root / '.env').exists()


def test_failed_ssh_cleans_child_and_does_not_start_api(config_root, monkeypatch):
    import contextlib
    class FailedProcess:
        def poll(self):
            return 255
    calls = []
    monkeypatch.setattr(bootstrap.subprocess, 'Popen', lambda command, **kw: calls.append(command) or FailedProcess())
    with pytest.raises(RuntimeError, match='SSH未连接'):
        with bootstrap.runner_connection(config_root, None, 'teacher@example.test'):
            pytest.fail('认证失败不能进入可用分支')
    assert 'StrictHostKeyChecking=ask' in calls[0]
    assert not any('app.launch' in c for command in calls for c in command)
    with contextlib.suppress(OSError):
        (config_root / '.runtime').rmdir()
