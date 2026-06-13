/* ============================================================
   BERMEJO — business profile & product page interactions
   ============================================================ */
(function () {
  "use strict";
  const ph = (s, w, h) => `https://picsum.photos/seed/${s}/${w}/${h}`;
  const WA = `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M17.5 14.4c-.3-.2-1.7-.8-2-.9-.3-.1-.5-.2-.7.2s-.8.9-.9 1.1c-.2.2-.3.2-.6.1-1.7-.9-2.9-1.6-4-3.6-.3-.5.3-.5.8-1.5.1-.2 0-.4 0-.5 0-.2-.7-1.6-.9-2.2-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1.1 2.9 1.2 3.1c.2.2 2.1 3.3 5.2 4.6 1.9.8 2.6.9 3.6.7.6-.1 1.7-.7 2-1.4.2-.7.2-1.2.2-1.4Z"/></svg>`;

  /* ----- Tabs (profile) ----- */
  const tabs = document.querySelectorAll(".tab");
  tabs.forEach((t) =>
    t.addEventListener("click", () => {
      tabs.forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".tabpanel").forEach((p) => p.classList.remove("active"));
      t.classList.add("active");
      document.getElementById(t.dataset.tab).classList.add("active");
    })
  );

  /* ----- Product card builder ----- */
  const products = [
    { name: "iPhone 13 128GB", price: "499 USD", s: "iphone13" },
    { name: 'Smart TV 55" 4K', price: "399 USD", s: "tv55" },
    { name: "Notebook Gamer", price: "650 USD", s: "laptop" },
    { name: "AirPods Pro", price: "120 USD", s: "airpods" },
    { name: "PlayStation 5", price: "520 USD", s: "ps5" },
    { name: "Smartwatch", price: "85 USD", s: "watch" },
    { name: "Cámara DSLR", price: "430 USD", s: "camera" },
    { name: "Tablet 11\"", price: "240 USD", s: "tablet" },
  ];
  const card = (p) => `
    <a class="offer" href="producto.html">
      <div class="media"><img src="${ph(p.s, 400, 400)}" alt="${p.name}" loading="lazy"/></div>
      <div class="body">
        <h4>${p.name}</h4>
        <div class="price">${p.price}</div>
        <div class="foot">
          <span class="biz">Importadora ABC</span>
          <span class="wa-mini" style="background:var(--wa)">${WA}</span>
        </div>
      </div>
    </a>`;
  const fill = (id, list) => { const el = document.getElementById(id); if (el) el.innerHTML = list.map(card).join(""); };
  fill("bizProducts", products);
  fill("bizOffers", products.slice(0, 4));
  fill("related", products.slice(2, 6));

  /* ----- Videos in profile ----- */
  const bv = document.getElementById("bizVideos");
  if (bv) {
    bv.innerHTML = ["v1","v2","v3","v4","v5"].map((s, i) => `
      <div class="vid">
        <img src="${ph("biz" + s, 300, 500)}" alt="" loading="lazy"/>
        <span class="play"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M6 4l14 8-14 8Z"/></svg></span>
        <span class="views"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px"><path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>${(9 - i)}.${i}K</span>
      </div>`).join("");
  }

  /* ----- Product gallery swap ----- */
  const main = document.getElementById("mainImg");
  document.querySelectorAll(".gallery .thumbs img").forEach((th) =>
    th.addEventListener("click", () => {
      document.querySelectorAll(".gallery .thumbs img").forEach((x) => x.classList.remove("active"));
      th.classList.add("active");
      if (main) main.src = th.dataset.full;
    })
  );
})();
