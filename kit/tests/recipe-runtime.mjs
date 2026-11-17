import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const template = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../template');

class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.style = {}; this.attrs = {}; this.className = ''; this.innerHTML = ''; this.textContent = ''; }
  get classList() { return { add: (...names) => { this.className += ' ' + names.join(' '); } }; }
  appendChild(e) { this.children.push(e); return e; }
  setAttribute(k, v) { this.attrs[k] = v; }
  querySelectorAll(selector) {
    const matches = e => selector.startsWith('.') ? e.className.split(/\s+/).includes(selector.slice(1)) : e.tag === selector;
    return this.children.flatMap(e => [...(matches(e) ? [e] : []), ...e.querySelectorAll(selector)]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
}
function runtime(spec, recipe) {
  const calls = [], tl = { to: (e, to, at) => calls.push({ e, to, at }), fromTo: (e, from, to, at) => calls.push({ e, from, to, at }) };
  const document = { createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag) };
  const scope = { window: { __timelines: {} }, document, Math };
  vm.createContext(scope); vm.runInContext(fs.readFileSync(path.join(template, 'assets/yice.js'), 'utf8'), scope);
  const Y = scope.window.YF, root = new Element('div'), cam = new Element('div'); root.appendChild(cam);
  // 此轻量替身只测旧配方参数；全局机位行为另由真实浏览器测试覆盖。
  const c = { sid: 'test', spec:{...spec,reframe:false}, root, cam, wrap: root, dur: 10, tl, stage: 'paper-gray',
    at: (t, fallback = .6) => t == null ? fallback : t, m: () => new Element('img') };
  Object.assign(scope, { Y, c, s: spec, tl });
  if (recipe) vm.runInContext(fs.readFileSync(path.join(template, `recipes/_src/${recipe}.js`), 'utf8'), scope);
  return { scope, Y, c, calls, root };
}
for (const [checked, count] of [[undefined, 3], [[], 0], [[0], 1]]) {
  const r = runtime({ checked, title: '准备', items: ['甲', '乙', '丙'].map(text => ({ text })) }, 'checklist');
  assert.equal(r.root.querySelectorAll('.n').filter(e => e.innerHTML === '✓').length, count);
}
const photo = runtime({ obj: { x: 800, y: 100, w: 800 }, circle: { x: 900, y: 300, w: 300, h: 200, at: 1.5 }, episodeId: 'ep02' }, 'photo-word');
assert.equal(photo.root.querySelectorAll('path').length, 1);
assert.equal(photo.root.querySelector('path').attrs.stroke, 'var(--stamp)');
assert.ok(photo.calls.some(c => c.e.tag === 'path' && c.at === 1.5));
assert.ok(photo.root.querySelectorAll('.meta').some(e => e.textContent.includes('EP02')));
const prop = runtime({});
prop.Y.props(prop.c, prop.c.cam, [{ m: 0, x: 900, y: 100, w: 200,
  press: { at: 2, d: .3, x: 1000, y: 350, target: '.word' }, stamp: { text: '完成', x: 1000, y: 380 } }], prop.c.tl);
const word = prop.Y.el('div', 'word', prop.c.cam, '重点');
prop.Y.finish(prop.c);
assert.ok(prop.calls.some(c => c.e === word && c.at === 2.3 && c.to.scaleY === .88));
assert.ok(prop.calls.some(c => c.e.className?.includes('yf-stamp') && c.at === 2.3));
assert.equal(prop.scope.window.__timelines.test, prop.c.tl);
const merged = runtime({ slips: [{ text: '甲', at: .2 }, { text: '乙', at: .6 }], merge: { at: 2, x: 750, y: 600 }, keep: { text: '合并' } }, 'strike-slips');
assert.equal(merged.calls.filter(c => c.at === 2 && c.to.opacity === 0).length, 2);
assert.equal(merged.root.querySelector('.keep').style.left, '750px');
assert.throws(() => runtime({ merge: { at: 2 } }, 'strike-slips'), /merge requires keep/);
console.log('recipe runtime: checklist defaults/empty/partial, independent red circle, EP02 HUD, deferred press/stamp, merge and invalid merge passed');
