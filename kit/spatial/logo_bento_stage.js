// logo_bento_stage (v13): Sac-style 0.18s snappy module & per-item word-synced landing with steady hold.
const cols = all('.bento-col');
const brand = q('.bento-brand');
if (brand) {
  tl.fromTo(brand, { y: -16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.2, ease: 'expo.out' }, 0.02);
}
cols.forEach((col, i) => {
  const mod = (data.modules && data.modules[i]) || {};
  const at = typeof mod.at === 'number' ? mod.at : 0.12 + i * 0.28;
  tl.fromTo(col,
    { y: 28, z: -60, scale: 0.9, opacity: 0 },
    { y: 0, z: 0, scale: 1, opacity: 1, duration: 0.21, ease: 'expo.out' },
    at);
  const items = col.querySelectorAll('.bento-item');
  const modItems = mod.items || [];
  items.forEach((el, j) => {
    const cfg = modItems[j];
    const itemAt = (cfg && typeof cfg === 'object' && typeof cfg.at === 'number') ? cfg.at : (at + 0.06 + j * 0.09);
    tl.fromTo(el,
      { y: 14, opacity: 0, scale: 0.94 },
      { y: 0, opacity: 1, scale: 1, duration: 0.18, ease: 'expo.out' },
      itemAt);
  });
});
all('.bento-spin').forEach((mark, idx) => {
  tl.fromTo(mark, { rotation: 0 }, { rotation: idx % 2 ? -90 : 90, duration: dur, ease: 'none' }, 0);
});
tl.fromTo(cam, { x: 0, y: 4, z: -18, ry: 0 }, { x: 0, y: 0, z: 14, ry: 0, duration: dur, ease: 'sine.out', onUpdate: applyCamera }, 0);

for (const focus of data.focus_sequence || []) {
  const label = cols[focus.index].querySelector('.bento-cat');
  tl.fromTo(label, {color:'#ff4d1c',scale:1.06},
    {color:'#111215',scale:1,duration:.40,ease:'power2.out',immediateRender:false}, focus.at);
}
