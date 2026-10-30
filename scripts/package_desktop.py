"""生成无凭据的macOS启动包；预构建界面不依赖收件人安装Node/npm。"""
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

from desktop_bootstrap import ROOT, frontend_manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.runtime/delivery/耘耘AI助教-macOS一键启动.zip')
    args = parser.parse_args()
    subprocess.run(['npm', '--prefix', str(ROOT / 'frontend'), 'run', 'build'], check=True)
    names = {'README.md', 'pyproject.toml', '.env.example', '一键启动.command',
             'scripts/start-easy.sh', 'scripts/start-desktop.sh', 'scripts/desktop_bootstrap.py'}
    for folder in ['backend/app', 'backend/seeds', 'frontend/src', 'frontend/dist', 'docs']:
        names.update(p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and not p.name.endswith('.pyc'))
    names.update('frontend/' + n for n in ['package.json', 'package-lock.json', 'index.html', 'vite.config.ts', 'tsconfig.json'])
    files = {name: (ROOT / name).read_bytes() for name in sorted(names)}
    assert not any(Path(n).name == '.env' or any(p in {'.runtime', '.git', '.venv', 'node_modules'}
                   for p in Path(n).parts) for n in files)
    for name, data in files.items():
        if re.search(rb'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|(?<!\w)sk-[A-Za-z0-9_-]{24,}', data):
            raise RuntimeError('启动包检测到疑似秘密，停止打包：' + name)
    prefix = '耘耘AI助教-macOS/'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            info = zipfile.ZipInfo(prefix + name)
            info.create_system = 3
            info.external_attr = (0o100755 if name.endswith(('.sh', '.command')) else 0o100644) << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED)
        archive.writestr(prefix + 'desktop-build.json', json.dumps(frontend_manifest(ROOT)))
    with zipfile.ZipFile(args.output) as archive:
        assert archive.testzip() is None
        assert all(hashlib.sha256(archive.read(prefix + n)).digest() == hashlib.sha256(b).digest()
                   for n, b in files.items())
    print('已生成启动包（不包含模型Key、SSH密码、Python环境或运行数据）：' + str(args.output))


if __name__ == '__main__':
    main()
