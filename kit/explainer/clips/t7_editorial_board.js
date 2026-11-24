// 编辑部看板：title / 1–4 card / footer。每帧由时间和 spec 直接计算。
CLIPS.t7_editorial_board = (() => {
  const BG = '#172322', CARD = '#21312f', LINE = '#465750';
  const INK = '#f6f0df', MUTED = '#b5c9a9', ACCENT = '#ff745a';
  const twoDigits = number => String(number).padStart(2, '0');

  function panel(c, x, y, w, h, fill, stroke=LINE) {
    c.beginPath();
    c.roundRect(x, y, w, h, 12);
    c.fillStyle = fill;
    c.fill();
    c.strokeStyle = stroke;
    c.lineWidth = 2;
    c.stroke();
  }

  function label(c, value, x, y, width, desired, color=INK, weight=550, mono=false) {
    const text = String(value ?? '').trim();
    if (!text) return 0;
    const family = mono ? 'monospace' : 'system-ui, sans-serif';
    c.font = `${weight} ${desired}px ${family}`;
    const size = Math.max(24, Math.min(desired, Math.floor(desired * width / Math.max(1, c.measureText(text).width))));
    c.font = `${weight} ${size}px ${family}`;
    let shown = text;
    if (c.measureText(shown).width > width) {
      let characters = [...shown];
      while (characters.length && c.measureText(characters.join('') + '…').width > width) characters.pop();
      shown = characters.join('') + '…';
    }
    c.fillStyle = color;
    c.textBaseline = 'middle';
    c.fillText(shown, x, y);
    return c.measureText(shown).width;
  }

  function comparison(c, value, x, y, width, progress, rejected) {
    if (!value || progress <= 0) return;
    c.save();
    c.globalAlpha *= progress;
    label(c, rejected ? '✗' : '✓', x, y, 30, 28, rejected ? ACCENT : MUTED, 800);
    const shown = label(c, value, x + 40, y, width - 40, 29, rejected ? '#d7b1a2' : INK);
    if (rejected) {
      c.strokeStyle = ACCENT;
      c.lineWidth = 2;
      c.beginPath();
      c.moveTo(x + 40, y + 1);
      c.lineTo(x + 40 + shown * U.clamp((progress - .25) / .75), y + 1);
      c.stroke();
    }
    c.restore();
  }

  return {
    safe: true,
    init({cues, data}) {
      const count = cues.filter(cue => cue.kind === 'card').length;
      if (count < 1 || count > 4) throw new Error('t7_editorial_board 需要一至四张 card');
      if (data.layout != null && !['rows', 'columns'].includes(data.layout))
        throw new Error('t7_editorial_board 的 layout 须为 rows 或 columns');
    },
    draw(c, time, ctx) {
      const {W, H, safe, cues, data} = ctx;
      const left = Math.max(safe.left, 80), right = W - Math.max(safe.right, 80);
      const top = Math.max(safe.top, 64), bottom = H - Math.max(safe.bottom, 172);
      const title = cues.find(cue => cue.kind === 'title');
      const cards = cues.filter(cue => cue.kind === 'card');
      const footer = cues.find(cue => cue.kind === 'footer');
      const current = cards.reduce((index, cue, i) => time >= cue.at ? i : index, -1);
      const wide = right - left;
      const vertical = data.layout !== 'columns' || wide < 900;
      const gap = 18;
      const startY = top + 198;
      const endY = bottom - (footer ? 82 : 24);
      const cardWidth = vertical ? wide : (wide - gap * (cards.length - 1)) / cards.length;
      const cardHeight = vertical ? (endY - startY - gap * (cards.length - 1)) / cards.length : endY - startY;

      c.fillStyle = BG;
      c.fillRect(0, 0, W, H);
      c.strokeStyle = '#263833';
      c.lineWidth = 1;
      c.beginPath();
      for (let x = left; x <= right; x += 64) {
        c.moveTo(x, top); c.lineTo(x, bottom);
      }
      for (let y = top; y <= bottom; y += 64) {
        c.moveTo(left, y); c.lineTo(right, y);
      }
      c.stroke();

      label(c, data.eyebrow, left, top + 29, wide - 220, 27, MUTED, 650, true);
      panel(c, right - 163, top + 10, 163, 44, CARD);
      label(c, `${twoDigits(current + 1)} / ${twoDigits(cards.length)}`, right - 144, top + 32, 130, 26, MUTED, 700, true);
      if (!title || time >= title.at) {
        label(c, title?.text || data.title, left, top + 107, wide, 66, INK, 760);
        label(c, title?.sub, left, top + 163, wide, 31, MUTED);
      }

      cards.forEach((cue, index) => {
        const reveal = ctx.p(time, cue.at, .36);
        if (reveal <= 0) return;
        const ease = 1 - (1 - reveal) ** 3;
        const x = left + (vertical ? 0 : index * (cardWidth + gap));
        const y = startY + (vertical ? index * (cardHeight + gap) : 0) + 18 * (1 - ease);
        const meta = cue.data || {};
        const sideBySide = vertical && wide >= 900;
        const rowInset = sideBySide ? Math.max(0, (cardHeight - 124) / 2) : 0;
        const textX = x + 106;
        const textWidth = sideBySide ? cardWidth * .43 - 119 : cardWidth - 126;
        const badgeText = meta.badge || twoDigits(index + 1);
        c.save();
        c.globalAlpha = ease;
        panel(c, x, y, cardWidth, cardHeight, CARD, index === current ? ACCENT : LINE);
        c.fillStyle = ACCENT;
        c.fillRect(x + 4, y + 14, 5, (cardHeight - 28) * ease);
        label(c, badgeText, x + 23, y + rowInset + 38, 68, 30, ACCENT, 750, true);
        label(c, cue.text, textX, y + rowInset + 38, textWidth, 35, INK, 740);
        label(c, cue.sub, sideBySide ? textX : x + 24, y + rowInset + 84, sideBySide ? textWidth : cardWidth - 48, 28, MUTED);
        const compareX = sideBySide ? x + cardWidth * .44 : x + 24;
        const compareY = sideBySide ? y + rowInset + 37 : y + 155;
        const compareWidth = sideBySide ? cardWidth - (compareX - x) - (meta.tag ? 226 : 24) : cardWidth - 48;
        comparison(c, meta.bad, compareX, compareY, compareWidth, ctx.p(time, cue.at + .07, .29), true);
        const goodY = compareY + (meta.bad ? 48 : 0);
        comparison(c, meta.good, compareX, goodY, compareWidth, ctx.p(time, cue.at + .20, .24), false);
        if (meta.tag && time >= cue.at + .21) {
          const width = Math.min(184, cardWidth - 48);
          const tagX = x + cardWidth - width - 24;
          const tagY = sideBySide ? y + (cardHeight - 44) / 2 : y + cardHeight - 67;
          panel(c, tagX, tagY, width, 44, '#2c423a');
          label(c, meta.tag, tagX + 13, tagY + 22, width - 26, 25, MUTED, 680);
        }
        c.restore();
      });
      if (footer && time >= footer.at) {
        panel(c, left, bottom - 64, wide, 58, '#263a34');
        label(c, footer.text, left + 22, bottom - 35, wide - 44, 30, INK, 650);
      }
    }
  };
})();
