// step_tree_focus: SVG stroke-grown workflow tree with seek-safe focus jumps between branches.
const branches = all('.tree-branch');
const children = all('.tree-child');
const links = all('.tree-link');
const stems = all('.tree-stem');

const heading = q('.editorial-heading');
if (heading) {
  tl.fromTo(heading, { x: -24, opacity: 0 }, { x: 0, opacity: 1, duration: 0.38, ease: 'power3.out' }, 0.03);
}

branches.forEach((box, i) => {
  const b = (data.branches || [])[i] || {};
  const at = typeof b.at === 'number' ? b.at : 0.18 + i * 1.4;
  tl.fromTo(box, { y: 28, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42, ease: 'power3.out' }, at);
  if (links[i - 1]) {
    tl.fromTo(links[i - 1], { strokeDashoffset: 1, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.45, ease: 'power2.inOut' }, Math.max(0.05, at - 0.35));
  }
});

let childCursor = 0;
(data.branches || []).forEach((b) => {
  (b.children || []).forEach((c) => {
    const el = children[childCursor];
    const stem = stems[childCursor];
    const at = typeof c.at === 'number' ? c.at : 0.8 + childCursor * 0.35;
    if (stem) {
      tl.fromTo(stem, { strokeDashoffset: 1, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.28, ease: 'power2.out' }, Math.max(0.05, at - 0.16));
    }
    if (el) {
      tl.fromTo(el, { y: -16, scale: 0.82, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.32, ease: 'back.out(1.5)' }, at);
    }
    childCursor += 1;
  });
});

// Deterministic focus jumps across branches, 100% pure function of tNow so seeking is reversible.
const seq = (data.focus_sequence && data.focus_sequence.length)
  ? data.focus_sequence
  : [{ index: 0, at: 0.35 }];

function applyFocusAt(tNow) {
  let active = -1;
  let activeAt = 0;
  for (const item of seq) {
    if (tNow >= item.at - 1e-4) {
      active = item.index;
      activeAt = item.at;
    }
  }
  const pop = active >= 0 ? Math.min(1, Math.max(0, (tNow - activeAt) / 0.22)) : 0;
  const eased = 1 - Math.pow(1 - pop, 3);
  branches.forEach((b, k) => {
    const focused = k === active;
    b.classList.toggle('is-focused', focused);
    const s = focused ? (1 + 0.045 * eased) : 1;
    b.style.scale = String(s);
  });
}
applyFocusAt(0);

const focusDriver = { p: 0 };
tl.to(focusDriver, {
  p: 1, duration: dur, ease: 'none',
  onUpdate: () => applyFocusAt(tl.time())
}, 0);

tl.fromTo(cam, { x: -12, y: 8, z: -20 }, { x: 14, y: -4, z: 32, duration: dur, ease: 'sine.inOut', onUpdate: applyCamera }, 0);
