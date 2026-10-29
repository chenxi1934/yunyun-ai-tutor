"""真实隔离验收：SSH临时Manager + Unix socket转发；不传Key、不发布端口。

先使用SSH agent/控制连接登录；脚本不读取或保存SSH密码。
"""
import argparse
import asyncio
import os
import re
import secrets
import shlex
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

from app.config import PROJECT_ROOT, Settings
from app.domain import dumps, now, sha, uid


def live_probe(socket, token, output):
    from app.agent import Agent
    from app.storage import Store
    from app.verification.runner import RemoteRunner

    async def run():
        # 沿用实例费用账本，禁止以临时数据库重置真实模型预算。
        settings = Settings(runner_socket=socket, runner_token=token,
                            yunyun_mode='web', max_output_tokens=2048)
        if settings.llm_provider != 'bailian':
            raise RuntimeError('真实探针必须使用百炼，不能使用Mock')
        store = Store(settings.yunyun_data_dir / 'state.sqlite3')
        try:
            agent = Agent(settings, store)
            agent.verification.runner = RemoteRunner(socket, token)
            session = agent.create_session('stage03-probe', {'stage': '初中', 'topic': '循环结构'})
            # 合成错误夹具明确不是模型生成；后续修复和重测由真实模型自主调用。
            code = 'n=int(input())\nprint(sum(range(1,n)))\n'
            call = {'id': uid(), 'name': 'propose_patch', 'run_id': 'fixture',
                    'arguments': dumps({'path': 'sum.py', 'content': code, 'base_hash': None})}
            with store.tx():
                agent.registry.execute(call, session, agent.workspace(session))
                spec = agent.verification.freeze(session['id'], 'sum.py', None, 'sum_1_to_n')
            run = agent.new_run(session['id'], 'sum.py 已有一个待验证草稿。请读取草稿和冻结测试，'
                '真实运行，依据真实错误修复累加边界，再在同一冻结规格下重测。通过后说明仍需教师审核，'
                '不要请求正式发布。', 0, 'stage03-live-' + uid())
            await agent.run(run['id'])
            reports = store.find('reports', session['id'])
            calls = store.find('calls', session['id'])
            data = {'timestamp': now(), 'mock': False, 'fixture_code_hash': sha(code),
                'fixture_source': 'synthetic incorrect code, not model generated',
                'session_id': session['id'], 'run': store.get('runs', run['id']),
                'spec': spec, 'reports': reports, 'calls': calls,
                'drafts': store.find('drafts', session['id']),
                'usage': store.find('usage', session['id']),
                'events': store.events(session['id'])}
            output.write_text(dumps(data), encoding='utf-8')
            assert data['run']['status'] == 'COMPLETED', data['run']
            assert reports[0]['status'] == 'OUTPUT_MISMATCH'
            assert reports[-1]['status'] == 'PASS'
            assert len({r['test_spec_hash'] for r in reports}) == 1
            assert len({r['test_spec_revision'] for r in reports}) == 1
            actual_usage = [u for u in data['usage'] if u['status'] == 'USAGE_ESTIMATE']
            assert len(actual_usage) >= 3
            assert all(u['provider_request_id'] and u['input_tokens'] > 0 for u in actual_usage)
            assert all(u['status'] in {'USAGE_ESTIMATE', 'RESERVED_UNKNOWN'} for u in data['usage'])
            data['unknown_usage_reservations'] = sum(u['status'] == 'RESERVED_UNKNOWN' for u in data['usage'])
            assert len(agent.verification.delivery_candidates(session['id'])) == 1
            data['status'] = 'PASS'
            output.write_text(dumps(data), encoding='utf-8')
            return {'status': 'PASS', 'session_id': session['id'],
                    'cny_estimate': sum(u['cny'] for u in data['usage'])}
        finally:
            store.close()
    return asyncio.run(run())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='已登录的 SSH 别名或 user@host')
    parser.add_argument('--real-model', action='store_true')
    parser.add_argument('--evidence-prefix', default='stage03', help='本轮证据文件名前缀')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', args.evidence_prefix):
        parser.error('证据前缀仅允许字母、数字、下划线和连字符')
    prefix = args.evidence_prefix
    runtime = PROJECT_ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    ident = uid()[:12]
    remote = '/tmp/yunyun-stage03-' + ident
    image = 'yunyun-stage03-manager:' + ident
    manager = 'yunyun-stage03-manager-' + ident
    options = ['-S', str(runtime / 'ssh_control'), '-o',
               'UserKnownHostsFile=' + str(runtime / 'ssh_known_hosts'), '-o', 'BatchMode=yes']
    ssh = ['ssh', *options, args.target]
    token = secrets.token_hex(32)
    tunnel = None
    summary = {'timestamp': now(), 'status': 'FAIL', 'ports_published': False,
               'model_called': args.real_model}

    def command(cmd, **kwargs):
        return subprocess.run([*ssh, cmd], check=True, **kwargs)

    with tempfile.TemporaryDirectory(prefix='yy03-') as temp:
        socket = Path(temp) / 'runner.sock'
        archive = Path(temp) / 'source.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar:
            for name in ['pyproject.toml', 'backend', 'runner']:
                tar.add(PROJECT_ROOT / name, arcname=name, filter=lambda x: None if
                        '__pycache__' in x.name or x.name.endswith('.pyc') else x)
        command('mkdir -m 700 ' + remote)
        try:
            with archive.open('rb') as source:
                command('tar xzf - -C ' + remote, stdin=source)
            command('cd ' + remote + ' && docker build -q -f runner/Dockerfile '
                '--build-arg PYPI_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple -t ' + image +
                ' .', timeout=240, stdout=subprocess.DEVNULL)
            digest = command("docker image inspect --format '{{.Id}}' python:3.12-slim",
                             capture_output=True, text=True).stdout.strip()
            command('mkdir -m 700 ' + remote + '/socket')
            # 只有该可信Manager容器获得Socket。候选和公网API都没有。
            run_args = ['docker', 'run', '-d', '--name', manager, '--network=none', '--read-only',
                '--cap-drop=ALL', '--security-opt=no-new-privileges', '--memory=256m', '--pids-limit=128',
                '--tmpfs', '/tmp:rw,nosuid,size=16m', '-v', '/var/run/docker.sock:/var/run/docker.sock',
                '-v', remote + '/socket:/run/yunyun', '-e', 'RUNNER_IMAGE=' + digest,
                '-e', 'RUNNER_SOCKET=/run/yunyun/runner.sock', '-e', 'RUNNER_TOKEN=' + token, image]
            command(shlex.join(run_args), stdout=subprocess.DEVNULL)
            for _ in range(50):
                exists = subprocess.run([*ssh, 'test -S ' + remote + '/socket/runner.sock'])
                if exists.returncode == 0:
                    break
                time.sleep(.2)
            else:
                raise RuntimeError('Manager socket 未就绪')
            tunnel = subprocess.Popen(['ssh', *options, '-o', 'ExitOnForwardFailure=yes', '-N',
                '-L', str(socket) + ':' + remote + '/socket/runner.sock', args.target])
            for _ in range(30):
                if socket.exists():
                    break
                time.sleep(.1)
            env = {**os.environ, 'YUNYUN_TEST_RUNNER_SOCKET': str(socket),
                   'YUNYUN_TEST_RUNNER_TOKEN': token}
            tests = subprocess.run([str(PROJECT_ROOT / '.venv/bin/python'), '-m', 'pytest',
                'backend/tests/integration/test_verification.py', '-q',
                f'--junitxml=.runtime/{prefix}-real-tests.xml', '-o', 'junit_family=xunit1'], env=env)
            summary['pytest_exit_code'] = tests.returncode
            if tests.returncode:
                raise RuntimeError('真实隔离回归失败')
            # 故障注入仅操作本次Manager与测试容器，模拟Manager被SIGKILL遗留作业。
            orphan = 'yunyun-stage03-orphan-' + ident
            orphan_id = command(shlex.join(['docker', 'run', '-d', '--name', orphan,
                '--label', 'yunyun.runner=stage03', '--network=none', '--read-only',
                '--user=10001:10001', '--cap-drop=ALL', '--security-opt=no-new-privileges',
                '--memory=64m', '--pids-limit=16', '--cpus=0.5', digest,
                'python', '-I', '-c', 'while True: pass']), capture_output=True, text=True).stdout.strip()
            command('docker kill ' + manager, stdout=subprocess.DEVNULL)
            command('docker start ' + manager, stdout=subprocess.DEVNULL)
            from app.verification.runner import RemoteRunner
            for _ in range(50):
                try:
                    identity = asyncio.run(RemoteRunner(socket, token).identity())
                    break
                except Exception:
                    time.sleep(.2)
            else:
                raise RuntimeError('重启后Manager未就绪')
            left = command('docker ps -aq --filter name=' + orphan,
                           capture_output=True, text=True).stdout.strip()
            assert not left
            summary['restart_orphan_cleanup'] = {'status': 'PASS', 'orphan_id': orphan_id,
                                                'remaining': left, 'identity': identity}
            if args.real_model:
                summary['live_model'] = live_probe(socket, token, runtime / f'{prefix}-live-model.json')
            summary['runtime_digest'] = digest
            summary['manager_image'] = command("docker image inspect --format '{{.Id}}' " + image,
                                              capture_output=True, text=True).stdout.strip()
            summary['remaining_cases'] = command('docker ps -aq --filter label=yunyun.runner=stage03',
                                                 capture_output=True, text=True).stdout.strip()
            assert not summary['remaining_cases']
            summary['status'] = 'PASS'
        finally:
            if tunnel:
                tunnel.terminate()
                tunnel.wait(timeout=10)
            subprocess.run([*ssh, 'docker rm -f ' + manager], stdout=subprocess.DEVNULL)
            subprocess.run([*ssh, 'docker image rm ' + image], stdout=subprocess.DEVNULL)
            subprocess.run([*ssh, 'python3 -c ' + shlex.quote('import shutil;shutil.rmtree(' + repr(remote) + ')')])
            summary['test_source_hashes'] = {str(p.relative_to(PROJECT_ROOT)): sha(p.read_text())
                for p in (PROJECT_ROOT / 'backend/tests/integration/test_verification.py',
                          PROJECT_ROOT / 'scripts/verify_stage03.py')}
            summary['source_hashes'] = {str(p.relative_to(PROJECT_ROOT)): sha(p.read_text()) for folder
                in ('backend/app', 'runner') for p in (PROJECT_ROOT / folder).rglob('*.py')}
            (runtime / f'{prefix}-summary.json').write_text(dumps(summary), encoding='utf-8')
    print(dumps(summary))


if __name__ == '__main__':
    main()
