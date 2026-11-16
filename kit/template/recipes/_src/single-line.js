  c.root.classList.add("r-one");
  Y.stage(c);
  var x = s.x == null ? 150 : s.x, y = s.y == null ? 380 : s.y, size = s.size || 200, ta = c.at(s.at, 0.25);
  var t = Y.el("div", "t", c.cam); Y.css(t, { left: x, top: y, fontSize: size }); Y.write(tl, t, s.text || "", ta, { per: 0.1 });
  if (s.sub) { var sb = Y.el("div", "sub", c.cam, s.sub.text); Y.css(sb, { left: x + 6, top: y + size + 40 }); Y.fadeUp(tl, sb, c.at(s.sub.at, ta + 0.8), { y: 8 }); }
  var w = Array.from(s.text || "").length * size, sv = Y.svg(c.cam), mt = c.at(s.markAt, ta + 0.9);
  var blue = c.stage === "charcoal" ? "#7EA1FF" : "var(--blue)";
  if (s.mark === "circle") Y.ellipse(sv, tl, { x: x, y: y, w: w, h: size }, mt, { color: blue, w: 6 });
  else if (s.mark !== "none") Y.underline(sv, tl, { x: x, y: y + size + 14, w: w }, mt, { color: s.markColor || "var(--stamp)", w: 7 });
  if (s.clip && s.clip.text) { var ct = Y.el("div", "clip tx", c.cam), cq = s.clip; Y.css(ct, { left: cq.x, top: cq.y, width: cq.w }); ct.innerHTML = "<b>" + cq.text + "</b>" + (cq.sub ? "<small>" + cq.sub + "</small>" : ""); Y.tape(ct, cq.w * 0.45, -20, 4, 140); Y.drop(tl, ct, c.at(cq.at, 1.4), { rot: cq.rot || 2, y: -50 }); }
  else if (c.m(0) && s.clip) { var cl = Y.el("div", "clip", c.cam), cp = s.clip; Y.css(cl, { left: cp.x, top: cp.y, width: cp.w }); cl.appendChild(c.m(0)); Y.tape(cl, cp.w * 0.45, -20, 4, 140); Y.drop(tl, cl, c.at(cp.at, 1.4), { rot: cp.rot || 2, y: -50 }); }
  if (s.extras) Y.props(c, c.cam, s.extras, tl);
  Y.camera(c, [{ at: 0, x: 960, y: 540, s: 1 }, { at: 0.2, x: x + Math.min(w, 900) / 2 + 200, y: y + size / 2 + 60, s: 1.06, d: Math.max(1, c.dur - 0.4), ease: "none" }]);
  Y.hud(c);
