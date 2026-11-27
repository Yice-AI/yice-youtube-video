// progressive_sim_cards: progressive 1 -> 2 -> 3 device showcase cards with live race bars & media.
const cards = all('.sim-card');
const heading = q('.sim-heading');
if (heading) {
  tl.fromTo(heading, { y: -22, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42, ease: 'power3.out' }, 0.03);
}

cards.forEach((card, i) => {
  const cfg = (data.cards || [])[i] || {};
  const at = typeof cfg.at === 'number' ? cfg.at : 0.15 + i * 0.85;
  tl.fromTo(card,
    { y: 48, z: -80, scale: 0.84, opacity: 0 },
    { y: 0, z: 0, scale: 1, opacity: 1, duration: 0.48, ease: 'back.out(1.45)' },
    at);

  const slowFill = card.querySelector('.sim-bar-fill.is-slow');
  const fastFill = card.querySelector('.sim-bar-fill.is-fast');
  const slowPct = card.querySelector('.sim-pct-slow');
  const fastPct = card.querySelector('.sim-pct-fast');
  if (slowFill && fastFill) {
    const slowEnd = cfg.slow_end ?? 26;
    const fastEnd = cfg.fast_end ?? 100;
    const slowVal = { p: 1 };
    const fastVal = { p: 0 };
    tl.to(slowVal, {
      p: slowEnd, duration: Math.max(0.6, dur - at), ease: 'none',
      onUpdate: () => {
        slowFill.style.width = slowVal.p.toFixed(1) + '%';
        if (slowPct) slowPct.textContent = Math.round(slowVal.p) + '%';
      }
    }, at);
    tl.to(fastVal, {
      p: fastEnd, duration: Math.min(0.62, Math.max(0.32, (dur - at) * 0.28)), ease: 'power3.out',
      onUpdate: () => {
        fastFill.style.width = fastVal.p.toFixed(1) + '%';
        if (fastPct) fastPct.textContent = Math.round(fastVal.p) + '%';
      }
    }, at + 0.16);
  }
});

tl.fromTo(cam, { x: -16, y: 8, z: -28, ry: 2 }, { x: 16, y: -4, z: 36, ry: -2, duration: dur, ease: 'sine.inOut', onUpdate: applyCamera }, 0);
