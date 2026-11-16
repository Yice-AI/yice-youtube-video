import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { checkTransitions } from './check-video.mjs';

const root = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2), json = args.includes('--json'), video = {};
for (const [flag, key] of [['--rendered', 'rendered'], ['--rendered-start', 'renderedStart'], ['--video-scenes', 'scenes']]) {
  const i = args.indexOf(flag);
  if (i >= 0) {
    if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`${flag} 缺少参数`);
    video[key] = key === 'rendered' ? path.resolve(args[i + 1]) : key === 'scenes' ? args[i + 1].split(',') : Number(args[i + 1]);
    args.splice(i, 2);
  }
}
const p = spawnSync('npx', ['--yes', 'hyperframes@0.9.52', 'check', ...args.filter(a => a !== '--json'), '--json'],
  { cwd: root, encoding: 'utf8', maxBuffer: 32e6, env: { ...process.env, HYPERFRAMES_TELEMETRY_DISABLED: '1' } });
if (p.stderr) process.stderr.write(p.stderr);
let result;
try { result = JSON.parse(p.stdout); }
catch { result = { ok: false, error: p.error?.message || p.stdout || 'HyperFrames 检查未返回 JSON' }; }
try { result.videoTransitions = checkTransitions(root, video); }
catch (e) { result.videoTransitions = { ok: false, findings: [{ severity: 'error', code: 'transition_check_failed', message: e.message }] }; }
result.ok = p.status === 0 && result.ok !== false && result.videoTransitions.ok;
fs.writeFileSync(path.join(root, 'check-report.json'), JSON.stringify(result, null, 2));
console.log(json ? JSON.stringify(result) : `检查${result.ok ? '通过' : '失败'}；转场视频 ${result.videoTransitions.ok ? '通过' : '有 error'}。详情：check-report.json`);
process.exitCode = result.ok ? 0 : 1;
