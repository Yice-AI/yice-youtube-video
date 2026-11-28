// chapter_drawer_grid (v16): recurring mental-model cabinet (3-6 drawers) with 3D active drawer pull-out.
const heading = q('.drawer-heading');
const cells = all('.drawer-cell');
if (heading) {
  tl.fromTo(heading, { y: -14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.2, ease: 'expo.out' }, 0.02);
}
const drawers = data.drawers || [];
cells.forEach((cell, i) => {
  const d = drawers[i] || {};
  const at = typeof d.at === 'number' ? d.at : 0.1 + i * 0.14;
  tl.fromTo(cell, { y: 24, scale: 0.94, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.22, ease: 'back.out(1.4)' }, at);
});
const activeIdx = typeof data.active_index === 'number' ? data.active_index : -1;
const openAt = typeof data.open_at === 'number' ? data.open_at : Math.min(dur * 0.44, 0.9);
if (activeIdx >= 0 && cells[activeIdx]) {
  cells.forEach((cell, i) => {
    if (i === activeIdx) {
      tl.to(cell, { z: 42, scale: 1.05, y: -6, duration: 0.26, ease: 'back.out(1.6)' }, openAt);
    } else {
      tl.to(cell, { opacity: 0.46, scale: 0.97, duration: 0.24, ease: 'power2.out' }, openAt);
    }
  });
  if (data.exit_zoom_active) {
    zoomToFrame(cells[activeIdx], [heading, ...cells.filter((_, k) => k !== activeIdx)]);
  }
}
tl.fromTo(
  cam,
  { z: -18, rx: 1.5 },
  {
    z: 8,
    rx: 0,
    duration: dur,
    ease: 'sine.out',
    onUpdate: () => {
      applyCamera();
      if (activeIdx >= 0 && cells[activeIdx]) {
        cells[activeIdx].classList.toggle('is-open', tl.time() >= openAt);
      }
    },
  },
  0
);
