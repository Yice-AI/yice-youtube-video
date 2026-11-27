// formula_pill_chain: centered source pill slides left, shoots arrow & target pill while media plays below.
const srcPill = q('.pill-src');
const arrow = q('.chain-arrow path');
const dstPill = q('.pill-dst');
const frame = q('.chain-frame');
const revealAt = data.reveal_at ?? dur * 0.34;

if (srcPill) {
  tl.fromTo(srcPill, { scale: 0.85, opacity: 0, x: 180 }, { scale: 1, opacity: 1, x: 180, duration: 0.38, ease: 'back.out(1.4)' }, 0.04);
  tl.to(srcPill, { x: 0, duration: 0.42, ease: 'power3.inOut' }, revealAt);
}
if (arrow) {
  tl.fromTo(arrow, { strokeDashoffset: 1, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.3, ease: 'power2.out' }, revealAt + 0.12);
}
if (dstPill) {
  tl.fromTo(dstPill, { x: -34, scale: 0.78, opacity: 0 }, { x: 0, scale: 1, opacity: 1, duration: 0.44, ease: 'back.out(1.5)' }, revealAt + 0.18);
}
if (frame) {
  tl.fromTo(frame, { y: 26, z: -45, rotationX: 4, scale: 0.95, opacity: 0 }, { y: 0, z: 18, rotationX: 0, scale: 1, opacity: 1, duration: 0.55, ease: 'power3.out' }, 0.08);
}
tl.fromTo(cam, { x: -14, y: 10, z: -20, ry: 2 }, { x: 14, y: -6, z: 38, ry: -2, duration: dur, ease: 'sine.inOut', onUpdate: applyCamera }, 0);
