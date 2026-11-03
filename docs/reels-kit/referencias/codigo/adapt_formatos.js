(cfg) => {
  const {fmt, y0, y1, textSel, sqBottom, hideSubSq} = cfg;
  const W = fmt === 'h' ? 1920 : 1080, H = 1080, WH = y1 - y0;
  const st = document.createElement('style');
  st.textContent = `
  html,body{width:${W}px!important;height:${H}px!important}
  .stage{width:${W}px!important;height:${H}px!important}
  .shade-top,.shade-bot{display:none!important}
  .visO{position:absolute;overflow:hidden;width:1080px;height:${WH}px;transform-origin:0 0;
    -webkit-mask-image:linear-gradient(to bottom,transparent,#000 5%,#000 95%,transparent),linear-gradient(to right,transparent,#000 4%,#000 96%,transparent);
    -webkit-mask-composite:source-in;mask-composite:intersect}
  .visI{position:absolute;left:0;top:${-y0}px;width:1080px;height:1920px}
  .txt{position:absolute;display:grid;z-index:5}
  .txt>*{position:relative!important;inset:auto!important;top:auto!important;left:auto!important;right:auto!important;grid-column:1;margin:0!important}
  .txt>.wrapT{opacity:1}
  .txt .title,.txt .sub{position:relative!important;top:auto!important;left:auto!important;right:auto!important;padding:0!important}
  .txt .chips{position:relative!important;top:auto!important;padding:0!important;margin-top:26px!important}
  .txt>.title,.txt>.wrapT,.txt>h1{grid-row:1}
  ${fmt === 'h' ? `
  .txt{left:110px;top:0;height:${H}px;align-content:center;row-gap:30px}
  .txt,.txt *{text-align:left!important}
  .txt .chips{justify-content:flex-start!important}
  .txt>.sub,.txt>.chips{grid-row:2}.txt>.foot{grid-row:3;margin-top:30px!important}
  .txt h1{font-size:82px!important}
  .txt .foot img{margin:0 0 14px!important;width:260px!important}
  .txt .sub{font-size:34px!important}
  ` : `
  .txt{left:50px;right:50px;top:0;height:${H}px;grid-template-rows:250px 1fr auto;padding-bottom:26px;text-align:center}
  .txt>.title,.txt>.wrapT,.txt>h1{align-self:center}
  .txt>.sub,.txt>.chips,.txt>.foot{grid-row:3;align-self:end}
  .txt .tl1,.txt .tl2{font-size:58px!important;letter-spacing:-1.5px!important}
  .txt .kick{font-size:20px!important;padding:6px 16px!important;margin-bottom:14px!important}
  .txt h1{font-size:68px!important}
  .txt .sub{font-size:27px!important;line-height:1.35!important}
  .txt>.sub[style*="font-weight:600"]{font-size:38px!important}
  .txt .chip{font-size:24px!important;padding:10px 20px!important}
  .txt .chips{justify-content:center!important;margin-top:0!important}
  .txt .foot img{width:170px!important;margin:0 auto 8px!important}
  .txt .foot .tl{font-size:24px!important}.txt .foot .url{font-size:34px!important}
  ${hideSubSq ? '.txt>.sub{display:none!important}' : ''}
  `}`;
  document.head.appendChild(st);
  const scenes = document.querySelectorAll('.sc').length ? [...document.querySelectorAll('.sc')] : [document.querySelector('.stage')];
  for (const sc of scenes) {
    const txt = document.createElement('div'); txt.className = 'txt';
    const vo = document.createElement('div'); vo.className = 'visO';
    const vi = document.createElement('div'); vi.className = 'visI'; vo.appendChild(vi);
    for (const ch of [...sc.children]) {
      if (ch.matches('.bg') || ch.tagName === 'STYLE' || ch.tagName === 'SCRIPT') continue;
      if (ch.matches('img') && ch.style.display === 'none') continue;
      if (ch.matches(textSel)) { txt.appendChild(ch); continue; }
      if (ch.tagName === 'DIV' && ch.querySelector(':scope > .title')) { ch.classList.add('wrapT'); txt.appendChild(ch); continue; }
      vi.appendChild(ch);
    }
    const hasText = txt.children.length > 0;
    let s, x, y;
    if (fmt === 'h') {
      s = H / WH; const vw = 1080 * s;
      x = hasText ? W - vw - 70 : (W - vw) / 2; y = 0;
      if (hasText) txt.style.width = (x - 110 - 30) + 'px';
    } else {
      const top = hasText ? 240 : 20, bot = hasText ? sqBottom : 20;
      const vh = H - top - bot; s = vh / WH; const vw = 1080 * s;
      x = (W - vw) / 2; y = top;
    }
    vo.style.transform = `translate(${x}px,${y}px) scale(${s})`;
    sc.appendChild(vo); sc.appendChild(txt);
  }
}
