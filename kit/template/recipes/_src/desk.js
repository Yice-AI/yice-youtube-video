  c.root.classList.add("r-desk");
  Y.stage(c);
  (s.items || []).forEach(function (it, i) {
    var e, t = c.at(it.at, 0.1 + i * 0.18), im = it.m != null ? c.m(it.m) : null;
    if (it.kind === "prop") { e = im; e.classList.add("yf-prop"); if (it.round) e.style.borderRadius = "50%"; c.cam.appendChild(e); Y.css(e, { left: it.x, top: it.y, width: it.w }); }
    else if (it.kind === "photo") { e = Y.el("div", "ph", c.cam); Y.css(e, { left: it.x, top: it.y, width: it.w, height: it.h }); e.appendChild(im); }
    else if (it.kind === "screen") { e = Y.el("div", "yf-screen", c.cam); Y.css(e, { left: it.x, top: it.y, width: it.w, height: it.h }); var g = Y.el("div", "glass", e); g.appendChild(im); Y.el("div", "glare", e); }
    else if (it.kind === "card") { e = Y.card(c.cam, { x: it.x, y: it.y }); e.classList.add("dc"); Y.el("div", "tx", e, it.text); if (it.sub) Y.el("div", "sb", e, it.sub); }
    else { e = Y.el("div", "lbl", c.cam, it.text); Y.css(e, { left: it.x, top: it.y }); if (it.size) e.style.fontSize = it.size + "px"; if (it.font === "song") { e.style.fontFamily = "var(--f-song)"; e.style.fontWeight = 900; } }
    e.style.zIndex = it.z || (5 + i);
    if (it.tape) Y.tape(e, (it.w || 300) * 0.35, -20, (i % 2 ? 4 : -5), 140);
    Y.drop(tl, e, t, { rot: it.rot || 0, y: -60 - (i % 3) * 20, spin: (i % 2 ? -3 : 3) });
  });
  Y.camera(c, s.keys || [{ at: 0, x: 960, y: 540, s: 0.86 }, { at: 1.2, x: 960, y: 540, s: 1.0, d: Math.max(1.5, c.dur - 1.4), ease: "sine.inOut" }], { cover: false });
  if (s.title) Y.label(c, s.title);
  Y.hud(c);
