// Lectura de `/pieza/<token>` en el SERVIDOR (docs/contenido-redes-tecnico.md §9.5).
//
// La página que el comerciante abre desde el WhatsApp que le mandamos: ve su
// video, lo baja para su estado y copia el texto. Se consulta en cada visita
// (`no-store`): el enlace vence a los 60 días y no se cachea nada. Sin login: el
// token de 22+ caracteres es la llave.
import { API_BASE } from "@/lib/content-pure";

export type PiezaCompartida = {
  comercio_nombre: string;
  comercio_slug: string;
  pillar: string;
  published_at: string | null;
  expires_at: string;
  /** Rutas relativas de la API; se les antepone la base con `urlApi`. */
  video_url: string;
  video_download_url: string;
  cover_url: string | null;
  posts: { network: string; network_label: string; post_url: string | null }[];
  /** El texto para el estado del comerciante, con `?ref=st-<slug>`. */
  status_text: string;
};

export type LecturaPieza =
  | { tipo: "ok"; datos: PiezaCompartida }
  | { tipo: "no_existe" }
  | { tipo: "vencido" }
  | { tipo: "error" };

/** Un token de verdad es largo y sólo tiene letras, números, `-` y `_`: lo demás
 *  ni se manda a la API (no se arma una URL con lo que escribió cualquiera). */
export function tokenValido(token: string): boolean {
  return /^[A-Za-z0-9_-]{22,128}$/.test(token);
}

export async function leerPieza(token: string): Promise<LecturaPieza> {
  if (!tokenValido(token)) return { tipo: "no_existe" };
  try {
    const res = await fetch(`${API_BASE}/public/pieces/${encodeURIComponent(token)}`, { cache: "no-store" });
    if (res.status === 404) return { tipo: "no_existe" };
    if (res.status === 410) return { tipo: "vencido" };
    if (!res.ok) return { tipo: "error" };
    const d = (await res.json()) as Partial<PiezaCompartida> | null;
    if (!d || typeof d.video_url !== "string") return { tipo: "error" };
    return {
      tipo: "ok",
      datos: {
        comercio_nombre: typeof d.comercio_nombre === "string" ? d.comercio_nombre : "",
        comercio_slug: typeof d.comercio_slug === "string" ? d.comercio_slug : "",
        pillar: typeof d.pillar === "string" ? d.pillar : "",
        published_at: d.published_at ?? null,
        expires_at: typeof d.expires_at === "string" ? d.expires_at : "",
        video_url: d.video_url,
        video_download_url: typeof d.video_download_url === "string" ? d.video_download_url : `${d.video_url}?download=1`,
        cover_url: d.cover_url ?? null,
        posts: Array.isArray(d.posts) ? d.posts : [],
        status_text: typeof d.status_text === "string" ? d.status_text : "",
      },
    };
  } catch {
    return { tipo: "error" };
  }
}
