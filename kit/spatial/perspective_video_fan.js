// perspective_video_fan (v13): snappy 16:9 widescreen 3D video fan with crisp 0.24s hero snap & optional glass punch.
const fanCards = all('.fan-card');
const focusIndex = data.focus_index ?? Math.min(2, fanCards.length - 1);
const focusAt = data.focus_at ?? dur * 0.42;
const portrait = data.card_aspect === 'portrait';
const spreadX = portrait ? 310 : 390;

function fanPose(i, progress) {
  const rel = i - focusIndex + (1 - progress) * 0.95;
  const x = rel * spreadX;
  const z = -Math.abs(rel) * 145 + (i === focusIndex ? 50 : 0);
  const y = Math.abs(rel) * 14 - 8;
  const ry = -22 + rel * 3.2;
  const depthNorm = Math.max(0, 1 - Math.abs(rel) * 0.22);
  return {
    x, y, z, rotationY: ry, rotationX: 3, scale: 0.92 + depthNorm * 0.08,
    opacity: 0.48 + 0.52 * depthNorm,
    '--light': 0.72 + 0.28 * depthNorm,
    '--dof': (Math.abs(rel) * 1.1).toFixed(2) + 'px'
  };
}

fanCards.forEach((card, i) => {
  tl.set(card, fanPose(i, 0), 0);
  const steps = 14;
  for (let s = 1; s <= steps; s++) {
    tl.to(card, { ...fanPose(i, s / steps), duration: focusAt / steps, ease: 'none' }, (s - 1) * focusAt / steps);
  }
  if (i === focusIndex) {
    tl.to(card, {
      x: 0, y: portrait ? 36 : 18, z: 235, rotationY: 0, rotationX: 0, scale: portrait ? 1.08 : 1.32,
      opacity: 1, '--light': 1.04, '--dof': '0px',
      duration: 0.26, ease: 'expo.out'
    }, focusAt);
    tl.fromTo(card, { '--sweep': '180%' }, { '--sweep': '-55%', duration: 0.42, ease: 'power2.out' }, focusAt + 0.04);
  } else {
    const endPose = fanPose(i, 1);
    const dir = i < focusIndex ? -1 : 1;
    tl.to(card, {
      x: endPose.x + dir * (portrait ? 240 : 340), y: endPose.y + 24, z: -520,
      rotationY: dir * -30, opacity: 0.16, '--dof': '6px',
      duration: 0.28, ease: 'expo.out'
    }, focusAt);
  }
});

const punch = q('.fan-punch');
const punchBox = q('.fan-punch-box');
if (punch && typeof data.punch_at === 'number') {
  tl.fromTo(punch, { opacity: 0 }, { opacity: 1, duration: 0.16, ease: 'power3.out' }, data.punch_at);
  if (punchBox) {
    tl.fromTo(punchBox, { scale: 0.86, y: 20 }, { scale: 1, y: 0, duration: 0.2, ease: 'expo.out' }, data.punch_at);
  }
}

tl.fromTo(q('.fan-badge'), { y: -14, opacity: 0, scale: 0.9 }, { y: 0, opacity: 1, scale: 1, duration: 0.2, ease: 'expo.out' }, 0.03);
tl.fromTo(cam, { x: -24, y: 6, z: -50, ry: 4, rx: -2 }, { x: 0, y: 0, z: 18, ry: 0, rx: 0, duration: Math.min(dur, focusAt + 0.35), ease: 'power3.out', onUpdate: applyCamera }, 0);
