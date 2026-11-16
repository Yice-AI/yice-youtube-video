import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

export function transitionWindows(report, index) {
  const windows = [];
  for (const scene of report) {
    const sid = scene.id.replace(/[^\w-]/g, '_').toLowerCase();
    if (!index.includes(`id="host-${sid}"`) || !scene.media.some(m => m.video)) continue;
    if (scene.enter !== 'cut') windows.push({ scene: scene.id, videos: scene.videoDetails, start: Math.max(0, scene.B - .5), end: Math.min(scene.E, scene.B + .5) });
    if (scene.exit !== 'cut') windows.push({ scene: scene.id, videos: scene.videoDetails, start: Math.max(0, scene.E - .5), end: scene.E });
  }
  return windows;
}

export function blackFrames(file, start, duration, crop) {
  if (!Number.isFinite(start) || start < 0 || !Number.isFinite(duration) || duration <= 0) throw new Error('转场检查区间无效');
  const probe = spawnSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'json', file], { encoding: 'utf8' });
  if (probe.error || probe.status !== 0) throw new Error(probe.error?.message || probe.stderr);
  const available = Number(JSON.parse(probe.stdout).streams?.[0]?.duration);
  if (!Number.isFinite(available) || start + duration > available + 1 / 60) throw new Error('成片没有覆盖完整转场，不能判为通过');
  const region = crop ? `crop=${Math.floor(crop.width)}:${Math.floor(crop.height)}:${Math.ceil(crop.x)}:${Math.ceil(crop.y)},` : '';
  const p = spawnSync('ffmpeg', ['-hide_banner', '-ss', String(start), '-i', file, '-t', String(duration),
    '-vf', region + 'blackframe=amount=98:threshold=38', '-an', '-f', 'null', '-'], { encoding: 'utf8', maxBuffer: 16e6 });
  if (p.error || p.status !== 0) throw new Error(p.error?.message || p.stderr);
  return [...p.stderr.matchAll(/frame:(\d+)\s+pblack:(\d+)\s+pts:\S+\s+t:([\d.]+)/g)]
    .map(m => ({ frame: Number(m[1]), blackPercent: Number(m[2]), time: start + Number(m[3]) }));
}

// Snapshot supplies only the moving video rectangle. Pixel truth comes from the
// rendered MP4: browser preview and the render decoder need not fail alike.
function videoRegions(root, folder, id, times, cli) {
  fs.mkdirSync(folder, { recursive: true });
  const started = Date.now();
  const p = spawnSync(cli[0], [...cli.slice(1), 'snapshot', '--at', times.join(','), '--no-end',
    '--zoom', `#${id}`, '--zoom-scale', '1', '--output', folder],
  { cwd: root, encoding: 'utf8', maxBuffer: 24e6, env: { ...process.env, DO_NOT_TRACK: '1', HYPERFRAMES_TELEMETRY_DISABLED: '1' } });
  fs.writeFileSync(path.join(folder, 'snapshot.log'), `${p.stdout || ''}\n${p.stderr || ''}`);
  if (p.error || p.status !== 0) throw new Error(`无法定位转场视频 ${id}: ${p.error?.message || p.status}`);
  const state = JSON.parse(fs.readFileSync(path.join(root, '.hyperframes/video-state.json'), 'utf8'));
  const records = [];
  function collect(value) {
    if (!value || typeof value !== 'object') return;
    if (value.image && value.metadata?.crop && path.dirname(value.image) === folder && value.createdAt >= started) records.push(value);
    else for (const child of Object.values(value)) collect(child);
  }
  collect(state.snapshots);
  const latest = new Map();
  for (const row of records.sort((a, b) => a.createdAt - b.createdAt)) latest.set(row.time.toFixed(6), row);
  const regions = [...latest.values()].filter(r => times.some(t => Math.abs(t - r.time) < 1e-5))
    .map(r => ({ time: r.time, ...r.metadata.crop })).filter(r => r.width >= 2 && r.height >= 2);
  if (!regions.length) throw new Error(`转场内未找到可见视频区域: ${id}`);
  fs.writeFileSync(path.join(folder, 'regions.json'), JSON.stringify(regions, null, 2));
  return regions;
}

// Check rendered transition frames, not the sparse layout-audit seek grid.
// Passing a render lets delivery reuse the exact MP4; otherwise render each window.
export function checkTransitions(root, { rendered, renderedStart = 0, scenes, cli = ['npx', '--yes', 'hyperframes@0.9.52'] } = {}) {
  root = path.resolve(root);
  const report = JSON.parse(fs.readFileSync(path.join(root, 'build-report.json'), 'utf8'));
  const index = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
  for (const scene of report) {
    const sid = scene.id.replace(/[^\w-]/g, '_').toLowerCase();
    const html = fs.readFileSync(path.join(root, 'compositions/scenes', `${sid}.html`), 'utf8').replace(/<!--[\s\S]*?-->/g, '');
    scene.videoDetails = [...html.matchAll(/<video\b[^>]*>/g)].map(m => {
      const attr = key => m[0].match(new RegExp(`\\b${key}="([^"]+)"`))?.[1];
      return { id: attr('id'), start: scene.start + Number(attr('data-start') || 0), duration: Number(attr('data-duration') || scene.dur) };
    });
    if (/<video\b/.test(html) && !scene.media.some(m => m.video)) scene.media.push({ video: true });
  }
  const selected = scenes ? report.filter(s => scenes.includes(s.id)) : report;
  if (scenes?.some(id => !selected.some(s => s.id === id))) throw new Error('未知的 video-scenes 场景');
  const windows = transitionWindows(selected, index), findings = [];
  const dir = path.join(root, '.hyperframes/video-check');
  fs.mkdirSync(dir, { recursive: true });
  for (const [i, window] of windows.entries()) {
    const start = Math.floor(window.start * 30) / 30, end = Math.ceil(window.end * 30) / 30;
    let file = rendered, offset = renderedStart;
    if (!file) {
      file = path.join(dir, `${i}.mp4`); offset = start;
      const p = spawnSync(cli[0], [...cli.slice(1), 'render', '--fps', '30', '--quality', 'high',
        '--start', String(start), '--end', String(end), '--output', file],
      { cwd: root, encoding: 'utf8', maxBuffer: 24e6, env: { ...process.env, HYPERFRAMES_TELEMETRY_DISABLED: '1' } });
      fs.writeFileSync(path.join(dir, `${i}.log`), `${p.stdout || ''}\n${p.stderr || ''}`);
      if (p.error || p.status !== 0) throw new Error(`转场渲染失败: ${window.scene} (${p.error?.message || p.status})`);
    }
    if (start < offset) throw new Error(`成片未覆盖 ${window.scene} 的转场起点`);
    const times = Array.from({ length: Math.round((end - start) * 30) }, (_, f) => +(start + f / 30).toFixed(6));
    for (const video of window.videos) {
      const id = video.id, visibleTimes = times.filter(t => t >= video.start && t < video.start + video.duration);
      if (!visibleTimes.length) continue;
      const regions = videoRegions(root, path.join(dir, `regions-${i}-${id}`), id, visibleTimes, cli);
      const frames = [];
      if (regions.every(r => r.x === 0 && r.y === 0 && r.width === 1920 && r.height === 1080)) {
        frames.push(...blackFrames(file, start - offset, end - start).map(f => ({ ...f, time: +(f.time + offset).toFixed(6) })));
      } else for (const region of regions) {
        frames.push(...blackFrames(file, region.time - offset, 1 / 30, region).map(f => ({ ...f, time: region.time, region })));
      }
      if (frames.length) findings.push({ code: 'transition_video_no_picture', severity: 'error', scene: window.scene, video: id, start, end, frames });
    }
  }
  return { ok: findings.length === 0, windows: windows.length, findings };
}
