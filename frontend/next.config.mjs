import { readFileSync } from "node:fs";

// Versión del producto horneada en el bundle. package.json es la versión
// semántica; GIT_SHA/APP_ENV los pasa el build (ARG del Dockerfile) y la
// fecha se toma del momento del build.
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));
const buildTime = new Date().toISOString();

// ---- Content-Security-Policy (SOLO REPORTE) -----------------------------------
// Se arma con lo que el sitio usa de verdad. `headers()` se evalúa en el BUILD,
// así que los orígenes salen de las mismas NEXT_PUBLIC_* que se hornean en el
// bundle (build args del compose): la API y el caché de tiles.
//
// Va en `Content-Security-Policy-Report-Only`: no bloquea nada, sólo anota en la
// consola del navegador lo que NO entraría. Se mira unos días, se ajusta la lista
// y recién entonces se pasa a `Content-Security-Policy`. 'unsafe-inline' en script
// y style es por los <script> y <style> en línea que Next y el sitio generan
// (arranque de Next, JSON-LD, tema); sacarlo exige nonces por pedido, que a su vez
// vuelven dinámicas las páginas estáticas, así que queda para otra etapa.
const origen = (u) => {
  try { return new URL(u).origin; } catch { return null; }
};
const ORIGEN_API = origen(process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");
const ORIGEN_TILES = origen(process.env.NEXT_PUBLIC_TILES_URL || "");
const OSM = "https://tile.openstreetmap.org"; // respaldo de mapa-tiles.ts
const UNPKG = "https://unpkg.com"; // Leaflet (+ markercluster): JS, CSS e íconos
const CF_BEACON = "https://static.cloudflareinsights.com"; // Cloudflare Web Analytics: el script
const CF_RUM = "https://cloudflareinsights.com"; // ...y adonde manda las métricas
const unicos = (xs) => [...new Set(xs.filter(Boolean))];
const enDev = process.env.NODE_ENV !== "production";

function politicaCsp() {
  const directivas = {
    "default-src": ["'self'"],
    "script-src": ["'self'", "'unsafe-inline'", UNPKG, CF_BEACON, ...(enDev ? ["'unsafe-eval'"] : [])],
    "style-src": ["'self'", "'unsafe-inline'", UNPKG],
    // picsum: marcador de las fotos que faltan en el panel admin.
    "img-src": ["'self'", "data:", "blob:", ORIGEN_API, ORIGEN_TILES, OSM, UNPKG, "https://picsum.photos"],
    // Poppins sale de next/font (se sirve desde el propio sitio).
    "font-src": ["'self'", "data:"],
    "media-src": ["'self'", "blob:", ORIGEN_API],
    // El service worker pide tiles y Leaflet con fetch(): cuentan como connect.
    "connect-src": ["'self'", ORIGEN_API, ORIGEN_TILES, OSM, UNPKG, CF_RUM, ...(enDev ? ["ws:", "wss:"] : [])],
    "worker-src": ["'self'"],
    "manifest-src": ["'self'"],
    "frame-src": ["'none'"],
    "object-src": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  return Object.entries(directivas)
    .map(([nombre, valores]) => `${nombre} ${unicos(valores).join(" ")}`)
    .join("; ");
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Sin `X-Powered-By: Next.js`: no hay por qué decir con qué se hizo el sitio.
  poweredByHeader: false,
  // Caché de ISR en MEMORIA con tope (LRU), no en disco. Con `isrFlushToDisk` (el
  // valor por defecto) cada ruta distinta que se pide —`/.env`, `/<azar>/<azar>`,
  // `/comercios/<azar>`, un escáner las genera de a miles— deja un archivo en
  // `.next/server/app` para siempre: el disco del VPS crece sin límite. Con `false`
  // las páginas regeneradas viven en un LRU de `cacheMaxMemorySize` bytes (lo más
  // pedido se queda, lo basura sale) y se pierden al reiniciar el contenedor: se
  // vuelven a armar en el primer pedido. Las páginas del BUILD siguen en disco.
  // `cacheMaxMemorySize` es el tope: 64 MB (por defecto 50).
  cacheMaxMemorySize: 64 * 1024 * 1024,
  experimental: {
    isrFlushToDisk: false,
  },
  // La demo local de los manuales (scripts/demo) compila en su propia carpeta
  // para poder correr al lado de `npm run dev` sin pisarse el `.next`.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  env: {
    NEXT_PUBLIC_APP_VERSION: pkg.version,
    NEXT_PUBLIC_GIT_SHA: process.env.GIT_SHA || "dev",
    NEXT_PUBLIC_BUILD_TIME: buildTime,
    NEXT_PUBLIC_ENV_LABEL: process.env.APP_ENV || "",
  },
  // /publicador se renombró a /contenido: "publicador" y "publicar" (la app de
  // campo) se confundían entre sí. La redirección permanente mantiene vivos los
  // accesos directos y links guardados de quien ya tenía la ruta vieja.
  async redirects() {
    return [{ source: "/publicador", destination: "/contenido", permanent: true }];
  },
  // Cabecera anti-indexado en todo lo que NO es producción.
  //
  // El robots.txt no alcanza: Cloudflare inyecta su propio bloque gestionado
  // ANTES del nuestro, y ese bloque trae `User-agent: * / Allow: /`. Cuando dos
  // reglas del mismo largo compiten para el mismo agente —`Allow: /` contra
  // nuestro `Disallow: /`— los buscadores se quedan con la permisiva. Así que
  // en QA el robots quedaba anulado por el proxy.
  //
  // `X-Robots-Tag` viaja en la respuesta HTTP, no en un archivo que alguien
  // pueda mezclar con el suyo, y le gana a cualquier robots.txt. Es la única
  // forma de estar seguro con un proxy en el medio.
  //
  // Ante la duda —variable vacía o mal escrita— bloquea: que un sitio de
  // pruebas no se indexe no le cuesta nada a nadie; que se indexe con los datos
  // reales de los comercios, sí.
  async headers() {
    const reglas = [
      // El service worker no se cachea en el borde. Cloudflare le ponía cuatro
      // horas por ser .js, y en esas cuatro horas el celular que preguntaba
      // "¿hay service worker nuevo?" recibía el viejo. El navegador ya lo pide
      // sin usar su propia caché; faltaba que el proxy hiciera lo mismo.
      { source: "/sw.js", headers: [{ key: "Cache-Control", value: "no-cache" }] },
      // /pieza/<token> es la página privada del comerciante con su video: nunca se
      // cachea (ni en el navegador ni en el proxy) y nunca se indexa, ni siquiera en
      // producción. La metadata de la página dice lo mismo; esto va en la respuesta
      // HTTP para que ningún proxy lo pise.
      {
        source: "/pieza/:path*",
        headers: [
          { key: "Cache-Control", value: "private, no-store" },
          { key: "X-Robots-Tag", value: "noindex, nofollow" },
        ],
      },
    ];
    if ((process.env.APP_ENV || "").toLowerCase() !== "prod") {
      reglas.push({
        source: "/:path*",
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" }],
      });
    }
    // HSTS, X-Frame-Options, nosniff, Referrer-Policy y Permissions-Policy los pone
    // Traefik (docker-compose.prod.yml) para el sitio y la API por igual; acá va
    // sólo la CSP, que depende de lo que carga ESTE sitio.
    reglas.push({
      source: "/:path*",
      headers: [{ key: "Content-Security-Policy-Report-Only", value: politicaCsp() }],
    });
    return reglas;
  },
  // El sitio usa <img> común (no next/image): sin optimizador de imágenes del
  // servidor, que además queda sin superficie de ataque. Tampoco hay dominios
  // remotos que autorizar.
  images: { unoptimized: true },
};

export default nextConfig;
