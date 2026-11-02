// Cliente del Banco de contenido y del Contenido para redes (docs/contenido-redes-tecnico.md).
//
// Los tipos son el espejo de los schemas de §8.2 (snake_case, tal como viajan) y las
// llamadas siguen las rutas de §8.3. Hay tres puertas, cada una con su token:
//   · el PANEL (`authFetch`, token del admin)        → `/admin/content/*`
//   · la APP DE CAMPO (token del agente)              → `/campo/mis-comercios/{id}/…`
//   · el COMERCIANTE (token de Mi comercio)           → `/comercio/social-consent`
// El front NUNCA lee estas tablas por PostgREST: todo pasa por la API, y los
// archivos privados se ven sólo con las URLs firmadas que ella devuelve.

import { authFetch, getToken } from "@/lib/api";
import { getAgenteToken, clearAgente } from "@/lib/campo";
import { getCToken, clearComercio } from "@/lib/comercio";
import { subirConProgreso } from "@/lib/upload";
import {
  API_BASE, camposSubida,
  type ConsentVia, type ContentNetwork, type ContentPieceStatus, type ContentPillar, type MetaSubida,
} from "@/lib/content-pure";

export type { ConsentVia, ContentNetwork, ContentPieceStatus, ContentPillar, ContentPostStatus, MetaSubida } from "@/lib/content-pure";

/* ─── Schemas (§8.2) ─────────────────────────────────────────────────────── */

export type SocialConsentResponse = {
  granted: boolean | null;
  via: ConsentVia | null;
  recorded_at: string | null;
  recorded_by: string | null;
  note: string | null;
};
export type SocialConsentUpdate = { granted: boolean; via: "admin" | "whatsapp_reply" | "subscription"; note: string | null };
export type SocialConsentRevokeResponse = {
  consent: SocialConsentResponse;
  pieces_skipped: number;
  /** Lo que ya salió en las redes y hay que borrar a mano. */
  published_posts: { network: ContentNetwork; post_url: string | null }[];
};

export type ContentMerchantResponse = {
  id: string; nombre: string; slug: string;
  rubro: string | null; calle: string | null;
  ciudad_slug: string; ciudad_nombre: string;
  is_subscriber: boolean;
  social_consent: SocialConsentResponse;
  bank_photos: number; bank_photos_usable: number; gallery_photos: number;
  last_piece_on: string | null;
};
export type ContentMerchantListResponse = { items: ContentMerchantResponse[]; recent: ContentMerchantResponse[] };

export type ContentAssetResponse = {
  id: string; comercio_id: string;
  width: number; height: number; bytes: number;
  too_small: boolean; usable_for_social: boolean;
  has_people: boolean; people_ok: boolean | null;
  use_count: number; last_used_at: string | null;
  /** Rutas firmadas RELATIVAS (vencen a los 15 min): se les antepone la base de la API. */
  thumb_url: string; file_url: string;
  created_at: string; uploaded_by: string;
};
export type ContentAssetListResponse = { items: ContentAssetResponse[]; usable_for_video: number; min_for_video: number };
export type ContentAssetUploadResponse = {
  ok: true; duplicate: boolean; asset: ContentAssetResponse;
  ficha: { requested: boolean; added: boolean; reason: "tope" | "error" | null };
  warnings: string[];
};
export type ContentAssetUpdate = { usable_for_social?: boolean | null; has_people?: boolean | null; people_ok?: boolean | null };

export type ContentPostResponse = {
  id: string; network: ContentNetwork; network_label: string;
  status: "pending" | "claimed" | "posted" | "skipped";
  ref_tag: string; caption_text: string;
  claimed_by: string | null; claimed_at: string | null; claim_expires_at: string | null;
  posted_by: string | null; posted_at: string | null;
  post_url: string | null; posted_without_link: boolean;
  skip_reason: string | null;
};

export type ContentPieceSummary = {
  id: string; scheduled_for: string;
  pillar: ContentPillar; pillar_label: string;
  status: ContentPieceStatus; status_label: string;
  comercio: { id: string; nombre: string; slug: string } | null;
  ciudad_nombre: string | null;
  counts_for_quota: boolean;
  cover_url: string | null; duration_s: number | null;
  skip_reason: string | null; render_error: string | null;
};
export type ContentPieceSource = {
  position: number; source_type: "asset" | "gallery" | "cover" | "offer";
  thumb_url: string; caption_fact: string | null; comercio_nombre: string | null;
};
export type ContentPieceResponse = ContentPieceSummary & {
  facts: Record<string, unknown>;
  caption_tiktok: string | null; caption_ig: string | null; caption_channel: string | null;
  hashtags: string[]; hashtags_allowed: string[];
  caption_engine: string; caption_checks: string[]; caption_edited: boolean;
  sources: ContentPieceSource[];
  video_url: string | null;
  render: { attempts: number; next_at: string | null; started_at: string | null; ms: number | null };
  posts: ContentPostResponse[];
  approved_by: string | null; approved_at: string | null;
};
export type ContentPieceUpdate = {
  caption_tiktok?: string | null; caption_ig?: string | null; caption_channel?: string | null; hashtags?: string[] | null;
};
export type ContentPieceSkip = { reason: "bad_photos" | "merchant_asked" | "other"; note: string | null };
export type ContentDownloadLinksResponse = { video_url: string; video_download_url: string; cover_url: string; expires_at: string };

export type ContentWeekResponse = {
  week_start: string;
  days: { date: string; weekday_label: string; pieces: ContentPieceSummary[] }[];
  queue: { queued: number; rendering: number; ready_for_review: number; failed: number };
};
export type ContentWeekPlanResponse = {
  week_start: string; created: number;
  slots_left_empty: { date: string; pillar: string; reason: string }[];
  tasks_created: number;
};

export type ContentDayItem = {
  piece: ContentPieceSummary;
  posts: ContentPostResponse[];
  /** El mensaje al comerciante (sólo piezas propias de un suscriptor). */
  delivery: { task_id: string; whatsapp: string | null; message_text: string } | null;
};
export type ContentDayPackageResponse = {
  date: string; items: ContentDayItem[]; overdue: ContentDayItem[];
  pending_review: ContentPieceSummary[];
  next: { date: string; pillar_label: string } | null;
};

export type ContentStatusResponse = {
  render_worker: "disabled" | "no_ffmpeg" | "idle" | "running" | "paused_disk" | "unsafe_dir";
  current_piece_id: string | null;
  queue: { queued: number; rendering: number; ready_for_review: number; failed: number };
  last_render: { piece_id: string; at: string; ms: number | null; ok: boolean; error: string | null } | null;
  disk: { content_bytes: number; free_bytes: number; max_bytes: number };
  gemini_configured: boolean;
};

/* ─── Errores ────────────────────────────────────────────────────────────── */

/** Un error de la API con lo que las pantallas necesitan para distinguirlo. */
export class ContentApiError extends Error {
  status?: number;
  codigo?: string;
  /** El `detail` crudo cuando no es un texto (lo lee `codigoDeError`). */
  datos?: unknown;
  constructor(mensaje: string, status?: number, codigo?: string, datos?: unknown) {
    super(mensaje);
    this.name = "ContentApiError";
    this.status = status;
    this.codigo = codigo;
    this.datos = datos;
  }
}

/** El `detail` de FastAPI es un texto o, donde la pantalla distingue, un
 *  `{codigo, mensaje}` (§8). `authFetch` ya lo deja colgado en `.detail`. */
function normalizarError(ex: unknown, porDefecto: string): ContentApiError {
  const e = ex as { message?: string; status?: number; detail?: unknown; datos?: unknown } | null;
  const detalle = (e?.detail ?? e?.datos) as { codigo?: unknown; mensaje?: unknown } | string | undefined;
  let mensaje = "";
  let codigo: string | undefined;
  if (detalle && typeof detalle === "object") {
    if (typeof detalle.mensaje === "string") mensaje = detalle.mensaje;
    if (typeof detalle.codigo === "string") codigo = detalle.codigo;
  } else if (typeof detalle === "string") {
    mensaje = detalle;
  }
  if (!mensaje) {
    const m = (e?.message ?? "").trim();
    // «Falló /admin/... (HTTP 409)» es el respaldo de authFetch: no le dice nada a quien opera.
    mensaje = m && !/^Falló\s/.test(m) ? m : porDefecto;
  }
  if (mensaje === "Failed to fetch" || mensaje === "Load failed" || mensaje === "NetworkError when attempting to fetch resource") {
    mensaje = "No hay conexión con el servidor";
  }
  return new ContentApiError(mensaje, e?.status, codigo, detalle && typeof detalle === "object" ? detalle : undefined);
}

/** El mensaje de cualquier error, listo para mostrar. */
export function mensajeContent(ex: unknown, porDefecto = "Algo falló. Probá de nuevo."): string {
  const m = ex instanceof Error ? ex.message.trim() : "";
  if (!m || m === "Failed to fetch" || m === "Load failed") return "No hay conexión con el servidor";
  return m || porDefecto;
}

/** Un pedido al panel (admin): JSON de ida y de vuelta, con errores legibles. */
export async function panelJson<T>(path: string, init: { method?: string; body?: unknown } = {}, porDefecto = "No se pudo completar"): Promise<T> {
  try {
    const res = await authFetch(path, {
      method: init.method ?? "GET",
      headers: init.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
    return (await res.json().catch(() => ({}))) as T;
  } catch (ex) {
    throw normalizarError(ex, porDefecto);
  }
}

/* ─── Identidad de quien usa el panel (sólo para mostrar) ─────────────────── */

/** Quién es la persona logueada en el panel, del token. Sirve para saber si una
 *  red «reclamada» la reclamó ella. Es sólo para mostrar: el backend decide con
 *  el token firmado. */
export function miIdentidad(): { email: string | null; nombre: string | null } {
  const t = getToken();
  if (!t) return { email: null, nombre: null };
  try {
    const cuerpo = t.split(".")[1];
    const bytes = Uint8Array.from(atob(cuerpo.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
    const j = JSON.parse(new TextDecoder().decode(bytes)) as { sub?: unknown; email?: unknown; nombre?: unknown };
    const txt = (x: unknown) => (typeof x === "string" && x.trim() ? x.trim() : null);
    return { email: txt(j.email) ?? txt(j.sub), nombre: txt(j.nombre) };
  } catch {
    return { email: null, nombre: null };
  }
}

/* ─── Banco y autorización: PANEL ────────────────────────────────────────── */

export const buscarComerciosBanco = (q: string, limit = 20): Promise<ContentMerchantListResponse> => {
  const p = new URLSearchParams({ limit: String(limit) });
  if (q.trim()) p.set("q", q.trim());
  return panelJson(`/admin/content/merchants?${p.toString()}`, {}, "No se pudo buscar comercios");
};

export const listarAssetsAdmin = (comercioId: string): Promise<ContentAssetListResponse> =>
  panelJson(`/admin/content/merchants/${encodeURIComponent(comercioId)}/assets`, {}, "No se pudieron cargar las fotos");

export const actualizarAssetAdmin = (assetId: string, patch: ContentAssetUpdate): Promise<ContentAssetResponse> =>
  panelJson(`/admin/content/assets/${encodeURIComponent(assetId)}`, { method: "PATCH", body: patch }, "No se pudo cambiar la foto");

export const darDeBajaAssetAdmin = async (assetId: string): Promise<void> => {
  await panelJson(`/admin/content/assets/${encodeURIComponent(assetId)}`, { method: "DELETE" }, "No se pudo dar de baja la foto");
};

export const guardarConsentAdmin = (
  comercioId: string, body: SocialConsentUpdate,
): Promise<SocialConsentResponse | SocialConsentRevokeResponse> =>
  panelJson(`/admin/content/merchants/${encodeURIComponent(comercioId)}/social-consent`, { method: "PUT", body }, "No se pudo guardar la autorización");

export const historialConsentAdmin = async (comercioId: string): Promise<SocialConsentResponse[]> => {
  const d = await panelJson<{ items?: SocialConsentResponse[] }>(
    `/admin/content/merchants/${encodeURIComponent(comercioId)}/social-consent/history`, {}, "No se pudo cargar el historial");
  return d.items ?? [];
};

/** Sube UNA foto al banco desde el panel. `subirConProgreso` es XHR: da el avance
 *  y conserva el `{codigo, mensaje}` del 409 en `.datos`. */
export function subirAssetAdmin(
  comercioId: string, file: File, meta: MetaSubida, onP?: (pct: number) => void,
): Promise<ContentAssetUploadResponse> {
  return subirConProgreso<ContentAssetUploadResponse>(
    `${API_BASE}/admin/content/merchants/${encodeURIComponent(comercioId)}/assets`,
    "foto", file, getToken(), camposSubida(meta), onP,
  ).catch((ex) => { throw errorDeSubida(ex); });
}

/** La subida lanza `Error` con `status` y `datos`; se normaliza al mismo tipo que el resto. */
function errorDeSubida(ex: unknown): ContentApiError {
  const e = ex as { message?: string; status?: number; datos?: unknown } | null;
  return normalizarError({ message: e?.message, status: e?.status, detail: e?.datos }, "No se pudo subir la foto");
}

/* ─── Banco y autorización: APP DE CAMPO (token del agente) ──────────────── */

const campoH = () => ({ Authorization: `Bearer ${getAgenteToken() ?? ""}` });

async function campoJson<T>(path: string, init: { method?: string; body?: unknown } = {}, porDefecto: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: init.method ?? "GET",
      headers: { ...campoH(), ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}) },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
  } catch (ex) {
    throw normalizarError(ex, "No hay conexión con el servidor");
  }
  if (res.status === 401) { clearAgente(); throw new ContentApiError("Sesión vencida, volvé a entrar", 401); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({} as { detail?: unknown }));
    throw normalizarError({ status: res.status, detail: d.detail }, porDefecto);
  }
  return (await res.json().catch(() => ({}))) as T;
}

export const listarAssetsCampo = (comercioId: string): Promise<ContentAssetListResponse> =>
  campoJson(`/campo/mis-comercios/${encodeURIComponent(comercioId)}/content-assets`, {}, "No se pudieron cargar las fotos para redes");

export function subirAssetCampo(
  comercioId: string, file: File, meta: MetaSubida, onP?: (pct: number) => void,
): Promise<ContentAssetUploadResponse> {
  return subirConProgreso<ContentAssetUploadResponse>(
    `${API_BASE}/campo/mis-comercios/${encodeURIComponent(comercioId)}/content-assets`,
    "foto", file, getAgenteToken(), camposSubida(meta), onP,
  ).catch((ex) => { throw errorDeSubida(ex); });
}

/** La vía queda fija en el backend (`agent_visit`). */
export const guardarConsentCampo = (comercioId: string, granted: boolean, note: string | null): Promise<SocialConsentResponse> =>
  campoJson(`/campo/mis-comercios/${encodeURIComponent(comercioId)}/social-consent`, { method: "PUT", body: { granted, note } }, "No se pudo guardar la autorización");

/* ─── Autorización: COMERCIANTE (Mi comercio) ────────────────────────────── */

async function comercioJson<T>(path: string, init: { method?: string; body?: unknown } = {}, porDefecto: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: init.method ?? "GET",
      headers: {
        Authorization: `Bearer ${getCToken() ?? ""}`,
        ...(init.body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
  } catch (ex) {
    throw normalizarError(ex, "No hay conexión con el servidor");
  }
  if (res.status === 401) { clearComercio(); throw new ContentApiError("Tu sesión venció, volvé a entrar.", 401); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({} as { detail?: unknown }));
    throw normalizarError({ status: res.status, detail: d.detail }, porDefecto);
  }
  return (await res.json().catch(() => ({}))) as T;
}

export const getConsentComercio = (): Promise<SocialConsentResponse> =>
  comercioJson("/comercio/social-consent", {}, "No se pudo cargar tu autorización");

export const guardarConsentComercio = (granted: boolean): Promise<SocialConsentResponse> =>
  comercioJson("/comercio/social-consent", { method: "PUT", body: { granted } }, "No se pudo guardar tu autorización");

/* ─── Piezas, semana y paquete del día: PANEL ────────────────────────────── */

export const getSemana = (start?: string): Promise<ContentWeekResponse> =>
  panelJson(`/admin/content/week${start ? `?start=${encodeURIComponent(start)}` : ""}`, {}, "No se pudo cargar la semana");

export const armarSemana = (weekStart: string | null): Promise<ContentWeekPlanResponse> =>
  panelJson("/admin/content/week/plan", { method: "POST", body: { week_start: weekStart } }, "No se pudo armar la semana");

export const listarPiezas = async (estados: readonly ContentPieceStatus[]): Promise<ContentPieceResponse[]> => {
  const d = await panelJson<{ items?: ContentPieceResponse[] }>(
    `/admin/content/pieces?status=${encodeURIComponent(estados.join(","))}`, {}, "No se pudieron cargar las piezas");
  return d.items ?? [];
};

export const getPieza = (id: string): Promise<ContentPieceResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}`, {}, "No se pudo cargar la pieza");

export const guardarTextosPieza = (id: string, patch: ContentPieceUpdate): Promise<ContentPieceResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}`, { method: "PATCH", body: patch }, "No se pudieron guardar los textos");

export const rearmarPieza = (id: string, removePositions: number[]): Promise<ContentPieceResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}/sources`, { method: "PUT", body: { remove_positions: removePositions } }, "No se pudo rearmar la pieza");

export const aprobarPieza = (id: string): Promise<ContentPieceResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}/approve`, { method: "POST" }, "No se pudo aprobar la pieza");

export const aprobarEnLote = (ids: string[]): Promise<{ approved: string[]; refused: { id: string; motivo: string }[] }> =>
  panelJson("/admin/content/pieces/approve-batch", { method: "POST", body: { ids } }, "No se pudieron aprobar las piezas");

export const saltarPieza = (id: string, body: ContentPieceSkip): Promise<ContentPieceResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}/skip`, { method: "POST", body }, "No se pudo saltar la pieza");

export const reintentarPieza = (id: string): Promise<ContentPieceResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}/retry`, { method: "POST" }, "No se pudo reintentar la pieza");

export const linksDeDescarga = (id: string): Promise<ContentDownloadLinksResponse> =>
  panelJson(`/admin/content/pieces/${encodeURIComponent(id)}/download-links`, {}, "No se pudo preparar la descarga");

export const getPaqueteDelDia = (date?: string): Promise<ContentDayPackageResponse> =>
  panelJson(`/admin/content/today${date ? `?date=${encodeURIComponent(date)}` : ""}`, {}, "No se pudo cargar el paquete del día");

export const reclamarPost = (id: string): Promise<ContentPostResponse> =>
  panelJson(`/admin/content/posts/${encodeURIComponent(id)}/claim`, { method: "POST" }, "No se pudo reclamar la publicación");

export const soltarPost = (id: string): Promise<ContentPostResponse> =>
  panelJson(`/admin/content/posts/${encodeURIComponent(id)}/release`, { method: "POST" }, "No se pudo soltar la publicación");

export const marcarPublicada = (id: string, postUrl: string | null, withoutLink: boolean): Promise<ContentPostResponse> =>
  panelJson(`/admin/content/posts/${encodeURIComponent(id)}/posted`, { method: "POST", body: { post_url: postUrl, without_link: withoutLink } }, "No se pudo marcar como publicada");

export const saltarPost = (id: string, reason: string): Promise<ContentPostResponse> =>
  panelJson(`/admin/content/posts/${encodeURIComponent(id)}/skip`, { method: "POST", body: { reason } }, "No se pudo saltar la red");

export const getEstadoContenido = (): Promise<ContentStatusResponse> =>
  panelJson("/admin/content/status", {}, "No se pudo leer el estado del armado de videos");

/* ─── APIs inyectadas en los componentes (panel vs. campo) ───────────────── */
// El banco del comercio es UN componente que no sabe con qué token habla: el
// padre le pasa estas funciones (mismo patrón que `GaleriaApi`).

export type ConsentApi = {
  /** `via` y `note` sólo importan en el panel; en campo la vía está fija. */
  guardar: (granted: boolean, via: SocialConsentUpdate["via"], note: string | null) => Promise<SocialConsentResponse | SocialConsentRevokeResponse>;
  /** Sin esto no hay «Ver historial» (el agente no lo ve). */
  historial?: () => Promise<SocialConsentResponse[]>;
  /** El agente sólo registra lo que le dijo el dueño en persona: no elige la vía. */
  eligeVia: boolean;
};

export type ContentBankApi = {
  listar: (comercioId: string) => Promise<ContentAssetListResponse>;
  subir: (comercioId: string, file: File, meta: MetaSubida, onP?: (pct: number) => void) => Promise<ContentAssetUploadResponse>;
  consent: (comercioId: string) => ConsentApi;
  /** Sin estas dos (el agente no las tiene) la grilla es de sólo lectura. */
  actualizar?: (assetId: string, patch: ContentAssetUpdate) => Promise<ContentAssetResponse>;
  baja?: (assetId: string) => Promise<void>;
  /** Cuál cola de IndexedDB: las subidas pendientes del panel y las del agente
   *  no se mezclan (cada una necesita SU token). */
  scope: "admin" | "campo";
};

export const apiBancoAdmin: ContentBankApi = {
  scope: "admin",
  listar: listarAssetsAdmin,
  subir: subirAssetAdmin,
  actualizar: actualizarAssetAdmin,
  baja: darDeBajaAssetAdmin,
  consent: (id) => ({
    eligeVia: true,
    guardar: (granted, via, note) => guardarConsentAdmin(id, { granted, via, note }),
    historial: () => historialConsentAdmin(id),
  }),
};

export const apiBancoCampo: ContentBankApi = {
  scope: "campo",
  listar: listarAssetsCampo,
  subir: subirAssetCampo,
  consent: (id) => ({
    eligeVia: false,
    guardar: (granted, _via, note) => guardarConsentCampo(id, granted, note),
  }),
};
