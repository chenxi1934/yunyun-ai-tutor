#!/bin/bash
# Finder双击时保留失败提示；终端执行也可使用相同参数。
project_dir="$(cd "$(dirname "$0")" && pwd)"
bash "$project_dir/scripts/start-easy.sh" "$@"
result=$?
if [[ "$result" -ne 0 && "$result" -ne 130 && -t 0 ]]; then
  read -r -p '启动未完成。按回车关闭，修正提示的问题后可再次双击。' _reply
fi
exit "$result"
