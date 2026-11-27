// logo_bento_stage: staggered brand bento modules with spring landing and rotating core mark.
const cols = all('.bento-col');
const brand = q('.bento-brand');
if (brand) {
  tl.fromTo(brand, { y: -24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42, ease: 'power3.out' }, 0.04);
}
cols.forEach((col, i) => {
  const at = (data.modules && data.modules[i] && typeof data.modules[i].at === 'number') ? data.modules[i].at : 0.2 + i * 0.38;
  tl.fromTo(col,
    { y: 65, z: -130, rotationX: 16, scale: 0.82, opacity: 0 },
    { y: 0, z: 0, rotationX: 0, scale: 1, opacity: 1, duration: Math.min(0.65, dur * 0.24), ease: 'back.out(1.45)' },
    at);
  const items = col.querySelectorAll('.bento-item');
  tl.fromTo(items,
    { y: 20, opacity: 0, scale: 0.92 },
    { y: 0, opacity: 1, scale: 1, duration: 0.35, stagger: 0.11, ease: 'power2.out' },
    at + 0.12);
});
all('.bento-spin').forEach((mark, idx) => {
  tl.fromTo(mark, { rotation: 0 }, { rotation: idx % 2 ? -180 : 180, duration: dur, ease: 'none' }, 0);
});
tl.fromTo(cam, { x: -30, y: 16, z: -65, ry: 4 }, { x: 24, y: -6, z: 55, ry: -3, duration: dur, ease: 'sine.inOut', onUpdate: applyCamera }, 0);
