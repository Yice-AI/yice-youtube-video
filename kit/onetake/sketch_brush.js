/* sketch_brush.js — 100% offline deterministic hand-drawn pencil/watercolor & Riso halftone engine.
 * Driven purely by (seed, boilFrame = Math.floor(t * 8)) so window.__seek(t) and 180° shutter integration
 * stay 100% deterministic and seek-safe without Math.random().
 */
(function (root) {
  'use strict';

  function rng(seed) {
    let s = (seed >>> 0) || 1;
    return () => {
      s ^= s << 13;
      s ^= s >>> 17;
      s ^= s << 5;
      return (s >>> 0) / 4294967296;
    };
  }

  function boilSeed(baseSeed, t, boilFps = 8) {
    const frame = Math.max(0, Math.floor(t * boilFps));
    return ((baseSeed * 73856093) ^ (frame * 2654435761)) >>> 0;
  }

  function line(ctx, x1, y1, x2, y2, opts = {}) {
    const {
      seed = 11, t = 0, color = '#211c17', width = 2.6,
      passes = 2, wobble = 2.4, boilFps = 8, alpha = 0.9
    } = opts;
    const rand = rng(boilSeed(seed, t, boilFps));
    const dx = x2 - x1, dy = y2 - y1;
    const dist = Math.hypot(dx, dy) || 1;
    const nx = -dy / dist, ny = dx / dist;
    const segs = Math.max(4, Math.min(28, Math.round(dist / 22)));
    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    for (let p = 0; p < passes; p++) {
      ctx.globalAlpha = alpha * (p === 0 ? 0.92 : 0.45);
      ctx.lineWidth = width * (p === 0 ? 1 : 0.72);
      ctx.beginPath();
      for (let i = 0; i <= segs; i++) {
        const u = i / segs;
        const j = (rand() - 0.5) * 2 * wobble * (i === 0 || i === segs ? 0.35 : 1);
        const px = x1 + dx * u + nx * j + (rand() - 0.5) * 0.9;
        const py = y1 + dy * u + ny * j + (rand() - 0.5) * 0.9;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
    }
    ctx.restore();
  }

  function blob(ctx, cx, cy, rx, ry, color, opts = {}) {
    const { seed = 23, t = 0, points = 16, roughness = 0.14, layers = 3, alpha = 0.34, boilFps = 8 } = opts;
    ctx.save();
    for (let l = 0; l < layers; l++) {
      const rand = rng(boilSeed(seed + l * 97, t, boilFps));
      const pts = [];
      for (let i = 0; i < points; i++) {
        const a = (i / points) * Math.PI * 2;
        const jitter = 1 + (rand() - 0.5) * 2 * roughness + l * 0.03;
        pts.push([cx + Math.cos(a) * rx * jitter, cy + Math.sin(a) * ry * jitter]);
      }
      ctx.globalAlpha = alpha / (l * 0.45 + 1);
      ctx.fillStyle = color;
      ctx.beginPath();
      for (let i = 0; i < points; i++) {
        const p0 = pts[i], p1 = pts[(i + 1) % points];
        const mx = (p0[0] + p1[0]) / 2, my = (p0[1] + p1[1]) / 2;
        if (i === 0) {
          const prev = pts[points - 1];
          ctx.moveTo((prev[0] + p0[0]) / 2, (prev[1] + p0[1]) / 2);
        }
        ctx.quadraticCurveTo(p0[0], p0[1], mx, my);
      }
      ctx.closePath();
      ctx.fill();
    }
    ctx.restore();
  }

  function roundedBox(ctx, x, y, w, h, r = 18, opts = {}) {
    const {
      seed = 41, t = 0, fill = '#fffaf0', stroke = '#211c17',
      width = 3, wobble = 2.0, fillAlpha = 0.88, boilFps = 8
    } = opts;
    if (fill) {
      ctx.save();
      ctx.globalAlpha = fillAlpha;
      ctx.fillStyle = fill;
      ctx.beginPath();
      ctx.roundRect(x + 3, y + 3, w - 6, h - 6, r);
      ctx.fill();
      ctx.restore();
    }
    const rr = Math.min(r, w * 0.25, h * 0.25);
    line(ctx, x + rr, y, x + w - rr, y, { seed: seed + 1, t, color: stroke, width, wobble, boilFps });
    line(ctx, x + w, y + rr, x + w, y + h - rr, { seed: seed + 2, t, color: stroke, width, wobble, boilFps });
    line(ctx, x + w - rr, y + h, x + rr, y + h, { seed: seed + 3, t, color: stroke, width, wobble, boilFps });
    line(ctx, x, y + h - rr, x, y + rr, { seed: seed + 4, t, color: stroke, width, wobble, boilFps });
    const corners = [
      [x + rr, y + rr, Math.PI, Math.PI * 1.5],
      [x + w - rr, y + rr, Math.PI * 1.5, Math.PI * 2],
      [x + w - rr, y + h - rr, 0, Math.PI * 0.5],
      [x + rr, y + h - rr, Math.PI * 0.5, Math.PI],
    ];
    const rand = rng(boilSeed(seed + 19, t, boilFps));
    ctx.save();
    ctx.strokeStyle = stroke;
    ctx.lineWidth = width;
    ctx.lineCap = 'round';
    corners.forEach(([cx, cy, a0, a1]) => {
      ctx.beginPath();
      ctx.arc(cx + (rand() - 0.5) * 1.2, cy + (rand() - 0.5) * 1.2, rr, a0, a1);
      ctx.stroke();
    });
    ctx.restore();
  }

  function arrow(ctx, x1, y1, x2, y2, progress = 1, opts = {}) {
    const p = Math.max(0, Math.min(1, progress));
    if (p <= 0.01) return;
    const ex = x1 + (x2 - x1) * p;
    const ey = y1 + (y2 - y1) * p;
    line(ctx, x1, y1, ex, ey, opts);
    if (p > 0.72) {
      const ang = Math.atan2(y2 - y1, x2 - x1);
      const headLen = opts.head || 16;
      const k = Math.min(1, (p - 0.72) / 0.28);
      line(ctx, ex, ey, ex - Math.cos(ang - 0.48) * headLen * k, ey - Math.sin(ang - 0.48) * headLen * k, { ...opts, seed: (opts.seed || 7) + 31 });
      line(ctx, ex, ey, ex - Math.cos(ang + 0.48) * headLen * k, ey - Math.sin(ang + 0.48) * headLen * k, { ...opts, seed: (opts.seed || 7) + 47 });
    }
  }

  function paper(ctx, w, h, opts = {}) {
    const { bg = '#F6EFE0', gridColor = 'rgba(130,112,86,0.14)', grainAlpha = 0.08, seed = 5 } = opts;
    ctx.save();
    const grad = ctx.createRadialGradient(w * 0.5, h * 0.42, 80, w * 0.5, h * 0.5, w * 0.72);
    grad.addColorStop(0, '#FFFDF7');
    grad.addColorStop(0.55, bg);
    grad.addColorStop(1, '#E5DAC0');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, w, h);

    if (gridColor) {
      ctx.strokeStyle = gridColor;
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 64) {
        ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
      }
      for (let y = 0; y < h; y += 64) {
        ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
      }
    }
    const rand = rng(seed);
    ctx.fillStyle = `rgba(92,74,52,${grainAlpha})`;
    for (let i = 0; i < 420; i++) {
      ctx.fillRect(rand() * w, rand() * h, 1 + rand() * 2, 1 + rand() * 2);
    }
    ctx.restore();
  }

  function risoHalftone(ctx, x, y, w, h, opts = {}) {
    const {
      t = 0, spacing = 22, colorA = '#ff48b0', colorB = '#0078bf',
      colorC = '#ffd83b', maxR = 8.2, seed = 77
    } = opts;
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();
    for (let py = y; py < y + h; py += spacing) {
      const row = Math.round((py - y) / spacing);
      for (let px = x + (row % 2) * (spacing * 0.5); px < x + w; px += spacing) {
        const wave = 0.5 + 0.5 * Math.sin(px * 0.011 + py * 0.008 - t * 2.4);
        const wave2 = 0.5 + 0.5 * Math.cos(px * 0.007 - py * 0.012 + t * 1.9);
        const r = Math.max(1.1, maxR * (0.28 + 0.72 * wave));
        ctx.fillStyle = wave > 0.62 ? colorA : (wave2 > 0.56 ? colorB : colorC);
        ctx.globalAlpha = 0.22 + 0.42 * wave;
        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
    ctx.restore();
  }

  function monster(ctx, cx, cy, scale = 1, opts = {}) {
    const { t = 0, bodyColor = '#32828a', hornColor = '#697c31', seed = 101 } = opts;
    const bounce = Math.sin(t * 5.2) * 5;
    ctx.save();
    ctx.translate(cx, cy + bounce);
    ctx.scale(scale, scale);
    // Cute hand-drawn multi-eye monster body
    blob(ctx, 0, 10, 126, 138, bodyColor, { seed, t, alpha: 0.92, layers: 2, roughness: 0.08 });
    // Horns / arms
    line(ctx, -78, -90, -108, -148, { seed: seed + 1, t, color: '#1b1a18', width: 5 });
    line(ctx, -108, -148, -42, -108, { seed: seed + 2, t, color: '#1b1a18', width: 5 });
    blob(ctx, -78, -118, 22, 24, hornColor, { seed: seed + 3, t, alpha: 0.85, layers: 2 });
    line(ctx, 78, -90, 108, -148, { seed: seed + 4, t, color: '#1b1a18', width: 5 });
    line(ctx, 108, -148, 42, -108, { seed: seed + 5, t, color: '#1b1a18', width: 5 });
    blob(ctx, 78, -118, 22, 24, hornColor, { seed: seed + 6, t, alpha: 0.85, layers: 2 });
    // Eyes
    const eyes = [[-42, -38, 21], [28, -44, 24], [-12, 6, 17], [52, 8, 15]];
    eyes.forEach(([ex, ey, er], idx) => {
      blob(ctx, ex, ey, er, er, '#fffdf5', { seed: seed + 20 + idx, t, alpha: 0.98, layers: 1 });
      ctx.strokeStyle = '#1b1a18';
      ctx.lineWidth = 3.2;
      ctx.beginPath(); ctx.arc(ex, ey, er, 0, Math.PI * 2); ctx.stroke();
      const lookX = Math.sin(t * 2.5 + idx) * (er * 0.26);
      ctx.fillStyle = '#1b1a18';
      ctx.beginPath(); ctx.arc(ex + lookX, ey, er * 0.36, 0, Math.PI * 2); ctx.fill();
    });
    // Smile
    line(ctx, -38, 52, -12, 62, { seed: seed + 40, t, color: '#1b1a18', width: 4.5 });
    line(ctx, -12, 62, 14, 54, { seed: seed + 41, t, color: '#1b1a18', width: 4.5 });
    line(ctx, 14, 54, 42, 62, { seed: seed + 42, t, color: '#1b1a18', width: 4.5 });
    ctx.restore();
  }

  function icon(ctx, kind, cx, cy, r = 28, opts = {}) {
    const { t = 0, color = '#1f1b16', fill = '#f4b942', seed = 61 } = opts;
    blob(ctx, cx, cy, r * 0.95, r * 0.95, fill, { seed, t, alpha: 0.52, layers: 2 });
    if (kind === 'bulb') {
      ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(cx, cy - 4, r * 0.56, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
      line(ctx, cx - 8, cy + r * 0.58, cx + 8, cy + r * 0.58, { seed: seed + 1, t, color, width: 3 });
    } else if (kind === 'chart') {
      line(ctx, cx - r * 0.6, cy + r * 0.5, cx + r * 0.6, cy + r * 0.5, { seed: seed + 2, t, color, width: 3 });
      line(ctx, cx - r * 0.35, cy + r * 0.5, cx - r * 0.35, cy, { seed: seed + 3, t, color, width: 5 });
      line(ctx, cx, cy + r * 0.5, cx, cy - r * 0.45, { seed: seed + 4, t, color, width: 5 });
      line(ctx, cx + r * 0.35, cy + r * 0.5, cx + r * 0.35, cy - r * 0.2, { seed: seed + 5, t, color, width: 5 });
    } else {
      ctx.save(); ctx.strokeStyle = color; ctx.lineWidth = 3;
      ctx.beginPath(); ctx.arc(cx, cy, r * 0.52, 0, Math.PI * 2); ctx.stroke();
      ctx.restore();
      line(ctx, cx - r * 0.3, cy, cx + r * 0.3, cy, { seed: seed + 6, t, color, width: 3 });
      line(ctx, cx, cy - r * 0.3, cx, cy + r * 0.3, { seed: seed + 7, t, color, width: 3 });
    }
  }

  function gauge(ctx, x, y, w, h, pct, label, opts = {}) {
    const { t = 0, stroke = '#1f1b16', fill = '#4d8b31', seed = 88 } = opts;
    roundedBox(ctx, x, y, w, h, w / 2, { seed, t, fill: '#fffdf7', stroke, width: 3.5, fillAlpha: 0.95 });
    const clamped = Math.max(0, Math.min(1, pct));
    const fillH = Math.max(12, (h - 18) * clamped);
    blob(ctx, x + w / 2, y + h - 9 - fillH / 2, (w - 16) / 2, fillH / 2, fill, { seed: seed + 5, t, alpha: 0.85, layers: 2 });
    ctx.save();
    ctx.font = '700 24px "Source Han Sans CN", sans-serif';
    ctx.fillStyle = stroke;
    ctx.textAlign = 'center';
    ctx.fillText(label || '', x + w / 2, y - 16);
    ctx.fillText(Math.round(clamped * 100) + '%', x + w / 2, y + h + 34);
    ctx.restore();
  }

  root.SKETCH = { rng, boilSeed, line, blob, roundedBox, arrow, paper, risoHalftone, monster, icon, gauge };
})(typeof window !== 'undefined' ? window : globalThis);
