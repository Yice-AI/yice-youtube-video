  c.root.classList.add("r-ledger");
  Y.stage(c);
  var cd = s.card || { x: 170, y: 120, w: 1000 }, io = s.mode === "io";
  if (s.sides) Y.props(c, c.cam, s.sides, tl);
  var card = Y.card(c.cam, { x: cd.x, y: cd.y, w: cd.w }); card.classList.add("lc"); card.style.height = "auto";
  if (io) card.classList.add("io");
  card.style.transform = "rotate(" + (cd.rot || -0.8) + "deg)";
  Y.drop(tl, card, 0.1, { rot: cd.rot || -0.8, y: -40, spin: 2 });
  Y.tape(card, cd.w - 120, -20, 6, 150);
  if (s.kicker) Y.el("div", "kick", card, s.kicker);
  var ti = Y.el("div", "ti", card); Y.write(tl, ti, s.title || "", 0.2);
  if (!io && s.cols) { var hd = Y.el("div", "hd", card, "<span>" + s.cols[0] + "</span><span>" + s.cols[1] + "</span>"); Y.fadeUp(tl, hd, 0.3, { y: 8 }); }
  (s.rows || []).forEach(function (r, i) {
    if (io && i > 0) { var ar = Y.el("div", "arrow", card, "↓"); Y.fadeUp(tl, ar, c.at(r.at, 1 + i) - 0.2, { y: -8 }); }
    var row = Y.el("div", "row", card), k = Y.el("div", "k", row, r.k + (r.sub ? "<small>" + r.sub + "</small>" : "")), v = Y.el("div", "v", row);
    var t = c.at(r.at, 1 + i * 0.6);
    row.style.overflow = "hidden";
    tl.fromTo(row, { opacity: 0, height: 0 }, { opacity: 1, height: io ? 112 : 104, duration: 0.45, ease: "power2.out" }, t - 0.3);
    Y.write(tl, v, r.v, t, { y: 10 });
  });
  if (s.total) {
    var tr = Y.el("div", "row tot", card), tk = Y.el("div", "k", tr, s.total.k), tv = Y.el("div", "v", tr), tt = c.at(s.total.at, c.dur - 1.6);
    tr.style.overflow = "hidden";
    tl.fromTo(tr, { opacity: 0, height: 0 }, { opacity: 1, height: 124, duration: 0.45 }, tt - 0.35);
    Y.write(tl, tv, s.total.v, tt);
  }
  var cam = Y.camera(c, [{ at: 0, x: 960, y: 540, s: 1 }, { at: Math.max(1.4, (s.stamp ? c.at(s.stamp.at) : c.dur) - 0.9), x: cd.x + cd.w * 0.7, y: cd.y + 480, s: 1.03, d: 1.6, ease: "sine.inOut" }]);
  if (s.stamp) Y.stamp(card, tl, s.stamp.text, { x: cd.w - 330, y: (s.stampY || 440) }, c.at(s.stamp.at), { size: 60 });
  Y.hud(c);
