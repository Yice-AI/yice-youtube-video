#!/bin/bash
# 等下一条录屏任务：<收件箱>/tasks/ 里出现还没有对应 done/<名>.md 的任务文件，就打印它的路径并退出。
# 最多等 50 分钟；超时打印 NO_TASK，调用方再调一次即可。
B="${1:?用法: dsh-wait-next.sh <收件箱目录>}"
mkdir -p "$B/tasks" "$B/done"
for _ in $(seq 1 600); do
  for f in "$B"/tasks/task-*.md; do
    [ -e "$f" ] || continue
    n="$(basename "$f" .md)"
    [ -f "$B/done/$n.md" ] || { echo "NEW_TASK $f"; exit 0; }
  done
  sleep 5
done
echo NO_TASK
