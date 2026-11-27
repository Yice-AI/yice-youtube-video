// formula_pill_chain (v13): snappy 0.18s pill snap + arrow shoot with rock-steady frame below.
const srcPill = q('.pill-src');
const arrow = q('.chain-arrow path');
const dstPill = q('.pill-dst');
const frame = q('.chain-frame');
const revealAt = data.reveal_at ?? dur * 0.32;

if (srcPill) {
  tl.fromTo(srcPill, { scale: 0.9, opacity: 0, x: 170 }, { scale: 1, opacity: 1, x: 170, duration: 0.18, ease: 'expo.out' }, 0.02);
  tl.to(srcPill, { x: 0, duration: 0.22, ease: 'expo.out' }, revealAt);
}
if (arrow) {
  tl.fromTo(arrow, { strokeDashoffset: 1, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.16, ease: 'expo.out' }, revealAt + 0.06);
}
if (dstPill) {
  tl.fromTo(dstPill, { x: -20, scale: 0.88, opacity: 0 }, { x: 0, scale: 1, opacity: 1, duration: 0.2, ease: 'expo.out' }, revealAt + 0.1);
}
if (frame) {
  tl.fromTo(frame, { y: 20, scale: 0.96, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.24, ease: 'expo.out' }, 0.05);
}
tl.fromTo(cam, { x: 0, y: 4, z: -12 }, { x: 0, y: 0, z: 12, duration: dur, ease: 'sine.out', onUpdate: applyCamera }, 0);
