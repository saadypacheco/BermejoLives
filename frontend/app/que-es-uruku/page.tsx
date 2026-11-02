// uruku.bo/que-es-uruku: «Qué es URUKU», la página de Acerca de / Prensa.
//
// Indexable (docs/visibilidad-buscadores-ia.md §3.10): es la que contesta
// «¿qué es URUKU?», «¿quién lo hace?», «¿es confiable?» a buscadores y asistentes
// de IA. El texto vive en content/manuales/uruku.md (la misma página, con el
// botón «Guardar como PDF», se arma en /manual/uruku, que NO se indexa para no
// duplicar). Sin cifras de comercios.
//
// Es estática (el .md se lee durante `next build`; en producción no existe la
// carpeta content/): las ciudades y las preguntas de abajo son las del momento
// del build, y se actualizan en cada despliegue.

import type { Metadata } from "next";
import Link from "next/link";
import { PaginaManualServidor } from "@/components/manual/manual-servidor";
import { JsonLd } from "@/components/json-ld";
import { getCiudades, getCityCategoryPages, getRedes, getSaberLocalPorSeccion } from "@/lib/data";
import {
  aboutPageNode, breadcrumbNode, cityPath, faqPageNode, jsonLdGraph, organizationNodes, sameAsFromRedes,
} from "@/lib/seo";
import { conFundador } from "@/lib/seo-paginas";
import { META_DESCRIPTION, RESPONSIBLE } from "@/lib/marca";

export const dynamic = "force-static";

export const metadata: Metadata = {
  // `absolute`: el título ya lleva el nombre; sin esto la plantilla le suma « · Uruku».
  title: { absolute: "Qué es URUKU — guía de comercios y servicios de Bolivia" },
  description: META_DESCRIPTION,
  alternates: { canonical: "/que-es-uruku" },
  robots: { index: true, follow: true },
};

export default async function QueEsUruku() {
  const [ciudades, pares, redes, saber] = await Promise.all([
    getCiudades(), getCityCategoryPages(), getRedes(), getSaberLocalPorSeccion(null),
  ]);
  const activas = ciudades.filter((c) => c.activa);
  const conPaginas = new Set(pares.filter((p) => p.indexable).map((p) => p.city_slug));
  // Sólo las preguntas de la sección `general` se marcan acá (§3.8): cada pregunta, en una sola página.
  const preguntas = (saber.general ?? []).map((s) => ({ pregunta: s.pregunta, respuesta: s.respuesta }));

  const datos = jsonLdGraph([
    ...conFundador(organizationNodes({
      ciudades: activas.filter((c) => conPaginas.has(c.slug)).map((c) => ({ nombre: c.nombre, departamento: c.departamento, pais: c.pais })),
      sameAs: sameAsFromRedes(redes),
    })),
    aboutPageNode(),
    breadcrumbNode([{ name: "URUKU", path: "/" }, { name: "Qué es URUKU" }]),
    preguntas.length > 0 ? faqPageNode(preguntas) : null,
  ]);

  return (
    <>
      <JsonLd data={datos} />
      <PaginaManualServidor tipo="uruku" />
      {/* Lo que el Markdown no sabe dibujar: los datos del momento y los enlaces.
          Reusa las clases del manual para verse igual que la hoja de arriba. */}
      <div className="mn-root" data-tipo="uruku" style={{ minHeight: 0, paddingTop: 0 }}>
        <article className="mn-hoja">
          <div className="mn-cuerpo">
            {activas.length > 0 && (
              <>
                <h2 className="mn-h2">Dónde está URUKU</h2>
                <p className="mn-p">
                  {activas.map((c, i) => (
                    <span key={c.slug}>
                      {i > 0 && (i === activas.length - 1 ? " y " : ", ")}
                      {conPaginas.has(c.slug) ? <Link href={cityPath(c.slug)}>{c.nombre}</Link> : c.nombre}
                    </span>
                  ))}
                  .
                </p>
              </>
            )}

            <h2 className="mn-h2">Más sobre URUKU</h2>
            <ul className="mn-lista mn-ul">
              <li><Link href="/agentes">Agentes de URUKU</Link>: quiénes visitan comercios en nombre de la marca (nunca cobran).</li>
              <li><Link href="/comprar-en-bermejo">Comprar en Bermejo desde Argentina</Link>: qué conviene, cómo cruzar y cómo pagar.</li>
              <li><Link href="/guia">Guía para venir a Bermejo</Link>: paso fronterizo, documentos y aduana.</li>
              <li><Link href="/cambio">Cotización del peso en Bermejo</Link>.</li>
            </ul>

            {preguntas.length > 0 && (
              <>
                <h2 className="mn-h2">Preguntas frecuentes</h2>
                {preguntas.map((p) => (
                  <div key={p.pregunta}>
                    <h3 className="mn-h3">{p.pregunta}</h3>
                    <p className="mn-p">{p.respuesta}</p>
                  </div>
                ))}
              </>
            )}

            <p className="mn-p"><small>Quien responde por el sitio: {RESPONSIBLE}.</small></p>
          </div>
        </article>
      </div>
    </>
  );
}
