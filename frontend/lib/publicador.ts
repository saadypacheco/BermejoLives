// Cliente del panel de PUBLICADOR (contenido de la home: cotizaciones/clima/videos).
import { postFormData, subirConProgreso } from "@/lib/upload";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_publicador_token";

export const getPubToken = (): string | null =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
export const clearPub = () => localStorage.removeItem(TOKEN_KEY);
export const hayPub = () => Boolean(getPubToken());

export async function publicadorLogin(email: string, password: string): Promise<void> {
  const res = await fetch(`${API}/auth/publicador/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  localStorage.setItem(TOKEN_KEY, (await res.json()).access_token);
}

async function pFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getPubToken() ?? ""}`, ...(init?.headers ?? {}) },
  });
  // La sesión vencida BORRA el token, como ya hacían el panel de campo y el de
  // mi-comercio. Éste era el único que no: el token queda guardado, `hayPub()`
  // sigue diciendo que sí, y la pantalla se queda mostrando el formulario lleno
  // mientras cada Guardar contesta "token expirado". No hay forma de salir de
  // ahí salvo saber que existe el botón de cerrar sesión.
  if (res.status === 401) {
    if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("uk-sesion-vencida"));
    clearPub();
    throw new Error("Tu sesión venció. Volvé a entrar.");
  }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "Error");
  }
  return res.json();
}

export const editarCotizacion = (clave: string, valor: number) =>
  pFetch(`/contenido/cotizaciones/${clave}`, { method: "PUT", body: JSON.stringify({ valor }) });
export const overrideClima = (b: { temp_c?: number; descripcion?: string; icono?: string; horas?: number }) =>
  pFetch("/contenido/clima", { method: "PUT", body: JSON.stringify(b) });
export const refrescarClima = () => pFetch("/contenido/clima/refresh", { method: "POST" });
export type FronteraPatch = { puente?: string; chalanas?: string; rio?: string; nota?: string; chalanas_horario?: string; ciudad?: string };
export const editarFrontera = (b: FronteraPatch) => pFetch("/contenido/frontera", { method: "PUT", body: JSON.stringify(b) });

export type VideoPromoItem = { id: string; titulo: string | null; url: string };
export const listarVideosPromo = (): Promise<VideoPromoItem[]> =>
  pFetch("/contenido/videos-promo").then((d) => d.items ?? []);
export const subirVideoPromo = (file: File, titulo: string, onP?: (p: number) => void): Promise<VideoPromoItem> =>
  subirConProgreso<{ video: VideoPromoItem }>(`${API}/contenido/videos-promo`, "video", file, getPubToken(), titulo ? { titulo } : {}, onP).then((d) => d.video);
export const borrarVideoPromo = (id: string) =>
  pFetch(`/contenido/videos-promo/${id}`, { method: "DELETE" });

// ---- Novedades de URUKU (0150, docs/novedades-uruku.md) ----
// Mismo permiso `contenido` y mismo token que los videos promo. El backend las
// da de baja con soft-delete (`activo=false`); nunca se borra una fila.

export type NovedadUrukuFoto = { url: string; thumb_url: string | null };
export type NovedadUrukuAdmin = {
  id: string;
  ciudad_id: string | null;       // null = todas las ciudades
  titulo: string;
  texto: string | null;
  fecha: string;                  // YYYY-MM-DD
  portada_url: string | null;
  portada_thumb_url: string | null;
  fotos: NovedadUrukuFoto[];
  video_url: string | null;
  video_poster_url: string | null;
  enlace_url: string | null;
  destacada: boolean;
  activo: boolean;
};
/** Lo que se manda al crear o editar. `ciudad_slug: null` = todas las ciudades. */
export type NovedadUrukuCampos = {
  titulo?: string; texto?: string | null; fecha?: string; ciudad_slug?: string | null;
  enlace_url?: string | null; destacada?: boolean; activo?: boolean;
};

const txtONull = (x: unknown) => (typeof x === "string" && x ? x : null);
/** Normaliza una fila del backend; `fotos` viene de un jsonb y puede venir raro. */
function novedadAdmin(r: Record<string, unknown>): NovedadUrukuAdmin {
  const fotos = Array.isArray(r.fotos)
    ? (r.fotos as unknown[]).flatMap((f): NovedadUrukuFoto[] => {
        const o = f as { url?: unknown; thumb_url?: unknown } | null;
        return o && typeof o.url === "string" && o.url ? [{ url: o.url, thumb_url: txtONull(o.thumb_url) }] : [];
      })
    : [];
  return {
    id: String(r.id), ciudad_id: txtONull(r.ciudad_id), titulo: String(r.titulo ?? ""), texto: txtONull(r.texto),
    fecha: String(r.fecha ?? "").slice(0, 10), portada_url: txtONull(r.portada_url),
    portada_thumb_url: txtONull(r.portada_thumb_url), fotos, video_url: txtONull(r.video_url),
    video_poster_url: txtONull(r.video_poster_url), enlace_url: txtONull(r.enlace_url),
    destacada: r.destacada === true, activo: r.activo !== false,
  };
}
/** La novedad de una respuesta: viene pelada o envuelta en `novedad`/`item`. */
function unaNovedad(d: Record<string, unknown>): NovedadUrukuAdmin {
  const interna = (d.novedad ?? d.item) as Record<string, unknown> | undefined;
  return novedadAdmin(interna && typeof interna === "object" ? interna : d);
}

export const listarNovedadesUruku = (): Promise<NovedadUrukuAdmin[]> =>
  pFetch("/contenido/novedades").then((d: unknown) => {
    const filas = Array.isArray(d) ? d : ((d as { items?: unknown }).items ?? []);
    return (filas as Record<string, unknown>[]).map(novedadAdmin);
  });
export const crearNovedadUruku = (b: NovedadUrukuCampos): Promise<NovedadUrukuAdmin> =>
  pFetch("/contenido/novedades", { method: "POST", body: JSON.stringify(b) }).then(unaNovedad);
export const editarNovedadUruku = (id: string, b: NovedadUrukuCampos): Promise<NovedadUrukuAdmin> =>
  pFetch(`/contenido/novedades/${id}`, { method: "PATCH", body: JSON.stringify(b) }).then(unaNovedad);
/** Baja lógica: la novedad deja de verse, la fila queda. */
export const bajaNovedadUruku = (id: string) =>
  pFetch(`/contenido/novedades/${id}`, { method: "DELETE" });

/** Las subidas van por XHR y no pasan por `pFetch`: un 401 acá también tiene que
 *  cerrar la sesión vencida, no mostrar «No se pudo subir» para siempre. */
function conSesion<T>(p: Promise<T>): Promise<T> {
  return p.catch((e: unknown) => {
    if ((e as { status?: number } | null)?.status === 401) {
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("uk-sesion-vencida"));
      clearPub();
      throw new Error("Tu sesión venció. Volvé a entrar.");
    }
    throw e;
  });
}
const urlNovedad = (id: string, parte: string) => `${API}/contenido/novedades/${id}/${parte}`;
export const subirPortadaNovedad = (id: string, file: File, onP?: (p: number) => void) =>
  conSesion(subirConProgreso<{ portada_url?: string; portada_thumb_url?: string }>(urlNovedad(id, "portada"), "foto", file, getPubToken(), {}, onP));
export const subirFotoNovedad = (id: string, file: File, onP?: (p: number) => void) =>
  conSesion(subirConProgreso(urlNovedad(id, "fotos"), "foto", file, getPubToken(), {}, onP));
export const quitarFotoNovedad = (id: string, url: string) =>
  pFetch(`/contenido/novedades/${id}/fotos?url=${encodeURIComponent(url)}`, { method: "DELETE" });
/** El video y, si se elige, su póster, en un solo pedido (el backend los toma juntos). */
export const subirVideoNovedad = (id: string, video: File, poster: File | null, onP?: (p: number) => void) => {
  if (!poster) return conSesion(subirConProgreso(urlNovedad(id, "video"), "video", video, getPubToken(), {}, onP));
  const fd = new FormData();
  fd.append("video", video);
  fd.append("poster", poster);
  return conSesion(postFormData(urlNovedad(id, "video"), fd, getPubToken(), onP));
};

export const editarRed = (clave: string, url: string) =>
  pFetch(`/contenido/redes/${clave}`, { method: "PUT", body: JSON.stringify({ url }) });
