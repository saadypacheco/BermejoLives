// /manual/agente · /manual/admin · /manual/comercio · /manual/uruku (= /que-es-uruku)
//
// El contenido vive en `content/manuales/<tipo>.md` (lo escribe el redactor) y
// se lee ACÁ, en el servidor, una sola vez: `generateStaticParams` + `dynamicParams
// = false` hacen que el build genere las tres páginas y que cualquier otra
// (`/manual/otra-cosa`) sea un 404.
//
// POR QUÉ NO HACE FALTA COPIAR EL .md AL SERVIDOR
// El Dockerfile de producción copia sólo `.next`, `public` y `next.config.mjs`
// (`next start`, no `standalone`). El .md se lee durante `next build`, cuando la
// carpeta `content/` sí está, y queda adentro del HTML ya generado en `.next`.
// En runtime no se vuelve a abrir ningún archivo.

import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PaginaManualServidor } from "@/components/manual/manual-servidor";
import { TIPOS_MANUAL, TITULO_MANUAL, esTipoManual } from "@/lib/manuales";

export const dynamicParams = false;
export const dynamic = "force-static";

export function generateStaticParams() {
  return TIPOS_MANUAL.map((tipo) => ({ tipo }));
}

export function generateMetadata({ params }: { params: { tipo: string } }): Metadata {
  const titulo = esTipoManual(params.tipo) ? TITULO_MANUAL[params.tipo] : "Manual";
  // El contenido no es secreto, pero no es para buscadores.
  return { title: titulo, robots: { index: false, follow: false, nocache: true } };
}

export default async function ManualRuta({ params }: { params: { tipo: string } }) {
  if (!esTipoManual(params.tipo)) notFound();
  return <PaginaManualServidor tipo={params.tipo} />;
}
