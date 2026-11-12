/* In-page layout probe. Runs only with ?check in the URL. It reports, per slide, text that
   overlaps other text, text outside its slide or its svg, clipped overflow, and text over figures.
   ?stress swaps in wide fallback fonts to test robustness against missing fonts. */
(function () {
  const q = new URLSearchParams(location.search);
  if (!q.has('check')) return;
  if (q.has('stress')) {
    const st = document.createElement('style');
    st.textContent = ':root{--cond:Arial,sans-serif!important;--sans:Arial,sans-serif!important;--mono:Courier New,monospace!important}';
    document.head.appendChild(st);
  }
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
    items.forEach((it) => {
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
    const imgs = [...s.querySelectorAll('img')].map((i) => i.getBoundingClientRect());
    items.forEach((it) => it.rects.forEach((r) => imgs.forEach((ib) => { if (inter({ l: r.left, r: r.right, t: r.top, b: r.bottom }, { l: ib.left, r: ib.right, t: ib.top, b: ib.bottom }) > 20) add('text-over-figure', it.text, {}); })));
  });
  const pre = document.createElement('pre');
  pre.id = 'layout-report';
  pre.textContent = JSON.stringify(issues);
  document.body.appendChild(pre);
})();
