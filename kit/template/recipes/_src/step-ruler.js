  c.root.classList.add("r-ruler");
  Y.stage(c);
  if (s.kicker) { var kk = Y.el("div", "kick", c.cam, s.kicker); Y.fadeUp(tl, kk, 0.1, { y: 8 }); }
  var wd = Y.el("div", "word", c.cam); if (s.word) Y.write(tl, wd, s.word.text, c.at(s.word.at, 0.2));
  var rl = Y.el("div", "rl", c.cam), base = Y.el("div", "base", rl), tk = Y.el("div", "ticks", rl);
  tl.fromTo([base, tk], { scaleX: 0 }, { scaleX: 1, duration: 0.7, ease: "power2.inOut", stagger: 0.08 }, 0.05);
  var steps = s.steps || [], L = 1580, xs = steps.map(function (_, i) { return Math.round(L * (i * 2 + 1) / (steps.length * 2)); });
  var labs = [];
  steps.forEach(function (lab, i) {
    var mj = Y.el("div", "maj", rl); Y.css(mj, { left: xs[i] - 1 });
    var nm = Y.el("div", "num", rl, "0" + (i + 1)); Y.css(nm, { left: xs[i] });
    var lb = Y.el("div", "lab" + (i === s.active ? " on" : ""), rl, lab); labs.push(lb);
    tl.fromTo([mj, nm, lb], { opacity: 0, y: 12 }, { opacity: 1, y: 0, duration: 0.4, ease: "power2.out", stagger: 0.05 }, 0.35 + i * 0.12);
  });
  // center labels under their tick after layout-independent estimate (font-size 62, CJK square glyphs)
  labs.forEach(function (lb, i) { var w = Array.from(steps[i]).length * 62; Y.css(lb, { left: xs[i] - w / 2 }); });
  (s.done || []).forEach(function (i) { var ck = Y.el("div", "chk", rl, "✓"); Y.css(ck, { left: xs[i] + Array.from(steps[i]).length * 31 + 14 }); Y.fadeUp(tl, ck, 0.9, { y: 6 }); });
  (s.ticks || []).forEach(function (q) { var ck = Y.el("div", "chk", rl, "✓"); Y.css(ck, { left: xs[q.i] + Array.from(steps[q.i]).length * 31 + 14 }); Y.fadeUp(tl, ck, c.at(q.at, 1), { y: 6 }); });
  var ta = c.at(s.at, 0.9), sv = Y.svg(rl); sv.style.overflow = "visible";
  if (s.active != null) {
    var ptr = Y.el("div", "ptr", rl);
    tl.fromTo(ptr, { left: 0, opacity: 0 }, { left: xs[s.active], opacity: 1, duration: 0.8, ease: "power3.inOut" }, Math.max(0.2, ta - 0.6));
    var w = Array.from(steps[s.active]).length * 62;
    Y.ellipse(sv, tl, { x: xs[s.active] - w / 2, y: 80, w: w, h: 66 }, ta + 0.2, { color: c.stage === "charcoal" ? "#7EA1FF" : "var(--blue)" });
    Y.camera(c, [{ at: 0, x: 960, y: 540, s: 1 }, { at: ta, x: 170 + xs[s.active] * 0.5 + 480, y: 560, s: 1.08, d: 1.4, ease: "sine.inOut" }]);
  }
  var rd = Y.el("div", "read", c.cam, s.readout || ("STEP 0" + ((s.active || 0) + 1) + " / 0" + steps.length));
  Y.fadeUp(tl, rd, 0.9, { y: 6 });
  Y.hud(c);
