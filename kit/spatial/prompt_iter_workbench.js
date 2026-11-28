const before = q('.workbench-frame.before');
const after = q('.workbench-frame.after');
all('.workbench-chip').forEach((chip, i) => {
  tl.fromTo(chip, {opacity:0, y:18, scale:.96}, {opacity:1, y:0, scale:1, duration:.18, ease:'expo.out'}, data.prompt_chips[i].at);
});
tl.fromTo(after, {clipPath:'inset(0 100% 0 0)', opacity:0}, {clipPath:'inset(0 0% 0 0)', opacity:1, duration:.18, ease:'expo.out'}, data.iter_at);
tl.set(before, {visibility:'hidden'}, data.iter_at + .18);
const badge = q('.workbench-label');
tl.fromTo(badge, {textContent:badge.textContent}, {textContent:badge.dataset.after, duration:0, immediateRender:false}, data.iter_at);
if (data.exit_zoom_after) zoomToFrame(after, all('.workbench-heading,.workbench-chips,.workbench-label'));
