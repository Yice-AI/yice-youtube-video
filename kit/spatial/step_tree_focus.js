// step_tree_focus (v13): snappy 0.18s workflow branches & tags with crisp reversible focus snaps.
const branches = all('.tree-branch');
const children = all('.tree-child');
const links = all('.tree-link');
const stems = all('.tree-stem');

const heading = q('.editorial-heading');
if (heading) {
  tl.fromTo(heading, { x: -16, opacity: 0 }, { x: 0, opacity: 1, duration: 0.18, ease: 'expo.out' }, 0.02);
}

branches.forEach((box, i) => {
  const b = (data.branches || [])[i] || {};
  const at = typeof b.at === 'number' ? b.at : 0.12 + i * 1.1;
  tl.fromTo(box, { y: 18, scale: 0.94, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.2, ease: 'expo.out' }, at);
  if (links[i - 1]) {
    tl.fromTo(links[i - 1], { strokeDashoffset: 1, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.22, ease: 'expo.out' }, Math.max(0.03, at - 0.16));
  }
});

let childCursor = 0;
(data.branches || []).forEach((b) => {
  (b.children || []).forEach((c) => {
    const el = children[childCursor];
    const stem = stems[childCursor];
    const at = typeof c.at === 'number' ? c.at : 0.55 + childCursor * 0.26;
    if (stem) {
      tl.fromTo(stem, { strokeDashoffset: 1, opacity: 0 }, { strokeDashoffset: 0, opacity: 1, duration: 0.15, ease: 'power3.out' }, Math.max(0.03, at - 0.1));
    }
    if (el) {
      tl.fromTo(el, { y: -10, scale: 0.88, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.18, ease: 'expo.out' }, at);
    }
    childCursor += 1;
  });
});

const seq = (data.focus_sequence && data.focus_sequence.length)
  ? data.focus_sequence
  : [{ index: 0, at: 0.25 }];

function applyFocusAt(tNow) {
  let active = -1;
  let activeAt = 0;
  for (const item of seq) {
    if (tNow >= item.at - 1e-4) {
      active = item.index;
      activeAt = item.at;
    }
  }
  const pop = active >= 0 ? Math.min(1, Math.max(0, (tNow - activeAt) / 0.14)) : 0;
  const eased = 1 - Math.pow(1 - pop, 4);
  branches.forEach((b, k) => {
    const focused = k === active;
    b.classList.toggle('is-focused', focused);
    const s = focused ? (1 + 0.05 * eased) : 1;
    b.style.scale = String(s);
  });
}
applyFocusAt(0);

const focusDriver = { p: 0 };
tl.to(focusDriver, {
  p: 1, duration: dur, ease: 'none',
  onUpdate: () => applyFocusAt(tl.time())
}, 0);

tl.fromTo(cam, { x: 0, y: 4, z: -12 }, { x: 0, y: 0, z: 10, duration: dur, ease: 'sine.out', onUpdate: applyCamera }, 0);
