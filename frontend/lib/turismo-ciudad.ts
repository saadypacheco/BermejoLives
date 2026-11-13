import "server-only";
import { buscarComerciosOrNull } from "@/lib/data";
import { hasSupabase, supabase } from "@/lib/supabase";
import { conMemoriaTtl } from "@/lib/memoria-ttl";
import type { ResultadoBusqueda } from "@/lib/types";
import {
  RUBRO_TAXIS, RUBRO_TURISMO, SUBCATS_MOVERSE, filtrarMoverse, lugaresParaCarrusel, partirTurismo,
  type LocalTurismo, type ResumenTurismo,
} from "@/lib/turismo-ciudad-pure";
import { RUBRO_PARA_VISITAR } from "@/lib/para-visitar";

/**
 * Las lecturas de «Visitá {ciudad}» (home y /{ciudad}/turismo). docs/turismo-home-y-repetidos.md §3.
 *
 * Todas por PostgREST con la anon key y columnas explícitas (regla 11 de AGENTS.md):
 *  - `buscar_comercios(p_ciudad, p_rubro[, p_subcategoria], p_limit = 500)`: la misma RPC (SECURITY DEFINER,
 *    sólo `activo` y no suspendido) que usan las páginas /{ciudad}/{rubro}. Trae los comercios con ese rubro
 *    aunque sea secundario y NO exige punto en el mapa (los guías y radio móviles no lo tienen).
 *  - `comercios.select("id, telefono").in("id", ids)`: el teléfono, que la RPC no devuelve. Columna ya pública
 *    (está en `COLUMNAS_COMERCIO`).
 *
 * La home es `force-dynamic`: no puede pegarle a la base en cada pedido. Por eso el resultado se recuerda 10
 * minutos por ciudad (`conMemoriaTtl`: una lectura por ventana, y ante un fallo se sigue sirviendo la última
 * buena). Un fallo sin nada bueno LANZA: la página con ISR conserva su versión anterior y la home lo traga y
 * muestra la banda sin carrusel (`cargarVisitaCiudadOpcional`). Nunca se recuerda un fallo.
 */

export type VisitaCiudad = {
  /** Lugares para visitar, ya en el orden del carrusel (con foto primero, tipos alternados). */
  lugares: LocalTurismo[];
  /** Todos los lugares (la lista completa, para JSON-LD). */
  todosLosLugares: LocalTurismo[];
  guias: LocalTurismo[];
  agencias: LocalTurismo[];
  moverse: LocalTurismo[];
};

const TOPE = 500;
const TOPE_CARRUSEL = 12;
const DIEZ_MIN_MS = 10 * 60_000;

function aLocal(f: ResultadoBusqueda, telefonos: ReadonlyMap<string, string>): LocalTurismo {
  return {
    id: f.id, slug: f.slug, nombre: f.nombre, subcategoria: f.subcategoria ?? null,
    whatsapp: f.whatsapp || null, telefono: telefonos.get(f.id) ?? null, foto: f.portada_thumb_url || null,
  };
}

/** `telefono` de cada comercio, de a 100 ids por consulta (el largo de la URL de PostgREST). Lanza si falla. */
async function cargarTelefonos(ids: readonly string[]): Promise<Map<string, string>> {
  const telefonos = new Map<string, string>();
  if (!hasSupabase || ids.length === 0) return telefonos;
  const lotes: string[][] = [];
  for (let i = 0; i < ids.length; i += 100) lotes.push(ids.slice(i, i + 100));
  const resultados = await Promise.all(lotes.map((lote) => supabase.from("comercios").select("id, telefono").in("id", lote)));
  for (const { data, error } of resultados) {
    if (error) throw new Error(`turismo: no se pudieron leer los teléfonos: ${error.message}`);
    for (const f of (data ?? []) as { id: string; telefono: string | null }[]) {
      if (f.telefono && f.telefono.trim()) telefonos.set(f.id, f.telefono.trim());
    }
  }
  return telefonos;
}

async function leer(ciudadSlug: string, rubro: string, subcategoria?: string): Promise<ResultadoBusqueda[]> {
  const filas = await buscarComerciosOrNull({ ciudad: ciudadSlug, rubro, subcategoria }, TOPE, 0);
  if (filas === null) throw new Error(`turismo: no se pudo leer ${rubro}${subcategoria ? ` (${subcategoria})` : ""} en ${ciudadSlug}`);
  return filas;
}

async function armar(ciudadSlug: string): Promise<VisitaCiudad> {
  // Cuatro lecturas: lugares, todo el rubro turismo, y las dos subcategorías de taxis que sirven para moverse
  // (filtradas en la base: el rubro `taxis` puede tener más de 500 locales y las del tope quedarían afuera).
  const [lugares, turismo, ...moverse] = await Promise.all([
    leer(ciudadSlug, RUBRO_PARA_VISITAR),
    leer(ciudadSlug, RUBRO_TURISMO),
    ...SUBCATS_MOVERSE.map((s) => leer(ciudadSlug, RUBRO_TAXIS, s)),
  ]);
  const unicos = new Map<string, ResultadoBusqueda>();
  for (const f of moverse.flat()) unicos.set(f.id, f);
  // El teléfono sólo hace falta para quienes tienen botón de llamar: los de turismo y los de moverse.
  const telefonos = await cargarTelefonos([...new Set([...turismo.map((f) => f.id), ...unicos.keys()])]);
  const partido = partirTurismo(turismo.map((f) => aLocal(f, telefonos)));
  const todos = lugares.map((f) => aLocal(f, telefonos));
  return {
    lugares: lugaresParaCarrusel(todos, TOPE_CARRUSEL),
    todosLosLugares: [...todos].sort((a, b) => a.nombre.localeCompare(b.nombre, "es")),
    guias: partido.guias,
    agencias: partido.agencias,
    moverse: filtrarMoverse([...unicos.values()].map((f) => aLocal(f, telefonos))),
  };
}

const memorias = new Map<string, () => Promise<VisitaCiudad>>();

/** Lo cargado de una ciudad para «Visitá», recordado 10 minutos. LANZA si no se pudo leer y no hay una versión
 *  buena anterior. En el build no se recuerda nada (mismo motivo que `getCityCategoryPagesCached`). */
export async function cargarVisitaCiudad(ciudadSlug: string): Promise<VisitaCiudad> {
  if (process.env.NEXT_PHASE === "phase-production-build") return armar(ciudadSlug);
  let leerMemoria = memorias.get(ciudadSlug);
  if (!leerMemoria) {
    leerMemoria = conMemoriaTtl(DIEZ_MIN_MS, () => armar(ciudadSlug));
    memorias.set(ciudadSlug, leerMemoria);
  }
  return leerMemoria();
}

/** Lo mismo, para la home: ante un fallo, `null` (la banda sale con los accesos que salen sólo de los rubros y
 *  sin carrusel) en vez de romper la portada. */
export async function cargarVisitaCiudadOpcional(ciudadSlug: string): Promise<VisitaCiudad | null> {
  try {
    return await cargarVisitaCiudad(ciudadSlug);
  } catch (e) {
    console.warn("visita ciudad: lectura falló:", e instanceof Error ? e.message : e);
    return null;
  }
}

export function resumenDe(v: VisitaCiudad | null): ResumenTurismo | null {
  return v ? { guias: v.guias.length > 0, agencias: v.agencias.length > 0, moverse: v.moverse.length > 0 } : null;
}
