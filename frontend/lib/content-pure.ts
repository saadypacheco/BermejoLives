// Funciones PURAS del Banco de contenido, del Contenido para redes y del Cuidado
// de suscriptores (docs/contenido-redes-tecnico.md §9, §10.2).
//
// Acá no hay red, ni navegador, ni React: sólo lo que se puede probar con
// `npm test` (tests/content.test.ts). Por eso los imports son RELATIVOS (el
// compilador de los tests no conoce el alias `@/`) y los tipos que comparten
// estas funciones con `lib/content.ts` se declaran acá y allá se re-exportan.

import { linkWhatsapp, whatsappValido } from "./ficha-whatsapp";

/* ─── Tipos que se comparten (los schemas completos están en lib/content.ts) ─ */

export type ContentNetwork = "tiktok" | "instagram" | "facebook" | "wa_channel";
export type ContentPieceStatus =
  | "queued" | "rendering" | "ready_for_review" | "approved" | "published" | "skipped" | "failed";
export type ContentPostStatus = "pending" | "claimed" | "posted" | "skipped";
export type ContentPillar = "comercio_del_dia" | "ofertas";
export type ConsentVia =
  | "agent_signup" | "agent_visit" | "admin" | "merchant_panel" | "whatsapp_reply" | "subscription";

/* ─── Etiquetas ──────────────────────────────────────────────────────────── */
// El backend manda `status_label`, `network_label` y `pillar_label`; estas son
// el respaldo para cuando falta o para lo que arma el front solo.

export const NETWORK_LABEL: Record<ContentNetwork, string> = {
  tiktok: "TikTok",
  instagram: "Instagram",
  facebook: "Facebook",
  wa_channel: "Canal de WhatsApp",
};

export const NETWORKS: readonly ContentNetwork[] = ["tiktok", "instagram", "facebook", "wa_channel"];

export const PIECE_STATUS_LABEL: Record<ContentPieceStatus, string> = {
  queued: "En cola",
  rendering: "Armando el video",
  ready_for_review: "Para revisar",
  approved: "Aprobada",
  published: "Publicada",
  skipped: "Salteada",
  failed: "Con problemas",
};

export const POST_STATUS_LABEL: Record<ContentPostStatus, string> = {
  pending: "Pendiente",
  claimed: "Publicándola",
  posted: "Publicada",
  skipped: "Salteada",
};

export const PILLAR_LABEL: Record<ContentPillar, string> = {
  comercio_del_dia: "Comercio del día",
  ofertas: "Ofertas de la semana",
};

export const CONSENT_VIA_LABEL: Record<ConsentVia, string> = {
  agent_signup: "en el alta",
  agent_visit: "en una visita",
  admin: "registrada por URUKU",
  merchant_panel: "desde Mi comercio",
  whatsapp_reply: "por WhatsApp",
  subscription: "al suscribirse",
};

export const SKIP_REASON_LABEL: Record<string, string> = {
  bad_photos: "Fotos malas",
  merchant_asked: "El comercio lo pidió",
  consent_revoked: "Retiró la autorización",
  unpaid: "No pagó",
  other: "Otro motivo",
};

export const SUBSCRIPTION_STATE_LABEL: Record<string, string> = {
  al_dia: "Al día",
  por_vencer: "Por vencer",
  vencido: "Vencido",
  cortesia: "De cortesía",
  suspendido: "Suspendido",
  sin_plan: "Sin plan",
};

/** Un valor desconocido (el backend puede sumar estados) no rompe la pantalla:
 *  se muestra tal cual. */
export function etiquetaDe(mapa: Record<string, string>, clave: string | null | undefined): string {
  if (!clave) return "";
  return mapa[clave] ?? clave;
}

export function redLabel(n: string): string {
  return etiquetaDe(NETWORK_LABEL, n);
}

/* ─── Textos de las piezas ───────────────────────────────────────────────── */

/** Tope de caracteres de cada texto (los mismos que valida el backend, §6.3). */
export const CAPTION_MAX = { caption_tiktok: 300, caption_ig: 600, caption_channel: 400 } as const;
export type CaptionCampo = keyof typeof CAPTION_MAX;

export const CAPTION_LABEL: Record<CaptionCampo, string> = {
  caption_tiktok: "TikTok",
  caption_ig: "Instagram y Facebook",
  caption_channel: "Canal de WhatsApp",
};

/** «212/300», y si se pasó, lo dice con palabras (no sólo con el color). */
export function contadorTexto(texto: string, max: number): { texto: string; pasado: boolean } {
  const n = texto.length;
  return { texto: `${n}/${max}`, pasado: n > max };
}

/** `#Bermejo` y `bermejo` son lo mismo para la lista de permitidos. */
export function normalizarHashtag(h: string): string {
  const limpio = h.trim().replace(/^#+/, "");
  return limpio ? `#${limpio}` : "";
}

/** Los hashtags que se pueden sumar: los permitidos que todavía no están. */
export function hashtagsDisponibles(permitidos: readonly string[], elegidos: readonly string[]): string[] {
  const ya = new Set(elegidos.map((h) => normalizarHashtag(h).toLowerCase()));
  return permitidos.filter((h) => !ya.has(normalizarHashtag(h).toLowerCase()));
}

/* ─── Links de las redes ─────────────────────────────────────────────────── */

/** Los hosts válidos de cada red (§8.3). Se compara el host ENTERO (o un
 *  subdominio suyo): `tiktok.com.malo.com` y `eviltiktok.com` no pasan. */
const HOSTS_POR_RED: Record<ContentNetwork, readonly string[]> = {
  tiktok: ["tiktok.com", "vm.tiktok.com"],
  instagram: ["instagram.com"],
  facebook: ["facebook.com", "fb.watch", "m.facebook.com"],
  wa_channel: ["whatsapp.com"],
};

export type ResultadoLink = { ok: true; url: string } | { ok: false; motivo: string };

function hostDeRed(host: string, validos: readonly string[]): boolean {
  const h = host.toLowerCase();
  return validos.some((v) => h === v || h.endsWith(`.${v}`));
}

/**
 * ¿El link que pegó la persona es de la red que está marcando? Se chequea acá
 * para avisar al instante; igual lo vuelve a chequear el backend.
 *
 * Sólo https (el backend lo exige en `post_url`). El canal de WhatsApp además
 * tiene que ser `whatsapp.com/channel/…`.
 */
export function validarLinkDeRed(red: ContentNetwork, link: string): ResultadoLink {
  const crudo = link.trim();
  if (!crudo) return { ok: false, motivo: "Pegá el link o marcá que salió sin link" };
  let u: URL;
  try { u = new URL(crudo); } catch { return { ok: false, motivo: `Ese link no es de ${redLabel(red)}` }; }
  if (u.protocol !== "https:") return { ok: false, motivo: "El link tiene que empezar con https://" };
  if (!hostDeRed(u.hostname, HOSTS_POR_RED[red] ?? [])) return { ok: false, motivo: `Ese link no es de ${redLabel(red)}` };
  if (red === "wa_channel" && !u.pathname.toLowerCase().startsWith("/channel/")) {
    return { ok: false, motivo: `Ese link no es de ${redLabel(red)}` };
  }
  return { ok: true, url: u.toString() };
}

/* ─── URLs de la API ─────────────────────────────────────────────────────── */

export const API_BASE: string = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Las URLs firmadas y las rutas públicas que devuelve el backend son RELATIVAS
 * (`/content/files/…`): el front les antepone la base de la API (§4.2). Sin
 * barras de más ni de menos, y si ya vienen completas se dejan como están.
 */
export function urlApi(rel: string, base: string = API_BASE): string {
  if (/^https?:\/\//i.test(rel)) return rel;
  return `${base.replace(/\/+$/, "")}/${rel.replace(/^\/+/, "")}`;
}

/** Como `urlApi` pero tolera `null` (una portada que todavía no existe). */
export function urlApiOpt(rel: string | null | undefined, base: string = API_BASE): string | null {
  return rel ? urlApi(rel, base) : null;
}

/* ─── WhatsApp de las tareas ─────────────────────────────────────────────── */

/**
 * El link `wa.me` de un mensaje a un comerciante: abre el chat con el texto ya
 * escrito. NUNCA se manda nada solo: lo envía la persona desde su WhatsApp.
 * Si el número no sirve (menos de 8 dígitos o vacío), no hay link: la pantalla
 * ofrece «Copiar texto» en su lugar (§8.4).
 */
export function linkWhatsappTarea(whatsapp: string | null | undefined, texto: string | null | undefined): string | null {
  const t = (texto ?? "").trim();
  if (!t || !whatsappValido(whatsapp)) return null;
  return linkWhatsapp(whatsapp as string, t);
}

/* ─── Fechas (Bolivia, UTC-4 sin horario de verano) ──────────────────────── */

const DIAS_CORTOS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
const BOLIVIA_OFFSET_MS = 4 * 3600 * 1000;

function dosDigitos(n: number): string {
  return String(n).padStart(2, "0");
}

/** Parte `AAAA-MM-DD` sin pasar por zonas horarias. */
function partesFecha(iso: string): { y: number; m: number; d: number } | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? { y: Number(m[1]), m: Number(m[2]), d: Number(m[3]) } : null;
}

/** «04/11» de `2026-11-04`. */
export function fechaCorta(iso: string): string {
  const p = partesFecha(iso);
  return p ? `${dosDigitos(p.d)}/${dosDigitos(p.m)}` : iso;
}

/** «mié 04/11» de `2026-11-04`. */
export function fechaConDia(iso: string): string {
  const p = partesFecha(iso);
  if (!p) return iso;
  const dia = new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay();
  return `${DIAS_CORTOS[dia]} ${dosDigitos(p.d)}/${dosDigitos(p.m)}`;
}

/** Un instante (ISO con zona) llevado a la hora de Bolivia. */
function enBolivia(iso: string): Date | null {
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? null : new Date(ms - BOLIVIA_OFFSET_MS);
}

/** «03/01/2027» (hora de Bolivia). */
export function fechaBo(iso: string | null | undefined): string {
  const d = iso ? enBolivia(iso) : null;
  if (!d) return "";
  return `${dosDigitos(d.getUTCDate())}/${dosDigitos(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`;
}

/** «12/10» (hora de Bolivia). */
export function fechaCortaBo(iso: string | null | undefined): string {
  const d = iso ? enBolivia(iso) : null;
  if (!d) return "";
  return `${dosDigitos(d.getUTCDate())}/${dosDigitos(d.getUTCMonth() + 1)}`;
}

/** «19:04» (hora de Bolivia). */
export function horaBo(iso: string | null | undefined): string {
  const d = iso ? enBolivia(iso) : null;
  if (!d) return "";
  return `${dosDigitos(d.getUTCHours())}:${dosDigitos(d.getUTCMinutes())}`;
}

/** Minutos enteros entre un instante y `ahora` (nunca negativo). */
export function minutosDesde(iso: string | null | undefined, ahora: number = Date.now()): number {
  const ms = iso ? Date.parse(iso) : NaN;
  if (Number.isNaN(ms)) return 0;
  return Math.max(0, Math.floor((ahora - ms) / 60000));
}

/** Minutos que le quedan a un reclamo (0 si ya venció o no hay fecha). */
export function minutosRestantes(iso: string | null | undefined, ahora: number = Date.now()): number {
  const ms = iso ? Date.parse(iso) : NaN;
  if (Number.isNaN(ms)) return 0;
  return Math.max(0, Math.ceil((ms - ahora) / 60000));
}

/** El lunes (`AAAA-MM-DD`) de la semana que contiene a esa fecha. */
export function lunesDe(iso: string): string {
  const p = partesFecha(iso);
  if (!p) return iso;
  const d = new Date(Date.UTC(p.y, p.m - 1, p.d));
  const atras = (d.getUTCDay() + 6) % 7;   // lunes = 0
  d.setUTCDate(d.getUTCDate() - atras);
  return `${d.getUTCFullYear()}-${dosDigitos(d.getUTCMonth() + 1)}-${dosDigitos(d.getUTCDate())}`;
}

/** Suma (o resta) días a una fecha `AAAA-MM-DD`. */
export function sumarDias(iso: string, dias: number): string {
  const p = partesFecha(iso);
  if (!p) return iso;
  const d = new Date(Date.UTC(p.y, p.m - 1, p.d));
  d.setUTCDate(d.getUTCDate() + dias);
  return `${d.getUTCFullYear()}-${dosDigitos(d.getUTCMonth() + 1)}-${dosDigitos(d.getUTCDate())}`;
}

/** Hoy en Bolivia como `AAAA-MM-DD`. */
export function hoyBolivia(ahora: number = Date.now()): string {
  const d = new Date(ahora - BOLIVIA_OFFSET_MS);
  return `${d.getUTCFullYear()}-${dosDigitos(d.getUTCMonth() + 1)}-${dosDigitos(d.getUTCDate())}`;
}

/* ─── Subida de fotos al banco ───────────────────────────────────────────── */

export type MetaSubida = {
  source_sha256: string | null;
  /** `File.lastModified` en milisegundos: lo que informa el teléfono. */
  taken_at_ms: number | null;
  show_in_ficha: boolean;
  has_people: boolean;
  people_ok: boolean | null;
};

/** Los campos de formulario de `ContentAssetCreate` (§8.2). Los vacíos no se mandan. */
export function camposSubida(meta: MetaSubida): Record<string, string> {
  const c: Record<string, string> = {
    show_in_ficha: String(meta.show_in_ficha),
    has_people: String(meta.has_people),
  };
  if (meta.source_sha256) c.source_sha256 = meta.source_sha256;
  if (meta.taken_at_ms && meta.taken_at_ms > 0) c.taken_at = new Date(meta.taken_at_ms).toISOString();
  if (meta.people_ok !== null) c.people_ok = String(meta.people_ok);
  return c;
}

/** Clave de una foto en la cola del teléfono: el mismo archivo para el mismo
 *  comercio es UNA entrada, así encolar dos veces no la duplica. */
export function claveCola(comercioId: string, sha256: string): string {
  return `${comercioId}:${sha256}`;
}

/** El hexadecimal de un resumen SHA-256 (de `crypto.subtle.digest`). */
export function hexDe(bytes: ArrayBuffer): string {
  return Array.from(new Uint8Array(bytes), (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Lo que sabemos de un error de subida, sin depender del tipo exacto. */
export type ErrorConDatos = { status?: number; datos?: unknown; message?: string };

/** El `codigo` de un `detail = {codigo, mensaje}` (§8), si lo trae. */
export function codigoDeError(ex: unknown): string | null {
  const e = ex as ErrorConDatos | null;
  const d = e?.datos as { codigo?: unknown } | undefined;
  return typeof d?.codigo === "string" ? d.codigo : null;
}

/** ¿Falló por falta de señal (y entonces conviene dejarla en la cola del
 *  teléfono) y no por otra cosa? Un 4xx o 5xx del servidor NO es falta de señal. */
export function esErrorDeRed(ex: unknown, online: boolean = true): boolean {
  if (!online) return true;
  const e = ex as ErrorConDatos | null;
  if (typeof e?.status === "number" && e.status > 0) return false;
  return ex instanceof TypeError || /fetch|network|failed|load|timeout|conexi|red\b/i.test(String((ex as Error | null)?.message ?? ex));
}

/** El 507 (disco lleno) y el 503 (banco apagado) frenan TODA la tanda: no tiene
 *  sentido intentar las demás fotos. */
export function frenaLaTanda(ex: unknown): boolean {
  const s = (ex as ErrorConDatos | null)?.status;
  return s === 507 || s === 503 || s === 401 || s === 403;
}

/** Un mensaje claro para el error de una subida. */
export function mensajeDeSubida(ex: unknown): string {
  const e = ex as ErrorConDatos | null;
  const s = e?.status;
  if (s === 507) return "El banco de contenido llegó a su tope de espacio. Avisale al admin.";
  if (s === 413) return "La foto supera los 15 MB";
  if (s === 503) return "El banco de contenido no está configurado";
  if (s === 401) return "Se venció la sesión. Entrá de nuevo.";
  if (s === 403) return "No tenés permiso para subir fotos al banco";
  if (codigoDeError(ex) === "people_not_confirmed") return "Confirmá que las personas de la foto aceptaron aparecer";
  const m = (e?.message ?? "").trim();
  return m || "No se pudo subir la foto";
}

/* ─── Semana ─────────────────────────────────────────────────────────────── */

/** Por qué un lugar del calendario quedó vacío (`slots_left_empty[].reason`).
 *  Los códigos conocidos son pocos; lo desconocido se muestra como viene. */
export function motivoLugarVacio(reason: string): string {
  switch (reason) {
    case "not_enough_offers": return "no hay 4 ofertas que sirvan";
    case "no_candidates": return "no hay comercios autorizados con piezas pendientes";
    case "no_photos": return "faltan fotos que sirvan";
    default: return reason;
  }
}

/** «Se armaron 4 piezas. Jueves quedó vacío: no hay 4 ofertas que sirvan». */
export function resumenDePlan(
  creadas: number,
  vacios: readonly { date: string; pillar: string; reason: string }[],
): string {
  const base = creadas === 0
    ? "No se armó ninguna pieza nueva."
    : creadas === 1 ? "Se armó 1 pieza." : `Se armaron ${creadas} piezas.`;
  if (vacios.length === 0) return base;
  const partes = vacios.map((v) => `${fechaConDia(v.date)} quedó vacío: ${motivoLugarVacio(v.reason)}`);
  return `${base} ${partes.join(". ")}.`;
}

/* ─── Piezas ─────────────────────────────────────────────────────────────── */

/** Los estados que siguen cambiando solos en el servidor: mientras haya alguno,
 *  la pantalla de Revisión pregunta cada 20 s. */
export function piezaEnMovimiento(status: string): boolean {
  return status === "queued" || status === "rendering";
}

/** ¿Se puede aprobar en lote? Sólo lo que está en verde y nadie tocó (§8.3). */
export function aprobableEnLote(p: { status: string; caption_checks: readonly string[]; caption_edited: boolean }): boolean {
  return p.status === "ready_for_review" && p.caption_checks.length === 0 && !p.caption_edited;
}
