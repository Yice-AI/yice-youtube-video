import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';

export function probeVideo(file) {
  const data = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'stream=start_time,duration,width,height', '-of', 'json', file], { encoding: 'utf8' }));
  if (!data.streams?.length) throw new Error(`视频没有图像流: ${file}`);
  return data.streams[0];
}

// Stream-copy trims can leave the first decoded picture at a non-zero PTS.
// Browser preload cannot repair that timeline hole; prepare a zero-origin video.
export function prepareVideo(file, root) {
  const info = probeVideo(file), start = Number(info.start_time || 0);
  if (Math.abs(start) < 0.001) return { file, sourceStart: start, prepared: false };
  const key = createHash('sha256').update('zero-pts-v1').update(fs.readFileSync(file)).digest('hex').slice(0, 20);
  const out = path.join(root, 'assets/prepared', `${key}.mp4`);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (!fs.existsSync(out)) {
    const tmp = `${out}.tmp.mp4`;
    try {
      execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', file, '-map', '0:v:0', '-an',
        '-vf', 'setpts=PTS-STARTPTS', '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', tmp], { stdio: ['ignore', 'ignore', 'pipe'] });
      fs.renameSync(tmp, out);
    } finally { fs.rmSync(tmp, { force: true }); }
  }
  return { file: out, sourceStart: start, prepared: true };
}
