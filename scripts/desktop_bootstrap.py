"""macOS一键入口：本地准备、集中配置、临时SSH及既有PC启动器。"""
import argparse
import asyncio
import contextlib
import fcntl
import getpass
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
from pathlib import Path

from app.config import Settings
from app.demo_gateway import DemoRunner
from app.domain import AppError
from app.verification.runner import RemoteRunner

ROOT = Path(__file__).resolve().parent.parent
NODE_VERSION = '22.22.3'


def write_private(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            os.fchmod(file.fileno(), 0o600)
            file.write(content)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def frontend_inputs(root):
    files = [root / 'frontend' / name for name in (
        'package.json', 'package-lock.json', 'index.html', 'vite.config.ts', 'tsconfig.json')]
    files += sorted((root / 'frontend/src').rglob('*'))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in files if p.is_file()}


def frontend_manifest(root):
    return {'inputs': frontend_inputs(root), 'assets': {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / 'frontend/dist').rglob('*')) if p.is_file()}}


def frontend_ready(root, manifest):
    if not (root / 'frontend/dist/index.html').is_file():
        return False
    try:
        saved = json.loads(manifest.read_text())
        return bool(saved['assets']) and saved == frontend_manifest(root)
    except (OSError, ValueError, KeyError):
        return False


def ensure_frontend(root):
    cache = root / '.runtime/bootstrap'
    marker = cache / 'frontend.json'
    if frontend_ready(root, marker) or frontend_ready(root, root / 'desktop-build.json'):
        print('界面已准备，复用已校验的本地文件。', flush=True)
        return
    node = shutil.which('node')
    try:
        version = subprocess.check_output([node, '--version'], text=True).strip().lstrip('v') if node else ''
        available = tuple(map(int, version.split('.'))) >= (22, 19, 0)
    except (OSError, ValueError, subprocess.SubprocessError):
        available = False
    env = dict(os.environ)
    if not available:
        architecture = {'arm64': 'arm64', 'x86_64': 'x64'}.get(platform.machine())
        if architecture is None:
            raise RuntimeError('不支持此Mac架构，请使用README中的手动构建方式。')
        name = f'node-v{NODE_VERSION}-darwin-{architecture}'
        binary = cache / 'node' / name / 'bin'
        if not (binary / 'node').exists():
            print('从Node.js官方来源准备项目专用构建工具，不修改系统安装。', flush=True)
            folder = cache / 'node'
            folder.mkdir(parents=True, exist_ok=True)
            base = f'https://nodejs.org/dist/v{NODE_VERSION}/'
            with urllib.request.urlopen(base + 'SHASUMS256.txt', timeout=30) as response:
                sums = response.read().decode()
            filename = name + '.tar.gz'
            expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1] == filename)
            with tempfile.TemporaryDirectory(dir=folder) as temporary:
                archive = Path(temporary) / filename
                with urllib.request.urlopen(base + filename, timeout=60) as response, archive.open('wb') as file:
                    shutil.copyfileobj(response, file)
                if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
                    raise RuntimeError('Node下载校验失败，请检查网络后重试。')
                with tarfile.open(archive) as tar:
                    tar.extractall(folder, filter='data')
        env['PATH'] = str(binary) + os.pathsep + env.get('PATH', '')
    npm = shutil.which('npm', path=env['PATH'])
    if not npm:
        raise RuntimeError('未找到npm，请按README安装Node22.19+后重试。')
    print('准备界面：安装锁定依赖并构建，完成后下次直接复用。', flush=True)
    subprocess.run([npm, 'ci', '--registry=https://registry.npmjs.org', '--no-audit', '--no-fund'],
                   cwd=root / 'frontend', env=env, check=True)
    subprocess.run([npm, 'run', 'build'], cwd=root / 'frontend', env=env, check=True)
    write_private(marker, json.dumps(frontend_manifest(root)))


def prompt(label, default=''):
    if not sys.stdin.isatty():
        raise RuntimeError(f'缺少{label}。请在终端或双击“一键启动.command”完成首次配置。')
    value = input(label + (f' [{default}]' if default else '') + '：').strip()
    return value or default


def configuration(root, args):
    path = root / '.runtime/desktop-settings.json'
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        saved = {}
    settings = Settings(_env_file=root / '.env')
    if settings.llm_provider == 'bailian' and not settings.dashscope_api_key.get_secret_value().strip():
        if not sys.stdin.isatty():
            raise RuntimeError('缺少模型Key。请双击入口输入，或在本地.env填写DASHSCOPE_API_KEY。')
        key = getpass.getpass('百炼API Key（隐藏输入，仅保存到本地.env）：').strip()
        if not key or '\n' in key or '\r' in key:
            raise RuntimeError('未填写有效模型Key；没有启动或切换Mock。')
        env_file = root / '.env'
        original = env_file.read_text() if env_file.exists() else ''
        write_private(env_file, original.rstrip() + '\nDASHSCOPE_API_KEY=' + json.dumps(key) + '\n')
        settings = Settings(_env_file=root / '.env')
    if settings.llm_provider == 'mock':
        print('MOCK_LLM：模型为显式演示模式；代码执行仍须真实隔离Runner。', flush=True)
    value = args.workspace or saved.get('workspace') or prompt('教师教学目录', str(Path.home() / 'Documents/耘耘备课'))
    workspace = Path(value).expanduser()
    if workspace.is_symlink():
        raise RuntimeError('教学目录不能是符号链接，请选择真实目录。')
    workspace.mkdir(parents=True, exist_ok=True)
    workspace = workspace.resolve()
    data = settings.yunyun_data_dir.resolve()
    if data == workspace or data.is_relative_to(workspace):
        raise RuntimeError('教学目录不能包含项目运行数据；请在项目目录之外选择文件夹。')
    direct = bool(settings.runner_socket and settings.runner_token.get_secret_value())
    target = args.runner_ssh or (None if direct else saved.get('runner_ssh'))
    if not direct:
        target = target or prompt('隔离执行器SSH（由管理员提供）', 'root@111.229.226.186')
    if target and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*(?:@[A-Za-z0-9][A-Za-z0-9_.-]*)?', target):
        raise RuntimeError('SSH连接名称不合法，请填写已有别名或user@host。')
    write_private(path, json.dumps({'workspace': str(workspace), 'runner_ssh': target}, ensure_ascii=False))
    return settings, workspace, target


@contextlib.contextmanager
def runner_connection(root, settings, target):
    if not target:
        yield settings.runner_socket, settings.runner_token.get_secret_value()
        return
    with tempfile.TemporaryDirectory(prefix='yy-easy-', dir='/tmp') as temporary:
        control = Path(temporary) / 'ssh'
        known = root / '.runtime/ssh_known_hosts'
        ssh = ['ssh', '-S', str(control), '-o', 'StrictHostKeyChecking=ask', '-o',
               'UserKnownHostsFile=' + str(known), '-o', 'ConnectTimeout=10']
        master = tunnel = None
        try:
            print('连接私有执行器；首次须核对SSH主机指纹并输入自己的认证信息。密码不会保存。', flush=True)
            master = subprocess.Popen([*ssh, '-M', '-o', 'ControlPersist=no', '-N', target], stdout=subprocess.DEVNULL)
            deadline = time.monotonic() + 120
            while not control.exists():
                if master.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('执行器SSH未连接；请核对网络/认证后重试，不会启动不可验证的备课服务。')
                time.sleep(.1)
            response = subprocess.run([*ssh, target, 'cat /opt/yunyun-tutor/runner.env'],
                                      capture_output=True, text=True, timeout=15)
            token = next((line.split('=', 1)[1] for line in response.stdout.splitlines()
                          if line.startswith('RUNNER_TOKEN=')), '')
            if response.returncode or len(token) < 32:
                raise RuntimeError('没有取得有效执行器配置；请管理员检查Runner，勿在聊天发送Token。')
            socket_path = Path(temporary) / 'runner.sock'
            tunnel = subprocess.Popen([*ssh, '-o', 'ExitOnForwardFailure=yes', '-o', 'StreamLocalBindMask=0177',
                '-N', '-L', str(socket_path) + ':/opt/yunyun-tutor/socket/runner.sock', target], stdin=subprocess.DEVNULL)
            for _ in range(100):
                if socket_path.exists():
                    break
                if tunnel.poll() is not None:
                    raise RuntimeError('执行器转发失败，请检查SSH权限后重试。')
                time.sleep(.1)
            else:
                raise RuntimeError('执行器转发超时，请重试。')
            yield socket_path, token
        finally:
            for process in (tunnel, master):
                if process is not None and process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description='macOS集中配置并一键打开耘耘AI助教')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--runner-ssh')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--check', action='store_true', help='准备并检查后退出，不启动界面，不调用模型')
    parser.add_argument('--standalone', action='store_true', help='高级独立模式：使用自己的模型Key和SSH/Runner配置')
    parser.add_argument('--gateway-url', default='https://111.229.226.186', help='演示服务地址；无需模型Key或SSH')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('此一键入口目前只支持macOS。')
    if not 1 <= args.port <= 65535:
        parser.error('端口须在1～65535之间。')
    def interrupted(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    lock = ROOT / '.runtime/desktop.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock.open('a') as file:
            os.chmod(lock, 0o600)
            try:
                fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError('本项目已在启动或运行。请使用原浏览器窗口；关闭原终端后可再次启动。') from None
            try:
                with socket.socket() as probe:
                    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    probe.bind(('127.0.0.1', args.port))
            except OSError:
                raise RuntimeError(f'端口{args.port}被占用；可运行 bash scripts/start-easy.sh --port {args.port + 1}。不会关闭已有服务。') from None
            if not args.standalone:
                ensure_frontend(ROOT)
                identity = asyncio.run(DemoRunner(args.gateway_url).identity())
                if not identity.get('model_ready'):
                    raise RuntimeError('演示模型尚未就绪，请联系演示者。无需在本机填写Key。')
                print('演示服务及隔离执行器已连接；无需本地模型Key或SSH。', flush=True)
                if args.check:
                    return 0
                command = [sys.executable, '-m', 'app.launch', '--gateway-url', args.gateway_url,
                           '--port', str(args.port)]
                if args.workspace:
                    command += ['--workspace', str(args.workspace)]
                if args.no_browser:
                    command.append('--no-browser')
                print('打开浏览器后点击“打开本地工作区”选择教学目录；Ctrl+C退出。', flush=True)
                return subprocess.run(command, cwd=ROOT).returncode
            settings, workspace, target = configuration(ROOT, args)
            ensure_frontend(ROOT)
            with runner_connection(ROOT, settings, target) as (runner_socket, token):
                asyncio.run(RemoteRunner(runner_socket, token).identity())
                print('隔离执行器已就绪。未调用模型；真实教学代码仍会逐份验证。', flush=True)
                if args.check:
                    return 0
                env = {**os.environ, 'RUNNER_SOCKET': str(runner_socket), 'RUNNER_TOKEN': token}
                command = [sys.executable, '-m', 'app.launch', '--workspace', str(workspace), '--port', str(args.port)]
                if args.no_browser:
                    command.append('--no-browser')
                print('打开本机界面。保留本终端；按Ctrl+C退出，教案和会话继续保留。', flush=True)
                return subprocess.run(command, cwd=ROOT, env=env).returncode
    except KeyboardInterrupt:
        print('\n已退出，教学文件和会话保留。', flush=True)
        return 130
    except (OSError, ValueError, RuntimeError, AppError, subprocess.SubprocessError) as error:
        message = error.message if isinstance(error, AppError) else str(error)
        print('启动未完成：' + message, file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
