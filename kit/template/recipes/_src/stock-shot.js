  c.root.classList.add("r-stock");
  var ph = s.mediaFallback && s.mediaFallback[0], framed = ph || s.frame === "print", m0 = c.m(0), side = (s.title && s.title.side) || "left";
  var layer = Y.el("div", framed ? "on-stage" : "on-photo", c.root); Y.css(layer, { position: "absolute", inset: 0, zIndex: 30 });
  if (!framed) {
    var bleed = Y.el("div", "bleed", c.cam), kb = Y.el("div", "kb", bleed); kb.appendChild(m0);
    var push = s.props?.push || s.push || {}, a = (s.kb && s.kb.from) || { s: push.from ?? 1, x: 0, y: 0 }, b = (s.kb && s.kb.to) || { s: push.to ?? 1.17, x: 0, y: 0 };
    kb.dataset.camera = 'push';
    tl.fromTo(kb, { scale: a.s, x: a.x, y: a.y }, { scale: b.s, x: b.x, y: b.y, duration: s.kb ? c.dur : Math.min(c.dur,push.duration??3), ease: "none" }, 0);
    var sc = Y.el("div", "scrim", bleed);
    sc.style.background = side === "left"
      ? "radial-gradient(90% 120% at 0% 60%, rgba(12,10,8,.70) 0%, rgba(12,10,8,.28) 55%, rgba(12,10,8,0) 80%), radial-gradient(140% 80% at 50% 120%, rgba(0,0,0,.35), transparent 60%)"
      : "radial-gradient(90% 120% at 100% 60%, rgba(12,10,8,.70) 0%, rgba(12,10,8,.28) 55%, rgba(12,10,8,0) 80%), radial-gradient(140% 80% at 50% 120%, rgba(0,0,0,.35), transparent 60%)";
    tl.fromTo(bleed, { opacity: 0 }, { opacity: 1, duration: 0.35, ease: "sine.out" }, 0);
  } else {
    Y.stage(c);
    var pr = Y.el("div", "print", c.cam), box = side === "left" ? { x: ph ? 860 : 920, y: ph ? 120 : 190, w: ph ? 900 : 860, h: ph ? 700 : 484 } : { x: 160, y: ph ? 120 : 190, w: ph ? 900 : 860, h: ph ? 700 : 484 };
    Y.css(pr, { left: box.x, top: box.y, width: box.w, height: box.h + 84 });
    var im = Y.el("div", "img", pr); im.appendChild(m0);
    Y.el("div", "cap", pr, s.credit || "");
    Y.tape(pr, box.w / 2 - 80, -22, -3, 160);
    Y.drop(tl, pr, 0.05, { rot: side === "left" ? 2.2 : -2.2, y: -80 });
    tl.fromTo(m0, { scale: 1.0 }, { scale: 1.06, duration: c.dur, ease: "none", transformOrigin: "50% 60%" }, 0);
  }
  if (s.title) {
    var t = Y.el("div", "t", layer), ta = c.at(s.title.at, 0.4);
    var y = 430;
    if (side === "left") Y.css(t, { left: 150, top: y }); else { t.style.right = "150px"; t.style.top = y + "px"; t.style.textAlign = "right"; }
    Y.write(tl, t, s.title.text, ta);
    var r = Y.el("div", "rule", layer); if (side === "left") Y.css(r, { left: 154, top: y + 210 }); else { r.style.right = "154px"; r.style.top = (y + 210) + "px"; r.style.transformOrigin = "100% 50%"; }
    tl.fromTo(r, { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.inOut" }, ta + 0.45);
    if (s.sub) { var sb = Y.el("div", "sub", layer, s.sub.text); if (side === "left") Y.css(sb, { left: 154, top: y + 240 }); else { sb.style.right = "154px"; sb.style.top = (y + 240) + "px"; } Y.fadeUp(tl, sb, c.at(s.sub.at, ta + 0.7), { y: 10 }); }
  }
  if(window.YV)window.YV.overlays(c,s.props||s);
  Y.hud(c, { onMedia: !framed });
