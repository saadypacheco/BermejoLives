import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "URUKU — Comercios y ofertas en el mapa",
    short_name: "URUKU",
    description: "URUKU en el mapa. Reservalo en la tienda.",
    start_url: "/",
    scope: "/", // cubre todo el dominio, incluida la futura tienda en /tienda
    display: "standalone",
    orientation: "portrait",
    background_color: "#0d1117",
    theme_color: "#0d1117",
    lang: "es",
    categories: ["shopping", "business", "maps"],
    icons: [
      { src: "/logouruku-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/logouruku.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // maskable queda en el ícono con margen seguro (el logo circular se recortaría en Android).
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
