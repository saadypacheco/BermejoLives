// uruku.bo/que-es-uruku: «Qué es URUKU», para la gente y los medios (7/10,
// lanzamiento). Es la dirección corta y fácil de dictar de /manual/uruku; las
// dos arman la misma página. No figura en ningún menú: se comparte el enlace.

import type { Metadata } from "next";
import { PaginaManualServidor } from "@/components/manual/manual-servidor";

export const dynamic = "force-static";

export const metadata: Metadata = {
  title: "Qué es URUKU",
  description: "Todo lo que se vende y se ofrece en Bermejo, desde el celular. Cómo nace, qué ofrece y cómo contactar a URUKU.",
  // No figura en los menús: se comparte el enlace. Tampoco se ofrece a buscadores.
  robots: { index: false, follow: false },
};

export default function QueEsUruku() {
  return <PaginaManualServidor tipo="uruku" />;
}
