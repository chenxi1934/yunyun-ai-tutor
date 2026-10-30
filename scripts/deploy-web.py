"""部署到明确授权的Docker宿主；新增独立443入口，保留现有80服务。凭据仅走SSH stdin。"""
import argparse
import io
import secrets
import shlex
import subprocess
import tarfile
from pathlib import Path

from app.config import PROJECT_ROOT, Settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('target', help='SSH别名或user@host；先交互登录')
    parser.add_argument('--domain', required=True, help='已指向宿主的演示域名')
    args = parser.parse_args()
    if any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-.' for c in args.domain):
        parser.error('域名不合法')
    ssh = ['ssh', '-S', str(PROJECT_ROOT / '.runtime/ssh_control'), '-o',
           'UserKnownHostsFile=' + str(PROJECT_ROOT / '.runtime/ssh_known_hosts'), '-o', 'BatchMode=yes', args.target]
    def run(command, data=None, capture=False):
        return subprocess.run([*ssh, command], input=data, check=True,
                              stdout=subprocess.PIPE if capture else None)
    root = '/opt/yunyun-tutor'
    def write(path, content, mode=0o600):
        script = f"import os,sys; p={path!r}; f=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,{mode}); os.write(f,sys.stdin.buffer.read()); os.fchmod(f,{mode}); os.close(f)"
        run('python3 -c ' + shlex.quote(script), content.encode())
    run(f'mkdir -p {root}/source {root}/data {root}/socket')
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
        for name in ['pyproject.toml', 'backend', 'runner', 'Dockerfile', 'scripts', 'frontend']:
            archive.add(PROJECT_ROOT / name, arcname=name, filter=lambda x: None if any(
                part in {'node_modules', '__pycache__', '.env', '.runtime'} for part in Path(x.name).parts)
                or x.name.endswith(('.pyc', '.tsbuildinfo')) else x)
    run(f'tar xzf - -C {root}/source', buffer.getvalue())
    run(f'cd {root}/source && docker build -q --build-arg PYPI_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple -t yunyun-api:stage05 .')
    run(f'cd {root}/source && docker build -q -f runner/Dockerfile --build-arg PYPI_INDEX_URL=https://mirrors.cloud.tencent.com/pypi/simple -t yunyun-manager:stage05 .')
    # 更新API配置不输出Key；保留已有Runner token，避免重启后身份无故变化。
    existing = run(f'test -f {root}/runner.env && cat {root}/runner.env || true', capture=True).stdout.decode()
    token = next((line.split('=', 1)[1] for line in existing.splitlines() if line.startswith('RUNNER_TOKEN=')), secrets.token_hex(32))
    digest = run("docker image inspect --format '{{.Id}}' python:3.12-slim", capture=True).stdout.decode().strip()
    settings = Settings()
    if not settings.dashscope_api_key.get_secret_value():
        raise RuntimeError('请先配置本机百炼凭据；不会部署Mock冒充真实服务')
    write(root + '/runtime.env', '\n'.join([
        'DASHSCOPE_API_KEY=' + settings.dashscope_api_key.get_secret_value(),
        'DASHSCOPE_BASE_URL=' + settings.dashscope_base_url, 'LLM_MODEL=' + settings.llm_model,
        'LLM_PROVIDER=bailian', 'YUNYUN_MODE=web', 'YUNYUN_DATA_DIR=/data',
        'YUNYUN_HOSTS=' + args.domain + ',127.0.0.1,localhost', 'YUNYUN_SECURE_COOKIE=true',
        'RUNNER_SOCKET=/run/yunyun/runner.sock', 'RUNNER_TOKEN=' + token, '']))
    write(root + '/runner.env', f'RUNNER_IMAGE={digest}\nRUNNER_SOCKET=/run/yunyun/runner.sock\nRUNNER_TOKEN={token}\n')
    run(f'chown -R 10001:10001 {root}/data {root}/socket')
    gid = run('stat -c %g /var/run/docker.sock', capture=True).stdout.decode().strip()
    # 仅替换本项目命名容器，绝不操作其他服务。
    run('docker rm -f yunyun-stage05-api yunyun-stage05-manager 2>/dev/null || true')
    run(f'docker run -d --name yunyun-stage05-manager --restart unless-stopped --user 10001:10001 --group-add {gid} '
        f'--network none --read-only --cap-drop ALL --security-opt no-new-privileges --memory 256m --pids-limit 128 '
        f'--tmpfs /tmp:rw,nosuid,size=16m --env-file {root}/runner.env '
        f'-v /var/run/docker.sock:/var/run/docker.sock -v {root}/socket:/run/yunyun yunyun-manager:stage05')
    run(f'docker run -d --name yunyun-stage05-api --restart unless-stopped -p 127.0.0.1:18005:8000 '
        f'--read-only --cap-drop ALL --security-opt no-new-privileges --memory 512m --pids-limit 128 '
        f'--tmpfs /tmp:rw,nosuid,size=16m --env-file {root}/runtime.env '
        f'-v {root}/data:/data -v {root}/socket:/run/yunyun yunyun-api:stage05')
    subprocess.run([str(PROJECT_ROOT / '.venv/bin/python'), str(PROJECT_ROOT / 'scripts/configure-https.py'),
                    args.target, '--domain', args.domain], check=True)
    print('已部署；请实际检查HTTPS、隔离器和端到端，不将部署命令成功视为验收通过。')


if __name__ == '__main__':
    main()
