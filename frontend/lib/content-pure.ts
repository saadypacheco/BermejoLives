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
export type ContentPillar = "comercio_del_dia" | "ofertas" | "rubro";
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
  rubro: "Repaso de rubro",
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
  comercio_inactivo: "El comercio está de baja",
  asset_removed: "Se quitó una foto",
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

/** ¿Se puede aprobar en lote? Sólo lo que está en verde y nadie tocó (§8.3). En las
 *  piezas v2 además tienen que estar limpios los textos del video y las fotos
 *  marcadas (§16.9); en las v1 esos campos no vienen y no cuentan. */
export function aprobableEnLote(p: {
  status: string; caption_checks: readonly string[]; caption_edited: boolean;
  video_texts_checks?: readonly string[] | null;
  photo_flags_ok?: boolean | null;
  sources?: readonly { photo_flags?: readonly string[] | null }[] | null;
}): boolean {
  return p.status === "ready_for_review" && p.caption_checks.length === 0 && !p.caption_edited
    && motivoNoAprobable(p) === null;
}

/* ─── Textos del video (plantillas v2, §16) ──────────────────────────────── */

/** Las piezas v2 traen `template_version >= 2`. Si el backend todavía no manda ese
 *  campo, `video_texts` con contenido alcanza para reconocerlas. */
export function esPiezaV2(p: { template_version?: number | null; video_texts?: object | null }): boolean {
  if (typeof p.template_version === "number") return p.template_version >= 2;
  return !!p.video_texts;
}

/** ¿La foto tiene alguna marca de Gemini (precio o código a la vista)? */
export function fotoMarcadaPorGemini(flags: readonly string[] | null | undefined): boolean {
  return !!flags && flags.length > 0;
}

/**
 * Por qué una pieza v2 no se puede aprobar todavía (los mismos dos 409 de §16.9),
 * o `null` si no hay nada que lo impida. El backend vuelve a decidir; esto sólo
 * avisa antes de apretar.
 */
export function motivoNoAprobable(p: {
  video_texts_checks?: readonly string[] | null;
  photo_flags_ok?: boolean | null;
  sources?: readonly { photo_flags?: readonly string[] | null }[] | null;
}): string | null {
  if ((p.video_texts_checks ?? []).length > 0) return "Revisá los textos del video: el validador tiene objeciones.";
  const hayMarcadas = (p.sources ?? []).some((s) => fotoMarcadaPorGemini(s.photo_flags));
  if (hayMarcadas && !p.photo_flags_ok) return "Hay fotos marcadas: cambialas o confirmá que están bien.";
  return null;
}

/** De dónde salieron los textos del video (`video_texts_engine`, §16.8). */
export function origenTextosVideo(engine: string | null | undefined): string {
  const e = (engine ?? "").trim();
  if (e.startsWith("gemini:")) return "Propuesto por Gemini";
  if (e === "human") return "Escrito a mano";
  if (e === "template") return "Texto fijo";
  return "";
}

/** En `ofertas` y `rubro` la frase de cada foto es el nombre del comercio: no se edita (§16.5, §17.3). */
export function chipsEditables(pillar: ContentPillar | string): boolean {
  return pillar !== "ofertas" && pillar !== "rubro";
}

/** Los campos del video que escribe o corrige una persona (§16.9). */
export type VideoTextsEditable = {
  kick: string | null;
  title1: string;
  title2: string;
  subtitle: string | null;
  search_term: string;
};
export type CampoVideo = keyof VideoTextsEditable;

export const CAMPO_VIDEO_LABEL: Record<CampoVideo, string> = {
  kick: "Frase de arriba",
  title1: "Título, línea 1",
  title2: "Título, línea 2",
  subtitle: "Subtítulo",
  search_term: "Búsqueda",
};

/** Topes de cada campo (§16.6). `palabras` = [mínimo, máximo]. */
export const VIDEO_LIMITES: Record<CampoVideo | "chip", { max: number; palabras?: readonly [number, number]; obligatorio: boolean }> = {
  kick: { max: 22, obligatorio: false },
  title1: { max: 18, palabras: [1, 4], obligatorio: true },
  title2: { max: 18, palabras: [1, 4], obligatorio: true },
  subtitle: { max: 42, obligatorio: false },
  search_term: { max: 16, palabras: [1, 2], obligatorio: true },
  chip: { max: 30, palabras: [2, 5], obligatorio: false },
};

// Emoji y pictogramas: los mismos rangos que el validador del backend (§6.3).
const RE_EMOJI_VIDEO = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/u;
const RE_ENLACE = /https?:|www\.|@|(?:^|[^\p{L}\d])[\p{L}\d-]+\.(?:com|bo|ar|net|org|store|app|io|me|info|shop|link)(?![\p{L}])/iu;
const RE_CODIGO = /URUKU-[A-Z0-9]{3,}|CONFIRMAR-/i;
const RE_FORMA_CLAVE = /(?:^|[^\p{L}])[A-ZÁÉÍÓÚÑ]{3,}-[A-Z0-9]{4,}(?![\p{L}\d])/u;
const RE_PLATA = /\$|(?:^|[^\p{L}])bs(?![\p{L}])/iu;

/** Lo que no se promete (§6.3). */
const PROMESAS: readonly string[] = [
  "el mejor", "la mejor", "el más barato", "más barato", "te traemos clientes",
  "envío", "envíos", "garantía", "garantizado", "próximamente",
];
const RE_PROMESAS = new RegExp(`(?:^|[^\\p{L}])(${PROMESAS.join("|")})(?![\\p{L}])`, "iu");

/** Voseo y tuteo: palabras completas (§16.6). */
const TONO_PROHIBIDO: ReadonlySet<string> = new Set([
  "vos", "sos", "tenés", "querés", "podés", "sabés", "buscá", "mirá", "escribile", "escribí", "conocé",
  "encontrá", "vení", "pedí", "llamá", "tú", "ti", "tu", "tus", "te", "puedes", "quieres", "tienes", "sabes",
]);
/** `busca` y `encuentra` sólo son tuteo cuando hay un «tu/te» al lado (imperativo). */
const TONO_CON_TU: ReadonlySet<string> = new Set(["busca", "encuentra"]);

function cantidadDeCaracteres(t: string): number {
  return Array.from(t).length;
}
function palabrasDe(t: string): string[] {
  return t.trim().split(/\s+/).filter(Boolean);
}

/** Las objeciones que valen para TODOS los campos del video (§16.6, fila «Todos»). */
function objecionesComunes(texto: string): string[] {
  const o: string[] = [];
  if (/\d/.test(texto)) o.push("no puede tener números");
  if (RE_PLATA.test(texto)) o.push("no puede nombrar plata (Bs, $, US$)");
  if (RE_EMOJI_VIDEO.test(texto)) o.push("no puede tener emoji");
  if (RE_ENLACE.test(texto)) o.push("no puede tener links, @ ni direcciones web");
  if (RE_CODIGO.test(texto) || RE_FORMA_CLAVE.test(texto)) o.push("no puede tener códigos ni claves");
  const promesa = RE_PROMESAS.exec(texto);
  if (promesa) o.push(`promete algo que no se puede («${promesa[1].toLowerCase()}»)`);
  for (const m of texto.matchAll(/(^|[^\p{L}])cuero(?![\p{L}])/giu)) {
    const antes = texto.slice(0, (m.index ?? 0) + m[1].length);
    if (!/(?:^|[^\p{L}])eco\s+$/iu.test(antes)) { o.push("«cuero» sólo puede decirse «eco cuero»"); break; }
  }
  const palabras = texto.toLowerCase().split(/[^\p{L}]+/u).filter(Boolean);
  const tieneTu = palabras.some((w) => w === "tu" || w === "tus" || w === "te");
  const mala = palabras.find((w) => TONO_PROHIBIDO.has(w) || (tieneTu && TONO_CON_TU.has(w)));
  if (mala) o.push(`tiene tuteo o voseo («${mala}»): se escribe de usted`);
  return o;
}

/** Objeciones de un campo, sin el nombre del campo adelante. */
function objecionesDeCampo(clave: CampoVideo | "chip", valor: string | null | undefined): string[] {
  const texto = (valor ?? "").trim();
  const lim = VIDEO_LIMITES[clave];
  if (!texto) return lim.obligatorio ? ["es obligatorio"] : [];
  const o: string[] = [];
  const largo = cantidadDeCaracteres(texto);
  if (largo > lim.max) o.push(`pasa de ${lim.max} caracteres (tiene ${largo})`);
  if (lim.palabras) {
    const n = palabrasDe(texto).length;
    const [min, max] = lim.palabras;
    if (n < min || n > max) o.push(`tiene que tener de ${min} a ${max} palabras`);
  }
  return [...o, ...objecionesComunes(texto)];
}

export type ObjecionesVideo = {
  campos: Partial<Record<CampoVideo, string[]>>;
  /** Una entrada por foto, en el mismo orden que los chips recibidos. */
  chips: string[][];
};

/**
 * Las objeciones de los textos del video, campo por campo: el espejo de
 * `validate_video_texts` del backend (§16.6). Sirve para avisar mientras se
 * escribe; el que manda es el backend (devuelve 400 con la objeción).
 * En `ofertas` y `rubro` los chips no se editan (son el nombre del comercio) y no se validan.
 */
export function validateVideoTextsPorCampo(
  texts: VideoTextsEditable,
  chips: readonly (string | null)[],
  pillar: ContentPillar | string,
): ObjecionesVideo {
  const campos: Partial<Record<CampoVideo, string[]>> = {};
  (Object.keys(CAMPO_VIDEO_LABEL) as CampoVideo[]).forEach((c) => {
    const o = objecionesDeCampo(c, texts[c]);
    if (o.length > 0) campos[c] = o;
  });
  const editables = chipsEditables(pillar);
  return { campos, chips: chips.map((c) => (editables ? objecionesDeCampo("chip", c) : [])) };
}

/** La lista plana («Título, línea 1: pasa de 18 caracteres (tiene 21)»). Vacía = en verde. */
export function validateVideoTexts(
  texts: VideoTextsEditable,
  chips: readonly (string | null)[],
  pillar: ContentPillar | string,
): string[] {
  const r = validateVideoTextsPorCampo(texts, chips, pillar);
  const lista: string[] = [];
  (Object.keys(CAMPO_VIDEO_LABEL) as CampoVideo[]).forEach((c) => {
    for (const o of r.campos[c] ?? []) lista.push(`${CAMPO_VIDEO_LABEL[c]}: ${o}`);
  });
  r.chips.forEach((os, i) => { for (const o of os) lista.push(`Frase de la foto ${i + 1}: ${o}`); });
  return lista;
}

/* ─── Pedir un video a mano e interruptores de costo (§17.4) ─────────────── */

/** Cuántos comercios hacen falta para el video de un rubro (el backend es el que manda). */
export const RUBRO_MIN_COMERCIOS = 4;

export type PiezaOrigen = "selector" | "pedido";

/** Lo mínimo de una pieza que hace falta para ponerle título. */
export type PiezaTitulable = {
  pillar: string;
  pillar_label?: string;
  comercio?: { nombre: string } | null;
  rubro?: { nombre: string; slug?: string } | null;
  ciudad_nombre?: string | null;
};

/** El tipo de pieza en palabras. `rubro` siempre dice «Repaso de rubro», aunque el backend mande otra cosa. */
export function etiquetaDePilar(p: Pick<PiezaTitulable, "pillar" | "pillar_label">): string {
  if (p.pillar === "rubro") return PILLAR_LABEL.rubro;
  return p.pillar_label || etiquetaDe(PILLAR_LABEL, p.pillar);
}

/** Lo que identifica a la pieza: «Zapatillas en Bermejo» (rubro), el nombre del comercio o, sin nada, el tipo. */
export function detalleDePieza(p: PiezaTitulable): string {
  if (p.pillar === "rubro" || p.rubro) {
    const rubro = p.rubro?.nombre?.trim();
    if (rubro) return p.ciudad_nombre ? `${rubro} en ${p.ciudad_nombre}` : rubro;
  }
  return p.comercio?.nombre ?? etiquetaDePilar(p);
}

/** «Repaso de rubro · Zapatillas en Bermejo» / «Comercio del día · Casa Pérez» / «Ofertas de la semana». */
export function tituloDePieza(p: PiezaTitulable): string {
  const etiqueta = etiquetaDePilar(p);
  const detalle = detalleDePieza(p);
  return detalle && detalle !== etiqueta ? `${etiqueta} · ${detalle}` : etiqueta;
}

export const esPiezaPedida = (origin: string | null | undefined): boolean => origin === "pedido";

/** `uruku 1234`, `Uruku-ab12` → `URUKU-1234`: el buscador acepta el código como lo escriba la persona. */
export function normalizarBusquedaComercio(q: string): string {
  const t = q.trim();
  const m = /^uruku[-\s_]?([a-z0-9]{3,8})$/i.exec(t);
  return m ? `URUKU-${m[1].toUpperCase()}` : t;
}

/** La respuesta de `GET …/merchants/{id}/request-check`. */
export type RequestCheck = { consent: boolean; usable_photos: number; ok: boolean; reason: string | null };

/** Lo que se le muestra a quien va a pedir el video de un negocio. */
export function resumenRequestCheck(c: RequestCheck): { tono: "ok" | "error"; texto: string } {
  const fotos = `${c.usable_photos} ${c.usable_photos === 1 ? "foto que sirve" : "fotos que sirven"}`;
  if (c.ok) return { tono: "ok", texto: `Tiene autorización y ${fotos}.` };
  const motivo = (c.reason ?? "").trim();
  if (motivo) return { tono: "error", texto: motivo };
  return { tono: "error", texto: c.consent ? `No se puede pedir todavía: tiene ${fotos}.` : "No tiene la autorización para redes vigente." };
}

export type RubroOpcion = { slug: string; nombre: string; eligible: boolean };

/** Cómo se dibuja un rubro en la lista: si no llega al mínimo de comercios, se deshabilita y lo dice. */
export function opcionDeRubro(r: RubroOpcion): { texto: string; deshabilitada: boolean; ayuda: string | null } {
  return r.eligible
    ? { texto: r.nombre, deshabilitada: false, ayuda: null }
    : { texto: r.nombre, deshabilitada: true, ayuda: `Hay menos de ${RUBRO_MIN_COMERCIOS} comercios con autorización y foto` };
}

export type PedidoDeVideo =
  | { kind: "comercio"; comercio_id: string }
  | { kind: "rubro"; rubro_slug: string; ciudad_slug: string };

/** El body de `POST /admin/content/pieces/request`, o null si todavía falta elegir algo. */
export function armarPedidoDeVideo(
  modo: "comercio" | "rubro",
  e: { comercioId?: string | null; ciudadSlug?: string | null; rubroSlug?: string | null },
): PedidoDeVideo | null {
  if (modo === "comercio") return e.comercioId ? { kind: "comercio", comercio_id: e.comercioId } : null;
  return e.ciudadSlug && e.rubroSlug ? { kind: "rubro", rubro_slug: e.rubroSlug, ciudad_slug: e.ciudadSlug } : null;
}

/** ¿Estos permisos incluyen `permiso`? (`*` = admin de todo). Sólo para mostrar u ocultar: el backend decide. */
export function tienePermiso(permisos: readonly string[], permiso: string): boolean {
  return permisos.includes("*") || permisos.includes(permiso);
}

/** El estado de un interruptor, en palabras (nunca sólo color). */
export function estadoDeInterruptor(enabled: boolean): { texto: string; tono: "ok" | "aviso"; icono: "listo" | "aviso" } {
  return enabled
    ? { texto: "Prendido · tiene costo", tono: "aviso", icono: "aviso" }
    : { texto: "Apagado · costo cero", tono: "ok", icono: "listo" };
}

/** La clave del interruptor de Gemini para los textos del contenido (`GET /admin/cost-switches`). */
export const SWITCH_GEMINI_CONTENT = "gemini_content";

/** ¿Gemini está prendido para el contenido? `null` si el interruptor no vino (no se sabe). */
export function geminiContentPrendido(items: readonly { key: string; enabled: boolean }[]): boolean | null {
  const it = items.find((x) => x.key === SWITCH_GEMINI_CONTENT);
  return it ? it.enabled : null;
}

/** El texto de la confirmación de «Pedir otra propuesta»: dice la verdad según el interruptor. */
export function avisoOtraPropuesta(geminiPrendido: boolean | null, huboTextosPropios: boolean): string {
  if (geminiPrendido === false) {
    return "Gemini está apagado: se vuelven a poner los textos fijos y se pisan las frases que escribiste. ¿Seguir?";
  }
  return "¿Pedir otra propuesta a Gemini? Se reemplazan los textos del video"
    + (huboTextosPropios ? " (incluido lo que escribiste vos)" : "")
    + " y el video se vuelve a armar: tarda unos minutos.";
}

/** La insignia «sin Gemini» del panel: falta la key o el interruptor está apagado; `null` si Gemini trabaja. */
export function insigniaSinGemini(geminiConfigurado: boolean, geminiPrendido: boolean | null): string | null {
  if (!geminiConfigurado) return "Sin Gemini: los textos salen de la plantilla fija";
  if (geminiPrendido === false) return "Gemini apagado · costo cero";
  return null;
}

/** Prender manda la casilla; apagar nunca pide confirmación. */
export function bodyDeInterruptor(enabled: boolean, entiendeCosto: boolean): { enabled: boolean; confirm_cost: boolean } {
  return { enabled, confirm_cost: enabled ? entiendeCosto : false };
}
