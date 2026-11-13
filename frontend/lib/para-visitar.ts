// «Para visitar» (docs/lugares-turismo.md): lo puro del rubro no comercial de los lugares turísticos
// (plazas, museos, miradores, iglesias, excursiones, áreas protegidas), sin red ni navegador, para
// poder probarlo con `npm test`.
//
// Viven en `comercios` con el rubro `para-visitar` (`comercial = false`, como los baños). Acá están:
// la lista fija de subcategorías, el encuadre del mapa (sólo los pines cercanos a la ciudad), cuándo
// sale el acceso del home, el enlace a la página de origen y los textos de la ficha pública.

export const RUBRO_PARA_VISITAR = "para-visitar";

/** El destino del acceso «Para visitar» (home y resultados). */
export const HREF_PARA_VISITAR = `/buscar?rubro=${RUBRO_PARA_VISITAR}&vista=mapa`;

/** La lista fija de tipos de lugar (el backend rechaza lo que no esté: 400). El orden es el del desplegable. */
export const SUBCATEGORIAS_VISITAR = [
  "Plaza", "Parque", "Mirador", "Museo", "Biblioteca o archivo", "Iglesia", "Patrimonio",
  "Centro cultural", "Excursión", "Área protegida",
] as const;
export type SubcategoriaVisitar = (typeof SUBCATEGORIAS_VISITAR)[number];

/** Éstos suelen quedar lejos o ser enormes: el punto de la búsqueda por nombre no sirve, hay que
 *  ponerlo a mano en la entrada o en el centro de visitantes. */
const SUBCATEGORIAS_DE_ENTRADA: readonly string[] = ["Excursión", "Área protegida"];

export const AVISO_PUNTO_ENTRADA = "Poné el punto en la entrada o en el centro de visitantes";

export function esSubcategoriaVisitar(s: string | null | undefined): s is SubcategoriaVisitar {
  return (SUBCATEGORIAS_VISITAR as readonly string[]).includes((s ?? "").trim());
}

/** ¿Hay que avisar que el punto va en la entrada? Sólo Excursión y Área protegida. */
export function pideAvisoPunto(subcategoria: string | null | undefined): boolean {
  return SUBCATEGORIAS_DE_ENTRADA.includes((subcategoria ?? "").trim());
}

export function esParaVisitar(rubroSlug: string | null | undefined): boolean {
  return rubroSlug === RUBRO_PARA_VISITAR;
}

/** El sello de la ficha de revisión: «Para visitar · Museo». Sin subcategoría, sólo «Para visitar». */
export function selloParaVisitar(subcategoria: string | null | undefined): string {
  const s = (subcategoria ?? "").trim();
  return s ? `Para visitar · ${s}` : "Para visitar";
}

/** Un item de Importados se revisa como lugar si es de turismo y su rubro (el elegido en la ficha, si lo
 *  cambiaron) es `para-visitar`. Si quien revisa le pone otro rubro, vuelve a ser un negocio. */
export function esLugarParaVisitar(item: { fuente: string; rubro_slug?: string | null }, rubroElegido?: string | null): boolean {
  if (item.fuente !== "turismo") return false;
  return esParaVisitar(rubroElegido !== undefined ? rubroElegido : item.rubro_slug);
}

// ── Rubros no comerciales ───────────────────────────────────────────────────

/** `comercial === false` es no comercial. Ausente significa comercial (los datos viejos no lo traen). */
export function esNoComercial(x: { comercial?: boolean | null } | null | undefined): boolean {
  return x?.comercial === false;
}

// ── El acceso del home ──────────────────────────────────────────────────────

/** ¿Sale el acceso «Para visitar»? Sólo si la ciudad tiene el par (ciudad, `para-visitar`) en
 *  `city_category_pages()`. Sin ciudad o sin pares (la lectura falló), no sale: un acceso que lleva a un
 *  mapa vacío es peor que no tenerlo. Sin números. */
export function hayParaVisitar(
  pares: readonly { city_slug: string; category_slug: string }[] | null | undefined,
  ciudadSlug: string | null | undefined,
): boolean {
  if (!ciudadSlug || !pares) return false;
  return pares.some((p) => p.city_slug === ciudadSlug && p.category_slug === RUBRO_PARA_VISITAR);
}

// ── El encuadre del mapa ────────────────────────────────────────────────────

/** Hasta dónde llega el encuadre desde el centro de la ciudad. Una excursión a 76 km se ve en el mapa
 *  (se puede arrastrar hasta ella) pero no aleja el encuadre hasta que la ciudad queda en un cúmulo. */
export const RADIO_ENCUADRE_KM = 30;

export type Punto = readonly [number, number];

/** Distancia en km entre dos puntos (haversine). */
export function distanciaKm(a: Punto, b: Punto): number {
  const rad = (g: number) => (g * Math.PI) / 180;
  const dLat = rad(b[0] - a[0]);
  const dLng = rad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Los puntos que cuentan para el encuadre: los que están a `radioKm` o menos del centro de la ciudad.
 *  Sin centro, o si ninguno queda dentro (una búsqueda de puros lugares lejanos), valen todos: encuadrar
 *  nada dejaría el mapa mirando una ciudad vacía. */
export function pinesParaEncuadre<T extends Punto>(puntos: readonly T[], centro: Punto | null | undefined, radioKm: number = RADIO_ENCUADRE_KM): T[] {
  if (!centro) return [...puntos];
  const cerca = puntos.filter((p) => distanciaKm(centro, p) <= radioKm);
  return cerca.length > 0 ? cerca : [...puntos];
}

// ── La página de origen ─────────────────────────────────────────────────────

/** La URL de origen si es http(s) válida; si no, null (un `javascript:` cargado en la base no es un enlace). */
export function urlFuente(url: string | null | undefined): string | null {
  const t = (url ?? "").trim();
  if (!t) return null;
  try {
    const u = new URL(t);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** El dominio sin «www.», para decir de dónde salió: «tarijaturismo.com». */
export function dominioFuente(url: string | null | undefined): string | null {
  const ok = urlFuente(url);
  if (!ok) return null;
  return new URL(ok).hostname.replace(/^www\./, "").toLowerCase();
}

/** El enlace del panel: «Ver en tarijaturismo.com». */
export function textoVerEnOrigen(url: string | null | undefined): string {
  const d = dominioFuente(url);
  return d ? `Ver en ${d}` : "Ver la página de origen";
}

/** El enlace de la ficha pública. Para la página de la Alcaldía de Tarija el texto es el de la spec. */
export function textoMasInformacion(url: string | null | undefined): string {
  return dominioFuente(url) === "tarijaturismo.com"
    ? "Más información en la página de Turismo de Tarija"
    : "Más información en la página de origen";
}
