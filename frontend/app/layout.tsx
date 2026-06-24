import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Encontralo — Comercios y ofertas en el mapa",
  description:
    "Encontralo en el mapa. Reservalo en la tienda. Todo lo que se vende en tu ciudad, en tiempo real.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
