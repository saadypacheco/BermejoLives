// uruku.bo/privacidad: la política de privacidad. El texto vive en
// content/legal/politica-privacidad.md (copia de docs/legal/politica-privacidad.md). Estática.

import type { Metadata } from "next";
import { PaginaLegal } from "@/components/legal/pagina-legal";
import { LEGAL, LEGAL_PUBLICADO } from "@/lib/legal-pure";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: LEGAL.privacidad.titulo,
  description: LEGAL.privacidad.descripcion,
  alternates: { canonical: LEGAL.privacidad.ruta },
  // Sin indexar hasta que el texto esté completo (LEGAL_PUBLICADO).
  robots: { index: LEGAL_PUBLICADO, follow: LEGAL_PUBLICADO },
};

export default function Privacidad() {
  return <PaginaLegal tipo="privacidad" />;
}
