// 镜头表的单调度检查；不读取/改写成片，也不把转场重叠重复计时。
import fs from 'node:fs';
import path from 'node:path';
import { RECORDING_CONTAINERS, prepareVocab, vocabLayout } from './vocab-props.mjs';

export const SOURCE_TYPES = ['recording', 'code_animation', 'third_party', 'web_capture', 'image2'];
export const DEFAULT_VISUAL_LIMITS = Object.freeze({
  maxBareRecordingSeconds: 20, minNonRecordingRatio: 0.4, minSourceTypes: 3,
  maxRecipeUses: 4, minTransitionKinds: 3, maxPreviousRecipeOverlap: 0.7, minNewRecipes: 1,
  minRecordingContainerKinds: 2,
  minTitleFreeRatio: 0.4, maxConsecutiveLayout: 3,
});
const EPS = 1e-6;
const round = n => Math.round(n * 1e6) / 1e6;

function union(intervals) {
  const result = [];
  for (const [a, b] of intervals.filter(([a, b]) => b > a).sort((a, b) => a[0] - b[0])) {
    const last = result.at(-1);
    if (last && a <= last[1] + EPS) last[1] = Math.max(last[1], b);
    else result.push([a, b]);
  }
  return result;
}
const seconds = intervals => union(intervals).reduce((sum, [a, b]) => sum + b - a, 0);

function subtract(intervals, masks) {
  let parts = union(intervals);
  for (const [a, b] of union(masks)) parts = parts.flatMap(([x, y]) =>
    b <= x || a >= y ? [[x, y]] : [[x, Math.min(a, y)], [Math.max(b, x), y]].filter(([s, e]) => e > s));
  return parts;
}

function sourceType(value) {
  if (value == null) return null;
  if (!SOURCE_TYPES.includes(value)) throw new Error(`未知素材源 ${value}；允许 ${SOURCE_TYPES.join(', ')}`);
  return value;
}

function inferMedia(media, recipe, assumptions) {
  if (media.sourceType) return sourceType(media.sourceType);
  const src = String(Array.isArray(media.src) ? media.src[0] : media.src || '');
  let type = recipe === 'rec-zoom' || RECORDING_CONTAINERS.includes(recipe) ? 'recording' : ['doc-zoom', 'news-card'].includes(recipe) ? 'web_capture' :
    recipe === 'stock-shot' ? 'third_party' : /@assets\/|\/props\/|\/image-\d/.test(src) ? 'image2' :
    /\.(mp4|mov|webm)(?:[?#]|$)/i.test(src) ? 'recording' : null;
  if (type) assumptions.add(`兼容旧镜头表：${recipe || '未注明配方'} / ${src} → ${type}；新素材请显式写 sourceType。`);
  return type;
}

export function evaluateVisualVariety({ beats, episode = {}, timing = [], buildReport = [], previous = null, limits = {} }) {
  const config = { ...DEFAULT_VISUAL_LIMITS, ...(episode.visual?.limits || {}), ...limits };
  for (const [key, value] of Object.entries(config)) {
    if (!(key in DEFAULT_VISUAL_LIMITS) || !Number.isFinite(value) || value < 0) throw new Error(`无效 visual.limits.${key}`);
  }
  if (config.minNonRecordingRatio > 1 || config.maxPreviousRecipeOverlap > 1 || config.minTitleFreeRatio > 1) throw new Error('比例阈值必须在 0–1 之间');
  const scenes = Array.isArray(beats) ? beats : beats.scenes || beats.shots;
  if (!Array.isArray(scenes) || !scenes.length) throw new Error('beats.scenes / shots 不能为空');
  const T = new Map(timing.map(t => [t.id, t]));
  const reports = new Map((Array.isArray(buildReport) ? buildReport : buildReport.scenes || []).map(s => [s.id, s]));
  const end = episode.end ?? beats.end ?? scenes.at(-1).E ?? scenes.at(-1).end ?? reports.get(scenes.at(-1).id)?.E;
  if (!Number.isFinite(end) || end <= 0) throw new Error('需要正数 episode.end / beats.end');
  const starts = scenes.map((s, i) => {
    const explicit = s.B ?? s.start;
    if (Number.isFinite(explicit)) return explicit;
    const first = T.get(s.sents?.[0])?.firstCharTime;
    if (Number.isFinite(first)) return i === 0 ? 0 : Number((first - 0.2).toFixed(3));
    return reports.get(s.id)?.B;
  });
  const assumptions = new Set(), recipeCounts = {}, sourceIntervals = Object.fromEntries(SOURCE_TYPES.map(s => [s, []]));
  const recordings = [], nonRecordings = [], overlays = [], transitions = new Set();
  const timeline = scenes.map((s, i) => {
    const B = starts[i], E = s.E ?? s.end ?? starts[i + 1] ?? end;
    if (!Number.isFinite(B) || !Number.isFinite(E) || B < 0 || E <= B || E > end + EPS ||
      (i === 0 && Math.abs(B) > EPS) || (i && Math.abs(B - (scenes[i - 1].E ?? scenes[i - 1].end ?? B)) > EPS)) {
      throw new Error(`${s.id || i} 缺少有效且连续的镜头边界；提供时间轴或先 build`);
    }
    if (i === scenes.length - 1 && Math.abs(E - end) > EPS) throw new Error('末镜头边界与 episode.end 不符');
    if (!s.recipe) throw new Error(`${s.id || i} 缺少 recipe`);
    recipeCounts[s.recipe] = (recipeCounts[s.recipe] || 0) + 1;
    if (i > 0) transitions.add(s.enter || s.transition || 'cut');
    const anchor = at => {
      if (at == null) return B;
      if (typeof at === 'number') return B + at;
      if (typeof at === 'string' && /^\+[-\d.]+$/.test(at)) return B + Number(at.slice(1));
      if (typeof at === 'string' && at.startsWith('first:')) {
        const value = T.get(at.slice(6))?.firstCharTime;
        if (Number.isFinite(value)) return value;
      }
      if (typeof at === 'string' && at.startsWith('@')) {
        const [phrase, nth = '1'] = at.slice(1).split('#');
        const matches = (s.sents || []).flatMap(id => T.get(id)?.anchors || []).filter(a => a.phrase === phrase);
        if (Number.isFinite(matches[Number(nth) - 1]?.time)) return matches[Number(nth) - 1].time;
      }
      throw new Error(`${s.id} 无法解析画面锚点 ${at}`);
    };
    const span = item => {
      const a = item.static ? B : anchor(item.at), b = item.duration == null ? E : a + Number(item.duration);
      if (!Number.isFinite(b) || (item.duration != null && Number(item.duration) < 0)) throw new Error(`${s.id} 无效素材/叠加层时长`);
      return [Math.max(B, Math.min(E, a)), Math.max(B, Math.min(E, b))];
    };
    const media = (s.props ? prepareVocab(s).media : s.media || []).map(m => ({ ...m, type: inferMedia(m, s.recipe, assumptions) }));
    const primary = sourceType(s.sourceType || s.visual?.sourceType) || media.find(m => m.type && m.role !== 'overlay')?.type ||
      (s.recipe === 'rec-zoom' || RECORDING_CONTAINERS.includes(s.recipe) ? 'recording' : ['doc-zoom', 'news-card'].includes(s.recipe) ? 'web_capture' : 'code_animation');
    sourceIntervals[primary].push([B, E]);
    (primary === 'recording' ? recordings : nonRecordings).push([B, E]);
    for (const m of media) {
      if (m.type) sourceIntervals[m.type].push(span(m));
      if (m.role === 'overlay') overlays.push(span(m));
      if (m.role === 'insert') { overlays.push(span(m)); if (m.type !== 'recording') nonRecordings.push(span(m)); }
    }
    for (const source of s.visual?.sources || []) {
      const type = sourceType(source.type); if (!type) throw new Error(`${s.id} visual.sources 缺少 type`);
      sourceIntervals[type].push(span(source));
      if (source.role === 'overlay') overlays.push(span(source));
    }
    // 已有配方的信息层直接读取；显式 overlays 可描述新配方，不要求为门重新实现视觉。
    const spec = s.spec || {};
    const layers = [...(s.overlays || []), ...(s.visual?.overlays || []), ...(spec.hls || []), ...(spec.notes || []), ...(Array.isArray(spec.props)?spec.props:[]), ...(s.recipe==='news-card'&&Array.isArray(s.props?.highlight)?s.props.highlight:[])];
    for(const layer of s.layers||[])if(layer.kind==='notification-stack'){
      for(const [index,item]of (layer.items||[{}]).slice(0,3).entries())layers.push({at:item.at??layer.at??(.5+index*.2)});
    }
    for (const key of ['title', 'tag', 'hl', 'clip', 'stamp', 'circle']) {
      const value = spec[key];
      if (value && typeof value === 'object' && !Array.isArray(value)) layers.push(value);
      else if (typeof value === 'string' && value) layers.push({ at: 0 });
    }
    for (const layer of layers) overlays.push(span(layer));
    for (const insert of [...(s.inserts || []), ...(s.visual?.inserts || [])]) {
      const type = sourceType(insert.sourceType); if (!type) throw new Error(`${s.id} insert 缺少 sourceType`);
      const range = span(insert); overlays.push(range); sourceIntervals[type].push(range);
      if (type !== 'recording') nonRecordings.push(range);
    }
    return { id: s.id, recipe: s.recipe, B, E, sourceType: primary, ...vocabLayout(s) };
  });
  const bare = subtract(recordings, overlays);
  const sourceDurations = Object.fromEntries(SOURCE_TYPES.map(type => [type, round(seconds(sourceIntervals[type]))]));
  const sourceTypes = SOURCE_TYPES.filter(type => sourceDurations[type] > EPS);
  const nonRecordingSeconds = seconds(nonRecordings), nonRecordingRatio = nonRecordingSeconds / end;
  const recordingContainers=[...new Set(timeline.filter(s=>s.sourceType==='recording'&&RECORDING_CONTAINERS.includes(s.recipe)).map(s=>s.recipe))].sort();
  const titleFreeScenes=timeline.filter(s=>!s.titleBar).length,titleFreeRatio=titleFreeScenes/timeline.length,layoutRuns=[];
  for(const s of timeline){const last=layoutRuns.at(-1);if(last?.skeleton===s.layoutSkeleton){last.count++;last.sceneIds.push(s.id);}else layoutRuns.push({skeleton:s.layoutSkeleton,count:1,sceneIds:[s.id]});}
  const fingerprint = { schemaVersion: 1, episodeId: episode.id || beats.id || null, duration: end,
    recipeCounts, sourceDurations, sourceTypes, recordingContainers, transitionKinds: [...transitions].sort(),titleFreeScenes,titleFreeRatio:round(titleFreeRatio),layoutRuns,
    nonRecordingSeconds: round(nonRecordingSeconds), nonRecordingRatio: round(nonRecordingRatio),
    bareRecordingRuns: bare.map(([start, end]) => ({ start: round(start), end: round(end), duration: round(end - start) })), timeline };
  const findings = [];
  const fail = (code, message, details) => findings.push({ severity: 'error', code, message, details });
  const longRuns = fingerprint.bareRecordingRuns.filter(r => r.duration > config.maxBareRecordingSeconds + EPS);
  if (longRuns.length) fail('bare_recording_too_long', `无叠加/插镜的连续录屏超过 ${config.maxBareRecordingSeconds} 秒`, longRuns);
  if (nonRecordingRatio + EPS < config.minNonRecordingRatio) fail('non_recording_ratio_low', `非录屏主画面占比不足 ${config.minNonRecordingRatio * 100}%`, { actual: round(nonRecordingRatio) });
  if (sourceTypes.length < config.minSourceTypes) fail('source_types_low', `素材来源不足 ${config.minSourceTypes} 类`, { actual: sourceTypes });
  const repeats = Object.fromEntries(Object.entries(recipeCounts).filter(([, count]) => count > config.maxRecipeUses));
  if (Object.keys(repeats).length) fail('recipe_repeated', `同一配方使用超过 ${config.maxRecipeUses} 次`, repeats);
  if (transitions.size < config.minTransitionKinds) fail('transition_kinds_low', `转场不足 ${config.minTransitionKinds} 类`, { actual: [...transitions] });
  if(recordingContainers.length<config.minRecordingContainerKinds)fail('recording_containers_low',`录屏B族容器不足 ${config.minRecordingContainerKinds} 种`,{actual:recordingContainers});
  if(titleFreeRatio+EPS<config.minTitleFreeRatio)fail('title_free_ratio_low',`不出左上标题的镜头不足 ${config.minTitleFreeRatio*100}%`,{actual:round(titleFreeRatio),titleFreeScenes,totalScenes:timeline.length});
  const repeatedLayouts=layoutRuns.filter(r=>r.count>config.maxConsecutiveLayout);
  if(repeatedLayouts.length)fail('layout_repeated',`同一版式骨架连续超过 ${config.maxConsecutiveLayout} 镜`,repeatedLayouts);
  let comparison = { status: 'no_previous', note: '未提供上一期指纹；仅首期可省略，后续请配置 visual.previousFingerprint。' };
  if (previous) {
    if (!previous.recipeCounts || !Object.keys(previous.recipeCounts).length) throw new Error('上一期视觉指纹缺少 recipeCounts');
    const current = Object.keys(recipeCounts), old = new Set(Object.keys(previous.recipeCounts));
    const shared = current.filter(r => old.has(r)), fresh = current.filter(r => !old.has(r)), overlap = shared.length / current.length;
    comparison = { status: 'compared', previousEpisodeId: previous.episodeId, overlap: round(overlap), sharedRecipes: shared, newRecipes: fresh };
    if (overlap > config.maxPreviousRecipeOverlap + EPS) fail('previous_recipe_overlap', `本期配方集合复用率超过 ${config.maxPreviousRecipeOverlap * 100}%`, comparison);
    if (fresh.length < config.minNewRecipes) fail('no_new_recipe', `本期新增配方不足 ${config.minNewRecipes} 个`, { newRecipes: fresh });
  }
  return { ok: findings.length === 0, findings, limits: config, fingerprint, comparison, assumptions: [...assumptions] };
}

export function checkVisualVariety(root, { previousPath, outputDir = root } = {}) {
  const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
  const optional = file => fs.existsSync(file) ? read(file) : [];
  const episode = read(path.join(root, 'episode.json')), beats = read(path.join(root, 'beats.json'));
  const timingFile = episode.voice_timing ? path.resolve(root, episode.voice_timing) : path.resolve(root, episode.voiceDir || 'voice', 'voice-timing.json');
  const previousFile = previousPath || episode.visual?.previousFingerprint;
  const result = evaluateVisualVariety({ beats, episode, timing: optional(timingFile),
    buildReport: optional(path.join(root, 'build-report.json')),
    previous: previousFile ? read(path.resolve(root, previousFile)) : null });
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, 'visual-fingerprint.json'), JSON.stringify(result.fingerprint, null, 2) + '\n');
  fs.writeFileSync(path.join(outputDir, 'visual-check-report.json'), JSON.stringify(result, null, 2) + '\n');
  return result;
}
