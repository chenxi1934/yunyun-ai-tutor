#!/bin/bash
set -euo pipefail
umask 077
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
for argument in "$@"; do
  if [[ "$argument" == --help || "$argument" == -h ]]; then
    echo '用法：bash scripts/start-easy.sh [--port 8000] [--no-browser] [--check]'
    echo '自动准备项目环境；浏览器选择教学目录即可使用演示服务，无需Key/SSH。Ctrl+C退出。'
    echo '高级独立模式：--standalone --workspace 教学目录 --runner-ssh user@host'
    exit 0
  fi
done
if [[ "$(uname -s)" != Darwin ]]; then
  echo '此一键入口目前支持macOS；其他平台请使用README中的开发启动方式。' >&2
  exit 2
fi
bootstrap_dir="$project_dir/.runtime/bootstrap"
mkdir -p "$bootstrap_dir"
trap 'echo "准备未完成：请检查网络后重试；已下载内容会复用，不会清空教学文件。" >&2' ERR
export YUNYUN_PROJECT_ROOT="$project_dir"
export UV_CACHE_DIR="$bootstrap_dir/cache"
export UV_PYTHON_INSTALL_DIR="$bootstrap_dir/python"
export UV_NO_MODIFY_PATH=1
# 只影响当前启动进程：不继承其他项目的包镜像或关闭TLS校验设置。
unset UV_INDEX UV_EXTRA_INDEX_URL UV_DEFAULT_INDEX UV_INDEX_URL UV_FIND_LINKS
unset PIP_INDEX_URL PIP_EXTRA_INDEX_URL PIP_FIND_LINKS PIP_TRUSTED_HOST UV_INSECURE_HOST
unset UV_ASTRAL_MIRROR_URL UV_PYTHON_INSTALL_MIRROR UV_PYTHON_DOWNLOADS_JSON_URL
unset UV_INSTALLER_GITHUB_BASE_URL UV_INSTALLER_GHE_BASE_URL UV_DOWNLOAD_URL
if [[ -x "$bootstrap_dir/bin/uv" ]]; then
  uv_bin="$bootstrap_dir/bin/uv"
elif command -v uv >/dev/null 2>&1; then
  uv_bin="$(command -v uv)"
else
  echo '首次准备：从Astral官方来源下载uv到本项目目录，不修改系统PATH。'
  installer="$bootstrap_dir/uv-installer.sh"
  curl --fail --location --proto '=https' --tlsv1.2 --retry 2 \
    'https://astral.sh/uv/0.13.6/install.sh' -o "$installer"
  UV_UNMANAGED_INSTALL="$bootstrap_dir/bin" sh "$installer"
  uv_bin="$bootstrap_dir/bin/uv"
fi
if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import sys; assert sys.version_info[:2] == (3,12)' >/dev/null 2>&1; then
  if [[ -e .venv ]]; then
    echo '现有.venv不是可用的Python3.12环境；请先将它改名保留，再重试。不会自动删除。' >&2
    exit 2
  fi
  echo '准备项目专用Python3.12（缺少时自动下载），不安装到系统。'
  "$uv_bin" venv --no-config --system-certs --no-project --python 3.12 "$project_dir/.venv"
fi
dependency_hash="$(shasum -a 256 pyproject.toml | awk '{print $1}')"
if [[ ! -f "$bootstrap_dir/dependencies.sha256" ]] || \
   [[ "$(cat "$bootstrap_dir/dependencies.sha256")" != "$dependency_hash" ]] || \
   ! .venv/bin/python -c 'import app.api' >/dev/null 2>&1; then
  echo '安装项目依赖到.venv（官方PyPI）；首次需要联网。'
  "$uv_bin" pip install --no-config --system-certs --python .venv/bin/python \
    --index-url https://pypi.org/simple --editable .
  "$uv_bin" pip check --no-config --python .venv/bin/python
  printf '%s\n' "$dependency_hash" > "$bootstrap_dir/dependencies.sha256"
fi
trap - ERR
exec .venv/bin/python scripts/desktop_bootstrap.py "$@"
