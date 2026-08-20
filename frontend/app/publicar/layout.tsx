import type { Metadata } from "next";

// El manifest raíz tiene start_url '/' y display 'standalone', así que instalar
// desde /publicar dejaba una app que abría el mapa y —sin barra de direcciones—
// no tenía ninguna forma de volver acá. Este manifest propio (id y scope
// distintos) hace que Chrome ofrezca instalar "URUKU Campo" como una app
// SEPARADA, que arranca directo en el alta de comercios.
export const metadata: Metadata = {
  title: "URUKU Campo — cargar comercios",
  manifest: "/campo.webmanifest",
  robots: { index: false, follow: false },  // herramienta interna
};

export default function PublicarLayout({ children }: { children: React.ReactNode }) {
  return children;
}
