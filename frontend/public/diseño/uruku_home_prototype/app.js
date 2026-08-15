// Base simple para empezar.
// Acá podés conectar luego:
// - buscador real
// - selector de ciudad
// - cotizaciones vía API
// - clima
// - ofertas desde Supabase / API propia

document.querySelector('.search')?.addEventListener('submit', (e) => {
  e.preventDefault();
  const q = e.currentTarget.querySelector('input').value.trim();
  if (q) alert(`Buscar: ${q}`);
});
