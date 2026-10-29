#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv/bin/python || ! -f frontend/dist/index.html ]]; then
  echo '请先按 README.md 安装 Python 依赖并构建前端。' >&2
  exit 1
fi
exec .venv/bin/python -m app.launch "$@"
