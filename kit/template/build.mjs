// 一策 HF build: beats.json + voice-timing.json -> compositions/scenes/*.html + index.html
// usage: node build.mjs [--only S0-1,S0-2] [--from 0 --to 30]
import fs from "node:fs";
import path from "node:path";
import { prepareVideo } from "./video.mjs";
import { mixAudio } from "./audio.mjs";
import { prepareVocab } from "./vocab-props.mjs";

import { fileURLToPath } from "node:url";
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const episode = JSON.parse(fs.readFileSync(path.join(ROOT, "episode.json"), "utf8"));
if (!episode.id || !episode.voiceDir || !episode.chapters) throw new Error("episode.json requires id, voiceDir and chapters");
const IP = path.resolve(ROOT, episode.assetBase || ".");
const voiceDir = path.resolve(ROOT, episode.voiceDir);
const ALIAS = Object.fromEntries(Object.entries(episode.mediaRoots || {}).map(([alias, dir]) => {
  if (!alias.endsWith("/")) throw new Error(`mediaRoots alias must end with /: ${alias}`);
  return [alias, path.resolve(ROOT, dir) + path.sep];
}));
ALIAS["@vo/"] = voiceDir + path.sep;
const OV = 0.5, LEAD = 0.2;
const args = process.argv.slice(2);
const argv = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };

const beats = JSON.parse(fs.readFileSync(path.join(ROOT, "beats.json"), "utf8"));
const timing = JSON.parse(fs.readFileSync(path.join(voiceDir, "voice-timing.json"), "utf8"));
const manifest = JSON.parse(fs.readFileSync(path.join(voiceDir, "voice-manifest.json"), "utf8"));
const S = Object.fromEntries(timing.map((t) => [t.id, t]));

function resolveFile(spec) {
  const cands = Array.isArray(spec) ? spec : [spec];
  for (let i = 0; i < cands.length; i++) {
    let p = cands[i];
    for (const [a, d] of Object.entries(ALIAS)) if (p.startsWith(a)) p = d + p.slice(a.length);
    p = path.resolve(ROOT, p);
    if (p.includes("*")) { // simple glob on basename
      const dir = path.dirname(p), re = new RegExp("^" + path.basename(p).replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*") + "$");
      if (fs.existsSync(dir)) { const hit = fs.readdirSync(dir).filter((f) => re.test(f)).sort()[0]; if (hit) return { file: path.join(dir, hit), idx: i, cand: cands[i] }; }
      continue;
    }
    if (fs.existsSync(p)) return { file: p, idx: i, cand: cands[i] };
  }
  return null;
}
const copied = new Map();
fs.rmSync(path.join(ROOT, "assets/media"), { recursive: true, force: true });
function useAsset(abs) {
  if (copied.has(abs)) return copied.get(abs);
  if (abs.startsWith(path.join(ROOT, "assets") + path.sep)) { const u = path.relative(ROOT, abs); copied.set(abs, u); return u; }
  const rel = path.relative(IP, abs).replace(/[\/\\]/g, "__").replace(/[^\w.\-]/g, "_");
  const short = rel.length > 90 ? rel.slice(-90) : rel;
  const out = path.join(ROOT, "assets/media", short);
  fs.mkdirSync(path.dirname(out), { recursive: true });
  if (!fs.existsSync(out) || fs.statSync(out).size !== fs.statSync(abs).size) fs.copyFileSync(abs, out);
  const url = "assets/media/" + short; copied.set(abs, url); return url;
}

// ---- scene boundaries ----
const scenes = beats.scenes;
scenes.forEach((sc, i) => {
  const first = S[sc.sents[0]];
  if (!first) throw new Error("unknown sentence " + sc.sents[0]);
  sc.B = i === 0 ? 0 : +(first.firstCharTime - LEAD).toFixed(3);
});
const END = episode.end ?? beats.end;
if (!Number.isFinite(END) || END <= 0) throw new Error("episode.end must be a positive number");
scenes.forEach((sc, i) => {
  sc.E = i + 1 < scenes.length ? scenes[i + 1].B : END;
  sc.enter = sc.enter || "cut";
  sc.exit = i + 1 < scenes.length && scenes[i + 1].enter && scenes[i + 1].enter !== "cut" ? scenes[i + 1].enter : "cut";
  sc.start = +(sc.B - (sc.enter !== "cut" && i > 0 ? OV : 0)).toFixed(3);
  sc.dur = +(sc.E - sc.start).toFixed(3);
});

function anchorTime(sc, v) {
  if (typeof v === "number") return sc.B + v; // seconds after the boundary
  if (typeof v !== "string") return v;
  if (v.startsWith("+")) return sc.B + parseFloat(v.slice(1));
  if (v.startsWith("@")) {
    let [ph, nth] = v.slice(1).split("#"); nth = +(nth || 1);
    let k = 0;
    for (const id of sc.sents) for (const a of S[id].anchors) if (a.phrase === ph && ++k === nth) return a.time;
    throw new Error(`${sc.id}: anchor ${v} not found`);
  }
  if (v.startsWith("first:")) return S[v.slice(6)].firstCharTime;
  return v;
}
function localize(sc, o) {
  if (Array.isArray(o)) return o.map((x) => localize(sc, x));
  if (o && typeof o === "object") {
    const r = {};
    for (const [k, v] of Object.entries(o)) r[k] = (k === "at" || k === "strike" || k === "markAt") ? +(anchorTime(sc, v) - sc.start).toFixed(3) : localize(sc, v);
    return r;
  }
  return o;
}

const chapterOf = (sc) => {
  const id = sc.sents[0], base = id.split('.')[0];
  const declared = manifest.chapters.find(c => (c.scenes || []).some(s => s === id || s === base));
  if (declared) return declared;
  const prefix = id.match(/^(\d+)-/);
  const byId = prefix && manifest.chapters.find(c => Number(c.id) === Number(prefix[1]));
  if (byId) return byId;
  const first = S[id].firstCharTime;
  return manifest.chapters.find(c => first >= c.start && first < c.end);
};
const only = argv("--only") ? new Set(argv("--only").split(",")) : null;
const report = [];
fs.mkdirSync(path.join(ROOT, "compositions/scenes"), { recursive: true });

const hostClips = [];
scenes.forEach((sc, i) => {
  const tpl = fs.readFileSync(path.join(ROOT, "recipes", sc.recipe + ".html"), "utf8");
  const sid = sc.id.replace(/[^\w-]/g, "_").toLowerCase();
  const ch = chapterOf(sc);
  if (!ch || !episode.chapters[ch.id]) throw new Error(`${sc.id}: chapter missing from voice-manifest or episode.json`);
  if (typeof sc.props?.cursorLog === 'string') {
    const file=resolveFile(sc.props.cursorLog);
    if(!file)throw new Error(`${sc.id}: cursorLog 文件不存在`);
    const log=JSON.parse(fs.readFileSync(file.file,'utf8'));
    sc.props.cursorLog=Array.isArray(log)?log:log.points;
  }
  const vocabulary=prepareVocab({...sc,stage:sc.stage||sc.props?.stage||episode.chapters[ch.id].stage});
  sc.media=vocabulary.media;
  // media
  const mediaHtml = [], used = [];
  (sc.media || []).forEach((m, mi) => {
    const r = resolveFile(m.src);
    if (!r) throw new Error(`${sc.id}: no media for ${JSON.stringify(m.src)}`);
    const isVid = /\.(mp4|mov|webm)$/i.test(r.file);
    const prepared = isVid ? prepareVideo(r.file, ROOT) : { file: r.file };
    const url = useAsset(prepared.file);
    used.push({ cand: r.cand, fallback: r.idx > 0 && !m.optionalFirst ? true : r.idx > 0, idx: r.idx, kind: m.kind,
      ...(isVid ? { video: true, url, sourceStart: prepared.sourceStart, prepared: prepared.prepared } : {}) });
    if (isVid) mediaHtml.push(`<video id="${sid}-m${mi}" src="${url}" muted playsinline preload="auto" data-start="${(m.at || 0)}" data-duration="${sc.dur}"${m.start ? ` data-media-start="${m.start}"` : ""}${m.rate ? ` data-playback-rate="${m.rate}"` : ""}></video>`);
    else mediaHtml.push(`<img id="${sid}-m${mi}" src="${url}" alt="" />`);
  });
  // a scene can declare alternate spec overrides used when its preferred media fell back
  let specSrc = { ...sc.spec };
  if(vocabulary.props) specSrc.props=vocabulary.props;
  if(sc.layers)specSrc.layers=sc.layers;
  if (used.some((u) => u.idx > 0) && sc.fallbackSpec) specSrc = { ...specSrc, ...sc.fallbackSpec };
  const loc = localize(sc, specSrc), lb = sc.B - sc.start;
  for (const k of ["word", "title", "lead"]) if (loc[k] && typeof loc[k].at === "number" && loc[k].at > lb + 0.9) loc[k].at = +(lb + 0.9).toFixed(3);
  if (sc.recipe === "single-line" && typeof loc.at === "number" && loc.at > lb + 0.9) loc.at = +(lb + 0.9).toFixed(3);
  const spec = {
    ...loc,
    id: sc.id, sid, t0: sc.start, dur: sc.dur, enter: i === 0 ? "cut" : sc.enter, exit: sc.exit,
    stage: sc.stage || sc.props?.stage || episode.chapters[ch.id].stage, chapter: ch.id, chapterTitle: episode.chapters[ch.id].title, episodeId: episode.id,
    mediaFallback: used.map((u) => u.idx > 0),
  };
  const html = tpl.replaceAll("__SID__", sid).replace("__MEDIA__", mediaHtml.join("\n")).replace("__SPEC__", JSON.stringify(spec).replace(/</g, "\\u003c"));
  fs.writeFileSync(path.join(ROOT, "compositions/scenes", sid + ".html"), html);
  let z = 10 + i * 2; if (sc.exit === "lift") z = 10 + (i + 1) * 2 + 1;
  hostClips.push({ sid, start: sc.start, dur: sc.dur, z, sc });
  report.push({ id: sc.id, recipe: sc.recipe, chapter: ch.id, start: sc.start, B: sc.B, E: sc.E, dur: sc.dur, enter: spec.enter, exit: sc.exit, media: used });
});

const from = +(argv("--from") ?? 0), to = argv("--to") != null ? +argv("--to") : END;
const sel = hostClips.filter((h) => (!only || only.has(h.sc.id)) && h.start < to && h.start + h.dur > from);
const offset = from;
const total = +(Math.min(to, END) - from).toFixed(3);
const audioSetting = argv("--audio") || episode.audio;
const audioConfig = typeof audioSetting === "string" ? JSON.parse(fs.readFileSync(path.resolve(ROOT, audioSetting), "utf8")) : audioSetting;
const master = audioConfig ? mixAudio({ root: ROOT, config: audioConfig, manifest, timing, scenes, end: END, voiceDir,
  resolve: src => { const file = resolveFile(src); if (!file) throw new Error(`音频素材不存在: ${src}`); return file.file; },
  events: (audioConfig.events || []).map(e => {
    const scene = scenes.find(s => s.id === e.scene);
    if (e.scene && !scene) throw new Error(`音效引用未知场景: ${e.scene}`);
    return { ...e, time: scene ? anchorTime(scene, e.at) : e.at };
  }),
}) : null;
const audio = master ? [`    <audio id="master" src="${useAsset(master)}" data-start="0" data-duration="${total}" data-media-start="${from}" data-track-index="1" data-volume="1"></audio>`] : manifest.chapters.filter((c) => c.start < to && c.end > from).map((c) => {
  const url = useAsset(path.resolve(voiceDir, c.path));
  const st = c.start - offset, ms = st < 0 ? -st : 0;
  return `    <audio id="vo-${c.id}" src="${url}" data-start="${Math.max(0, st).toFixed(3)}" data-duration="${(c.end - c.start - ms).toFixed(3)}"${ms ? ` data-media-start="${ms.toFixed(3)}"` : ""} data-track-index="1" data-volume="1"></audio>`;
});
const clipsHtml = sel.map((h) => {
  const st = h.start - offset, cut = st < 0 ? -st : 0;
  return `    <div id="host-${h.sid}" data-composition-id="${h.sid}" data-composition-src="compositions/scenes/${h.sid}.html" data-start="${Math.max(0, st).toFixed(3)}" data-duration="${(h.dur - cut).toFixed(3)}" data-track-index="${2 + (sel.indexOf(h) % 2)}" data-width="1920" data-height="1080" style="position:absolute;inset:0;z-index:${h.z}"></div>`;
});
const index = `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <title>一策 ${String(episode.id).replace(/[<>&\"]/g, "")} · HF</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <link rel="stylesheet" href="assets/frame.css" />
    <script src="assets/yice.js"></script>
    <link rel="stylesheet" href="assets/vocab.css" />
    <script src="assets/vocab.js"></script>
    <style>
      html, body { margin: 0; background: #141416; }
      #root { position: relative; width: 100%; height: 100%; overflow: hidden; background: #141416; }
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-width="1920" data-height="1080" data-duration="${total}">
${audio.join("\n")}
${clipsHtml.join("\n")}
    </div>
    <script>
      window.__timelines["main"] = gsap.timeline({ paused: true });
    </script>
  </body>
</html>
`;
fs.writeFileSync(path.join(ROOT, "index.html"), index);
fs.writeFileSync(path.join(ROOT, "build-report.json"), JSON.stringify(report, null, 1));
console.log(`scenes ${scenes.length}, in index ${sel.length}, duration ${total}s, assets ${copied.size}`);
const fb = report.filter((r) => r.media.some((m) => m.idx > 0)).map((r) => r.id);
if (fb.length) console.log("fallback media in:", fb.join(" "));
