import argparse
import secrets
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from pydantic import SecretStr

from app.api import create_app
from app.config import PROJECT_ROOT, Settings


def main():
    parser = argparse.ArgumentParser(description='耘耘AI助教 PC 启动入口')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--runner-ssh', help='可选：连接已部署的私有Runner，使用SSH agent或已有控制连接')
    parser.add_argument('--gateway-url', help='可选：演示服务HTTPS地址；模型Key仅留在服务器')
    args = parser.parse_args()
    if args.workspace is None and not args.gateway_url:
        if sys.platform != 'darwin':
            parser.error('请使用 --workspace 选择真实教学目录。')
        selected = subprocess.run(['osascript', '-e', 'POSIX path of (choose folder with prompt "选择教师教学工作区")'], capture_output=True, text=True)
        if selected.returncode:
            parser.exit(message='已取消选择工作区。\n')
        args.workspace = Path(selected.stdout.strip())
    if args.workspace is not None and (args.workspace.is_symlink() or not args.workspace.is_dir()):
        parser.error('--workspace 必须指向已有的真实教学目录。')
    token = secrets.token_urlsafe(32)
    settings = Settings(yunyun_mode='pc', yunyun_workspace=args.workspace.resolve() if args.workspace else None,
                        desktop_gateway_url=args.gateway_url,
                        yunyun_local_token=SecretStr(token))
    if args.gateway_url:
        settings.llm_provider = 'bailian'
    tunnel = None
    with tempfile.TemporaryDirectory(prefix='yy-pc-', dir='/tmp') as temporary:
        try:
            if args.runner_ssh:
                ssh = ['ssh']
                runtime = PROJECT_ROOT / '.runtime'
                if (runtime / 'ssh_control').exists():
                    ssh += ['-S', str(runtime / 'ssh_control')]
                if (runtime / 'ssh_known_hosts').exists():
                    ssh += ['-o', 'UserKnownHostsFile=' + str(runtime / 'ssh_known_hosts')]
                response = subprocess.run([*ssh, args.runner_ssh, 'cat /opt/yunyun-tutor/runner.env'],
                                          capture_output=True, text=True)
                if response.returncode:
                    parser.error('私有执行器连接失败，请先在终端完成SSH登录。')
                runner_token = next((line.split('=', 1)[1] for line in response.stdout.splitlines()
                                     if line.startswith('RUNNER_TOKEN=')), '')
                if len(runner_token) < 32:
                    parser.error('私有执行器未配置有效鉴权。')
                socket = Path(temporary) / 'runner.sock'
                tunnel = subprocess.Popen([*ssh, '-o', 'ExitOnForwardFailure=yes', '-o',
                    'StreamLocalBindMask=0177', '-N', '-L', str(socket) +
                    ':/opt/yunyun-tutor/socket/runner.sock', args.runner_ssh])
                for _ in range(100):
                    if socket.exists():
                        break
                    if tunnel.poll() is not None:
                        parser.error('私有执行器转发失败。')
                    time.sleep(.1)
                else:
                    parser.error('私有执行器转发超时。')
                settings.runner_socket, settings.runner_token = socket, SecretStr(runner_token)
            app = create_app(settings)
            timer = None
            if not args.no_browser:
                url = f'http://127.0.0.1:{args.port}/#token={token}'
                timer = threading.Timer(1.0, lambda: webbrowser.open(url))
                timer.start()
            print('本机工作台已准备；正式文件写入须在界面确认Diff。', flush=True)
            try:
                uvicorn.run(app, host='127.0.0.1', port=args.port, access_log=False)
            finally:
                if timer:
                    timer.cancel()
        finally:
            if tunnel:
                tunnel.terminate()
                tunnel.wait(timeout=10)


if __name__ == '__main__':
    main()
