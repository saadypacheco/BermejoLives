// Los interruptores «Abiertos» y «Más cerca» del encabezado (docs/home-ciudades.md §3): lo puro, sin React ni
// navegador, para poder probarlo con `npm test`. El estado vive en `sessionStorage` (clave `uk-filtros-rapidos`):
// al abrir otra sesión del navegador arrancan apagados.

export type FiltrosRapidos = { abiertos: boolean; cerca: boolean };

export const CLAVE_FILTROS_RAPIDOS = "uk-filtros-rapidos";
export const SIN_FILTROS: FiltrosRapidos = { abiertos: false, cerca: false };

/** Lo guardado, con tolerancia: un texto roto, vacío o con tipos raros vuelve a «todo apagado». */
export function leerFiltros(raw: string | null | undefined): FiltrosRapidos {
  if (!raw) return SIN_FILTROS;
  try {
    const o = JSON.parse(raw) as Partial<Record<keyof FiltrosRapidos, unknown>> | null;
    if (!o || typeof o !== "object") return SIN_FILTROS;
    return { abiertos: o.abiertos === true, cerca: o.cerca === true };
  } catch {
    return SIN_FILTROS;
  }
}

export function serializarFiltros(f: FiltrosRapidos): string {
  return JSON.stringify({ abiertos: f.abiertos === true, cerca: f.cerca === true });
}

export const hayFiltros = (f: FiltrosRapidos): boolean => f.abiertos || f.cerca;

/** ¿El enlace va al buscador o al mapa? Sólo a esos se les suman los interruptores. */
function esEnlaceDeBusqueda(path: string): boolean {
  return path === "/buscar" || path.startsWith("/buscar/") || path === "/mapa";
}

/** Suma `abierto=1` y/o `cerca=1` a un enlace al buscador o al mapa. Lo que no es de esos (la ficha, una
 *  URL externa, `/ofertas`) vuelve igual; lo que ya traía el parámetro no se repite; el `#ancla` se conserva. */
export function conFiltros(href: string, f: FiltrosRapidos): string {
  if (!hayFiltros(f)) return href;
  const almohadilla = href.indexOf("#");
  const ancla = almohadilla >= 0 ? href.slice(almohadilla) : "";
  const sinAncla = almohadilla >= 0 ? href.slice(0, almohadilla) : href;
  const q = sinAncla.indexOf("?");
  const path = q >= 0 ? sinAncla.slice(0, q) : sinAncla;
  if (!esEnlaceDeBusqueda(path)) return href;
  const params = new URLSearchParams(q >= 0 ? sinAncla.slice(q + 1) : "");
  const extra: string[] = [];
  if (f.abiertos && !params.has("abierto")) extra.push("abierto=1");
  if (f.cerca && !params.has("cerca")) extra.push("cerca=1");
  if (extra.length === 0) return href;
  const resto = q >= 0 ? sinAncla.slice(q + 1) : "";
  return `${path}?${[resto, ...extra].filter(Boolean).join("&")}${ancla}`;
}
