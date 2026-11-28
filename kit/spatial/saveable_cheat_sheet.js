// saveable_cheat_sheet (v16): high-save-rate end-of-episode screenshot summary table above subtitle safe zone.
const heading = q('.cheat-heading');
const pill = q('.cheat-save-pill');
const sheet = q('.cheat-sheet-card');
const rows = all('.cheat-row');

if (heading) {
  tl.fromTo(heading, { x: -18, opacity: 0 }, { x: 0, opacity: 1, duration: 0.2, ease: 'expo.out' }, 0.02);
}
if (sheet) {
  tl.fromTo(sheet, { y: 20, opacity: 0 }, { y: 0, opacity: 1, duration: 0.24, ease: 'power3.out' }, 0.05);
}
const cfgRows = data.rows || [];
rows.forEach((row, i) => {
  const r = cfgRows[i] || {};
  const at = typeof r.at === 'number' ? r.at : 0.18 + i * 0.16;
  tl.fromTo(row, { x: -16, opacity: 0 }, { x: 0, opacity: 1, duration: 0.2, ease: 'expo.out' }, at);
});
if (pill) {
  const badgeAt = typeof data.badge_at === 'number' ? data.badge_at : Math.min(dur * 0.42, 0.85);
  tl.fromTo(pill, { scale: 0.82, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.24, ease: 'back.out(1.8)' }, badgeAt);
}
tl.fromTo(cam, { z: -8 }, { z: 4, duration: dur, ease: 'sine.out', onUpdate: applyCamera }, 0);
