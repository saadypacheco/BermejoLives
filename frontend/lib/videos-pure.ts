// Los videos de URUKU en la home (docs/contenido-redes-tecnico.md §15.2).
//
// Acá sólo hay lo PURO (tipos, armado de direcciones, duración ISO 8601 y el nodo
// JSON-LD `VideoObject`): se prueba con `npm test` (tests/videos.test.ts). Por eso
// los imports son relativos. La lectura de la API está en `lib/videos-public.ts`.

import { urlApi, API_BASE } from "./content-pure";
import { absoluteUrl, cityPath, type JsonLdNode } from "./seo";

/* ─── Contrato de `GET /public/videos` (§15.1) ───────────────────────────── */

export type VideoNetwork = "tiktok" | "instagram" | "facebook" | "youtube";

export type PublicVideo = {
  id: string;
  title: string;
  comercio: { nombre: string; slug: string } | null;
  /** Video de un rubro («Zapatillas en Bermejo»): su `title` YA trae la ciudad. */
  rubro: { nombre: string; slug: string } | null;
  city_slug: string | null;
  published_at: string;
  duration_s: number | null;
  /** Rutas RELATIVAS estables (`/public/videos/{id}/cover`): se les antepone la base de la API. */
  cover_url: string;
  video_url: string;
  network_links: Partial<Record<VideoNetwork, string>>;
};

export type PublicVideoList = { items: PublicVideo[] };

export const VIDEO_NETWORK_LABEL: Record<VideoNetwork, string> = {
  tiktok: "TikTok",
  instagram: "Instagram",
  facebook: "Facebook",
  youtube: "YouTube",
};

/* ─── Lectura defensiva ──────────────────────────────────────────────────── */

const esTexto = (v: unknown): v is string => typeof v === "string" && v.trim() !== "";

/** Un link de red sólo se muestra si es `http(s)`: viene de la base y no se confía en que sea un link. */
export function esLinkWeb(v: unknown): v is string {
  if (!esTexto(v)) return false;
  try {
    const u = new URL(v);
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}

/**
 * Del JSON de la API a la lista que dibuja la home. Descarta lo que no sirve (sin id,
 * título, portada o video) en vez de romper: la franja nunca tira la home.
 */
export function normalizarVideos(raw: unknown): PublicVideo[] {
  const items = (raw as { items?: unknown } | null)?.items;
  if (!Array.isArray(items)) return [];
  const out: PublicVideo[] = [];
  for (const it of items as unknown[]) {
    const v = it as Record<string, unknown> | null;
    if (!v || !esTexto(v.id) || !esTexto(v.title) || !esTexto(v.cover_url) || !esTexto(v.video_url)) continue;
    const c = v.comercio as { nombre?: unknown; slug?: unknown } | null | undefined;
    const comercio = c && esTexto(c.nombre) && esTexto(c.slug) ? { nombre: c.nombre, slug: c.slug } : null;
    const r = v.rubro as { nombre?: unknown; slug?: unknown } | null | undefined;
    const rubro = r && esTexto(r.nombre) && esTexto(r.slug) ? { nombre: r.nombre, slug: r.slug } : null;
    const links: Partial<Record<VideoNetwork, string>> = {};
    const nl = (v.network_links ?? {}) as Record<string, unknown>;
    for (const red of Object.keys(VIDEO_NETWORK_LABEL) as VideoNetwork[]) {
      if (esLinkWeb(nl[red])) links[red] = nl[red] as string;
    }
    out.push({
      id: v.id,
      title: v.title,
      comercio,
      rubro,
      city_slug: esTexto(v.city_slug) ? v.city_slug : null,
      published_at: esTexto(v.published_at) ? v.published_at : "",
      duration_s: typeof v.duration_s === "number" && Number.isFinite(v.duration_s) && v.duration_s > 0 ? v.duration_s : null,
      cover_url: v.cover_url,
      video_url: v.video_url,
      network_links: links,
    });
  }
  return out;
}

/* ─── Direcciones ────────────────────────────────────────────────────────── */

/** La portada o el video, con la base de la API delante (las rutas vienen relativas). */
export function videoUrl(rel: string, base: string = API_BASE): string {
  return urlApi(rel, base);
}

/** El link «Ver el rubro» de un video de rubro: `/{city_slug}/{rubro.slug}`. Sin rubro o sin ciudad, `null`. */
export function rubroHref(v: Pick<PublicVideo, "rubro" | "city_slug">): string | null {
  if (!v.rubro || !v.city_slug) return null;
  return `${cityPath(v.city_slug)}/${v.rubro.slug}`;
}

/* ─── Duración ISO 8601 ──────────────────────────────────────────────────── */

/** `90` → `PT1M30S`, `3725` → `PT1H2M5S`. Sin dato o inválido, `undefined` (no se declara). */
export function duracionIso(segundos: number | null | undefined): string | undefined {
  if (segundos == null || !Number.isFinite(segundos) || segundos <= 0) return undefined;
  const total = Math.round(segundos);
  if (total <= 0) return undefined;
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return `PT${h ? `${h}H` : ""}${m ? `${m}M` : ""}${s ? `${s}S` : ""}`;
}

/** `75` → `1:15`, para la etiqueta de la portada. */
export function duracionCorta(segundos: number | null | undefined): string | null {
  if (segundos == null || !Number.isFinite(segundos) || segundos <= 0) return null;
  const total = Math.round(segundos);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

/* ─── JSON-LD ────────────────────────────────────────────────────────────── */

/**
 * El `VideoObject` de un video para el grafo de la home. `thumbnailUrl` y `contentUrl`
 * son absolutos (base de la API). Sin fecha de publicación válida no se declara el nodo:
 * `uploadDate` es obligatorio para Google y un valor inventado sería peor que nada.
 */
export function videoObjectNode(v: PublicVideo, o: { ciudad?: string | null; base?: string } = {}): JsonLdNode | null {
  const fecha = Date.parse(v.published_at);
  if (!Number.isFinite(fecha)) return null;
  const base = o.base ?? API_BASE;
  // En un video de rubro el título ya dice la ciudad («Zapatillas en Bermejo»): no se repite.
  const donde = o.ciudad && !v.rubro ? ` en ${o.ciudad}` : "";
  const description = v.comercio
    ? `Video de ${v.comercio.nombre}${donde}, publicado en las redes de URUKU.`
    : `${v.title}${donde}: video de URUKU.`;
  const duration = duracionIso(v.duration_s);
  return {
    "@type": "VideoObject",
    name: v.title,
    description,
    thumbnailUrl: [urlApi(v.cover_url, base)],
    contentUrl: urlApi(v.video_url, base),
    uploadDate: new Date(fecha).toISOString(),
    ...(duration ? { duration } : {}),
    inLanguage: "es",
    publisher: { "@id": absoluteUrl("/#organization") },
  };
}

/** Los nodos de toda la franja, sin los que no se pueden declarar. */
export function videoObjectNodes(videos: readonly PublicVideo[], o: { ciudad?: string | null; base?: string } = {}): JsonLdNode[] {
  return videos.map((v) => videoObjectNode(v, o)).filter((n): n is JsonLdNode => n !== null);
}
