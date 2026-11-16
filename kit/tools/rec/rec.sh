#!/bin/bash
set -euo pipefail
# Native capture: no -C (cursor), no -k (clicks), no -g (microphone), no rescaling.
if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo 'usage: rec.sh <seconds> <out.mov> [x,y,w,h]' >&2
  exit 2
fi
rec_seconds=$1
rec_out=$2
rec_region=${3-}
rec_dir=$(cd -- "$(dirname -- "$0")" && pwd)
python3 - "$rec_seconds" "$rec_region" <<'PY'
import sys
s=float(sys.argv[1]);assert 0<s<=3600,'seconds must be in (0,3600]'
if sys.argv[2]:
 r=[float(x) for x in sys.argv[2].split(',')];assert len(r)==4 and r[2]>0 and r[3]>0,'invalid region'
PY
if [[ -e "$rec_out" || -e "${rec_out%.*}.cursor.json" ]]; then
  echo 'refusing to overwrite an existing recording or cursor log' >&2
  exit 2
fi
mkdir -p -- "$(dirname -- "$rec_out")"
if [[ ! -x "$rec_dir/cursorlog" || "$rec_dir/cursorlog.swift" -nt "$rec_dir/cursorlog" ]]; then
  xcrun swiftc -O "$rec_dir/cursorlog.swift" -o "$rec_dir/cursorlog"
fi
rec_epoch=$(python3 -c 'import time;print(time.time())')
"$rec_dir/cursorlog" "$rec_seconds" "${rec_out%.*}.cursor.json" "$rec_epoch" "$rec_region" &
rec_logger=$!
trap 'kill "$rec_logger" 2>/dev/null || true' EXIT INT TERM
rec_args=(-v -V "$rec_seconds" -x)
if [[ -n "$rec_region" ]]; then rec_args+=(-R "$rec_region"); fi
set +e
/usr/sbin/screencapture "${rec_args[@]}" "$rec_out" 2>"${rec_out%.*}.capture.log"
rec_code=$?
set -e
wait "$rec_logger" || true
trap - EXIT INT TERM
python3 - "$rec_out" "$rec_epoch" "$rec_code" "$rec_region" <<'PY'
import json,pathlib,sys,subprocess
p=pathlib.Path(sys.argv[1]);d={'recorder':'macOS screencapture -v','cursor_baked_in':False,'native_pixels_requested':True,'launch_epoch':float(sys.argv[2]),'exit_code':int(sys.argv[3]),'region_points':sys.argv[4],'exists':p.exists(),'bytes':p.stat().st_size if p.exists() else 0,'first_frame_timestamp_available':False}
if p.exists() and p.stat().st_size:
 try:
  info=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,duration,r_frame_rate,nb_frames','-of','json',str(p)]))['streams'][0]
  d['video']=info
  if sys.argv[4]: d['observed_pixels_per_point']=info['width']/float(sys.argv[4].split(',')[2])
 except Exception as e:d['probe_error']=type(e).__name__
p.with_suffix('.capture.json').write_text(json.dumps(d,indent=2)+'\n')
print(json.dumps(d))
PY
exit "$rec_code"
