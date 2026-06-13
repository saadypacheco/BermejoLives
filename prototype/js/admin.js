/* ============================================================
   BERMEJO — admin dashboard & moderation
   ============================================================ */
(function () {
  "use strict";
  const ph = (s, w, h) => `https://picsum.photos/seed/${s}/${w}/${h}`;

  /* ----- View switching (sidebar) ----- */
  const links = document.querySelectorAll(".side-link[data-view]");
  links.forEach((l) =>
    l.addEventListener("click", (e) => {
      e.preventDefault();
      links.forEach((x) => x.classList.remove("active"));
      document.querySelectorAll(".side-link").forEach((x) => x.classList.remove("active"));
      l.classList.add("active");
      ["dashboard", "moderacion"].forEach((v) => {
        const el = document.getElementById(v);
        if (el) el.style.display = v === l.dataset.view ? "block" : "none";
      });
    })
  );
  // any non-view link just highlights
  document.querySelectorAll(".side-link:not([data-view])").forEach((l) =>
    l.addEventListener("click", (e) => e.preventDefault())
  );

  /* ----- Chart ----- */
  const chart = document.getElementById("chart");
  if (chart) {
    const data = [38, 52, 44, 67, 58, 80, 72];
    const days = ["L", "M", "M", "J", "V", "S", "D"];
    chart.innerHTML = data
      .map((v, i) => `<div class="bar" style="height:${v}%"><span>${days[i]}</span></div>`)
      .join("");
  }

  /* ----- Business table ----- */
  const biz = [
    { n: "Importadora ABC", z: "Importadoras", o: 32, plan: "Premium", st: "ok", lbl: "Verificado", a: "abc" },
    { n: "Moda Bermejo", z: "Zona Moda", o: 27, plan: "Pro", st: "ok", lbl: "Verificado", a: "moda" },
    { n: "Tecno Store", z: "Tecnología", o: 18, plan: "Pro", st: "pend", lbl: "En revisión", a: "tec" },
    { n: "Perfumería VIP", z: "Centro", o: 22, plan: "Premium", st: "ok", lbl: "Verificado", a: "perf" },
    { n: "Calzados Top", z: "Zona Moda", o: 15, plan: "Gratis", st: "pend", lbl: "En revisión", a: "calz" },
  ];
  const bt = document.getElementById("bizTable");
  if (bt) {
    bt.innerHTML = biz
      .map(
        (b) => `<tr>
        <td><div class="u"><img src="${ph(b.a, 80, 80)}" alt=""/><b>${b.n}</b></div></td>
        <td>${b.z}</td>
        <td>${b.o}</td>
        <td>${b.plan}</td>
        <td><span class="status ${b.st}">${b.lbl}</span></td>
      </tr>`
      )
      .join("");
  }

  /* ----- Moderation queue ----- */
  const queue = [
    { biz: "Importadora ABC", txt: "Notebooks gamer recién llegadas, stock limitado a precio de frontera.", price: "650 USD", zone: "Importadoras", time: "Hace 3 min", img: "qmod1" },
    { biz: "Moda Bermejo", txt: "Camperas de cuero temporada invierno. Todos los talles disponibles.", price: "280 Bs", zone: "Zona Moda", time: "Hace 7 min", img: "qmod2" },
    { biz: "Perfumería VIP", txt: "Set de perfumes importados originales, ideal para regalo.", price: "450 Bs", zone: "Centro Comercial", time: "Hace 12 min", img: "qmod3" },
    { biz: "Tecno Store", txt: "Smart TV 55 pulgadas 4K última generación con garantía.", price: "399 USD", zone: "Tecnología", time: "Hace 18 min", img: "qmod4" },
  ];
  const mq = document.getElementById("modQueue");
  if (mq) {
    mq.innerHTML = queue
      .map(
        (q, i) => `<div class="mod-item" data-i="${i}">
        <img src="${ph(q.img, 240, 168)}" alt=""/>
        <div>
          <h4>${q.biz}</h4>
          <p>${q.txt}</p>
          <div class="mm">
            <span style="color:var(--neon);font-weight:700">${q.price}</span>
            <span>📍 ${q.zone}</span>
            <span>🕒 ${q.time}</span>
          </div>
        </div>
        <div class="mod-actions">
          <button class="mbtn approve" title="Aprobar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6 9 17l-5-5"/></svg></button>
          <button class="mbtn edit" title="Solicitar cambios"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4v16h16v-7"/><path d="M18.5 2.5a2.1 2.1 0 0 1 3 3L12 15l-4 1 1-4Z"/></svg></button>
          <button class="mbtn reject" title="Rechazar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
        </div>
      </div>`
      )
      .join("");

    // wire up actions
    mq.addEventListener("click", (e) => {
      const btn = e.target.closest(".mbtn");
      if (!btn) return;
      const item = btn.closest(".mod-item");
      const action = btn.classList.contains("approve") ? "Aprobada ✅" : btn.classList.contains("reject") ? "Rechazada ❌" : "Cambios solicitados ✏️";
      item.style.transition = ".4s cubic-bezier(.22,.61,.36,1)";
      item.style.opacity = "0";
      item.style.transform = "translateX(40px)";
      setTimeout(() => {
        item.outerHTML = `<div class="mod-item" style="justify-content:center;color:var(--txt-3)"><span>Publicación ${action}</span></div>`;
        // update badge count
        const badge = document.querySelector(".side-link .badge");
        if (badge) { const n = Math.max(0, parseInt(badge.textContent) - 1); badge.textContent = n; }
      }, 380);
    });
  }
})();
