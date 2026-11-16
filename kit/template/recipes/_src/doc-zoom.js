  c.root.classList.add("r-doc");
  Y.stage(c);
  var ph = s.mediaFallback && s.mediaFallback[0], pg = s.page || { x: 260, y: 130, w: 1400, rot: -1 };
  var bar = s.bar !== false, barH = bar ? 52 : 0, asp = s.aspect || 0.56, ph_h = pg.w * asp;
  var win, pageEl;
  if (bar) {
    win = Y.el("div", "yf-browser", c.cam); Y.css(win, { left: pg.x, top: pg.y, width: pg.w });
    var b = Y.el("div", "bar", win); ["#ED6A5E", "#F5BF4F", "#61C554"].forEach(function (col) { var i = Y.el("i", "", b); i.style.background = col; });
    Y.el("div", "url", b, s.url || "");
    pageEl = Y.el("div", "page", win); Y.css(pageEl, { height: ph_h });
  } else {
    win = Y.el("div", "clipping", c.cam); Y.css(win, { left: pg.x - 34, top: pg.y - 28, width: pg.w + 68 });
    pageEl = Y.el("div", "", win); Y.css(pageEl, { position: "relative", width: pg.w, height: ph_h });
    Y.tape(win, pg.w * 0.12, -24, -4, 150); Y.tape(win, pg.w * 0.8, ph_h + 30, 3, 150);
  }
  if (!ph) pageEl.appendChild(c.m(0));
  else { var sk = Y.el("div", "skel", pageEl); [["62%", 54], ["44%", 30], ["38%", 30]].forEach(function (r) { var i = Y.el("i", "", sk); Y.css(i, { width: r[0], height: r[1] }); }); Y.el("i", "btn", sk); [["90%", 22], ["86%", 22], ["70%", 22]].forEach(function (r) { var i = Y.el("i", "", sk); Y.css(i, { width: r[0], height: r[1], marginTop: 30 }); }); }
  win.style.transform = "rotate(" + (pg.rot || 0) + "deg)";
  tl.fromTo(win, { opacity: 0, y: 60, rotation: (pg.rot || 0) + 2 }, { opacity: 1, y: 0, rotation: pg.rot || 0, duration: 0.7, ease: "power3.out" }, 0.05);
  function P(x, y) { return { x: pg.x + x / 100 * pg.w, y: pg.y + barH + y / 100 * ph_h }; }
  var keys = (s.keys || [{ at: 0, x: 50, y: 50, z: 1 }]).map(function (k) { var p = P(k.x, k.y); return { at: k.at, x: p.x, y: p.y, s: k.z || 1, d: k.d || 1.2 }; });
  Y.camera(c, keys);
  (s.hls || []).forEach(function (h) { Y.hl(pageEl, tl, { x: h.x / 100 * pg.w, y: h.y / 100 * ph_h, w: h.w / 100 * pg.w, h: h.h / 100 * ph_h }, c.at(h.at)); });
  var sv = Y.svg(c.cam);
  if (s.circle) { var p0 = P(s.circle.x, s.circle.y); Y.ellipse(sv, tl, { x: p0.x, y: p0.y, w: s.circle.w / 100 * pg.w, h: s.circle.h / 100 * ph_h }, c.at(s.circle.at)); }
  if (s.stamp) { var sp = P(s.stamp.x, s.stamp.y); Y.stamp(c.cam, tl, s.stamp.text, sp, c.at(s.stamp.at), { size: s.stamp.size || 60 }); }
  if (s.title) {
    var right = s.title.side === "right", lb = Y.card(c.wrap, { x: 140, y: 800 }); lb.classList.add("yf-label");
    if (right) { lb.style.left = "auto"; lb.style.right = "150px"; }
    if (s.title.top != null) lb.style.top = s.title.top + "px";
    var k = Y.el("div", "k", lb); if (s.title.sub) Y.el("div", "s", lb, s.title.sub);
    Y.tape(lb, right ? 30 : 200, -24, right ? -5 : 4, 150);
    var ta = c.at(s.title.at, 0.6);
    tl.fromTo(lb, { opacity: 0, y: 40, rotation: right ? 5 : -6 }, { opacity: 1, y: 0, rotation: right ? 1.4 : -1.6, duration: 0.55, ease: "back.out(1.3)" }, ta);
    Y.write(tl, k, s.title.text, ta + 0.25);
  }
  if (ph || s.ph) Y.el("div", "yf-ph", c.wrap, s.ph || "待截图");
  Y.hud(c);
