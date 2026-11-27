// perspective_video_fan: 3D tilted video wall fan gliding across Z depth before focusing hero card.
const fanCards = all('.fan-card');
const focusIndex = data.focus_index ?? Math.min(2, fanCards.length - 1);
const focusAt = data.focus_at ?? dur * 0.48;

function fanPose(i, progress) {
  const rel = i - focusIndex + (1 - progress) * 1.15;
  const x = rel * 320;
  const z = -Math.abs(rel) * 130 + (i === focusIndex ? 45 : 0);
  const y = Math.abs(rel) * 18 - 10;
  const ry = -26 + rel * 2.5;
  const depthNorm = Math.max(0, 1 - Math.abs(rel) * 0.22);
  return {
    x, y, z, rotationY: ry, rotationX: 4, scale: 0.94 + depthNorm * 0.08,
    opacity: 0.45 + 0.55 * depthNorm,
    '--light': 0.68 + 0.32 * depthNorm,
    '--dof': (Math.abs(rel) * 1.1).toFixed(2) + 'px'
  };
}

fanCards.forEach((card, i) => {
  tl.set(card, fanPose(i, 0), 0);
  const steps = 16;
  for (let s = 1; s <= steps; s++) {
    tl.to(card, { ...fanPose(i, s / steps), duration: focusAt / steps, ease: 'none' }, (s - 1) * focusAt / steps);
  }
  if (i === focusIndex) {
    tl.to(card, {
      x: 0, y: 42, z: 220, rotationY: 0, rotationX: 0, scale: 1.09,
      opacity: 1, '--light': 1.04, '--dof': '0px',
      duration: Math.max(0.45, dur - focusAt), ease: 'power3.inOut'
    }, focusAt);
    tl.fromTo(card, { '--sweep': '180%' }, { '--sweep': '-55%', duration: (dur - focusAt) * 0.65, ease: 'sine.inOut' }, focusAt + (dur - focusAt) * 0.18);
  } else {
    const endPose = fanPose(i, 1);
    const dir = i < focusIndex ? -1 : 1;
    tl.to(card, {
      x: endPose.x + dir * 240, y: endPose.y + 30, z: -480,
      rotationY: dir * -32, opacity: 0.24, '--dof': '5px',
      duration: Math.max(0.4, (dur - focusAt) * 0.8), ease: 'power2.inOut'
    }, focusAt);
  }
});

tl.fromTo(q('.fan-badge'), { y: -18, opacity: 0, scale: 0.86 }, { y: 0, opacity: 1, scale: 1, duration: Math.min(0.45, dur * 0.16), ease: 'back.out(1.5)' }, 0.05);
tl.fromTo(cam, { x: -48, y: 12, z: -90, ry: 7, rx: -3 }, { x: 0, y: 0, z: 36, ry: 0, rx: 0, duration: dur, ease: 'power2.inOut', onUpdate: applyCamera }, 0);
