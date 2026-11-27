// documentary_ken_burns: 2.5D museum Ken Burns with floating golden dust and optional 1-to-3 anatomy split.
const frame = q('.doc-frame');
const painting = q('.doc-painting');
const plaque = q('.doc-plaque');
const header = q('.doc-header');
const anatomyRow = q('.doc-anatomy-row');
const anatomyCards = all('.doc-anatomy-card');
const fromPose = data.focal_from || [0.38, 0.42, 1.36];
const toPose = data.focal_to || [0.52, 0.50, 1.06];
const splitAt = (data.split_at && anatomyCards.length === 3) ? data.split_at : null;

const dustCanvas = q('.dust-canvas');
const dctx = dustCanvas ? dustCanvas.getContext('2d') : null;
const motes = Array.from({ length: 56 }, (_, i) => ({
  x: ((i * 197 + 43) % 1620) + 150,
  y: ((i * 131 + 89) % 780) + 120,
  r: 1.4 + (i % 4) * 1.1,
  vx: ((i % 7) - 3) * 14,
  vy: -22 - (i % 5) * 11,
  phase: (i * 0.37) % 1
}));

function drawGoldDust(p) {
  if (!dctx) return;
  dctx.clearRect(0, 0, 1920, 1080);
  motes.forEach((m) => {
    const x = m.x + m.vx * p;
    const y = m.y + m.vy * p;
    const pulse = 0.25 + 0.55 * (0.5 + 0.5 * Math.sin((p * 3 + m.phase) * Math.PI * 2));
    const grad = dctx.createRadialGradient(x, y, 0, x, y, m.r * 3.2);
    grad.addColorStop(0, `rgba(255, 232, 165, ${pulse.toFixed(3)})`);
    grad.addColorStop(1, 'rgba(255, 210, 120, 0)');
    dctx.fillStyle = grad;
    dctx.beginPath();
    dctx.arc(x, y, m.r * 3.2, 0, Math.PI * 2);
    dctx.fill();
  });
}

function focalTransform(pose) {
  const [fx, fy, sc] = pose;
  const tx = (0.5 - fx) * 420;
  const ty = (0.5 - fy) * 240;
  return { x: tx, y: ty, scale: sc };
}

if (header) {
  tl.fromTo(header, { y: -16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.45, ease: 'power3.out' }, 0.04);
}
if (plaque) {
  tl.fromTo(plaque, { x: -24, opacity: 0 }, { x: 0, opacity: 1, duration: 0.5, ease: 'power3.out' }, 0.14);
}

const kbEnd = splitAt || dur;
tl.fromTo(painting, focalTransform(fromPose), { ...focalTransform(toPose), duration: kbEnd, ease: 'sine.inOut' }, 0);
tl.fromTo(frame, { scale: 0.97, z: -40 }, { scale: 1, z: 20, duration: kbEnd, ease: 'sine.inOut' }, 0);

if (splitAt) {
  tl.to(frame, { opacity: 0, scale: 0.92, z: -140, duration: 0.42, ease: 'power2.in' }, splitAt);
  if (plaque) tl.to(plaque, { opacity: 0, duration: 0.14, ease: 'power2.out' }, splitAt);
  if (anatomyRow) {
    tl.fromTo(anatomyRow, { opacity: 0 }, { opacity: 1, duration: 0.1 }, splitAt + 0.15);
  }
  anatomyCards.forEach((card, i) => {
    const dir = i - 1;
    tl.fromTo(card,
      { x: dir * -110, y: 48, z: -180, rotationY: dir * -14, scale: 0.82, opacity: 0 },
      { x: 0, y: 0, z: i === 1 ? 36 : 0, rotationY: dir * -6, scale: 1, opacity: 1, duration: 0.62, ease: 'back.out(1.35)' },
      splitAt + 0.18 + i * 0.12);
  });
}

const dustDriver = { p: 0 };
tl.to(dustDriver, { p: 1, duration: dur, ease: 'none', onUpdate: () => drawGoldDust(dustDriver.p) }, 0);
tl.fromTo(cam, { x: -16, y: 10, z: -30, ry: 2.5 }, { x: 16, y: -8, z: 45, ry: -2.5, duration: dur, ease: 'sine.inOut', onUpdate: applyCamera }, 0);
