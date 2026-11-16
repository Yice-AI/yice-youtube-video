import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';

export const AUDIO_DEFAULTS = Object.freeze({
  crossfade_s: .6, final_fade_s: 3, bgm_below_voice_db: 24, gap_rise_db: 4,
  attack_s: .1, release_s: .6, dense_extra_db: -3, bgm_trim_db: .6,
  sfx_normal_below_voice_db: 18, sfx_key_below_voice_db: 12, sfx_lead_s: 2 / 30,
  sfx_trim_norm_db: -1, sfx_trim_key_db: -2.3,
  master: { lufs: -14, truepeak_ceiling_db: -1, gain_db: -.59 },
});
const SR = 48000, db = x => 10 ** (x / 20);
function run(args, input) {
  return execFileSync('ffmpeg', ['-hide_banner', '-nostdin', ...args], { input, maxBuffer: 512 * 1024 * 1024 });
}
function decode(file) {
  const buf = run(['-v', 'error', '-i', file, '-f', 'f32le', '-ac', '2', '-ar', String(SR), 'pipe:1']);
  return new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
}
function save(file, data) {
  run(['-v', 'error', '-y', '-f', 'f32le', '-ac', '2', '-ar', String(SR), '-i', 'pipe:0', '-c:a', 'pcm_f32le', file], Buffer.from(data.buffer));
}
// spawnSync exposes loudnorm's stderr without logging the entire audio probe.
import { spawnSync } from 'node:child_process';
export function measure(file, lufs = -14, peak = -1) {
  const p = spawnSync('ffmpeg', ['-hide_banner', '-i', file, '-af',
    `apad=whole_dur=0.4,loudnorm=I=${lufs}:TP=${peak}:LRA=11:print_format=json`, '-f', 'null', '-'], { encoding: 'utf8' });
  if (p.error || p.status !== 0) throw new Error(p.error?.message || p.stderr);
  return JSON.parse(p.stderr.slice(p.stderr.lastIndexOf('{'), p.stderr.lastIndexOf('}') + 1));
}
function add(dst, src, seconds, gain = 1) {
  const start = Math.round(seconds * SR) * 2;
  for (let i = Math.max(0, -start); i < src.length && i + start < dst.length; i++) dst[i + start] += src[i] * gain;
}
function positive(config, names) {
  for (const name of names) if (!Number.isFinite(config[name]) || config[name] <= 0) throw new Error(`音频 ${name} 必须大于 0`);
}

export function mixAudio({ root, config, manifest, timing, scenes, end, voiceDir, resolve, events }) {
  const c = { ...AUDIO_DEFAULTS, ...config, master: { ...AUDIO_DEFAULTS.master, ...config.master } };
  positive(c, ['crossfade_s', 'final_fade_s', 'attack_s', 'release_s']);
  const dir = path.join(root, 'assets/audio'); fs.mkdirSync(dir, { recursive: true });
  const count = Math.round(end * SR) * 2;
  const voice = new Float32Array(count), music = new Float32Array(count), sfx = new Float32Array(count);
  for (const ch of manifest.chapters) add(voice, decode(path.resolve(voiceDir, ch.path)), ch.start, db(c.voice_gain_db || 0));
  const voiceFile = path.join(dir, 'voice-stem.wav'); save(voiceFile, voice);
  const measuredVoice = Number(measure(voiceFile).input_i), voiceLufs = c.voice_lufs ?? measuredVoice;
  if (!Number.isFinite(voiceLufs)) throw new Error('旁白是静音，无法确定音乐和音效的相对音量');
  const chapters = manifest.chapters;
  const segments = c.segments || { A: [0, chapters[1]?.start], B: [chapters[1]?.start, chapters.at(-1).start], C: [chapters.at(-1).start, end] };
  const levels = {}, speech = timing.map(t => [Math.max(0, t.firstCharTime - .04), t.end]);
  const dense = scenes.filter(s => s.recipe === 'rec-zoom').map(s => [s.B, s.E]);
  if (c.bgm) {
    let prior = 0;
    for (const key of ['A', 'B', 'C']) {
      const [a, b] = segments[key] || [];
      if (![a, b].every(Number.isFinite) || a !== prior || b <= a || b > end || !c.bgm[key])
        throw new Error(`BGM ${key} 需要连续有效的 A/B/C 分段和素材；短片可显式指定 segments`);
      prior = b;
      const file = resolve(c.bgm[key]), data = decode(file), finish = Math.min(end, b + (key === 'C' ? 0 : c.crossfade_s));
      const n = Math.round((finish - a) * SR), start = Math.round(a * SR);
      if (data.length < n * 2) throw new Error(`BGM ${key} 长度不足，需要 ${finish - a} 秒`);
      const inputLufs = c.bgm_lufs?.[key] ?? Number(measure(file).input_i);
      if (!Number.isFinite(inputLufs)) throw new Error(`BGM ${key} 是静音`);
      const gain = db(voiceLufs - c.bgm_below_voice_db - inputLufs + c.gap_rise_db + c.bgm_trim_db);
      levels[key] = { gain, inputLufs, start: a, end: b };
      for (let i = 0; i < n; i++) {
        const t = i / SR;
        let env = key === 'A' ? 1 : Math.sin(Math.min(1, t / c.crossfade_s) * Math.PI / 2);
        env *= key === 'C' ? Math.max(0, Math.min(1, (b - a - t) / c.final_fade_s))
          : Math.cos(Math.max(0, Math.min(1, (t - (b - a)) / c.crossfade_s)) * Math.PI / 2);
        music[(start + i) * 2] += data[i * 2] * gain * env;
        music[(start + i) * 2 + 1] += data[i * 2 + 1] * gain * env;
      }
    }
    if (prior !== end) throw new Error('BGM C 段必须延伸到 episode.end');
    const dt = .02, low = db(-c.gap_rise_db), down = (1 - low) / c.attack_s, up = (1 - low) / c.release_s;
    const envelope = []; let value = 1;
    for (let t = 0; t <= end + dt; t += dt) {
      const speaking = speech.some(([a, b]) => a <= t + c.attack_s && t + c.attack_s <= b);
      let factor = 1;
      for (const [a, b] of dense) {
        const e = Math.max(0, Math.min(1, (t - (a - .5)) / .5, ((b + .5) - t) / .5));
        factor = Math.min(factor, 1 - e * (1 - db(c.dense_extra_db)));
      }
      const target = (speaking ? low : 1) * factor;
      value = value > target ? Math.max(target, value - down * dt) : Math.min(target, value + up * dt);
      envelope.push(value);
    }
    for (let i = 0; i < count / 2; i++) {
      const pos = i / SR / dt, lo = Math.floor(pos), f = pos - lo;
      const gain = envelope[lo] * (1 - f) + envelope[lo + 1] * f;
      music[i * 2] *= gain; music[i * 2 + 1] *= gain;
    }
  }
  const placed = [];
  for (const event of events || []) {
    if (!Number.isFinite(event.time) || event.time < 0 || event.time >= end) throw new Error(`音效时间超出 episode.end: ${event.name}`);
    const file = resolve(event.src || c.sfx_files?.[event.name] || path.join(c.sfx_dir || '', `${event.name}.wav`));
    const key = event.key ?? ['stamp', 'counter'].includes(event.name);
    const inputLufs = c.sfx_file_lufs ?? Number(measure(file).input_i);
    if (!Number.isFinite(inputLufs)) throw new Error(`音效 ${event.name} 是静音`);
    const gain = db(voiceLufs - (key ? c.sfx_key_below_voice_db : c.sfx_normal_below_voice_db) - inputLufs + (key ? c.sfx_trim_key_db : c.sfx_trim_norm_db));
    const start = Math.max(0, event.time - c.sfx_lead_s);
    add(sfx, decode(file), start, gain); placed.push({ ...event, start, key, gain, inputLufs });
  }
  save(path.join(dir, 'music-stem.wav'), music); save(path.join(dir, 'sfx-stem.wav'), sfx);
  for (let i = 0; i < count; i++) voice[i] = (voice[i] + music[i] + sfx[i]) * db(c.master.gain_db);
  const premaster = path.join(dir, 'premaster.wav'); save(premaster, voice);
  const m = measure(premaster, c.master.lufs, c.master.truepeak_ceiling_db);
  const filter = `loudnorm=I=${c.master.lufs}:TP=${c.master.truepeak_ceiling_db}:LRA=11:measured_I=${m.input_i}:measured_TP=${m.input_tp}:measured_LRA=${m.input_lra}:measured_thresh=${m.input_thresh}:offset=${m.target_offset}:linear=true,aresample=${SR},apad,atrim=end_sample=${count / 2}`;
  const output = path.join(dir, 'master.wav');
  run(['-v', 'error', '-y', '-i', premaster, '-af', filter, '-ar', String(SR), '-c:a', 'pcm_s24le', output]);
  const report = { config: c, duration: end, sampleRate: SR, samples: count / 2, voiceLufs, segments: c.bgm ? segments : null, levels, events: placed, loudness: measure(output, c.master.lufs, c.master.truepeak_ceiling_db) };
  fs.writeFileSync(path.join(root, 'audio-report.json'), JSON.stringify(report, null, 2));
  return output;
}
