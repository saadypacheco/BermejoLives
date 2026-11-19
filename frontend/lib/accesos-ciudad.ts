// La lista de accesos de la fila de servicios del home y de los resultados (components/accesos-ciudad.tsx).
// Está acá, sin React, para poder probarla con `npm test`: qué accesos salen según la ciudad.
import type { NombreIcono } from "@/components/ic";
import { HREF_PARA_VISITAR, RUBRO_PARA_VISITAR } from "./para-visitar";

export type Acceso = { i: NombreIcono; t: string; href: string };

/** Hoteles y boliches: van primero porque son lo que más se busca en el mapa al llegar a una ciudad. */
export const HREF_HOTELES = "/buscar?rubro=hospedaje&vista=mapa";
export const HREF_NOCTURNA = "/buscar?rubro=nocturna&vista=mapa";

const DESTACADOS: Acceso[] = [
  { i: "hospedaje", t: "Hoteles", href: HREF_HOTELES },
  { i: "nocturna", t: "Boliches y karaoke", href: HREF_NOCTURNA },
];

const SERVICIOS: Acceso[] = [
  ...DESTACADOS,
  { i: "banos", t: "Baños", href: "/buscar?rubro=banos&vista=mapa" },
  { i: "farmacia", t: "Farmacias", href: "/buscar?rubro=farmacia&vista=mapa" },
  { i: "cajeros", t: "Cajeros", href: "/buscar?rubro=cajeros&vista=mapa" },
  { i: "estacionamiento", t: "Estacionamiento", href: "/buscar?rubro=estacionamiento&vista=mapa" },
  { i: "cambio", t: "Casas de cambio", href: "/cambio" },
  { i: "taxis", t: "Taxis", href: "/buscar?rubro=taxis&vista=mapa" },
  { i: "wifi", t: "WiFi", href: "/buscar?rubro=wifi&vista=mapa" },
  { i: "policia", t: "Policía", href: "/buscar?rubro=emergencias&vista=mapa" },
  { i: "transporte", t: "Transporte", href: "/guia#transporte" },
  { i: "frontera", t: "Frontera", href: "/guia#frontera" },
];

/** Sin guía (ciudad que no es de frontera): se van los dos accesos a la guía
 *  del paso, y el cambio deja de ser una página para ser un rubro del mapa. */
const SIN_GUIA: Acceso[] = SERVICIOS
  .filter((c) => !c.href.startsWith("/guia"))
  .map((c) => (c.href === "/cambio" ? { ...c, t: "Cambio", href: "/buscar?rubro=cambio&vista=mapa" } : c));

/** «Para visitar» (lugares turísticos, 0196): va antes del transporte y la frontera. Sin números. */
const PARA_VISITAR: Acceso = { i: "para-visitar", t: "Para visitar", href: HREF_PARA_VISITAR };

/** Los rubros que son nuevos en la fila: si no se sabe qué hay en la ciudad (falló la lectura), NO salen.
 *  Los de siempre (baños, cajeros…) en ese caso salen como antes: esconder toda la fila por un error de
 *  lectura sería peor que un acceso de más. */
const SOLO_CON_DATO = new Set(["hospedaje", "nocturna", RUBRO_PARA_VISITAR]);

/** El rubro al que lleva un enlace (`/buscar?rubro=x…`). `null` si no es un acceso a un rubro (guía, /cambio). */
export function rubroDeHref(href: string): string | null {
  const q = href.indexOf("?");
  if (q < 0 || !href.startsWith("/buscar")) return null;
  return new URLSearchParams(href.slice(q + 1)).get("rubro") || null;
}

/** Los rubros con al menos un comercio en la ciudad, según `city_category_pages()` (sin conteos).
 *  `null` = no se sabe: sin ciudad, o la lectura falló (la función devuelve `[]` ante un error, y la base
 *  nunca está vacía de verdad). Un conjunto vacío sí es un dato: la ciudad no tiene nada cargado. */
export function rubrosDeCiudad(
  pares: readonly { city_slug: string; category_slug: string }[] | null | undefined,
  ciudadSlug: string | null | undefined,
): Set<string> | null {
  if (!ciudadSlug || !pares || pares.length === 0) return null;
  return new Set(pares.filter((p) => p.city_slug === ciudadSlug).map((p) => p.category_slug));
}

/** ¿El acceso lleva a algo? Los que no van a un rubro (guías, /cambio) siempre. Los de un rubro, sólo si la
 *  ciudad tiene comercios de ese rubro: un acceso que abre un mapa vacío no tiene que estar. */
export function accesoConComercios(href: string, rubros: ReadonlySet<string> | null): boolean {
  const rubro = rubroDeHref(href);
  if (!rubro) return true;
  if (!rubros) return !SOLO_CON_DATO.has(rubro);
  return rubros.has(rubro);
}

/** La fila de accesos de la ciudad: con guía (frontera) o sin ella, y sólo los que traen algo. */
export function listaAccesos(conGuia: boolean, rubros: ReadonlySet<string> | null): Acceso[] {
  const base = conGuia ? SERVICIOS : SIN_GUIA;
  // «Para visitar» antes de «Transporte» y «Frontera» (las guías); si no hay guías, al final.
  const i = base.findIndex((c) => c.href.startsWith("/guia"));
  const todos = i < 0 ? [...base, PARA_VISITAR] : [...base.slice(0, i), PARA_VISITAR, ...base.slice(i)];
  return todos.filter((c) => accesoConComercios(c.href, rubros));
}
