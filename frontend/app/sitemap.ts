import type { MetadataRoute } from "next";
import { supabase, hasSupabase } from "@/lib/supabase";

/**
 * El mapa del sitio para los buscadores: las páginas fijas y la ficha de
 * cada comercio activo. Sin esto Google descubre las fichas una por una,
 * siguiendo enlaces, y a un local nuevo le puede llevar semanas aparecer
 * buscándolo por nombre. Con el sitemap lo encuentra en el próximo rastreo.
 *
 * Sólo en producción: en QA robots.ts bloquea todo, y un sitemap ahí sería
 * una invitación a indexar lo que se está bloqueando.
 */
export const revalidate = 3600;

const SITIO = "https://uruku.bo";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const esProd = (process.env.NEXT_PUBLIC_ENV_LABEL || "").toLowerCase() === "prod";
  if (!esProd) return [];
  const fijas: MetadataRoute.Sitemap = [
    { url: `${SITIO}/`, changeFrequency: "daily", priority: 1 },
    { url: `${SITIO}/buscar`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITIO}/buscar?vista=mapa`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITIO}/ofertas`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITIO}/novedades`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITIO}/guia`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITIO}/cambio`, changeFrequency: "daily", priority: 0.8 },
    { url: `${SITIO}/planes`, changeFrequency: "monthly", priority: 0.6 },
    { url: `${SITIO}/comunidad`, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITIO}/autoregistro`, changeFrequency: "monthly", priority: 0.5 },
  ];
  if (!hasSupabase) return fijas;
  const fichas: MetadataRoute.Sitemap = [];
  try {
    // De a mil: PostgREST corta ahí, y hay más de mil comercios.
    for (let desde = 0; desde < 20000; desde += 1000) {
      const { data } = await supabase.from("comercios").select("slug, created_at")
        .eq("activo", true).order("slug").range(desde, desde + 999);
      for (const c of data ?? []) {
        if (c.slug) fichas.push({ url: `${SITIO}/comercios/${c.slug}`, changeFrequency: "weekly", priority: 0.6,
                                  lastModified: c.created_at ? new Date(c.created_at) : undefined });
      }
      if (!data || data.length < 1000) break;
    }
  } catch { /* sin base, el mapa lleva las fijas */ }
  return [...fijas, ...fichas];
}
