  c.root.classList.add("r-rope");
  Y.stage(c);
  var cn = s.center || { x: 640, y: 420, w: 640 }, sv = Y.svg(c.cam); sv.style.zIndex = 5;
  var ctr = Y.card(c.cam, { x: cn.x, y: cn.y }); ctr.classList.add("ctr"); ctr.style.width = "auto"; ctr.style.height = "auto";
  var ct = Y.el("div", "tx", ctr); if (cn.sub) Y.el("div", "sb", ctr, cn.sub);
  ctr.style.zIndex = 10; ctr.style.transform = "rotate(-1.2deg)";
  Y.drop(tl, ctr, 0.1, { rot: -1.2, y: -40 });
  Y.write(tl, ct, cn.text || "", 0.4, { per: 0.04 });
  var cx = cn.x + (cn.cw || 560) / 2, cy = cn.y + 80;
  var pc = Y.el("div", "pin", c.cam); Y.css(pc, { left: cx, top: cy - 70 }); tl.fromTo(pc, { scale: 0 }, { scale: 1, duration: 0.25, ease: "back.out(2)" }, 0.5);
  var keys = [{ at: 0, x: 960, y: 540, s: 1.04 }];
  (s.nodes || []).forEach(function (n, i) {
    var t = c.at(n.at, 1 + i * 0.7), nd = Y.card(c.cam, { x: n.x, y: n.y }); nd.classList.add("nd"); nd.style.zIndex = 10;
    Y.el("div", "tx", nd, n.text); if (n.sub) Y.el("div", "sb", nd, n.sub);
    var rot = (i % 2 ? 2 : -2.4); nd.style.transform = "rotate(" + rot + "deg)";
    var nx = n.x + Array.from(n.text).length * 32 + 36, ny = n.y + 6;
    var mx = (cx + nx) / 2, my = Math.max(cy, ny) + 60; // sag
    var p = Y.path(sv, "M" + cx + " " + (cy - 70) + " Q " + mx + " " + my + " " + nx + " " + ny, { stroke: "#9C7B52", "stroke-width": 4, "stroke-linecap": "round" });
    var p2 = Y.path(sv, "M" + cx + " " + (cy - 70) + " Q " + mx + " " + my + " " + nx + " " + ny, { stroke: "rgba(255,240,210,.35)", "stroke-width": 1.4, "stroke-dasharray": "3 7" });
    Y.draw(tl, p, t, 0.55, "power2.out"); tl.fromTo(p2, { opacity: 0 }, { opacity: 1, duration: 0.2 }, t + 0.5);
    Y.drop(tl, nd, t + 0.35, { rot: rot, y: -30 });
    var pn = Y.el("div", "pin", c.cam); Y.css(pn, { left: nx, top: ny }); tl.fromTo(pn, { scale: 0 }, { scale: 1, duration: 0.25, ease: "back.out(2)" }, t + 0.6);
    keys.push({ at: t, x: (cx + nx) / 2, y: (cy + ny) / 2 + 40, s: 1.06, d: 1.0, ease: "sine.inOut" });
  });
  keys.push({ at: Math.max(c.dur - 1.6, 2), x: 960, y: 540, s: 1.0, d: 1.2, ease: "sine.inOut" });
  if (s.extras) Y.props(c, c.cam, s.extras, tl);
  Y.camera(c, keys);
  Y.hud(c);
