  c.root.classList.add("r-ed");
  Y.stage(c);
  var wb = s.win || { x: 220, y: 110, w: 1480, h: 860 };
  var win = Y.el("div", "win", c.cam); Y.css(win, { left: wb.x, top: wb.y, width: wb.w, height: wb.h });
  var tb = Y.el("div", "tb", win); ["#ED6A5E", "#F5BF4F", "#61C554"].forEach(function (col) { var i = Y.el("i", "", tb); i.style.background = col; });
  Y.el("div", "fn", tb, s.file || "index.html");
  var code = Y.el("div", "code", win);
  function hi(line) {
    var h = line.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    h = h.replace(/([\w-]+)=(&quot;|")([^"]*)"/g, '<span class="a">$1</span>=<span class="v">"$3"</span>').replace(/(&lt;\/?)([a-z]+)/g, '$1<span class="t">$2</span>').replace(/(\/\/.*)$/, '<span class="cm">$1</span>');
    return h;
  }
  var t0 = c.at(s.at, 0.3), per = Math.min(0.22, (c.dur * 0.55) / Math.max(1, (s.lines || []).length));
  tl.fromTo(win, { opacity: 0, y: 40, rotation: -1.5 }, { opacity: 1, y: 0, rotation: -0.6, duration: 0.6, ease: "power3.out" }, 0);
  var hlEl = null;
  (s.lines || []).forEach(function (ln, i) {
    var row = Y.el("div", "ln", code);
    if (s.hl && s.hl.line === i) { hlEl = Y.el("div", "hlbar", row); }
    Y.el("span", "g", row, String(i + 1)); var tx = Y.el("span", "", row, hi(ln));
    tl.fromTo(row, { opacity: 0, x: -10 }, { opacity: 1, x: 0, duration: 0.18, ease: "power1.out" }, t0 + i * per);
  });
  var keys = [{ at: 0, x: 960, y: 540, s: 1 }];
  if (hlEl) { var ht = c.at(s.hl.at, t0 + 1.2); tl.fromTo(hlEl, { scaleX: 0 }, { scaleX: 1, duration: 0.45, ease: "power2.inOut" }, ht); keys.push({ at: ht - 0.2, x: wb.x + wb.w * 0.42, y: wb.y + 74 + 24 + s.hl.line * 46, s: 1.45, d: 1.1 }); }
  Y.camera(c, keys);
  if (s.title) Y.label(c, s.title);
  Y.hud(c);
