import type { Metadata } from "next";

// Pantalla privada (de la cuenta o de una herramienta): fuera de los buscadores.
// La página es de cliente y no puede exportar `metadata`; por eso va en el layout.
// Va de la mano con `PRIVATE_PATHS` de lib/seo.ts (robots.txt).
export const metadata: Metadata = {
  robots: { index: false, follow: false },
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
