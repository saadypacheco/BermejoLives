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
    // La app instalada corre en 'standalone': NO tiene barra de direcciones. Sin
    // esto, el agente de campo que instaló la PWA no tiene ninguna forma de
    // llegar a /publicar — el ícono siempre abre start_url ('/') y la interfaz
    // no linkea a las herramientas internas. Los shortcuts salen al mantener
    // apretado el ícono en Android.
    shortcuts: [
      {
        name: "Cargar comercio",
        short_name: "Cargar",
        description: "Alta rápida de un comercio durante el recorrido",
        url: "/publicar",
        icons: [{ src: "/logouruku-192.png", sizes: "192x192", type: "image/png" }],
      },
      {
        name: "Mis comercios",
        short_name: "Mis comercios",
        description: "Los comercios que cargaste, para completarles fotos y datos",
        url: "/publicar?vista=mis-comercios",
        icons: [{ src: "/logouruku-192.png", sizes: "192x192", type: "image/png" }],
      },
      {
        name: "Panel",
        short_name: "Panel",
        description: "Moderación, comercios y suscripciones",
        url: "/admin",
        icons: [{ src: "/logouruku-192.png", sizes: "192x192", type: "image/png" }],
      },
    ],
    icons: [
      { src: "/logouruku-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/logouruku.png", sizes: "512x512", type: "image/png", purpose: "any" },
      // maskable queda en el ícono con margen seguro (el logo circular se recortaría en Android).
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
