import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SwRegister } from "@/components/sw-register";
import { VersionCheck } from "@/components/version-check";
import { InstallPrompt } from "@/components/install-prompt";
import { ErrorListener } from "@/components/error-listener";
import { WebVitalsReporter } from "@/components/web-vitals-reporter";
import { RefCapture } from "@/components/ref-capture";
import { PreguntaContesto } from "@/components/pregunta-contesto";
import { ContadorVisitas } from "@/components/contador-visitas";
import { Suspense } from "react";
import { MARCA, COLOR } from "@/lib/marca";
import { Poppins } from "next/font/google";

/** La tipografía de la marca (manual de identidad · Tipografía).
 *
 *  Va por `next/font` y no por un <link> a Google: así la fuente se sirve
 *  DESDE uruku.bo, sin una conexión más a otro dominio —que en Bermejo con
 *  3G es medio segundo— y sin el salto de texto al cargar.
 *
 *  Antes la web descargaba Inter y después no la usaba: `#ukroot` pedía la
 *  fuente del sistema. O sea que URUKU se veía con Segoe UI en Windows,
 *  Roboto en Android y SF en iPhone —tres marcas distintas— y encima pagaba
 *  la descarga de una fuente que nadie veía. */
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
  variable: "--uk-font",
});

export const metadata: Metadata = {
  // SIN CIUDAD. Éste es el título de respaldo: el que usa cualquier pantalla
  // que no declare el suyo. La home y las de contenido ponen la ciudad con su
  // propio `generateMetadata`, porque nombrar Bermejo acá significaría que
  // compartir el enlace de Santa Cruz muestra «Todo Bermejo en un solo lugar».
  title: { default: `${MARCA} · Comercios, ofertas y cambio del día`, template: `%s · ${MARCA}` },
  description:
    "Los comercios de tu ciudad en un solo lugar: qué se vende, cuánto cuesta, dónde queda y el WhatsApp de cada local.",
  metadataBase: new URL("https://uruku.bo"),
  openGraph: { siteName: MARCA, locale: "es_BO", type: "website" },
  appleWebApp: { capable: true, statusBarStyle: "default", title: MARCA },
  icons: {
    icon: [
      { url: "/favicon.svg", type: "image/svg+xml" },
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
    ],
    apple: "/apple-touch-icon.png",
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  // El verde de la marca, no el casi-negro que venía de la época «Bermejo
  // dark»: es el color de la barra del navegador en Android y de la franja
  // superior en iOS, o sea lo primero que se ve al abrir el sitio.
  themeColor: COLOR.verde,
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={poppins.variable}>
      <head>
        {/* Acelera la primera carga del mapa con internet lento */}
        <link rel="preconnect" href="https://unpkg.com" />
        <link rel="preconnect" href="https://tile.openstreetmap.org" crossOrigin="" />
      </head>
      {/* Poppins en TODO: el sitio público y el panel. Antes el panel usaba
          Inter y el sitio la fuente del sistema, así que no había una sola
          tipografía de URUKU en ningún lado. */}
      <body className={poppins.className}>
        <ErrorListener />
        <WebVitalsReporter />
        <RefCapture />
        <PreguntaContesto />
        {/* Cuenta las páginas vistas. Va en Suspense porque usa
            useSearchParams: sin esto, TODA la página se renderiza del lado del
            cliente y se pierde el HTML del servidor. */}
        <Suspense fallback={null}><ContadorVisitas /></Suspense>
        <InstallPrompt />
        {children}
        <SwRegister />
        <VersionCheck />
      </body>
    </html>
  );
}
