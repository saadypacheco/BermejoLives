import { cache } from "react";
import { buscarComerciosOrNull, getCiudades, getCiudadesReales, getCityCategoryPagesOrNull, getTurnosFarmacia } from "@/lib/data";
import { esSlugPublico, type CityCategoryPage } from "@/lib/seo";
import { hasSupabase, supabase } from "@/lib/supabase";
import { rangoTurnos } from "@/lib/turnos-farmacia";
import type { Ciudad, ResultadoBusqueda } from "@/lib/types";

/**
 * Lecturas compartidas por /{ciudad}, /{ciudad}/{rubro} y
 * /{ciudad}/farmacias-de-turno. `cache` de React: `generateMetadata` y la
 * página piden lo mismo y se paga una sola consulta por pedido.
 */

/**
 * REGLA DE ESTAS LECTURAS (ISR): «no se pudo leer» NUNCA se confunde con «no
 * existe». Ante un fallo se LANZA: Next sigue sirviendo la versión anterior de la
 * página y no guarda un 500 en caché. Un `notFound()` o un `noindex` sólo después
 * de una lectura que salió bien y confirma la ausencia; si no, un corte de la base
 * de dos segundos dejaba un 404 fijo toda la hora de `revalidate`.
 */

/** La ciudad de la URL, o `null` si no existe o no está activa (→ 404). Un slug
 *  con forma inválida (`/.env`, basura de un escáner) da `null` SIN tocar la base.
 *  Lanza si no se pudo leer la lista de ciudades. */
export const cargarCiudad = cache(async (slug: string): Promise<Ciudad | null> => {
  if (!esSlugPublico(slug)) return null;
  // Sin base configurada (desarrollo) vale la lista demo; con base, un `null` es un fallo.
  const ciudades = hasSupabase ? await getCiudadesReales() : await getCiudades();
  if (ciudades === null) throw new Error("No se pudieron leer las ciudades");
  const ciudad = ciudades.find((c) => c.slug === slug);
  return ciudad && ciudad.activa ? ciudad : null;
});

/** Los pares ciudad+rubro (`city_category_pages()`). Lanza si la RPC falla. */
export const cargarPares = cache(async (): Promise<CityCategoryPage[]> => {
  const pares = await getCityCategoryPagesOrNull();
  if (pares === null) throw new Error("No se pudo leer city_category_pages()");
  return pares;
});

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
  const filas = await buscarComerciosOrNull({ ciudad: ciudadSlug, rubro: rubroSlug }, TOPE_LISTA, 0);
  if (!filas || filas.length === 0) throw new Error(`No se pudieron leer los locales de ${rubroSlug} en ${ciudadSlug}`);
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
