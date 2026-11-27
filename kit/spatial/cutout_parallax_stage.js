// cutout_parallax_stage: 3-layer paper-cutout parallax theatre with tile flips, counter & dust motes.
const plaque = q('.hanging-plaque');
const tiles = all('.poem-tile');
const props = all('.parallax-prop');
const hero = q('.parallax-hero');
const mountains = q('.parallax-mountains');
const counterEl = q('.torn-main .cnt');
const counterCfg = data.counter || null;

// Deterministic dust particle renderer driven by GSAP timeline progress.
const dustCanvas = q('.dust-canvas');
const dctx = dustCanvas ? dustCanvas.getContext('2d') : null;
const dustPuffs = Array.from({ length: 18 }, (_, i) => ({
  phase: (i * 0.6180339) % 1,
  r: 14 + (i % 5) * 7,
  dy: ((i * 37) % 36) - 18,
  alpha: 0.22 + (i % 4) * 0.08
}));

function renderDust(progress) {
  if (!dctx) return;
  dctx.clearRect(0, 0, 1920, 1080);
  const heroRect = hero ? hero.getBoundingClientRect() : null;
  const originX = 760 + progress * 80;
  const originY = 805;
  dustPuffs.forEach((p) => {
    const life = (progress * 2.8 + p.phase) % 1;
    const x = originX - life * 290;
    const y = originY + p.dy - Math.sin(life * Math.PI) * 26;
    const rad = p.r * (0.55 + life * 0.9);
    const op = Math.sin(life * Math.PI) * p.alpha;
    dctx.fillStyle = `rgba(247, 239, 220, ${op.toFixed(3)})`;
    dctx.beginPath();
    dctx.arc(x, y, rad, 0, Math.PI * 2);
    dctx.fill();
  });
}

if (plaque) {
  tl.fromTo(plaque, { rotation: -4, y: -24, opacity: 0 }, { rotation: 0, y: 0, opacity: 1, duration: 0.55, ease: 'back.out(1.4)' }, 0.04);
}
tiles.forEach((tile, i) => {
  const at = 0.25 + i * Math.min(0.24, (dur * 0.46) / Math.max(1, tiles.length));
  tl.fromTo(tile,
    { rotationX: -88, y: 24, opacity: 0, scale: 0.84 },
    { rotationX: 0, y: 0, opacity: 1, scale: 1, duration: 0.38, ease: 'back.out(1.5)' },
    at);
});
if (counterEl && counterCfg) {
  const numState = { v: counterCfg.start };
  tl.fromTo(q('.torn-counter'), { x: 40, opacity: 0 }, { x: 0, opacity: 1, duration: 0.45, ease: 'power3.out' }, 0.15);
  tl.to(numState, {
    v: counterCfg.end, duration: dur * 0.85, ease: 'power1.inOut',
    onUpdate: () => { counterEl.textContent = String(Math.round(numState.v)); }
  }, 0.15);
}
if (mountains) {
  tl.fromTo(mountains, { x: 40, z: -30 }, { x: -240, z: -30, duration: dur, ease: 'none' }, 0);
}
props.forEach((prop, i) => {
  const startX = i === 0 ? 55 : (i === 1 ? 1510 : 840);
  const travel = i === 0 ? -180 : -230;
  const pz = i === 2 ? 12 : (32 + i * 16);
  tl.fromTo(prop, { x: startX, z: pz }, { x: startX + travel, z: pz, duration: dur, ease: 'none' }, 0);
});
if (hero) {
  tl.set(hero, { x: -85, y: 0, rotation: 0, z: 72 }, 0);
  const gallopSteps = 24;
  for (let s = 0; s < gallopSteps; s++) {
    const p0 = s / gallopSteps, p1 = (s + 1) / gallopSteps;
    const t0 = p0 * dur, segDur = dur / gallopSteps;
    const bob = -Math.abs(Math.sin(p1 * Math.PI * 5.5)) * 18;
    const tilt = Math.sin(p1 * Math.PI * 5.5) * 2.2;
    const hx = -85 + p1 * 115;
    tl.to(hero, { x: hx, y: bob, rotation: tilt, z: 72, duration: segDur, ease: 'sine.inOut' }, t0);
  }
}
const dustDriver = { p: 0 };
tl.to(dustDriver, { p: 1, duration: dur, ease: 'none', onUpdate: () => renderDust(dustDriver.p) }, 0);
tl.fromTo(cam, { x: -18, y: 6, z: -40, ry: 2 }, { x: 18, y: -4, z: 32, ry: -2, duration: dur, ease: 'sine.inOut', onUpdate: applyCamera }, 0);
