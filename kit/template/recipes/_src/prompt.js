  c.root.classList.add("r-prompt");
  Y.stage(c);
  if (s.kicker) { var kk = Y.el("div", "kick", c.cam, s.kicker); Y.fadeUp(tl, kk, 0.1, { y: 8 }); }
  var box = Y.el("div", "box", c.cam); Y.el("div", "plus", box, "+");
  var send = Y.el("div", "send", box, "↑");
  Y.el("div", "perm", box, "◌ 完全访问"); Y.el("div", "model", box, "GPT-6 Astra Max ⌄"); Y.el("div", "chips", box, "▭ 我的视频　　▢ 文件　　◎ 插件");
  tl.fromTo(box, { opacity: 0, y: 40 }, { opacity: 1, y: 0, duration: 0.6, ease: "power3.out" }, 0);
  var tx = Y.el("div", "tx", box), gs = Y.glyphs(tx, s.text || ""), caret = Y.el("span", "caret", tx);
  var t0 = c.at(s.at, 0.4), rate = s.rate || 14; // chars per second
  gs.forEach(function (g, i) { tl.fromTo(g, { opacity: 0 }, { opacity: 1, duration: 0.01 }, t0 + i / rate); });
  tl.fromTo(caret, { opacity: 1 }, { opacity: 0, duration: 0.01 }, t0 + gs.length / rate + 0.3);
  var full = s.text || "";
  (s.marks || []).forEach(function (m) {
    var idx = full.indexOf(m.phrase); if (idx < 0) return;
    var pre = Array.from(full.slice(0, idx)).length, n = Array.from(m.phrase).length;
    tl.to(gs.slice(pre, pre + n), { backgroundSize: "100% 46%", duration: 0.08, stagger: 0.035, ease: "none" }, c.at(m.at));
  });
  var keys = [{ at: 0, x: 960, y: 520, s: 1 }, { at: t0 + 0.6, x: 960, y: 500, s: 1.04, d: Math.max(1, gs.length / rate), ease: "sine.inOut" }];
  if (s.send) { var st = c.at(s.send.at); tl.to(send, { scale: 0.86, duration: 0.08, yoyo: true, repeat: 1, ease: "sine.inOut" }, st); tl.to(send, { backgroundColor: "#2C57C9", duration: 0.2 }, st); keys.push({ at: st - 0.6, x: 1240, y: 600, s: 1.08, d: 0.8 }); }
  Y.camera(c, keys);
  if (s.title) Y.label(c, s.title);
  Y.el("div", "yf-ph", c.wrap, s.ph || "示意 · 待录屏替换");
  Y.hud(c);
