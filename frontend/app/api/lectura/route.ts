import { NextResponse } from "next/server";
import {
  buscarComercios, getAdornosMapa, getCiudades, getCiudadesReales, getFarmaciasDeTurnoAhora,
  getClima, getCotizaciones, getFiltrosDisponibles, getFronteraEstado, getFuncionesDePlan, getOfertasDeComercios,
  getPuntosComercios, getRedes, getRefinamientos, getRubros, getZonas,
} from "@/lib/data";
import type { FiltrosBusqueda } from "@/lib/types";

// Lecturas de datos para los componentes cliente.
//
// El navegador ya no habla con PostgREST (la URL de la base y la anon key no
// van en el bundle). Lo que un componente cliente necesita leer pasa por acá:
// una LISTA BLANCA de funciones de lib/data.ts, cada una con sus argumentos
// validados y acotados (un `limit` desmedido no sirve para bajarse el catálogo
// de una vez). El cliente es lib/data-client.ts.
//
// POST y sin caché: son lecturas «de ahora» (ofertas, turnos, planes) y las
// listas de ids pueden ser largas para una URL.

export const dynamic = "force-dynamic";

const MAX_BODY = 64 * 1024;
const MAX_IDS = 1000;

type Args = unknown[];

function str(v: unknown, max = 200): string | undefined {
  return typeof v === "string" ? v.slice(0, max) : undefined;
}
function num(v: unknown): number | undefined {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}
function entero(v: unknown, def: number, min: number, max: number): number {
  const n = num(v);
  return n === undefined ? def : Math.min(max, Math.max(min, Math.trunc(n)));
}
function idOpt(v: unknown): string | null {
  return typeof v === "string" && v.length > 0 && v.length <= 64 ? v : null;
}

/** Sólo las claves conocidas de FiltrosBusqueda, con su tipo. */
function filtros(v: unknown): FiltrosBusqueda {
  const o = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  const f: FiltrosBusqueda = {};
  for (const k of ["q", "rubro", "subcategoria", "modalidad", "zona", "ciudad"] as const) {
    const s = str(o[k]);
    if (s !== undefined) f[k] = s;
  }
  const min = num(o.precioMin);
  if (min !== undefined) f.precioMin = min;
  const max = num(o.precioMax);
  if (max !== undefined) f.precioMax = max;
  return f;
}

function ciudadCoords(v: unknown): { lat: number | null; lng: number | null } {
  const o = (v && typeof v === "object" ? v : {}) as Record<string, unknown>;
  return { lat: num(o.lat) ?? null, lng: num(o.lng) ?? null };
}

const FUNCIONES: Record<string, (a: Args) => Promise<unknown>> = {
  getCiudades: () => getCiudades(),
  getCiudadesReales: () => getCiudadesReales(),
  getRubros: () => getRubros(),
  getCotizaciones: () => getCotizaciones(),
  getClima: () => getClima(),
  getRedes: () => getRedes(),
  getFronteraEstado: (a) => getFronteraEstado(idOpt(a[0])),
  getZonas: () => getZonas(),
  getFiltrosDisponibles: () => getFiltrosDisponibles(),
  getRefinamientos: (a) => getRefinamientos(filtros(a[0])),
  buscarComercios: (a) => buscarComercios(filtros(a[0]), entero(a[1], 24, 1, 500), entero(a[2], 0, 0, 100000)),
  getOfertasDeComercios: async (a) => {
    const ids = (Array.isArray(a[0]) ? a[0] : []).filter((x): x is string => typeof x === "string" && x.length <= 64).slice(0, MAX_IDS);
    const mapa = await getOfertasDeComercios(ids, entero(a[1], 3, 1, 10));
    return [...mapa.entries()];          // Map -> pares, el cliente lo rearma
  },
  getPuntosComercios: (a) => getPuntosComercios(ciudadCoords(a[0])),
  getAdornosMapa: (a) => getAdornosMapa(idOpt(a[0])),
  getFarmaciasDeTurnoAhora: (a) => getFarmaciasDeTurnoAhora(idOpt(a[0])),
  getFuncionesDePlan: (a) => getFuncionesDePlan(str(a[0], 64)),
};

export async function POST(req: Request) {
  const texto = await req.text();
  if (texto.length > MAX_BODY) return NextResponse.json({ error: "demasiado grande" }, { status: 413 });
  let cuerpo: { fn?: unknown; args?: unknown };
  try {
    cuerpo = JSON.parse(texto);
  } catch {
    return NextResponse.json({ error: "json inválido" }, { status: 400 });
  }
  const fn = typeof cuerpo.fn === "string" && Object.prototype.hasOwnProperty.call(FUNCIONES, cuerpo.fn) ? FUNCIONES[cuerpo.fn] : null;
  if (!fn) return NextResponse.json({ error: "función desconocida" }, { status: 404 });
  const args: Args = Array.isArray(cuerpo.args) ? cuerpo.args : [];
  try {
    const data = await fn(args);
    return NextResponse.json({ data }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "no se pudo leer" }, { status: 502, headers: { "Cache-Control": "no-store" } });
  }
}
