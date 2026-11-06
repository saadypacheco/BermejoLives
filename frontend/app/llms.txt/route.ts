import { getCiudadesConTurnos, getCityCategoryPagesOrNull } from "@/lib/data";
import { absoluteUrl, categoryPath, cityPath } from "@/lib/seo";
import { BRAND_NAME, CONTACT, FOUNDER, LAUNCH_DATE, ONE_LINER, RESPONSIBLE } from "@/lib/marca";
import { WA_URUKU_TEXTO } from "@/lib/contacto";
import { conMemoriaTtl } from "@/lib/memoria-ttl";

/**
 * /llms.txt — un resumen en texto plano de URUKU para asistentes de IA
 * (docs/visibilidad-buscadores-ia.md §3.10). Su valor es incierto: ningún
 * asistente grande confirmó que lo lea. Cuesta poco, y lo que dice es lo mismo
 * que /que-es-uruku. Sólo lista páginas que se indexan; sin cifras de comercios.
 *
 * Sólo en producción: en QA robots.ts bloquea todo y esto sería una invitación.
 */
// DINÁMICO a propósito (auditoría 5/11, A-02 paso 3): el build no puede leer la base. Se arma
// al primer pedido y se recuerda un día en memoria (`conMemoriaTtl`); si una lectura falla se
// sigue sirviendo el último bueno, o un 500 si no hay ninguno: nunca uno recortado.
export const dynamic = "force-dynamic";

const UN_DIA_MS = 24 * 60 * 60_000;

async function armarTexto(): Promise<string> {
  const [todos, ciudadesTurnos] = await Promise.all([getCityCategoryPagesOrNull(), getCiudadesConTurnos()]);
  if (todos === null || ciudadesTurnos === null) throw new Error("llms.txt: falló una lectura de la base");
  const pares = todos.filter((p) => p.indexable);
  // Las ciudades con al menos un par indexable, en el orden en que llegan.
  const ciudades = [...new Map(pares.map((p) => [p.city_slug, p.city_name])).entries()];

  const l: string[] = [];
  l.push(`# ${BRAND_NAME}`, "", `> ${ONE_LINER}`, "");
  if (ciudades.length > 0) l.push(`Ciudades: ${ciudades.map(([, n]) => n).join(", ")}.`);
  l.push(`Contacto: WhatsApp ${CONTACT.telefono.replace("+591", "+591 ")} (${WA_URUKU_TEXTO}) · ${CONTACT.email}`);
  l.push(`Quién lo hace: ${RESPONSIBLE}. Lo creó ${FOUNDER.nombre} (${FOUNDER.cargo.toLowerCase()}), que empezó a desarrollarlo en mayo de 2026. Lanzamiento público: ${LAUNCH_DATE.texto}.`);
  l.push("");

  l.push("## Páginas clave");
  l.push(`- [Qué es URUKU](${absoluteUrl("/que-es-uruku")}): quién lo hace, cómo funciona, contacto`);
  l.push(`- [Comprar en Bermejo desde Argentina](${absoluteUrl("/comprar-en-bermejo")}): qué conviene comprar, cómo cruzar y cómo pagar`);
  l.push(`- [Guía para venir a Bermejo](${absoluteUrl("/guia")}): paso fronterizo, documentos, aduana`);
  l.push(`- [Cotización del peso en Bermejo](${absoluteUrl("/cambio")}): cuánto dan por los pesos argentinos`);
  for (const c of ciudadesTurnos) l.push(`- [Farmacias de turno en ${c.nombre}](${absoluteUrl(`/${c.slug}/farmacias-de-turno`)})`);
  l.push(`- [Ofertas de los comercios](${absoluteUrl("/ofertas")})`);
  l.push(`- [Agentes de URUKU](${absoluteUrl("/agentes")}): quiénes visitan comercios en nombre de la marca`);
  for (const [slug, nombre] of ciudades) l.push(`- [Comercios de ${nombre}](${absoluteUrl(cityPath(slug))})`);
  l.push("");

  if (pares.length > 0) {
    l.push("## Rubros por ciudad");
    for (const p of pares) {
      l.push(`- [${p.category_name} en ${p.city_name}](${absoluteUrl(categoryPath(p.city_slug, p.category_slug))})`);
    }
    l.push("");
  }

  l.push("## Lo que URUKU no hace");
  l.push("- No vende por los comercios ni media pagos entre quien compra y el comercio. Los agentes de URUKU nunca cobran.");
  l.push("- No cruza mercadería de un país a otro.");
  l.push("");

  return l.join("\n");
}

const textoConMemoria = conMemoriaTtl(UN_DIA_MS, armarTexto);

export async function GET(): Promise<Response> {
  const esProd = (process.env.NEXT_PUBLIC_ENV_LABEL || "").toLowerCase() === "prod";
  if (!esProd) return new Response("No encontrado", { status: 404, headers: { "content-type": "text/plain; charset=utf-8" } });

  return new Response(await textoConMemoria(), {
    headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "public, s-maxage=86400, stale-while-revalidate=604800" },
  });
}
