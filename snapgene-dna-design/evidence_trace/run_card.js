/* Presentation only: actual match decisions are supplied by the Python projection. */
(() => {
  const card = document.getElementById('run-card');
  const full = document.getElementById('full-view');
  if (!card || !full) return;
  const payload = JSON.parse(document.getElementById('run-card-data').textContent);
  const back = document.getElementById('run-card-back');
  function mode(fullMode) {
    card.hidden = fullMode; full.hidden = !fullMode; back.hidden = !fullMode;
    window.dispatchEvent(new Event('resize'));
    if (!fullMode) draw();
  }
  document.querySelectorAll('[data-open-full]').forEach(link => link.addEventListener('click', event => {
    event.preventDefault(); mode(true); window.scrollTo(0,0);
  }));
  back.addEventListener('click', () => {mode(false); window.scrollTo(0,0);});
  const flow = card.querySelector('.rc-flow');
  const svg = flow.querySelector('.rc-lines');
  const ns = 'http://www.w3.org/2000/svg';
  function draw() {
    svg.replaceChildren();
    if (card.hidden || window.innerWidth <= 760) return;
    const base = flow.getBoundingClientRect();
    svg.setAttribute('viewBox',`0 0 ${base.width} ${base.height}`);
    for (const relation of payload.relations) {
      if (relation.from === relation.to) continue;
      const from = document.getElementById('rc-'+relation.from);
      const to = document.getElementById('rc-'+relation.to);
      if (!from || !to) continue;
      const a=from.getBoundingClientRect(), b=to.getBoundingClientRect();
      const sameColumn=Math.abs(a.left-b.left)<10;
      const x1=(sameColumn?a.right:a.right)-base.left, y1=(a.top+a.height/2)-base.top;
      const x2=(sameColumn?b.right:b.left)-base.left, y2=(b.top+b.height/2)-base.top;
      const bend=sameColumn?Math.min(base.width-6,x1+25):(x1+x2)/2;
      const path=document.createElementNS(ns,'path');
      path.setAttribute('d',`M${x1},${y1} C${bend},${y1} ${bend},${y2} ${x2},${y2}`);
      if (relation.verified) {path.classList.add('rc-verified');path.setAttribute('data-verified-file-link','true');}
      const title=document.createElementNS(ns,'title');title.textContent=relation.label+(relation.hashes.length?' · '+relation.hashes.join(', '):'');path.append(title);svg.append(path);
      if (relation.verified) {const text=document.createElementNS(ns,'text');text.setAttribute('x',String(bend+3));text.setAttribute('y',String((y1+y2)/2));text.textContent=relation.hashes[0].slice(0,8);svg.append(text);}
    }
  }
  window.addEventListener('resize',draw);
  mode(new URLSearchParams(window.location.search).get('view')==='full');
})();
