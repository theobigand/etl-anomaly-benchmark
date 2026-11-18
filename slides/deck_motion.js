/* Prepare one slide for its motion family: reading order, sides, and the marks of every chart. It only
   sets inline custom properties and data attributes; the animations themselves are in deck_motion.css.
   A visit with ?at=<ms> freezes every animation of the shown slide at that time (for review). */
const MOTION_AT = (location.search.match(/^\?at=(\d+)$/) || [])[1];
function motionPrep(s) {
  if (s.dataset.prepped) return;
  s.dataset.prepped = '1';
  let n = 0;
  [...s.children].forEach(c => {
    if (c.matches('.pg,.scrim,.ph')) return;
    c.style.setProperty('--i', n++);
    c.dataset.s = c.offsetLeft + c.offsetWidth / 2 < 640 ? 'l' : 'r';
  });
  const reverse = s.dataset.variant === '1';
  s.querySelectorAll('svg').forEach(svg => {
    const W = svg.width.baseVal.value, H = svg.height.baseVal.value;
    const all = svg.querySelectorAll('rect,circle,polyline,path,line,text');
    if (all.length > 120) svg.classList.add('dense');
    const rects = [...svg.querySelectorAll('rect')].filter(r => {
      const w = +r.getAttribute('width'), h = +r.getAttribute('height');
      return w < W * 0.9 && h < H * 0.9 && r.getAttribute('fill') !== 'none';
    });
    if (svg.classList.contains('dense')) {
      rects.forEach(r => { r.dataset.m = 'cell'; r.style.setProperty('--w', Math.round(+r.getAttribute('x') / W * 1000)); });
      return;
    }
    const lefts = rects.map(r => r.getAttribute('x'));
    const horizontal = rects.length > 1 && lefts.filter(x => x === lefts[0]).length >= rects.length * 0.6;
    const cap = k => Math.min(k, 40);
    rects.forEach((r, k) => {
      r.dataset.m = horizontal ? 'bar-h' : 'bar-v';
      r.style.setProperty('--k', cap(reverse ? rects.length - 1 - k : k));
    });
    let drawn = 0, dots = 0, labels = 0, axes = 0;
    svg.querySelectorAll('polyline,path,line,circle,text').forEach(e => {
      const tag = e.tagName.toLowerCase();
      if (tag === 'circle') { e.dataset.m = 'dot'; e.style.setProperty('--k', cap(dots++)); return; }
      if (tag === 'text') { e.dataset.m = 'label'; e.style.setProperty('--k', cap(labels++)); return; }
      if (tag === 'path' && e.getAttribute('fill') && e.getAttribute('fill') !== 'none') return;
      const x1 = +e.getAttribute('x1'), x2 = +e.getAttribute('x2'), y1 = +e.getAttribute('y1'), y2 = +e.getAttribute('y2');
      const long = tag === 'line' && (Math.abs(x2 - x1) > W * 0.5 || Math.abs(y2 - y1) > H * 0.5);
      if (long) { e.dataset.m = 'axis'; e.style.setProperty('--k', cap(axes++)); return; }
      e.setAttribute('pathLength', '1');
      e.dataset.m = 'draw';
      e.style.setProperty('--k', cap(reverse ? 40 - drawn++ : drawn++));
    });
  });
}
function motionFreeze() {
  if (MOTION_AT === undefined) return;
  requestAnimationFrame(() => document.getAnimations().forEach(a => { a.pause(); a.currentTime = +MOTION_AT; }));
}
