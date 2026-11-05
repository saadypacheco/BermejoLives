// Lecturas de datos desde el NAVEGADOR. Sin supabase-js, sin URL de la base ni
// anon key: cada función le pide al servidor (`/api/lectura`, app/api/lectura/
// route.ts) y devuelve lo mismo que su gemela de lib/data.ts. Los componentes
// cliente importan de acá; lib/data.ts es `server-only`.
//
// Un error de red o del servidor LANZA (como antes lanzaba un fetch roto): los
// componentes ya hacen `.catch(() => {})` o muestran su estado de error.
import type { Adorno } from "@/lib/adornos";
import type { Clima, Cotizacion, FiltrosDisponibles, FronteraEstado, Red } from "@/lib/data-pure";
import type { TurnoFarmacia } from "@/lib/turnos-farmacia";
import type { Ciudad, FeedItem, FiltrosBusqueda, ResultadoBusqueda, Rubro, Zona } from "@/lib/types";

async function leer<T>(fn: string, ...args: unknown[]): Promise<T> {
  const res = await fetch("/api/lectura", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fn, args }),
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`lectura ${fn}: ${res.status}`);
  const json = (await res.json()) as { data: T };
  return json.data;
}

export const getCiudades = () => leer<Ciudad[]>("getCiudades");
export const getCiudadesReales = () => leer<Ciudad[] | null>("getCiudadesReales");
export const getRubros = () => leer<Rubro[]>("getRubros");
export const getZonas = () => leer<Zona[]>("getZonas");
export const getFiltrosDisponibles = () => leer<FiltrosDisponibles>("getFiltrosDisponibles");
export const getRefinamientos = (f: FiltrosBusqueda) =>
  leer<{ subcategoria: string; n: number }[]>("getRefinamientos", f);
export const buscarComercios = (f: FiltrosBusqueda, limit = 24, offset = 0) =>
  leer<ResultadoBusqueda[]>("buscarComercios", f, limit, offset);
export const getPuntosComercios = (ciudad: { lat: number | null; lng: number | null }) =>
  leer<{ lat: number; lng: number }[]>("getPuntosComercios", ciudad);
export const getAdornosMapa = (ciudadId?: string | null) => leer<Adorno[]>("getAdornosMapa", ciudadId ?? null);
export const getFarmaciasDeTurnoAhora = (ciudadId: string | null | undefined) =>
  leer<TurnoFarmacia[] | null>("getFarmaciasDeTurnoAhora", ciudadId ?? null);
export const getCotizaciones = () => leer<Cotizacion[]>("getCotizaciones");
export const getClima = () => leer<Clima | null>("getClima");
export const getRedes = () => leer<Red[]>("getRedes");
export const getFronteraEstado = (ciudadId?: string | null) =>
  leer<FronteraEstado | null>("getFronteraEstado", ciudadId ?? null);
export const getFuncionesDePlan = (slug: string | null | undefined) =>
  leer<Record<string, boolean> | null>("getFuncionesDePlan", slug ?? null);

export async function getOfertasDeComercios(ids: string[], porComercio = 3): Promise<Map<string, FeedItem[]>> {
  if (ids.length === 0) return new Map();
  return new Map(await leer<[string, FeedItem[]][]>("getOfertasDeComercios", ids, porComercio));
}
