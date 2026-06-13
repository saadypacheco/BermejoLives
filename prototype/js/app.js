/* ============================================================
   BERMEJO LIVE MARKET — interactions & dynamic content
   ============================================================ */
(function () {
  "use strict";

  /* ---------- Image helpers (work offline via picsum/unsplash) ---------- */
  const ph = (seed, w, h) => `https://picsum.photos/seed/${seed}/${w}/${h}`;
  const av = (n) => `https://i.pravatar.cc/80?img=${n}`;

  /* ============================================================
     1. Isometric city grid (conceptual, not real streets)
     ============================================================ */
  const iso = document.getElementById("isoGrid");
  if (iso) {
    // height + accent pattern for a lively skyline
    const heights = ["low","mid","tall","mid","low","mid","tall","low","mid","tall","mid","low",
                     "mid","tall","low","mid","tall","mid","low","mid","tall","mid","low","tall",
                     "tall","low","mid","tall","low","mid","mid","tall","low","mid","tall","low"];
    const accents = { 2:"neon", 8:"purple", 14:"pink", 21:"neon", 27:"purple", 33:"pink", 6:"neon", 19:"purple" };
    for (let i = 0; i < 36; i++) {
      const tile = document.createElement("div");
      tile.className = "tile";
      const b = document.createElement("div");
      const accent = accents[i] ? " " + accents[i] : "";
      b.className = "bld " + (heights[i] || "mid") + accent;
      // tiny stagger via inline animation delay-like transform jitter
      tile.appendChild(b);
      iso.appendChild(tile);
    }
  }

  /* ============================================================
     2. Animated counters
     ============================================================ */
  const fmt = (n) => n.toLocaleString("es-BO");
  function animateCount(el) {
    const target = +el.dataset.count;
    const prefix = el.textContent.trim().startsWith("+") ? "+" : "";
    const dur = 1400, t0 = performance.now();
    function step(now) {
      const p = Math.min((now - t0) / dur, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = prefix + fmt(Math.floor(target * eased));
      if (p < 1) requestAnimationFrame(step);
      else el.textContent = prefix + fmt(target);
    }
    requestAnimationFrame(step);
  }
  const counters = document.querySelectorAll("[data-count]");
  const cObs = new IntersectionObserver((entries, o) => {
    entries.forEach((e) => { if (e.isIntersecting) { animateCount(e.target); o.unobserve(e.target); } });
  }, { threshold: 0.6 });
  counters.forEach((c) => cObs.observe(c));

  /* ============================================================
     3. Data
     ============================================================ */
  const offers = [
    { name: "Zapatillas Nike Air", price: "120 Bs", t: "14:32", biz: "Moda Bermejo", img: ph("nike", 400, 400), a: 11 },
    { name: "iPhone 13 128GB", price: "499 USD", t: "14:31", biz: "Importadora XYZ", img: ph("iphone", 400, 400), a: 32 },
    { name: "Perfume 212 VIP", price: "250 Bs", t: "14:29", biz: "Perfumería VIP", img: ph("perfume", 400, 400), a: 15 },
    { name: 'Smart TV 55" 4K', price: "399 USD", t: "14:26", biz: "Tecno Hogar", img: ph("tv", 400, 400), a: 45 },
  ];

  const vids = [
    { views: "12.4K", img: ph("hoodie", 300, 500) },
    { views: "8.7K",  img: ph("sneaker", 300, 500) },
    { views: "6.2K",  img: ph("store", 300, 500) },
  ];

  const feed = [
    { biz: "Importadora ABC", a: 8, time: "Hace 2 min", img: ph("electronics", 700, 440), verified: true,
      text: "🔥 Llegaron las nuevas notebooks gamer. Stock limitado, precio de frontera imbatible.",
      price: "650 USD", loc: "Zona Importadoras" },
    { biz: "Calzados Top", a: 14, time: "Hace 6 min", img: ph("boots", 700, 440), verified: true,
      text: "Botas de cuero 100% legítimo. Todos los talles disponibles para mayoristas y minoristas.",
      price: "320 Bs", loc: "Zona Moda" },
    { biz: "Perfumería VIP", a: 15, time: "Hace 11 min", img: ph("perfume2", 700, 440), verified: false,
      text: "Set de perfumes importados originales. Ideal para regalo. Consultá disponibilidad por WhatsApp.",
      price: "450 Bs", loc: "Centro Comercial" },
  ];

  const featured = [
    { name: "Importadora ABC", zone: "Zona Importadoras", offers: 32, rating: "4.9", img: ph("imp1", 120, 120), a: 5 },
    { name: "Moda Bermejo", zone: "Zona Moda", offers: 27, rating: "4.8", img: ph("moda1", 120, 120), a: 12 },
    { name: "Tecno Store", zone: "Zona Tecnología", offers: 18, rating: "4.7", img: ph("tec1", 120, 120), a: 8 },
  ];

  const bizGrid = [
    { name: "Importadora ABC", zone: "Zona Importadoras", offers: 32, img: ph("g1", 500, 340), logo: ph("l1", 120, 120) },
    { name: "Moda Bermejo", zone: "Zona Moda", offers: 27, img: ph("g2", 500, 340), logo: ph("l2", 120, 120) },
    { name: "Tecno Store", zone: "Zona Tecnología", offers: 18, img: ph("g3", 500, 340), logo: ph("l3", 120, 120) },
    { name: "Perfumería VIP", zone: "Centro Comercial", offers: 22, img: ph("g4", 500, 340), logo: ph("l4", 120, 120) },
    { name: "Calzados Top", zone: "Zona Moda", offers: 15, img: ph("g5", 500, 340), logo: ph("l5", 120, 120) },
  ];

  /* ============================================================
     4. Render
     ============================================================ */
  const WA = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2s-.8.9-.9 1.1c-.2.2-.3.2-.6.1-1.7-.9-2.9-1.6-4-3.6-.3-.5.3-.5.8-1.5.1-.2 0-.4 0-.5 0-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.3 5.2 4.6 1.9.8 2.6.9 3.6.7.6-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4-.1-.1-.3-.2-.6-.3ZM12 2a10 10 0 0 0-8.6 15l-1.3 4.7 4.8-1.3A10 10 0 1 0 12 2Z"/></svg>`;
  const PIN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 21s-7-5.5-7-11a7 7 0 0 1 14 0c0 5.5-7 11-7 11Z"/><circle cx="12" cy="10" r="2.5"/></svg>`;
  const VERIF = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="m9 12 2 2 4-4m-3-7 2.3 1.6 2.8-.2 1 2.6 2.3 1.6-.8 2.7.8 2.7-2.3 1.6-1 2.6-2.8-.2L12 23l-2.3-1.6-2.8.2-1-2.6L3.6 17l.8-2.7-.8-2.7 2.3-1.6 1-2.6 2.8.2Z"/></svg>`;

  const set = (id, html) => { const el = document.getElementById(id); if (el) el.innerHTML = html; };

  set("offersRow", offers.map((o) => `
    <article class="offer">
      <div class="media">
        <img src="${o.img}" alt="${o.name}" loading="lazy"/>
        <span class="time"><span class="dot-live"></span>${o.t}</span>
      </div>
      <div class="body">
        <h4>${o.name}</h4>
        <div class="price">${o.price}</div>
        <div class="foot">
          <span class="biz"><img src="${av(o.a)}" alt=""/>${o.biz}</span>
          <a class="wa-mini" href="https://wa.me/591700000000" target="_blank" rel="noopener" aria-label="WhatsApp">${WA}</a>
        </div>
      </div>
    </article>`).join(""));

  set("vidsRow", vids.map((v) => `
    <div class="vid">
      <img src="${v.img}" alt="" loading="lazy"/>
      <span class="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 4l14 8-14 8Z"/></svg></span>
      <span class="views"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>${v.views}</span>
    </div>`).join(""));

  set("feed", feed.map((p) => `
    <article class="post">
      <div class="phead">
        <img src="${av(p.a)}" alt=""/>
        <div style="flex:1">
          <b>${p.biz} ${p.verified ? `<span class="pverif">${VERIF}</span>` : ""}</b>
          <small>${p.time} · ${p.loc}</small>
        </div>
        <button class="wa-mini" aria-label="Más">···</button>
      </div>
      <div class="pmedia"><img src="${p.img}" alt="" loading="lazy"/></div>
      <div class="pbody">
        <p>${p.text}</p>
        <div class="pmeta">
          <span class="pprice">${p.price}</span>
          <span>${PIN}${p.loc}</span>
          <span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px"><path d="M12 8v4l3 2"/><circle cx="12" cy="12" r="9"/></svg>Aprobado</span>
        </div>
        <div class="pactions">
          <a class="btn btn-wa btn-sm" href="https://wa.me/591700000000" target="_blank" rel="noopener">${WA} WhatsApp</a>
          <a class="btn btn-ghost btn-sm" href="negocio.html">Ver comercio</a>
          <a class="btn btn-ghost btn-sm" href="producto.html">${PIN} Cómo llegar</a>
        </div>
      </div>
    </article>`).join(""));

  set("featuredBiz", featured.map((b) => `
    <article class="post">
      <div class="phead">
        <img src="${b.img}" alt=""/>
        <div style="flex:1">
          <b><a href="negocio.html">${b.name}</a></b>
          <small>${b.zone}</small>
        </div>
        <span class="pill" style="font-size:11px;padding:5px 10px;border-radius:999px;background:var(--panel-2);border:1px solid var(--stroke);color:var(--amber)">★ ${b.rating}</span>
      </div>
      <div class="pbody" style="padding-top:0">
        <div class="pmeta" style="margin-bottom:10px">
          <span><svg viewBox="0 0 24 24" fill="none" stroke="var(--neon)" stroke-width="2" style="width:14px"><path d="M12 2c1 3-2 4-2 7a4 4 0 0 0 8 0"/></svg>${b.offers} ofertas activas</span>
        </div>
        <div class="pactions">
          <a class="btn btn-wa btn-sm" href="https://wa.me/591700000000" target="_blank" rel="noopener">${WA} Contactar</a>
          <a class="btn btn-ghost btn-sm" href="negocio.html">Ver perfil</a>
        </div>
      </div>
    </article>`).join(""));

  set("bizGrid", bizGrid.map((b) => `
    <a class="bizcard" href="negocio.html">
      <div class="cover">
        <img src="${b.img}" alt="${b.name}" loading="lazy"/>
        <img class="logo" src="${b.logo}" alt=""/>
      </div>
      <div class="body">
        <h4>${b.name}</h4>
        <div class="zone">${b.zone}</div>
        <div class="row">
          <span class="pill">${b.offers} ofertas</span>
          <span class="wa-mini" style="background:var(--wa)">${WA}</span>
        </div>
      </div>
    </a>`).join(""));

  /* ============================================================
     5. Scroll reveal
     ============================================================ */
  const rObs = new IntersectionObserver((entries) => {
    entries.forEach((e) => { if (e.isIntersecting) { e.target.classList.add("in"); rObs.unobserve(e.target); } });
  }, { threshold: 0.12 });
  document.querySelectorAll(".reveal").forEach((el) => rObs.observe(el));

  /* ============================================================
     6. Live ticker — randomly bump "usuarios conectados"
     ============================================================ */
  const liveEl = [...counters].find((c) => c.dataset.count === "1235");
  if (liveEl) {
    let base = 1235;
    setInterval(() => {
      base += Math.floor(Math.random() * 7) - 3;
      liveEl.textContent = fmt(base);
    }, 2600);
  }

  /* ============================================================
     7. Mobile menu (simple toggle)
     ============================================================ */
  const hamb = document.getElementById("hamb");
  const links = document.querySelector(".nav-links");
  if (hamb && links) {
    hamb.addEventListener("click", () => {
      const open = links.style.display === "flex";
      links.style.display = open ? "" : "flex";
      links.style.position = "absolute";
      links.style.top = "var(--nav-h)";
      links.style.left = "0"; links.style.right = "0";
      links.style.flexDirection = "column";
      links.style.background = "rgba(6,9,17,.96)";
      links.style.padding = "16px 24px";
      links.style.borderBottom = "1px solid var(--stroke)";
    });
  }
})();
