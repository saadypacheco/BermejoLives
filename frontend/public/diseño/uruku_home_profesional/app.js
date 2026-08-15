const searchForm = document.getElementById("searchForm");
const searchInput = document.getElementById("searchInput");
const newsletterForm = document.getElementById("newsletterForm");
const newsletterEmail = document.getElementById("newsletterEmail");
const navItems = document.querySelectorAll(".nav-item");
const locationBtn = document.getElementById("locationBtn");

function toast(message) {
  const old = document.querySelector(".toast");
  if (old) old.remove();

  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  document.body.appendChild(el);

  setTimeout(() => el.remove(), 2600);
}

searchForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  const value = searchInput.value.trim();

  if (!value) {
    toast("Escribí qué comercio, producto o servicio querés encontrar.");
    searchInput.focus();
    return;
  }

  toast(`Buscando “${value}” en Bermejo...`);
});

newsletterForm?.addEventListener("submit", (e) => {
  e.preventDefault();
  const email = newsletterEmail.value.trim();

  if (!email) return;
  toast("¡Listo! Te sumaste a las novedades de Uruku.");
  newsletterForm.reset();
});

navItems.forEach((item) => {
  item.addEventListener("click", () => {
    navItems.forEach((x) => x.classList.remove("active"));
    item.classList.add("active");
    toast(`Categoría: ${item.dataset.category}`);
  });
});

locationBtn?.addEventListener("click", () => {
  toast("Selector de ciudad: por ahora Bermejo.");
});
