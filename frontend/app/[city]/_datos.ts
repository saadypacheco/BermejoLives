import { cache } from "react";
import { buscarComercios, getCiudades, getCityCategoryPages, getTurnosFarmacia } from "@/lib/data";
import type { CityCategoryPage } from "@/lib/seo";
import { hasSupabase, supabase } from "@/lib/supabase";
import { rangoTurnos } from "@/lib/turnos-farmacia";
import type { Ciudad, ResultadoBusqueda } from "@/lib/types";

/**
 * Lecturas compartidas por /{ciudad}, /{ciudad}/{rubro} y
 * /{ciudad}/farmacias-de-turno. `cache` de React: `generateMetadata` y la
 * página piden lo mismo y se paga una sola consulta por pedido.
 */

/** La ciudad de la URL, o `null` si no existe o no está activa (→ 404). */
export const cargarCiudad = cache(async (slug: string): Promise<Ciudad | null> => {
  const ciudad = (await getCiudades()).find((c) => c.slug === slug);
  return ciudad && ciudad.activa ? ciudad : null;
});

/** Los pares ciudad+rubro (`city_category_pages()`). `[]` si la RPC no está o falla. */
export const cargarPares = cache((): Promise<CityCategoryPage[]> => getCityCategoryPages());

/** Los slugs de ciudad que tienen algún par: lo que se pre-renderiza. */
export function ciudadesConPares(pares: readonly CityCategoryPage[]): string[] {
  return [...new Set(pares.map((p) => p.city_slug))];
}

/** Cuántos locales se listan como máximo en una página de rubro. */
export const TOPE_LISTA = 500;

/** `calle` de cada comercio (la RPC de búsqueda no la devuelve). Columnas
 *  explícitas de `COLUMNAS_COMERCIO`, nunca `select("*")` (regla 11 de AGENTS.md).
 *  De a 100 ids por consulta para no pasar el largo de URL de PostgREST. Una
 *  consulta que falla sólo deja a esos locales sin calle: no rompe la página. */
async function cargarCalles(ids: string[]): Promise<Map<string, string>> {
  const calles = new Map<string, string>();
  if (!hasSupabase || ids.length === 0) return calles;
  const lotes: string[][] = [];
  for (let i = 0; i < ids.length; i += 100) lotes.push(ids.slice(i, i + 100));
  const resultados = await Promise.all(lotes.map((lote) => supabase.from("comercios").select("id, calle").in("id", lote)));
  for (const { data, error } of resultados) {
    if (error) { console.warn("categoria: calle error:", error.message); continue; }
    for (const f of (data ?? []) as { id: string; calle: string | null }[]) {
      if (f.calle && f.calle.trim()) calles.set(f.id, f.calle.trim());
    }
  }
  return calles;
}

export type LocalDeCategoria = ResultadoBusqueda & { calle: string | null };

/**
 * Los locales de un rubro en una ciudad, con su calle. Se llama DESPUÉS de saber
 * que el par existe (`categoryPageState`): ahí la lista no puede estar vacía, y si
 * lo está es que la lectura falló. Se lanza el error en vez de devolver `[]`: Next
 * no guarda en caché una página que lanza (sigue sirviendo la anterior), mientras
 * que una lista vacía quedaría fija toda la hora de ISR.
 */
export const cargarLocales = cache(async (ciudadSlug: string, rubroSlug: string): Promise<LocalDeCategoria[]> => {
  const filas = await buscarComercios({ ciudad: ciudadSlug, rubro: rubroSlug }, TOPE_LISTA, 0);
  if (filas.length === 0) throw new Error(`No se pudieron leer los locales de ${rubroSlug} en ${ciudadSlug}`);
  const calles = await cargarCalles(filas.map((f) => f.id));
  return filas.map((f) => ({ ...f, calle: calles.get(f.id) ?? null }));
});

/** Los turnos de farmacia de la ciudad desde ayer hasta `dias` adelante. `turnos`
 *  es `null` si la lectura falló (la página no puede afirmar que «no hay»). */
export const cargarTurnos = cache(async (ciudadId: string, dias: number) => {
  const ahora = new Date();
  const { desde, hasta } = rangoTurnos(ahora, dias);
  return { ahora, turnos: await getTurnosFarmacia(ciudadId, desde, hasta) };
});

/** ¿La ciudad tiene un rol de turnos cargado (hoy o en el próximo mes)? Decide si
 *  existe /{ciudad}/farmacias-de-turno y si la ciudad lo enlaza. `null` = no se pudo leer. */
export async function ciudadTieneTurnos(ciudadId: string): Promise<boolean | null> {
  const { turnos } = await cargarTurnos(ciudadId, 30);
  return turnos === null ? null : turnos.length > 0;
}
