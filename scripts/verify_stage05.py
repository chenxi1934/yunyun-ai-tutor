"""复用已部署的私有Runner，运行真实交付测试；可继续运行双浏览器验收。"""
import argparse
import os
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
from app.config import PROJECT_ROOT, Settings
from app.storage import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target')
    parser.add_argument('--url', default='https://111.229.226.186')
    parser.add_argument('--browser', action='store_true')
    parser.add_argument('--tests-only', action='store_true')
    parser.add_argument('--evidence-prefix', default='stage05')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', args.evidence_prefix):
        parser.error('证据前缀仅允许字母、数字、下划线和连字符')
    prefix = args.evidence_prefix
    ssh = ['ssh', '-S', str(PROJECT_ROOT / '.runtime/ssh_control'), '-o',
           'UserKnownHostsFile=' + str(PROJECT_ROOT / '.runtime/ssh_known_hosts'), args.target]
    raw = subprocess.run([*ssh, 'cat /opt/yunyun-tutor/runner.env'], check=True, capture_output=True, text=True).stdout
    token = next(line.split('=', 1)[1] for line in raw.splitlines() if line.startswith('RUNNER_TOKEN='))
    with tempfile.TemporaryDirectory(prefix='yy05-', dir='/tmp') as temporary:
        socket = Path(temporary) / 'runner.sock'
        tunnel = subprocess.Popen([*ssh[:-1], '-o', 'ExitOnForwardFailure=yes', '-N', '-L',
            str(socket) + ':/opt/yunyun-tutor/socket/runner.sock', args.target])
        process = None
        scratch = None
        ledger = None
        try:
            for _ in range(100):
                if socket.exists():
                    break
                time.sleep(.1)
            env = {**os.environ, 'YUNYUN_TEST_RUNNER_SOCKET': str(socket), 'YUNYUN_TEST_RUNNER_TOKEN': token}
            if args.tests_only or not args.browser:
                subprocess.run([str(PROJECT_ROOT / '.venv/bin/python'), '-m', 'pytest',
                    'backend/tests/integration/test_delivery_real.py',
                    'backend/tests/integration/test_verification.py::test_real_isolation_network_files_commands_pids', '-q', '-o', 'junit_family=xunit1',
                    f'--junitxml=.runtime/{prefix}-real-delivery.xml'], env=env, check=True)
            if args.browser:
                teacher = Path(tempfile.mkdtemp(prefix='yunyun-stage05-teacher-', dir='/tmp')).resolve()
                shutil.copytree(PROJECT_ROOT / 'backend/seeds/core', teacher, dirs_exist_ok=True)
                (teacher / 'formal.md').write_text('教师原有正式文件\n')
                marker = secrets.token_hex(12) if os.environ.get('YUNYUN_FINAL_ACCEPTANCE') else ''
                if marker:
                    readme = teacher / 'README.md'
                    readme.write_text(readme.read_text() + '\n现场核验标记：' + marker + '\n')
                # 独立验收数据库避免重启探针影响PC会话；用量记录继承并合并。
                ledger = Settings().yunyun_data_dir / 'state.sqlite3'
                scratch = PROJECT_ROOT / '.runtime' / (prefix + '-state-' + secrets.token_hex(4))
                original = Store(ledger)
                baseline_usage = original.find('usage')
                original.close()
                working = Store(scratch / 'state.sqlite3')
                with working.tx():
                    for entry in baseline_usage:
                        working.put('usage', entry)
                working.close()
                local_token = secrets.token_urlsafe(32)
                env.update(RUNNER_SOCKET=str(socket), RUNNER_TOKEN=token, YUNYUN_MODE='pc',
                    YUNYUN_WORKSPACE=str(teacher), YUNYUN_LOCAL_TOKEN=local_token,
                    YUNYUN_SECURE_COOKIE='false',
                    YUNYUN_DATA_DIR=str(scratch), YUNYUN_EVIDENCE_PREFIX=prefix,
                    YUNYUN_ACCEPT_MARKER=marker,
                    YUNYUN_PC_URL='http://127.0.0.1:18006', YUNYUN_PC_WORKSPACE=str(teacher), YUNYUN_WEB_URL=args.url)
                (PROJECT_ROOT / f'.runtime/{prefix}-teacher-path.txt').write_text(str(teacher))
                log = (PROJECT_ROOT / f'.runtime/{prefix}-pc.log').open('a')
                def start():
                    value = subprocess.Popen([str(PROJECT_ROOT / '.venv/bin/python'), '-m', 'uvicorn',
                        'app.main:app', '--host', '127.0.0.1', '--port', '18006', '--no-access-log'],
                        env=env, stdout=log, stderr=log)
                    for _ in range(100):
                        try:
                            if httpx.get('http://127.0.0.1:18006/api/health', timeout=.5).status_code == 200:
                                return value
                        except httpx.RequestError:
                            pass
                        time.sleep(.1)
                    raise RuntimeError('PC服务启动失败')
                process = start()
                browser = subprocess.Popen(['node', str(PROJECT_ROOT / 'scripts/browser-stage05.cjs')],
                    env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
                for line in browser.stdout:
                    print(line, end='', flush=True)
                    if line.strip() == 'RESTART_PC':
                        process.kill()
                        process.wait(timeout=10)
                        process = start()
                        browser.stdin.write('ok\n')
                        browser.stdin.flush()
                if browser.wait():
                    raise RuntimeError('浏览器验收失败，请查看stage05-browser.json')
                log.close()
        finally:
            if process:
                process.terminate()
                process.wait(timeout=10)
            if scratch and ledger:
                original, working = Store(ledger), Store(scratch / 'state.sqlite3')
                try:
                    with original.tx():
                        existing = {u['id'] for u in original.find('usage')}
                        for entry in working.find('usage'):
                            if entry['id'] not in existing:
                                original.put('usage', entry)
                finally:
                    original.close()
                    working.close()
            tunnel.terminate()
            tunnel.wait(timeout=10)


if __name__ == '__main__':
    main()
