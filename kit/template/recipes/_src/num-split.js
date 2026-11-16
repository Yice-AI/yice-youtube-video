  c.root.classList.add("r-num");
  Y.stage(c);
  var L = s.left || {}, R = s.right || {}, hasBar = !!s.bar;
  var boxes = [{ x: 150, y: hasBar ? 120 : 150, w: 820, h: hasBar ? 600 : 700, rot: -1.2 }, { x: 1060, y: hasBar ? 200 : 250, w: 640, h: hasBar ? 470 : 540, rot: 1.4 }];
  var cards = [L, R].map(function (d, i) {
    var b = boxes[i], cd = Y.card(c.cam, { x: b.x, y: b.y, w: b.w, h: b.h }); cd.classList.add("nc"); cd.style.transform = "rotate(" + b.rot + "deg)";
    Y.el("div", "kick", cd, d.kicker || (i ? "B" : "A"));
    var big = Y.el("div", "big", cd); big.style.fontSize = (d.size || (i ? 170 : 220)) + "px";
    var foot = Y.el("div", "", cd); Y.el("div", "lab", foot, d.label || ""); if (d.sub) Y.el("div", "sb", foot, d.sub);
    var t = c.at(d.at, 0.3 + i * 1.2);
    var e0 = (c.spec.enter && c.spec.enter !== "cut" ? 0.3 : 0.05);
    Y.drop(tl, cd, i === 0 ? e0 : Math.max(e0 + 0.2, t - 0.3), { rot: b.rot, y: -60, d: 0.55 });
    if (d.text != null) Y.write(tl, big, d.text, t);
    else { big.style.position = "relative"; var dash = Y.el("span", "", big, "— —"); Y.css(dash, { position: "absolute", left: 0, top: 0, color: "#b9ae9c" }); var sp = Y.el("span", "", big); tl.fromTo(dash, { opacity: 1 }, { opacity: 0, duration: 0.12 }, t); tl.fromTo(sp, { opacity: 0 }, { opacity: 1, duration: 0.12 }, t); var _u = 0, un = d.unit ? Y.el("small", "", big, d.unit) : null; Y.count(tl, sp, d.from || 0, d.num, t, { dec: d.dec || 0, pre: d.pre, suf: d.suf, d: 0.9 }); }
    if (i === 0) Y.tape(cd, 40, -20, -6, 140); else Y.tape(cd, b.w - 180, -20, 5, 140);
    return { el: cd, b: b, big: big, fs: (d.size || (i ? 170 : 220)), n: Array.from(d.text != null ? d.text : ((d.pre || "") + d.num + (d.suf || ""))).length };
  });
  if (s.rel) { var rl = Y.el("div", "rel", c.cam, s.rel.text); Y.css(rl, { left: 984, top: hasBar ? 360 : 440 }); Y.fadeUp(tl, rl, c.at(s.rel.at, 1.4), { y: 10 }); }
  var keys = [{ at: 0, x: 960, y: 540, s: 1 }];
  if (hasBar) {
    var B = s.bar, bar = Y.el("div", "bar", c.cam), fill = Y.el("div", "fill", bar), tb = c.at(B.at, 2);
    Y.css(fill, { width: (B.a / B.max * 100) + "%" });
    var mk = Y.el("div", "mk", bar); Y.css(mk, { left: (B.b / B.max * 100) + "%" });
    [[0, "0"], [B.a / B.max, B.a + " " + (B.unit || "")], [B.b / B.max, B.b + " " + (B.unit || "")]].forEach(function (q) { var tk = Y.el("div", "tk", bar, q[1]); Y.css(tk, { left: (q[0] * 100) + "%" }); });
    tl.fromTo(bar, { opacity: 0 }, { opacity: 1, duration: 0.3 }, tb - 0.3);
    tl.fromTo(fill, { scaleX: 0 }, { scaleX: 1, duration: 0.9, ease: "power2.inOut" }, tb);
    keys.push({ at: tb - 0.2, x: 960, y: 560, s: 1.03, d: 1.2, ease: "sine.inOut" });
  }
  if (s.circle) { var cc = cards[s.circle.side === "right" ? 1 : 0], sv = Y.svg(c.cam); sv.style.zIndex = 30; var ew = Math.min(cc.b.w - 40, cc.n * cc.fs * 0.62 + 80), eh = cc.fs * 1.35; Y.ellipse(sv, tl, { x: cc.b.x + 30, y: cc.b.y + cc.b.h * 0.47 - eh / 2, w: ew, h: eh }, c.at(s.circle.at), { color: "var(--stamp)", w: 6 }); }
  if (s.note) { var nt = Y.el("div", "note", c.cam, s.note.text); Y.fadeUp(tl, nt, c.at(s.note.at), { y: 8 }); keys.push({ at: c.at(s.note.at) - 0.2, x: 960, y: 545, s: 1.03, d: 1.2 }); }
  if (keys.length === 1) keys.push({ at: 1.2, x: 1000, y: 520, s: 1.05, d: Math.max(1.5, c.dur - 1.5), ease: "sine.inOut" });
  if (s.extras) Y.props(c, c.cam, s.extras, tl);
  Y.camera(c, keys);
  Y.hud(c);
