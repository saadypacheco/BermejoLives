import { serializeJsonLd } from "../lib/seo";

/**
 * Dibuja datos estructurados (JSON-LD) en un `<script type="application/ld+json">`.
 * Componente de servidor: el JSON va en el HTML que reciben los robots.
 *
 * Uso: `<JsonLd data={jsonLdGraph([localBusinessNode(...), breadcrumbNode(...)])} />`
 * (los armadores están en `lib/seo.ts`). Un solo `<JsonLd>` por página.
 *
 * ESCAPE OBLIGATORIO: los nombres los cargan agentes y la IA. Sin escapar, un
 * comercio llamado `</script><b>` cerraría la etiqueta e inyectaría HTML.
 * `serializeJsonLd` escapa `<`, `>`, `&`, U+2028 y U+2029; no hay otra forma de
 * meter JSON en un script en este proyecto.
 */
export function JsonLd({ data }: { data: unknown }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }} />;
}
