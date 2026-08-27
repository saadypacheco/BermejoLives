import { readFileSync } from "node:fs";

// Versión del producto horneada en el bundle. package.json es la versión
// semántica; GIT_SHA/APP_ENV los pasa el build (ARG del Dockerfile) y la
// fecha se toma del momento del build.
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));
const buildTime = new Date().toISOString();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
    if ((process.env.APP_ENV || "").toLowerCase() === "prod") return [];
    return [{
      source: "/:path*",
      headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow, noarchive" }],
    }];
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
      { protocol: "https", hostname: "i.pravatar.cc" },
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },
};

export default nextConfig;
