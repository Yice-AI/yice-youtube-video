// progressive_sim_cards (v13): Sac-style 0.19s crisp snap-in cards with steady hold & fast race bar lock.
const cards = all('.sim-card');
const heading = q('.sim-heading');
if (heading) {
  tl.fromTo(heading, { y: -14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.18, ease: 'expo.out' }, 0.02);
}

cards.forEach((card, i) => {
  const cfg = (data.cards || [])[i] || {};
  const at = typeof cfg.at === 'number' ? cfg.at : 0.12 + i * 0.65;
  if (data.board) {
    if (cfg.reveal !== false) {
      const panel = card.querySelector('.sim-panel');
      tl.fromTo(panel, { filter: 'saturate(.4) brightness(.8)', scale: .96 },
        { filter: 'saturate(1) brightness(1)', scale: 1, duration: .24, ease: 'expo.out' }, at);
      tl.fromTo(card.querySelector('.sim-label'), { color: '#ff4d1c', x: 10 },
        { color: '#111215', x: 0, duration: .45, ease: 'power2.out', immediateRender: false }, at);
    }
  } else tl.fromTo(card,
    { y: 26, z: -40, scale: 0.9, opacity: 0 },
    { y: 0, z: 0, scale: 1, opacity: 1, duration: 0.2, ease: 'expo.out' },
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
      p: fastEnd, duration: 0.36, ease: 'expo.out',
      onUpdate: () => {
        fastFill.style.width = fastVal.p.toFixed(1) + '%';
        if (fastPct) fastPct.textContent = Math.round(fastVal.p) + '%';
      }
    }, at + 0.08);
  }
});

tl.fromTo(cam, { x: 0, y: 4, z: -14, ry: 0 }, { x: 0, y: 0, z: 12, ry: 0, duration: dur, ease: 'sine.out', onUpdate: applyCamera }, 0);

// Keep the revealed evidence centered until the next card needs its column.
if (root.dataset.stageLook === 'swiss_paper' && !data.board && cards.length > 1) {
  const row = q('.sim-row');
  const shiftFor = i => row.clientWidth / 2 - (cards[0].offsetLeft + cards[i].offsetLeft + cards[i].offsetWidth) / 2;
  tl.set(cards, { x: shiftFor(0) }, 0);
  cards.slice(1).forEach((card, index) => {
    const i = index + 1;
    const at = data.cards[i].at ?? (.12 + i * .65);
    tl.to(cards, { x: shiftFor(i), duration: .18, ease: 'power3.out' }, at);
  });
}

cards.forEach((card,i) => {
  const pages = card.querySelectorAll('.sim-page');
  (data.cards[i].pages || []).forEach((page,k) => {
    tl.set(pages[k], {visibility:'visible'}, page.at);
    if (k) tl.set(pages[k-1], {visibility:'hidden'}, page.at);
  });
  const outlines = card.querySelectorAll('.panel-accents i');
  (data.cards[i].panel_accents || []).forEach((at,k) => {
    tl.fromTo(outlines[k], {opacity:1}, {opacity:0,duration:.28,immediateRender:false}, at);
  });
});
