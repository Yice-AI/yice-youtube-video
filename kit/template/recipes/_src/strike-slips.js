  c.root.classList.add("r-strike");
  Y.stage(c);
  var sv = Y.svg(c.cam); sv.style.zIndex = 30;
  if (s.lead) { var ld = Y.el("div", "lead", c.cam); if (s.short) Y.css(ld, { top: 120, fontSize: 170 }); Y.write(tl, ld, s.lead.text, c.at(s.lead.at, 0.15)); }
  function slip(text, x, y, rot, t, cls) {
    var e = Y.card(c.cam, { x: x, y: y }); e.classList.add("slip"); if (cls) e.classList.add(cls);
    var tx = Y.el("div", "tx", e, text); e.style.transform = "rotate(" + rot + "deg)";
    Y.slideIn(tl, e, t, { x: 120, rot: rot, spin: 3 });
    return { e: e, tx: tx, w: Array.from(text).length * (cls === "mini" ? 46 : 76) };
  }
  if (s.props) Y.props(c, c.cam, s.props, tl);
  var keys = [{ at: 0, x: 960, y: 540, s: 1 }];
  (s.slips || []).forEach(function (sl, i) {
    var x = 820 + (i % 2) * 120, y = 170 + i * (s.step || 230), rot = i % 2 ? 1.8 : -2.2, t = c.at(sl.at, 0.5 + i * 0.5);
    var o = slip(sl.text, x, y, rot, t);
    if (sl.strike != null) {
      var st = c.at(sl.strike);
      // strike drawn in slip-local svg so it rotates with the paper
      var ls = Y.svg(o.e); ls.style.width = "100%"; ls.style.height = "100%"; ls.setAttribute("viewBox", "0 0 " + (o.w + 92) + " 128"); ls.setAttribute("preserveAspectRatio", "none");
      Y.strike(ls, tl, { x: 40, y: 64, w: o.w + 12 }, st, { tilt: -5, seed: sl.text, w: 8 });
    }
  });
  if (s.short) {
    var n = s.short.n || 5;
    for (var i = 0; i < n; i++) {
      var o2 = slip(s.short.text, 150 + (i % 3) * 230, 450 + Math.floor(i / 3) * 170 + (i % 2) * 18, (i % 2 ? 3 : -3), c.at(s.short.at, 0.3) + i * 0.12, "mini");
      var ls2 = Y.svg(o2.e); ls2.style.width = "100%"; ls2.style.height = "100%"; ls2.setAttribute("viewBox", "0 0 " + (o2.w + 52) + " 82"); ls2.setAttribute("preserveAspectRatio", "none");
      Y.strike(ls2, tl, { x: 20, y: 40, w: o2.w + 10 }, c.at(s.short.strike, 1.5) + i * 0.14, { tilt: -4, seed: "m" + i, w: 7 });
    }
  }
  if (s.keep) {
    var kx = s.short ? 900 : 820, ky = s.short ? 540 : 170 + (s.slips || []).length * (s.step || 230);
    var k = Y.card(c.cam, { x: kx, y: ky }); k.classList.add("slip", "keep");
    var kt = Y.el("div", "tx", k); if (s.keep.sub) Y.el("div", "sb", k, s.keep.sub);
    k.style.transform = "rotate(-1deg)";
    var kat = c.at(s.keep.at, 1.5);
    Y.drop(tl, k, kat - 0.3, { rot: -1, y: -40 });
    Y.write(tl, kt, s.keep.text, kat);
    Y.tape(k, -30, -14, -24, 130);
    var ulw = Array.from(s.keep.text).length * 84;
    var ul = Y.el("div", "", k); Y.css(ul, { position: "absolute", left: 54, bottom: 18, width: Math.min(ulw, 900), height: 6, background: "var(--blue)", borderRadius: 3, transformOrigin: "0 50%" });
    tl.fromTo(ul, { scaleX: 0 }, { scaleX: 1, duration: 0.5, ease: "power2.inOut" }, kat + 0.6);
    keys.push({ at: kat + 0.4, x: s.short ? 960 : kx + 400, y: s.short ? 560 : ky + 80, s: s.short ? 1.03 : 1.08, d: 1.4, ease: "sine.inOut" });
  } else {
    keys.push({ at: 0.8, x: 1000, y: 560, s: 1.05, d: Math.max(1.5, c.dur - 1.2), ease: "sine.inOut" });
  }
  Y.camera(c, keys);
  Y.hud(c);
