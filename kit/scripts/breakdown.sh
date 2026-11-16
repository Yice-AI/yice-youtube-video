#!/bin/bash
# 参考片拆解：镜头切点统计 + 分段缩略图墙
# 用法: breakdown.sh <视频> <输出目录> [窗口起点秒=60] [窗口长度秒=180]
set -euo pipefail
IN="$1"; OUT="$2"; SS="${3:-60}"; LEN="${4:-180}"
mkdir -p "$OUT"
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$IN")
# 1) 全片镜头切点（场景变化 > 0.3），低分辨率加速
ffmpeg -v info -i "$IN" -vf "scale=320:-1,select='gt(scene,0.3)',showinfo" -an -f null - 2>&1 \
  | grep -o 'pts_time:[0-9.]*' | cut -d: -f2 > "$OUT/cuts.txt" || true
N=$(wc -l < "$OUT/cuts.txt" | tr -d ' ')
python3 - "$OUT/cuts.txt" "$DUR" "$N" > "$OUT/cuts-summary.txt" <<'EOF'
import sys
ts=[float(x) for x in open(sys.argv[1]) if x.strip()]; dur=float(sys.argv[2])
gaps=[b-a for a,b in zip([0]+ts, ts+[dur])]
gaps.sort()
med=gaps[len(gaps)//2] if gaps else dur
print(f"时长 {dur:.0f}s，硬切 {len(ts)} 次，平均镜头 {dur/max(1,len(ts)+1):.1f}s，中位镜头 {med:.1f}s")
for i in range(0,int(dur),60):
    c=sum(1 for t in ts if i<=t<i+60); print(f"  {i//60:02d}:00-{i//60:02d}:59  切 {c} 次")
EOF
# 2) 窗口内每 2 秒一帧，拼成 6x5 墙（每张 60 秒）
for ((k=0; k<LEN; k+=60)); do
  ffmpeg -v error -y -ss $((SS+k)) -t 60 -i "$IN" -vf "fps=1/2,scale=384:-1,tile=6x5" -frames:v 1 "$OUT/wall-$((SS+k))s.jpg"
done
# 3) 开头 30 秒每秒一帧（钩子怎么做）
ffmpeg -v error -y -t 30 -i "$IN" -vf "fps=1,scale=384:-1,tile=6x5" -frames:v 1 "$OUT/hook-0-30s.jpg"
cat "$OUT/cuts-summary.txt"
