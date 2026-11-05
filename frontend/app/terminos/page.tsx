// uruku.bo/terminos: los términos y condiciones de uso. El texto vive en
// content/legal/terminos.md (copia de docs/legal/terminos.md). Estática.

import type { Metadata } from "next";
import { PaginaLegal } from "@/components/legal/pagina-legal";
import { LEGAL, LEGAL_PUBLICADO } from "@/lib/legal-pure";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: LEGAL.terminos.titulo,
  description: LEGAL.terminos.descripcion,
  alternates: { canonical: LEGAL.terminos.ruta },
  // Sin indexar hasta que el texto esté completo (LEGAL_PUBLICADO).
  robots: { index: LEGAL_PUBLICADO, follow: LEGAL_PUBLICADO },
};

export default function Terminos() {
  return <PaginaLegal tipo="terminos" />;
}
