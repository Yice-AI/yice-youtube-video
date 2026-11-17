/* 一策 yice.js — shared primitives for recipe sub-compositions.
   Every helper takes the recipe's own root element and a GSAP timeline; nothing touches the
   host document, nothing reads clocks or Math.random. Camera servo adapted from registry
   `ui-focus-zoom`, marker sweep from `marker-highlight`, strike from `strikethrough-replace`. */
(function () {
  "use strict";
  var W = 1920, H = 1080, OV = 0.5; // transition overlap (seconds)
  var NS = "http://www.w3.org/2000/svg";

  function el(tag, cls, parent, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  function css(e, o) { for (var k in o) e.style[k] = typeof o[k] === "number" && !/opacity|zIndex|flex|fontWeight|lineHeight/.test(k) ? o[k] + "px" : o[k]; return e; }
  function svg(parent) { var s = document.createElementNS(NS, "svg"); s.setAttribute("class", "yf-svg"); s.setAttribute("viewBox", "0 0 " + W + " " + H); parent.appendChild(s); return s; }
  function path(s, d, o) { var p = document.createElementNS(NS, "path"); p.setAttribute("d", d); p.setAttribute("fill", "none"); for (var k in o) p.setAttribute(k, o[k]); s.appendChild(p); return p; }
  // deterministic pseudo-random from a string seed
  function rng(seed) { var h = 2166136261; for (var i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); } return function () { h = Math.imul(h ^ (h >>> 15), 2246822507); h = Math.imul(h ^ (h >>> 13), 3266489909); h ^= h >>> 16; return (h >>> 0) / 4294967296; }; }

  // ---------- context ----------
  function ctx(sid, root) {
    root = root || document.getElementById(sid + "-root");
    var specEl = root.querySelector("#" + sid + "-spec");
    var spec = {};
    try { spec = JSON.parse(specEl.textContent); } catch (e) { spec = {}; }
    var stageName = spec.stage || "paper-cool";
    var inner = el("div", "yf-root st-" + stageName + (spec.recipeClass ? " " + spec.recipeClass : ""), root);
    var wrap = el("div", "yf-wrap", inner);
    var cam = el("div", "yf-cam", wrap);
    var tl = gsap.timeline({ paused: true });
    var dur = spec.dur || 5;
    var A = spec.anchors || {};
    function at(name, fallback) { var v = typeof name === "number" ? name : A[name]; if (v == null) v = fallback; return Math.max(0, Math.min(dur - 0.2, v == null ? 0.6 : v)); }
    function m(i) { return root.querySelector("#" + sid + "-m" + i); }
    return { sid: sid, spec: spec, root: inner, host: root, wrap: wrap, cam: cam, tl: tl, dur: dur, at: at, A: A, stage: stageName, m: m };
  }

  // ---------- stage + hud ----------
  function stage(c, opts) {
    opts = opts || {};
    var st = el("div", "yf-stage", c.cam);
    el("div", "tex", st); el("div", "grid", st);
    var m1 = el("div", "mullion", st); css(m1, { left: 1500 });
    var m2 = el("div", "mullion", st); css(m2, { left: 1760 });
    var win = el("div", "window", st);
    // ambient: window light drifts, mullion shadows creep (deterministic, finite)
    c.tl.fromTo(win, { x: -60, y: -20 }, { x: 140, y: 40, duration: c.dur, ease: "none" }, 0);
    c.tl.fromTo([m1, m2], { x: 0 }, { x: -90, duration: c.dur, ease: "none" }, 0);
    return st;
  }
  function tc(t) { var f = Math.round(t * 30), ff = f % 30, s = Math.floor(f / 30); var mm = Math.floor(s / 60), ss = s % 60; return "00:" + (mm < 10 ? "0" : "") + mm + ":" + (ss < 10 ? "0" : "") + ss + ":" + (ff < 10 ? "0" : "") + ff; }
  function hud(c, opts) {
    opts = opts || {};
    var s = c.spec, h = el("div", "yf-hud" + (opts.onMedia ? " on-media" : ""), c.root); h.setAttribute("data-layout-ignore", "");
    if (!opts.onMedia) {
      el("div", "ruler-t", h); el("div", "ruler-l", h);
      for (var x = 240; x < W; x += 240) css(el("div", "rnum", h, String(x)), { left: x + 5 });
    }
    var m = 116 - 34, mt = 65 - 22;
    [[m, mt, "2px 0 0 2px"], [W - m - 34, mt, "2px 2px 0 0"], [m, H - mt - 34, "0 0 2px 2px"], [W - m - 34, H - mt - 34, "0 2px 2px 0"]].forEach(function (r) {
      var e = el("div", "reg", h); css(e, { left: r[0], top: r[1] }); e.style.borderWidth = r[2];
    });
    var meta = el("div", "meta", h);
    meta.textContent = "YICE / " + String(s.episodeId || "").toUpperCase() + " · " + (s.chapter || "") + " " + (s.chapterTitle || "") + " · " + (s.id || "");
    css(meta, { left: 116, bottom: 30 });
    var right = el("div", "meta tc", h); css(right, { right: 116, bottom: 30 });
    var src = s.source ? el("div", "meta", h, s.source) : null;
    if (src) css(src, { right: 116, top: 36 });
    var proxy = { t: 0 }, t0 = s.t0 || 0;
    right.innerHTML = '<span class="dot"></span>' + tc(t0);
    c.tl.to(proxy, { t: c.dur, duration: c.dur, ease: "none", onUpdate: function () { right.innerHTML = '<span class="dot"></span>' + tc(t0 + proxy.t); } }, 0);
    return h;
  }

  // ---------- transitions (scene-local; host overlaps clips by OV) ----------
  function transitions(c) {
    if (window.YV) window.YV.transitions(c);
    var s = c.spec, tl = c.tl, w = c.wrap, d = c.dur;
    var e = s.enter || "cut", x = s.exit || "cut";
    if (e === "pan") tl.fromTo(w, { x: W }, { x: 0, duration: OV, ease: "power2.inOut" }, 0);
    else if (e === "push") tl.fromTo(w, { scale: 0.93, opacity: 0 }, { scale: 1, opacity: 1, duration: OV, ease: "power2.out" }, 0);
    else if (e === "match") tl.fromTo(w, { opacity: 0 }, { opacity: 1, duration: OV, ease: "sine.inOut" }, 0);
    else if (e === "lift") tl.fromTo(w, { scale: 1.025 }, { scale: 1, duration: OV + 0.4, ease: "power2.out" }, 0);
    else if (e === "rise") tl.fromTo(w, { y: H }, { y: 0, duration: OV, ease: "power3.inOut" }, 0);
    var xs = Math.max(0, d - OV);
    if (x === "pan") tl.to(w, { x: -W, duration: OV, ease: "power2.inOut" }, xs);
    else if (x === "push") tl.to(w, { scale: 1.32, opacity: 0, duration: OV, ease: "power2.in" }, xs);
    else if (x === "lift") tl.to(w, { y: -H * 1.08, rotation: -3.5, duration: OV, ease: "power2.in", boxShadow: "0 60px 90px rgba(0,0,0,.4)" }, xs);
    else if (x === "rise") tl.to(w, { y: -H * 0.25, opacity: 0.6, duration: OV, ease: "power3.inOut" }, xs);
  }

  // ---------- camera (camera-servo law, stage px; focus point -> screen center) ----------
  function camera(c, keys, opts) {
    opts = opts || {};
    var st = { s: 1, fx: W / 2, fy: H / 2 };
    var cover = opts.cover !== false; // keep 1920x1080 world covering viewport
    function apply() {
      var s = st.s, tx = W / 2 - s * st.fx, ty = H / 2 - s * st.fy;
      if (cover) { tx = Math.min(0, Math.max(W - s * W, tx)); ty = Math.min(0, Math.max(H - s * H, ty)); }
      c.cam.style.transform = "translate(" + tx.toFixed(2) + "px," + ty.toFixed(2) + "px) scale(" + s.toFixed(4) + ")";
      if (opts.onApply) opts.onApply(s, tx, ty, s * st.fx + tx, s * st.fy + ty);
    }
    if (keys && keys.length) { st.s = keys[0].s || 1; st.fx = keys[0].x != null ? keys[0].x : W / 2; st.fy = keys[0].y != null ? keys[0].y : H / 2; }
    apply();
    (keys || []).slice(1).forEach(function (k) {
      c.tl.to(st, { s: k.s || 1, fx: k.x != null ? k.x : W / 2, fy: k.y != null ? k.y : H / 2, duration: k.d || 1.2, ease: k.ease || "power2.inOut", onUpdate: apply }, Math.max(0, Math.min(c.dur - 0.1, k.at)));
    });
    return { state: st, apply: apply };
  }

  // ---------- text ----------
  function glyphs(e, text) { e.innerHTML = ""; var out = []; Array.from(text).forEach(function (ch) { var g = el("span", "yf-glyph", e); g.textContent = ch === " " ? " " : ch; out.push(g); }); return out; }
  function write(tl, e, text, t, o) {
    o = o || {}; var gs = glyphs(e, text), per = Math.min(o.per || 0.05, 0.26 / Math.max(1, gs.length));
    tl.fromTo(gs, { opacity: 0, y: o.y == null ? 18 : o.y, filter: "blur(6px)" }, { opacity: 1, y: 0, filter: "blur(0px)", duration: Math.min(o.d || 0.3, 0.3), ease: "power2.out", stagger: per }, t);
    return gs;
  }
  function fadeUp(tl, e, t, o) { o = o || {}; tl.fromTo(e, { opacity: 0, y: o.y == null ? 24 : o.y }, { opacity: 1, y: 0, duration: o.d || 0.5, ease: o.ease || "power2.out" }, t); }
  // physical object landing: overshoot residual x0.6
  function drop(tl, e, t, o) {
    o = o || {}; if (t > 0 && t < 0.9) t = t * 0.35;
    tl.fromTo(e, { opacity: 0, y: o.y == null ? -60 : o.y, x: o.x || 0, rotation: (o.rot || 0) - (o.spin == null ? 4 : o.spin), scale: o.scale || 1.06 },
      { opacity: 1, y: 0, x: 0, rotation: o.rot || 0, scale: 1, duration: o.d || 0.7, ease: "back.out(1.25)" }, t);
  }
  function slideIn(tl, e, t, o) { o = o || {}; tl.fromTo(e, { opacity: 0, x: o.x == null ? -80 : o.x, rotation: (o.rot || 0) + (o.spin || 0) }, { opacity: 1, x: 0, rotation: o.rot || 0, duration: o.d || 0.6, ease: "power3.out" }, t); }

  // ---------- marks ----------
  function hl(parent, tl, r, t, o) { // r: {x,y,w,h} px in parent space
    o = o || {}; var e = el("div", "yf-hl" + (o.under ? " under" : ""), parent); css(e, o.under ? { left: r.x, top: r.y + r.h - 7, width: r.w, height: 7 } : { left: r.x, top: r.y, width: r.w, height: r.h });
    tl.fromTo(e, { scaleX: 0 }, { scaleX: 1, duration: o.d || Math.min(0.6, 0.25 + r.w / 2400), ease: "power1.inOut" }, t);
    return e;
  }
  function wobbleLine(x1, y1, x2, y2, seed) { var r = rng(seed || "s"), my = (y1 + y2) / 2 + (r() - 0.5) * 8, mx = (x1 + x2) / 2; return "M" + x1 + " " + (y1 + (r() - .5) * 4) + " Q " + mx + " " + my + " " + x2 + " " + (y2 + (r() - .5) * 4); }
  function draw(tl, p, t, d, ease) {
    var L = p.getTotalLength ? p.getTotalLength() : 1000; p.style.strokeDasharray = L + " " + (L + 10);
    tl.fromTo(p, { strokeDashoffset: L }, { strokeDashoffset: 0, duration: d || 0.4, ease: ease || "power2.inOut" }, t);
  }
  function strike(s, tl, r, t, o) { o = o || {}; var p = path(s, wobbleLine(r.x - 10, r.y, r.x + r.w + 12, r.y + (o.tilt || -6), o.seed), { stroke: o.color || "var(--stamp)", "stroke-width": o.w || 7, "stroke-linecap": "round" }); draw(tl, p, t, o.d || 0.35); return p; }
  function underline(s, tl, r, t, o) { o = o || {}; var p = path(s, wobbleLine(r.x, r.y, r.x + r.w, r.y + 2, o.seed || "u"), { stroke: o.color || "var(--blue)", "stroke-width": o.w || 5, "stroke-linecap": "round", opacity: o.op || 1 }); draw(tl, p, t, o.d || 0.45); return p; }
  function ellipse(s, tl, r, t, o) { // hand-drawn, not closed
    o = o || {}; var cx = r.x + r.w / 2, cy = r.y + r.h / 2, rx = r.w / 2 + 18, ry = r.h / 2 + 14, pts = [], R = rng(o.seed || "e");
    for (var i = 0; i <= 44; i++) { var a = -2.2 + i / 44 * (Math.PI * 2 + 0.5), k = 1 + (R() - .5) * 0.035 + i * 0.0012; pts.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]); }
    var d = "M" + pts.map(function (p) { return p[0].toFixed(1) + " " + p[1].toFixed(1); }).join(" L");
    var p = path(s, d, { stroke: o.color || "var(--blue)", "stroke-width": o.w || 5, "stroke-linecap": "round", "stroke-linejoin": "round" });
    draw(tl, p, t, o.d || 0.6, "power1.inOut"); return p;
  }
  function stamp(parent, tl, text, pos, t, o) {
    o = o || {}; var e = el("div", "yf-stamp", parent, text); css(e, { left: pos.x, top: pos.y, fontSize: o.size || 56 });
    tl.fromTo(e, { opacity: 0, scale: 1.9, rotation: (o.rot || -8) - 6 }, { opacity: 0.92, scale: 1, rotation: o.rot || -8, duration: 0.24, ease: "power4.in" }, t);
    tl.to(e, { scale: 1.035, duration: 0.08, yoyo: true, repeat: 1, ease: "sine.out" }, t + 0.24);
    return e;
  }
  function count(tl, e, from, to, t, o) {
    o = o || {}; var p = { v: from }, dec = o.dec || 0;
    function f(v) { return (o.pre || "") + v.toFixed(dec) + (o.suf || ""); }
    e.textContent = f(from);
    tl.to(p, { v: to, duration: o.d || 0.9, ease: "power2.out", onUpdate: function () { e.textContent = f(p.v); } }, t);
  }

  // prop list: [{m,x,y,w,rot,at,z}] -> placed images with shadow + drop-in
  function props(c, parent, list, tl) {
    (list || []).forEach(function (p, i) {
      var im = c.m(p.m); if (!im) return; im.classList.add("yf-prop"); parent.appendChild(im);
      css(im, { position: "absolute", left: p.x, top: p.y, width: p.w, height: "auto", zIndex: p.z || 30 });
      drop(tl, im, c.at(p.at, 0.1 + i * 0.2), { rot: p.rot || 0, y: -70, scale: 1.05 });
      if (p.press || p.stamp) (c.deferred || (c.deferred = [])).push(function () {
        var q = p.press, impact = c.at(p.at, 0.1 + i * 0.2) + 0.4;
        if (q) {
          var at = c.at(q.at, impact), d = q.d || 0.24;
          impact = at + d;
          tl.to(im, { x: (q.x == null ? p.x : q.x) - p.x, y: (q.y == null ? p.y + 24 : q.y) - p.y,
            scale: q.scale || 1, duration: d, ease: "power3.in" }, at);
          if (q.target) {
            var target = c.cam.querySelector(q.target);
            if (!target) throw new Error(c.sid + ": press target missing: " + q.target);
            tl.to(target, { scaleY: q.depth || 0.88, transformOrigin: "50% 100%", duration: 0.1, repeat: 1, yoyo: true, ease: "sine.out" }, impact);
          }
        }
        if (p.stamp) {
          var st = p.stamp;
          stamp(parent, tl, st.text || "", { x: st.x == null ? p.x : st.x, y: st.y == null ? p.y : st.y }, c.at(st.at, impact), st);
        }
      });
    });
  }
  function card(parent, r, o) { o = o || {}; var e = el("div", "yf-card", parent); css(e, { left: r.x, top: r.y, width: r.w, height: r.h }); if (o.rot) e.style.transform = "rotate(" + o.rot + "deg)"; return e; }
  function tape(parent, x, y, rot, w) { var e = el("div", "yf-tape", parent); css(e, { left: x, top: y, width: w || 170 }); e.style.transform = "rotate(" + (rot || 0) + "deg)"; return e; }
  function chip(parent, html, x, y, o) { o = o || {}; var e = el("div", "yf-chip", parent, html); css(e, { left: x, top: y }); if (o.size) e.style.fontSize = o.size + "px"; if (o.color) e.style.color = o.color; return e; }
  // taped paper keyword label in screen space (B slot crossing the object)
  function label(c, t, o) {
    o = o || {}; if (!t) return null;
    var right = t.side === "right", lb = card(c.wrap, { x: o.x || 140, y: o.y || 800 }); lb.classList.add("yf-label");
    if (right) { lb.style.left = "auto"; lb.style.right = (o.r || 150) + "px"; }
    if (t.top) { lb.style.top = t.top + "px"; }
    var k = el("div", "k", lb); if (t.size) k.style.fontSize = t.size + "px";
    if (t.sub) el("div", "s", lb, t.sub);
    tape(lb, right ? 30 : 200, -24, right ? -5 : 4, 150);
    var ta = c.at(t.at, 0.6), rot = right ? 1.4 : -1.6;
    c.tl.fromTo(lb, { opacity: 0, y: 40, rotation: rot * 3.5 }, { opacity: 1, y: 0, rotation: rot, duration: 0.55, ease: "back.out(1.3)" }, ta);
    write(c.tl, k, t.text, ta + 0.25);
    return lb;
  }
  function autoReframe(c) {
    if(c.spec.reframe===false||c.spec.props?.reframe===false||c.dur<=2.5)return;
    var spans=[];
    c.tl.getChildren(false,true,false).forEach(function(tween){
      var foreground=tween.targets().some(function(e){return e instanceof Element&&c.cam.contains(e)&&!e.closest('.yf-stage,.yf-hud,.v-grain,[data-layout-ignore="true"]');});
      if(foreground)spans.push([Math.max(0,tween.startTime()),Math.min(c.dur,tween.endTime())]);
    });
    spans.sort(function(a,b){return a[0]-b[0];});spans.push([c.dur,c.dur]);
    var end=0,index=0,points=[];
    spans.forEach(function(span){
      for(var t=end+2.4;t<span[0]-.1;t+=2.4){index++;points.push(t);c.tl.set(c.cam,{scale:index%2?1.07:1.035,x:index%2?-68:-30,y:index%2?-28:-10},t);}
      end=Math.max(end,span[1]);
    });
    c.cam.dataset.reframes=JSON.stringify(points);
  }
  function finish(c) { (c.deferred || []).forEach(function (fn) { fn(); }); if (window.YV) window.YV.layers(c); autoReframe(c); transitions(c); window.__timelines[c.sid] = c.tl; }

  window.YF = { W: W, H: H, OV: OV, el: el, css: css, svg: svg, path: path, rng: rng, ctx: ctx, stage: stage, hud: hud, camera: camera, glyphs: glyphs, write: write, fadeUp: fadeUp, drop: drop, slideIn: slideIn, hl: hl, draw: draw, strike: strike, underline: underline, ellipse: ellipse, stamp: stamp, count: count, card: card, tape: tape, chip: chip, label: label, finish: finish, props: props, transitions: transitions, tc: tc };
})();
