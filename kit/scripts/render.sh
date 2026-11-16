#!/bin/bash
set -euo pipefail
project="${1:-.}"
if [ "$#" -gt 0 ]; then shift; fi
cd "$project"
test -f episode.json || { echo '缺少 episode.json' >&2; exit 2; }
mkdir -p renders
stamp="$(date +%Y%m%d-%H%M%S)"
log="renders/render-$stamp.log"
export HYPERFRAMES_TELEMETRY_DISABLED=1 DO_NOT_TRACK=1
# 前台等待真实渲染进程；不通过进程名称猜测完成状态。
set +e
npm run render -- --output "renders/render-$stamp.mp4" "$@" 2>&1 | tee "$log"
result=${PIPESTATUS[0]}
set -e
if [ "$result" -ne 0 ]; then
  echo "渲染失败（退出码 ${result}）；日志：${log}" >&2
  exit "$result"
fi
test -s "renders/render-$stamp.mp4" || { echo "渲染返回成功但文件不存在；查看 $log" >&2; exit 1; }
echo "Render complete: $PWD/renders/render-$stamp.mp4"
