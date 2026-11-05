import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    // Sin ciudad: el manifest es uno solo para todo el dominio y la app
    // instalada la abre gente de cualquier ciudad.
    name: "Uruku · Comercios, ofertas y cambio del día",
    short_name: "Uruku",
    description: "Los comercios de tu ciudad en un solo lugar: qué se vende, cuánto cuesta y dónde queda.",
    start_url: "/",
    scope: "/", // cubre todo el dominio, incluida la futura tienda en /tienda
    display: "standalone",
    orientation: "portrait",
    // Los del manual de identidad. El `background_color` es lo que se ve
    // mientras la app instalada arranca: el crema de la marca, no el casi
    // negro que venía de la época «Bermejo dark».
    background_color: "#F9F6ED",
    theme_color: "#1D8D52",
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
    // El símbolo COMPLETO de la marca (la U dorada con la gota y las semillas;
    // docs/Uruku-KIT-COMPLETO/2-Logos-y-Dax/uruku-simbolo-color.svg) sobre el
    // crema #F9F6ED. Antes eran la versión simplificada del kit, sin semillas,
    // y el dueño las veía «parecidas pero no las correctas».
    //
    // `any` y `maskable` van en entradas SEPARADAS: una sola con
    // `purpose: "any maskable"` obliga a que el mismo dibujo sirva para los dos,
    // y no sirve. El maskable tiene el símbolo dentro del 80 % central (zona
    // segura) para que Android lo recorte en círculo o en gota sin morder nada.
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
