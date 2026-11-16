  c.root.classList.add("r-chap");
  Y.stage(c);
  var no = Y.el("div", "no", c.cam, s.no || ""); tl.fromTo(no, { opacity: 0, x: -40 }, { opacity: 1, x: 0, duration: 0.6, ease: "power3.out" }, 0.0);
  var ti = Y.el("div", "ti", c.cam); Y.write(tl, ti, s.title || "", 0.15, { per: 0.07 });
  var ru = Y.el("div", "rule", c.cam); tl.fromTo(ru, { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.inOut" }, 0.45);
  if (s.sub) { var sb = Y.el("div", "sub", c.cam, s.sub); Y.fadeUp(tl, sb, 0.6, { y: 8 }); }
  var toc = Y.el("div", "toc", c.cam);
  (s.list || []).forEach(function (r, i) { var e = Y.el("div", "r" + (i === s.current ? " on" : ""), toc, "<b>" + r.no + "</b><span>" + r.title + "</span>"); tl.fromTo(e, { opacity: 0, x: 30 }, { opacity: i === s.current ? 1 : 0.6, x: 0, duration: 0.35, ease: "power2.out" }, 0.1 + i * 0.05); });
  var sw = Y.el("div", "sweep", c.cam); tl.fromTo(sw, { x: -700 }, { x: 2400, duration: Math.min(2.2, c.dur), ease: "sine.inOut" }, 0);
  Y.camera(c, [{ at: 0, x: 960, y: 540, s: 1.0 }, { at: 0.1, x: 900, y: 560, s: 1.04, d: Math.max(1, c.dur - 0.2), ease: "none" }]);
  Y.hud(c);
