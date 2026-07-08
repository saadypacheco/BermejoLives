import type { Metadata, Viewport } from "next";
import "./globals.css";
import { SwRegister } from "@/components/sw-register";
import { InstallPrompt } from "@/components/install-prompt";
import { ErrorListener } from "@/components/error-listener";
import { WebVitalsReporter } from "@/components/web-vitals-reporter";

export const metadata: Metadata = {
  title: "Encontralo — Comercios y ofertas en el mapa",
  description:
    "Encontralo en el mapa. Reservalo en la tienda. Todo lo que se vende en tu ciudad, en tiempo real.",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Encontralo" },
  icons: { icon: "/icon-192.png", apple: "/apple-touch-icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#0d1117",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* Acelera la primera carga del mapa con internet lento */}
        <link rel="preconnect" href="https://unpkg.com" />
        <link rel="preconnect" href="https://a.basemaps.cartocdn.com" crossOrigin="" />
        <link rel="dns-prefetch" href="https://b.basemaps.cartocdn.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <ErrorListener />
        <WebVitalsReporter />
        <InstallPrompt />
        {children}
        <SwRegister />
      </body>
    </html>
  );
}
