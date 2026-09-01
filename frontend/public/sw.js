/* Encontralo PWA service worker — resiliencia para internet malo.
   Estrategia:
   - Tiles del mapa (OpenStreetMap) + Leaflet (unpkg): cache-first (lo más pesado).
   - Estáticos de Next / iconos / fuentes: stale-while-revalidate.
   - Navegación (HTML): network-first con fallback a caché / home.
   Bump VERSION para invalidar cachés viejas en cada deploy importante. */
// v6 (2026-08-31): carrito de reservas, /reservas y las ofertas en la tarjeta
// del buscador. Sin el bump, el celular sigue sirviendo el bundle viejo desde
// la caché y el botón "Reservar" no aparece por más que el deploy haya salido
// bien — lo primero que hay que descartar cuando algo "no llegó" al teléfono.
// v5 (2026-08-31): el iPhone mandaba las altas de campo con el cuerpo vacío.
// El bump acá NO es cosmético: mientras el celular sirva el bundle viejo desde
// la caché, el arreglo no le llega y el agente sigue sin poder subir su
// trabajo. Es lo primero que hay que descartar cuando un arreglo "no funciona"
// en el teléfono y sí en el servidor.
const VERSION = "uruku-v17";
const SHELL = `${VERSION}-shell`;
const STATIC = `${VERSION}-static`;
const TILES = `${VERSION}-tiles`;
const TILE_MAX = 500;

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

async function trim(name, max) {
  const c = await caches.open(name);
  const keys = await c.keys();
  for (let i = 0; i < keys.length - max; i++) await c.delete(keys[i]);
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Tiles del mapa + Leaflet CDN → cache-first (no se vuelven a descargar)
  if (url.hostname === "tile.openstreetmap.org" || url.hostname === "unpkg.com") {
    e.respondWith((async () => {
      const c = await caches.open(TILES);
      const hit = await c.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res.ok) { await c.put(req, res.clone()); trim(TILES, TILE_MAX); }
        return res;
      } catch {
        return hit || Response.error();
      }
    })());
    return;
  }

  if (url.origin !== self.location.origin) return;

  // Estáticos de Next, iconos, fuentes, manifest → stale-while-revalidate
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/reservalo/_next/static/") ||
    url.pathname.startsWith("/icon") ||
    url.pathname === "/manifest.webmanifest" ||
    url.pathname === "/campo.webmanifest" ||
    /\.(png|jpe?g|svg|webp|ico|woff2?)$/.test(url.pathname)
  ) {
    e.respondWith((async () => {
      const c = await caches.open(STATIC);
      const hit = await c.match(req);
      const net = fetch(req).then((res) => { if (res.ok) c.put(req, res.clone()); return res; }).catch(() => hit);
      return hit || net;
    })());
    return;
  }

  // Navegación (HTML) → network-first, fallback a caché / home
  if (req.mode === "navigate") {
    e.respondWith((async () => {
      const c = await caches.open(SHELL);
      try {
        const res = await fetch(req);
        if (res.ok) c.put(req, res.clone());
        return res;
      } catch {
        return (await c.match(req)) || (await c.match("/")) || Response.error();
      }
    })());
  }
});
