import type { MetadataRoute } from "next";
import { supabase, hasSupabase } from "@/lib/supabase";
import { getBusinessesForSitemap, getCityCategoryPages } from "@/lib/data";
import { absoluteUrl, businessPath, categoryPath, cityPath } from "@/lib/seo";

/**
 * El mapa del sitio para los buscadores (docs/visibilidad-buscadores-ia.md §3.7).
 *
 *  - Fichas: sólo las indexables (`getBusinessesForSitemap` ya filtra las
 *    «vacías»), con `lastModified` = `updated_at`.
 *  - Ciudades (`/{city}`) y pares ciudad+rubro (`/{city}/{rubro}`): sólo los
 *    indexables según `city_category_pages()`; `lastModified` = `last_modified`
 *    del par (la ciudad toma el más reciente de sus pares).
 *  - Novedades de URUKU y las páginas de contenido.
 *  - NO lleva `/buscar` ni `/buscar?vista=mapa`: son `noindex`.
 *
 * Sólo en producción: en QA robots.ts bloquea todo, y un sitemap ahí sería
 * una invitación a indexar lo que se está bloqueando.
 */
export const revalidate = 3600;

const aFecha = (iso: string | null | undefined): Date | undefined => {
  if (!iso) return undefined;
  const d = new Date(iso);
  return Number.isFinite(d.getTime()) ? d : undefined;
};

/** Las novedades de URUKU activas (de cualquier ciudad), con su fecha. */
async function novedadesParaSitemap(): Promise<{ id: string; fecha: string | null }[]> {
  if (!hasSupabase) return [];
  try {
    const { data, error } = await supabase.from("novedades_uruku").select("id, fecha").eq("activo", true).limit(1000);
    if (error) return [];
    return (data ?? []) as { id: string; fecha: string | null }[];
  } catch {
    return [];
  }
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const esProd = (process.env.NEXT_PUBLIC_ENV_LABEL || "").toLowerCase() === "prod";
  if (!esProd) return [];
  // /planes salió del sitemap el 2/10: los precios se deciden por ciudad y todavía
  // no están definidos fuera de Bermejo. La página existe para uso interno.
  const fijas: MetadataRoute.Sitemap = [
    { url: absoluteUrl("/"), changeFrequency: "daily", priority: 1 },
    { url: absoluteUrl("/que-es-uruku"), changeFrequency: "monthly", priority: 0.8 },
    { url: absoluteUrl("/comprar-en-bermejo"), changeFrequency: "weekly", priority: 0.9 },
    { url: absoluteUrl("/guia"), changeFrequency: "weekly", priority: 0.9 },
    { url: absoluteUrl("/ofertas"), changeFrequency: "daily", priority: 0.9 },
    { url: absoluteUrl("/novedades"), changeFrequency: "daily", priority: 0.8 },
    { url: absoluteUrl("/cambio"), changeFrequency: "daily", priority: 0.8 },
    { url: absoluteUrl("/farmacias-de-turno"), changeFrequency: "daily", priority: 0.8 },
    { url: absoluteUrl("/comunidad"), changeFrequency: "monthly", priority: 0.7 },
    { url: absoluteUrl("/agentes"), changeFrequency: "monthly", priority: 0.5 },
    { url: absoluteUrl("/autoregistro"), changeFrequency: "monthly", priority: 0.5 },
  ];
  if (!hasSupabase) return fijas;

  const [pares, fichas, novedades] = await Promise.all([
    getCityCategoryPages(), getBusinessesForSitemap(), novedadesParaSitemap(),
  ]);

  const indexables = pares.filter((p) => p.indexable);
  // Una entrada por ciudad con la fecha más reciente de sus pares.
  const ciudades = new Map<string, Date | undefined>();
  for (const p of indexables) {
    const f = aFecha(p.last_modified);
    const previa = ciudades.get(p.city_slug);
    ciudades.set(p.city_slug, f && (!previa || f > previa) ? f : previa);
  }

  const out: MetadataRoute.Sitemap = [...fijas];
  for (const [slug, lastModified] of ciudades) {
    out.push({ url: absoluteUrl(cityPath(slug)), changeFrequency: "daily", priority: 0.8, lastModified });
  }
  for (const p of indexables) {
    out.push({
      url: absoluteUrl(categoryPath(p.city_slug, p.category_slug)),
      changeFrequency: "weekly", priority: 0.7, lastModified: aFecha(p.last_modified),
    });
  }
  for (const n of novedades) {
    out.push({ url: absoluteUrl(`/novedades/uruku/${n.id}`), changeFrequency: "monthly", priority: 0.4, lastModified: aFecha(n.fecha) });
  }
  for (const c of fichas) {
    out.push({ url: absoluteUrl(businessPath(c.slug)), changeFrequency: "weekly", priority: 0.6, lastModified: aFecha(c.updated_at) });
  }
  return out;
}
