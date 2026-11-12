/* In-page layout probe. Runs only with ?check in the URL. It reports, per slide, text that
   overlaps other text, text outside its slide or its svg, clipped overflow, and text over figures.
   It also reports text below the minimum size and text that crowds the source line at the foot of a slide.
   ?stress swaps in wide fallback fonts to test robustness against missing fonts.
   ?fonts=<family> swaps in a named family instead (generic names such as sans-serif are allowed). */
(function () {
  const q = new URLSearchParams(location.search);
  if (!q.has('check')) return;
  // Practical minimum at 1280x720 (1.5x on a 1080p projector): no text under 13px, and running words under 14px.
  const MIN_NUM = 13, MIN_WORD = 14;
  const forced = q.get('fonts') || (q.has('stress') ? 'Arial' : '');
  if (forced) {
    const st = document.createElement('style');
    const fam = forced.replace(/[^A-Za-z0-9 ,_-]/g, '');
    const mono = q.has('stress') ? 'Courier New,monospace' : 'monospace';
    st.textContent = ':root{--cond:' + fam + '!important;--sans:' + fam + '!important;--mono:' + mono + '!important}';
    document.head.appendChild(st);
  }
  const effScale = (el) => {
    let sc = 1;
    for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
      const t = getComputedStyle(e).transform;
      if (t && t !== 'none') { const m = new DOMMatrix(t); sc *= Math.hypot(m.a, m.b); }
    }
    return sc;
  };
  const issues = [];
  const slides = [...document.querySelectorAll('.slide')];
  const shrink = (r) => ({ l: r.left, r: r.right, t: r.top + r.height * 0.22, b: r.bottom - r.height * 0.22 });
  const inter = (a, b) => Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l)) * Math.max(0, Math.min(a.b, b.b) - Math.max(a.t, b.t));
  slides.forEach((s, idx) => {
    slides.forEach((x) => x.classList.remove('on'));
    s.classList.add('on');
    if (window.fitFlow) window.fitFlow(s);
    const sr = s.getBoundingClientRect();
    const k = sr.width / 1280;
    const items = [];
    const w = document.createTreeWalker(s, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = w.nextNode())) {
      if (!n.nodeValue.trim()) continue;
      const el = n.parentElement;
      if (el.closest('title,style,script') || getComputedStyle(el).visibility === 'hidden') continue;
      const rg = document.createRange();
      rg.selectNodeContents(n);
      const rects = [...rg.getClientRects()].filter((r) => r.width > 1 && r.height > 1);
      if (!rects.length) continue;
      items.push({ n, el, rects, text: n.nodeValue.trim().slice(0, 36), svg: el.closest('svg') });
    }
    const add = (kind, text, extra) => issues.push({ slide: idx + 1, kind, text, ...extra });
    const foot = s.querySelector('.src');
    const footTop = foot ? (foot.getBoundingClientRect().top - sr.top) / k : null;
    items.forEach((it) => {
      const px = parseFloat(getComputedStyle(it.el).fontSize) * effScale(it.el);
      const wordy = /[A-Za-z]{4,}/.test(it.text) && it.text.length >= 8 && !it.el.closest('.src');
      if (px < MIN_NUM - 0.05 || (wordy && px < MIN_WORD - 0.05)) add('small-text', it.text + ' (' + px.toFixed(1) + 'px)', {});
      if (footTop !== null && !it.el.closest('.src') && !/^\d+$/.test(it.text)) {
        const bottom = Math.max(...it.rects.map((r) => (r.bottom - sr.top) / k));
        if (bottom > footTop - 6 && bottom < 720 && it.rects.some((r) => (r.top - sr.top) / k < footTop + 4)) add('crowds-footer', it.text, {});
      }
      it.rects.forEach((r) => {
        if (r.left < sr.left - 2 || r.right > sr.right + 2 || r.top < sr.top - 2 || r.bottom > sr.bottom + 2) add('outside-slide', it.text, {});
        if (it.svg) {
          const b = it.svg.getBoundingClientRect();
          if (r.left < b.left - 1 || r.right > b.right + 1 || r.top < b.top - 1 || r.bottom > b.bottom + 1) add('outside-svg', it.text + ' [' + [r.left, r.top, r.right, r.bottom].map(Math.round) + ' in ' + [b.left, b.top, b.right, b.bottom].map(Math.round) + ']', {});
        }
      });
    });
    for (let i = 0; i < items.length; i++) {
      for (let j = i + 1; j < items.length; j++) {
        const a = items[i], b = items[j];
        if (a.el === b.el) continue;
        let hit = 0;
        a.rects.forEach((ra) => b.rects.forEach((rb) => { hit = Math.max(hit, inter(shrink(ra), shrink(rb)) / (k * k)); }));
        if (hit > 6) add('text-overlap', a.text + ' | ' + b.text, { area: Math.round(hit) });
      }
    }
    s.querySelectorAll('*').forEach((el) => {
      const cs = getComputedStyle(el);
      if (cs.overflow !== 'visible' && el.tagName !== 'svg' && !el.closest('svg') && (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2) && el.clientWidth > 0) add('clipped', (el.textContent || '').trim().slice(0, 36), {});
    });
    // a drawn box edge (CSS border or stroked svg rect) that runs through text which is not inside that box
    const edges = [];
    s.querySelectorAll('*').forEach((el) => {
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (r.width < 8 || r.height < 8) return;
      if (el.tagName.toLowerCase() === 'rect' && el.closest('svg')) {
        if (cs.stroke !== 'none' && parseFloat(cs.strokeWidth) >= 1 && cs.fill === 'none') edges.push({ el, h: [[r.left, r.right, r.top], [r.left, r.right, r.bottom]], v: [[r.top, r.bottom, r.left], [r.top, r.bottom, r.right]] });
      } else if (el.tagName.toLowerCase() !== 'svg' && ['Top', 'Bottom', 'Left', 'Right'].every((d) => parseFloat(cs['border' + d + 'Width']) >= 1.5 && cs['border' + d + 'Style'] !== 'none')) {
        edges.push({ el, h: [[r.left, r.right, r.top], [r.left, r.right, r.bottom]], v: [[r.top, r.bottom, r.left], [r.top, r.bottom, r.right]] });
      }
    });
    edges.forEach((b) => items.forEach((it) => {
      if (b.el.contains(it.el)) return;
      it.rects.forEach((r) => {
        const ins = shrink(r);
        const hit = b.h.some(([x0, x1, y]) => ins.t < y && ins.b > y && Math.min(r.right, x1) - Math.max(r.left, x0) > 3) || b.v.some(([y0, y1, x]) => r.left < x && r.right > x && Math.min(ins.b, y1) - Math.max(ins.t, y0) > 3);
        if (hit) add('box-crosses-text', it.text, {});
      });
    }));
    // text painted over by a later opaque shape or box (a title hidden behind a diagram panel, for example)
    const SHAPES = ['rect', 'path', 'circle', 'ellipse', 'polygon', 'polyline', 'line', 'image', 'img'];
    items.forEach((it) => {
      if (it.el.closest('.scrim')) return;
      it.rects.forEach((r) => {
        [0.12, 0.5, 0.88].forEach((f) => {
          const x = r.left + r.width * f, y = r.top + r.height * 0.5;
          if (x < sr.left || x > sr.right || y < sr.top || y > sr.bottom) return;
          const top = document.elementFromPoint(x, y);
          if (!top || top === it.el || it.el.contains(top) || top.contains(it.el)) return;
          const tag = top.tagName.toLowerCase();
          const box = !SHAPES.includes(tag) && !(top.textContent || '').trim() && getComputedStyle(top).backgroundColor !== 'rgba(0, 0, 0, 0)';
          if (SHAPES.includes(tag) || box) add('text-occluded', it.text + ' [under ' + tag + ']', {});
        });
      });
    });
    const imgs = [...s.querySelectorAll('img')].map((i) => i.getBoundingClientRect());
    items.forEach((it) => it.rects.forEach((r) => imgs.forEach((ib) => { if (inter({ l: r.left, r: r.right, t: r.top, b: r.bottom }, { l: ib.left, r: ib.right, t: ib.top, b: ib.bottom }) > 20) add('text-over-figure', it.text, {}); })));
  });
  const pre = document.createElement('pre');
  pre.id = 'layout-report';
  pre.textContent = JSON.stringify(issues);
  document.body.appendChild(pre);
})();
