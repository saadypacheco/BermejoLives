import { supabase, hasSupabase } from "@/lib/supabase";

/**
 * Cuándo se tocó por última vez el saber local de cada sección de la guía
 * (`updated_at` más reciente de sus preguntas activas), para el «Revisado el …»
 * de /guia y /comprar-en-bermejo (docs/visibilidad-buscadores-ia.md §3.8).
 *
 * Mismo filtro que `getSaberLocalPorSeccion` (saber de URUKU, de la ciudad o de
 * todas). Sin base o ante un error devuelve `{}`: la página simplemente no dice
 * la fecha en vez de inventarla.
 */
export async function getSaberRevisado(ciudadId?: string | null): Promise<Record<string, string>> {
  if (!hasSupabase) return {};
  try {
    let q = supabase.from("saber_local").select("seccion, updated_at").eq("activo", true).is("comercio_id", null);
    if (ciudadId) q = q.or(`ciudad_id.eq.${ciudadId},ciudad_id.is.null`);
    const { data, error } = await q;
    if (error) return {};
    const out: Record<string, string> = {};
    for (const r of (data ?? []) as { seccion: string | null; updated_at: string | null }[]) {
      const sec = r.seccion || "general";
      if (r.updated_at && (!out[sec] || r.updated_at > out[sec])) out[sec] = r.updated_at;
    }
    return out;
  } catch {
    return {};
  }
}
