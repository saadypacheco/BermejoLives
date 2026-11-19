// Importados › Mapa: la parte pura (sin DOM ni red) de la vista de puntos.
// Colores por fuente, conteo para la leyenda, filtro por fuentes tildadas, límites del encuadre,
// textos del resumen y a qué búsqueda vuelve «Ver la ficha».
import { nombreFuente, type FuenteFiltro } from "./tarjetas-pure";
import { RUBRO_PARA_VISITAR } from "./para-visitar";

/** Lo mínimo que se necesita de un punto (`PuntoImportado` de lib/api cumple con esto). */
export type PuntoLike = {
  id: string; nombre: string | null; fuente: string; lat: number; lng: number;
  rubro_slug: string | null; repetido: boolean; ubicacion: string | null;
};

/** Color por fuente. Distintos entre sí aun para quien no distingue rojo de verde (paleta tipo Okabe-Ito
 *  ampliada) y con cuerpo suficiente para leerse sobre los tiles claros de OpenStreetMap. */
export const COLOR_FUENTE: Record<string, string> = {
  overture: "#1F6FEB", // azul
  turismo: "#1D8D52",  // verde URUKU
  anh: "#E03131",      // rojo (estaciones de servicio)
  aduana: "#8E44AD",   // violeta
  osm: "#F59F00",      // ámbar
  tarjeta: "#0CA5B0",  // turquesa
};
export const COLOR_FUENTE_OTRA = "#5C677D"; // gris azulado: una fuente que todavía no tiene color
/** Borde de un punto normal y de un repetido: el repetido lleva un borde oscuro y más grueso. */
export const BORDE_NORMAL = { color: "#FFFFFF", peso: 1 };
export const BORDE_REPETIDO = { color: "#111111", peso: 3 };

export function colorFuente(fuente: string): string {
  return COLOR_FUENTE[fuente] ?? COLOR_FUENTE_OTRA;
}

const ETIQUETA: Record<string, string> = {
  osm: "OSM", tarjeta: "Tarjetas", turismo: "Turismo", overture: "Overture", anh: "ANH", aduana: "Aduana",
};

/** El nombre corto para la leyenda; el largo sale de `nombreFuente`. */
export function etiquetaFuente(fuente: string): string {
  return ETIQUETA[fuente] ?? (fuente || "Otras");
}

/** Número con punto de miles, a la argentina/boliviana (18.670), sin depender del ICU del entorno. */
export function miles(n: number): string {
  const v = Math.trunc(Number.isFinite(n) ? n : 0);
  return String(Math.abs(v)).replace(/\B(?=(\d{3})+(?!\d))/g, ".").replace(/^/, v < 0 ? "-" : "");
}

/** Un punto es dibujable sólo con latitud y longitud finitas dentro de rango. */
export function puntoValido(p: { lat: number; lng: number }): boolean {
  return Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180;
}

export type ConteoFuente = { fuente: string; n: number; repetidos: number };

/** Cuántos puntos hay de cada fuente (para la leyenda), de mayor a menor y, a igual cantidad, por nombre. */
export function contarPorFuente(items: readonly Pick<PuntoLike, "fuente" | "repetido">[]): ConteoFuente[] {
  const m = new Map<string, ConteoFuente>();
  for (const i of items) {
    const c = m.get(i.fuente) ?? { fuente: i.fuente, n: 0, repetidos: 0 };
    c.n += 1;
    if (i.repetido) c.repetidos += 1;
    m.set(i.fuente, c);
  }
  return [...m.values()].sort((a, b) => b.n - a.n || a.fuente.localeCompare(b.fuente));
}

/** Sólo los puntos de las fuentes tildadas. Se guarda lo DESTILDADO: una fuente que aparece más tarde nace tildada. */
export function filtrarPorFuentes<T extends { fuente: string }>(items: readonly T[], ocultas: ReadonlySet<string>): T[] {
  return ocultas.size === 0 ? [...items] : items.filter((i) => !ocultas.has(i.fuente));
}

/** Tilda o destilda una fuente sin tocar el conjunto anterior (el estado de React no se muta). */
export function alternarFuente(ocultas: ReadonlySet<string>, fuente: string): Set<string> {
  const n = new Set(ocultas);
  if (n.has(fuente)) n.delete(fuente); else n.add(fuente);
  return n;
}

/** Esquinas [[sur, oeste], [norte, este]] que encierran a los puntos, o null si no hay ninguno. */
export function limitesDe(items: readonly { lat: number; lng: number }[]): [[number, number], [number, number]] | null {
  let s = Infinity, w = Infinity, n = -Infinity, e = -Infinity;
  for (const p of items) {
    if (!puntoValido(p)) continue;
    if (p.lat < s) s = p.lat;
    if (p.lat > n) n = p.lat;
    if (p.lng < w) w = p.lng;
    if (p.lng > e) e = p.lng;
  }
  return Number.isFinite(s) ? [[s, w], [n, e]] : null;
}

export type ResumenPuntos = { total: number; sin_punto: number; truncado: boolean };

/** «18.670 en el mapa · 12 sin punto». Si el servidor cortó en su tope, lo dice y sugiere acotar. */
export function resumenMapa(r: ResumenPuntos, mostrados: number): string {
  const partes: string[] = [];
  if (r.truncado) {
    // El servidor no cuenta lo que quedó afuera (`total` es lo que mandó): sólo se sabe que hay más.
    partes.push(`Se muestran los primeros ${miles(mostrados)} en el mapa y hay más: filtrá por fuente para ver el resto`);
  } else {
    partes.push(`${miles(r.total)} en el mapa`);
  }
  if (r.sin_punto > 0) partes.push(`${miles(r.sin_punto)} sin punto`);
  return partes.join(" · ");
}

export const MSG_SIN_MAPA = "Esta versión del servidor todavía no tiene el mapa de importados";
export const MSG_ELEGI_CIUDAD = "Elegí una ciudad para ver el mapa";
export const MSG_MAPA_VACIO = "No hay importados con punto con estos filtros";

const FUENTES_DEL_FILTRO: readonly FuenteFiltro[] = ["osm", "tarjeta", "turismo", "overture", "anh", "aduana"];

/** A qué vuelve la lista con «Ver la ficha»: la búsqueda por el nombre del punto y, si la fuente del punto está
 *  entre las del filtro, ese filtro puesto (un lugar de turismo con rubro «para visitar» cae en su filtro propio).
 *  Sin fuente conocida el filtro queda como estaba (`null`). */
export function busquedaDeFicha(p: Pick<PuntoLike, "nombre" | "fuente" | "rubro_slug">): { q: string; fuente: FuenteFiltro | null } {
  const f = FUENTES_DEL_FILTRO.find((x) => x === p.fuente) ?? null;
  const fuente: FuenteFiltro | null = f === "turismo" && p.rubro_slug === RUBRO_PARA_VISITAR ? "turismo-visitar" : f;
  return { q: (p.nombre ?? "").trim(), fuente };
}

/** Las líneas del popup, en orden, ya como texto plano (el componente las pone con `textContent`). */
export function lineasPopup(p: Pick<PuntoLike, "nombre" | "fuente" | "rubro_slug" | "repetido" | "ubicacion">): string[] {
  const l: string[] = [p.nombre?.trim() || "(sin nombre)", `Fuente: ${nombreFuente({ fuente: p.fuente })}`];
  if (p.rubro_slug) l.push(`Rubro: ${p.rubro_slug}`);
  if (p.repetido) l.push("Repetido: ya hay uno parecido en URUKU");
  if (p.ubicacion === "aproximada") l.push("Punto aproximado: confirmalo");
  return l;
}
