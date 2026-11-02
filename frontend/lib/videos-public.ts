// Lectura en el SERVIDOR de los videos de URUKU para la home (§15.2). Nunca tira: ante
// cualquier falla (la API caída, lenta, una respuesta rara) devuelve `[]` y la home sigue.

import { API_BASE } from "./content-pure";
import { normalizarVideos, type PublicVideo } from "./videos-pure";

const TIMEOUT_MS = 2500;
const VIGENCIA_MS = 5 * 60_000;
const REINTENTO_MS = 30_000;

// La home es `force-dynamic`, que en Next 14 anula el caché de `fetch`: por eso, además de
// `next.revalidate`, se recuerda la lista unos minutos en memoria por ciudad (y 30 s si falló,
// para no pegarle a una API caída en cada pedido). En el build no se recuerda nada.
const memo = new Map<string, { hasta: number; videos: PublicVideo[] }>();

export async function getVideosUruku(citySlug: string | null | undefined, limit = 12): Promise<PublicVideo[]> {
  const enBuild = process.env.NEXT_PHASE === "phase-production-build";
  const clave = `${citySlug ?? ""}|${limit}`;
  const ahora = Date.now();
  const guardado = memo.get(clave);
  if (!enBuild && guardado && ahora < guardado.hasta) return guardado.videos;

  let videos: PublicVideo[] = [];
  let ok = false;
  try {
    const qs = new URLSearchParams();
    if (citySlug) qs.set("city", citySlug);
    qs.set("limit", String(limit));
    const res = await fetch(`${API_BASE.replace(/\/+$/, "")}/public/videos?${qs}`, {
      next: { revalidate: 300 },
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (res.ok) {
      videos = normalizarVideos(await res.json());
      ok = true;
    }
  } catch {
    videos = [];
  }
  if (!enBuild) memo.set(clave, { hasta: ahora + (ok ? VIGENCIA_MS : REINTENTO_MS), videos });
  return videos;
}
