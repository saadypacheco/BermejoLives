// Los filtros del buscador, en un solo lugar para que el SERVIDOR (que arma la
// primera tanda de resultados en el HTML de /buscar) y el CLIENTE (BuscarClient)
// pidan exactamente lo mismo. Si los dos calcularan por su cuenta, la tanda del
// servidor no coincidiría con la que el cliente espera y se pediría dos veces.
//
// Módulo puro: sin base, sin React. Lo importan tanto el servidor como el cliente.
import { detectarServicio, SERVICIOS } from "./servicios";
import type { FiltrosBusqueda, ResultadoBusqueda } from "./types";

/** Los parámetros de la URL de /buscar que cambian el resultado. */
export type ParamsBusqueda = {
  q: string;
  rubro: string;
  subcategoria: string;
  modalidad: string;
  zona: string;
  ciudad: string;
  precioMax: string;
};

/** Cuántos resultados trae la primera tanda (servidor y cliente). */
export const PRIMERAS_BUSQUEDA = 10;

/** Lo que el servidor le pasa a BuscarClient para que no repita la consulta. */
export type BusquedaInicial = {
  params: ParamsBusqueda;
  resultados: ResultadoBusqueda[];
};

/** El filtro que se manda a `buscar_comercios`. Un servicio escrito («baño
 *  público») se busca por SU rubro, no por texto (ver lib/servicios.ts). */
export function filtrosDeBusqueda(p: ParamsBusqueda): FiltrosBusqueda {
  const servicioEscrito = p.rubro ? null : detectarServicio(p.q);
  const precioMax = p.precioMax ? Number(p.precioMax) : undefined;
  return servicioEscrito
    ? { q: "", rubro: SERVICIOS[servicioEscrito].rubro, subcategoria: "", modalidad: p.modalidad, zona: p.zona, ciudad: p.ciudad, precioMax }
    : { q: p.q, rubro: p.rubro, subcategoria: p.subcategoria, modalidad: p.modalidad, zona: p.zona, ciudad: p.ciudad, precioMax };
}

/** Clave estable de una búsqueda: sirve para saber si los datos iniciales del
 *  servidor son los de lo que el cliente está por pedir. */
export function claveBusqueda(p: ParamsBusqueda): string {
  return JSON.stringify(filtrosDeBusqueda(p));
}

function uno(v: string | string[] | undefined): string {
  return typeof v === "string" ? v : Array.isArray(v) ? (v[0] ?? "") : "";
}

/** Los parámetros de /buscar a partir de `searchParams` de la página. La ciudad
 *  de la URL (?ciudad=) pisa a la del selector, igual que en el cliente. */
export function paramsDeUrl(
  sp: Record<string, string | string[] | undefined> | undefined,
  ciudadDelSelector: string,
): ParamsBusqueda {
  const s = sp ?? {};
  return {
    q: uno(s.q),
    rubro: uno(s.rubro),
    subcategoria: uno(s.sub),
    modalidad: uno(s.modalidad),
    zona: uno(s.zona),
    ciudad: s.ciudad === undefined ? ciudadDelSelector : uno(s.ciudad),
    precioMax: uno(s.precio_max),
  };
}
