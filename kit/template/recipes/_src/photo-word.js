  c.root.classList.add("r-pw");
  Y.stage(c);
  var o = s.obj || { x: 760, y: 120, w: 1000, rot: 0 }, im = c.m(0), host;
  if (o.photo) { host = Y.el("div", "photo", c.cam); Y.css(host, { left: o.x, top: o.y, width: o.w }); host.appendChild(im); Y.tape(host, o.w / 2 - 80, -22, -3, 160); }
  else { host = im; im.classList.add("yf-prop"); c.cam.appendChild(im); Y.css(im, { left: o.x, top: o.y, width: o.w }); }
  if (o.static) { host.style.transform = "rotate(" + (o.rot || 0) + "deg)"; } else Y.drop(tl, host, c.at(o.at, 0.05), { rot: o.rot || 0, y: -70, scale: 1.08 });
  if (s.extras) Y.props(c, c.cam, s.extras, tl);
  if (s.texts) s.texts.forEach(function (tx, i) {
    var e = Y.el("div", "ovl", c.cam, tx.text); Y.css(e, { left: tx.x, top: tx.y, fontSize: tx.size || 56, transform: "translate(-50%,-50%) rotate(" + (tx.rot || 0) + "deg)", zIndex: 31 });
    if (tx.color) e.style.color = tx.color;
    Y.write(tl, e, tx.text, c.at(tx.at, 0.9 + i * 0.5));
  });
  if (s.clip && s.clip.text) {
    var ct = Y.el("div", "clip tx", c.cam), cq = s.clip; Y.css(ct, { left: cq.x, top: cq.y, width: cq.w }); ct.innerHTML = '<b>' + cq.text + '</b>' + (cq.sub ? '<small>' + cq.sub + '</small>' : "");
    Y.tape(ct, cq.w * 0.4, -20, 3, 140);
    Y.drop(tl, ct, c.at(cq.at, 1.2), { rot: cq.rot || -2, y: -50 });
  } else if (c.m(1) && s.clip) {
    var cl = Y.el("div", "clip", c.cam), cp = s.clip; Y.css(cl, { left: cp.x, top: cp.y, width: cp.w }); cl.appendChild(c.m(1));
    Y.tape(cl, cp.w * 0.4, -20, 3, 140);
    Y.drop(tl, cl, c.at(cp.at, 1.2), { rot: cp.rot || -2, y: -50 });
  }
  if (s.word) {
    var wd = Y.el("div", "word", c.cam), w = s.word; Y.css(wd, { left: w.x == null ? 150 : w.x, top: w.y == null ? 400 : w.y, fontSize: w.size || 190 });
    if (w.color) wd.style.color = w.color;
    if (w.static) wd.textContent = w.text; else Y.write(tl, wd, w.text, c.at(w.at, 0.5));
  }
  var sv = Y.svg(c.cam); sv.style.zIndex = 21;
  if (s.circle) {
    var cr = s.circle;
    Y.ellipse(sv, tl, cr, c.at(cr.at, 1), { color: cr.color || "var(--stamp)", w: cr.stroke || 6, d: cr.d || 0.6, seed: c.sid });
  }
  var blue = c.stage === "charcoal" ? "#7EA1FF" : "var(--blue)";
  (s.notes || []).forEach(function (n, i) {
    var t = c.at(n.at, 1 + i * 0.6), d = Y.el("div", "dot", c.cam); Y.css(d, { left: n.ox, top: n.oy });
    tl.fromTo(d, { scale: 0, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3, ease: "back.out(2)" }, t);
    var lab = Y.el("div", "note", c.cam, n.text); Y.css(lab, { left: n.lx, top: n.ly });
    var midx = n.lx < n.ox ? n.lx + Array.from(n.text).length * 20 : n.lx;
    var p = Y.path(sv, "M" + n.ox + " " + n.oy + " L " + midx + " " + (n.ly + 46), { stroke: blue, "stroke-width": 2.5, "stroke-dasharray": "0" });
    Y.draw(tl, p, t + 0.1, 0.4);
    tl.fromTo(lab, { opacity: 0, x: n.lx < n.ox ? 20 : -20 }, { opacity: 1, x: 0, duration: 0.4, ease: "power2.out" }, t + 0.35);
  });
  var pu = s.push || { at: c.dur * 0.45, s: 1.08, x: o.x + o.w / 2, y: o.y + o.w * 0.35 };
  var psc = pu.s || 1.08, wx = s.word ? (s.word.x == null ? 150 : s.word.x) : 960, pfx = Math.min(960 + (pu.x - 960) * 0.3, wx + 820 / psc);
  Y.camera(c, [{ at: 0, x: 960, y: 540, s: 1 }, { at: c.at(pu.at, 1), x: pfx, y: 540 + (pu.y - 540) * 0.3, s: pu.s || 1.08, d: pu.d || 2.2, ease: "sine.inOut" }]);
  Y.hud(c);
