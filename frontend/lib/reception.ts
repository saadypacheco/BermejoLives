// Cliente de Recepción (docs/grupos-por-comercio.md §7.2, entrega E1).
//
// Todo requiere el permiso `whatsapp` del panel. Las miniaturas son PRIVADAS: viven
// en un disco del backend que no se sirve por /fotos, así que se piden con el token
// del panel y se muestran como `blob:` URL. Nunca un <img src> directo a la API.
import { authFetch } from "@/lib/api";

/** Un mensaje (casi siempre una foto) de alguien sin dueño. */
export type UnknownMessage = {
  wa_message_id: string;
  at: string;
  body: string | null;
  /** Hay foto guardada para pedir a `/inbox/{id}/media` (puede estar purgada → 404). */
  has_media: boolean;
};

type UnknownBase = {
  /** Clave estable y OPACA del renglón (sólo sirve de `key` de React: no se parsea). */
  key: string;
  at: string;
};

/** Fotos 1-a-1 de un número que ningún comercio tiene. El teléfono completo nunca llega al panel. */
export type UnknownPhone = UnknownBase & {
  kind: "phone";
  phone_masked: string | null;
  /** `false` cuando WhatsApp oculta el número (LID): se ve, pero no se puede asignar. */
  assignable: boolean;
  count: number;
  messages: UnknownMessage[];
};

/** Mensajes de un grupo que no está atado a ningún comercio. */
export type UnknownGroup = UnknownBase & {
  kind: "group";
  group_jid: string;
  count: number;
  messages: UnknownMessage[];
};

/** Alguien entró a la comunidad de comercios y no se supo de quién es (E2). */
export type UnknownCommunityJoin = UnknownBase & {
  kind: "community_join";
  phone_masked: string | null;
  lid: string | null;
  community: { id: string; name: string };
  candidates: { comercio_id: string; nombre: string; why: string }[];
};

export type Unknown = UnknownPhone | UnknownGroup | UnknownCommunityJoin;

export async function getUnknown(days = 30): Promise<Unknown[]> {
  const res = await authFetch(`/admin/whatsapp/unknown?days=${days}`);
  const d = (await res.json().catch(() => ({}))) as { items?: Unknown[] };
  return d.items ?? [];
}

/** La foto privada como Blob. Devuelve `null` si no hay o ya se purgó (404). */
export async function getInboxMedia(waMessageId: string): Promise<Blob | null> {
  try {
    const res = await authFetch(`/admin/whatsapp/inbox/${encodeURIComponent(waMessageId)}/media`);
    return await res.blob();
  } catch (e) {
    if (statusDe(e) === 404) return null;
    throw e;
  }
}

export type AssignResult = {
  /** Sólo al asignar un número (ya enmascarado por el backend). */
  numero_masked?: string;
  /** Mensajes `sin_comercio` de los últimos 30 días que se volvieron a procesar. */
  reprocessed: number;
  /** Lo reprocesado siempre queda pendiente de moderación, aunque el contador diga "published". */
  published: number;
  ignored: number;
};

/** Por qué falló «Es de…», ya traducido a algo que se pueda leer. */
export type AssignErrorKind = "owned_by_other" | "not_assignable" | "not_found" | "forbidden" | "invalid" | "other";

export class AssignError extends Error {
  constructor(public kind: AssignErrorKind, message: string) {
    super(message);
  }
}

export function statusDe(e: unknown): number | null {
  const s = (e as { status?: unknown } | null)?.status;
  return typeof s === "number" ? s : null;
}

function detalleDe(e: unknown, campo: "codigo" | "mensaje"): string | null {
  const det = (e as { detail?: unknown } | null)?.detail;
  if (det && typeof det === "object") {
    const v = (det as Record<string, unknown>)[campo];
    if (typeof v === "string" && v) return v;
  }
  return null;
}

/** Texto por código, para cuando el backend no manda `mensaje`. */
const TEXTO_POR_CODIGO: Record<string, string> = {
  own_number: "Es un número de URUKU",
  invalid_number: "El número no es válido",
  lid_not_assignable: "WhatsApp oculta este número: todavía no se puede asignar",
  explorer_message: "Es del explorador: sus fotos se publican con código",
  phone_owned_by_other:
    "Ese número ya es de otro comercio. No se movió nada: primero hay que soltarlo desde la ficha del otro.",
  group_owned_by_other:
    "Ese grupo ya es de otro comercio. No se movió nada: primero hay que soltarlo desde la ficha del otro.",
};

function traducir(e: unknown): AssignError {
  const st = statusDe(e);
  const cod = detalleDe(e, "codigo");
  const msg = detalleDe(e, "mensaje") ?? (cod ? TEXTO_POR_CODIGO[cod] : undefined);
  if (st === 409 || cod === "phone_owned_by_other" || cod === "group_owned_by_other") {
    return new AssignError("owned_by_other", msg ?? "Ya es de otro comercio. No se movió nada.");
  }
  if (st === 400) {
    const kind: AssignErrorKind = cod === "invalid_number" ? "invalid" : "not_assignable";
    return new AssignError(kind, msg ?? "No se puede asignar.");
  }
  if (st === 404) return new AssignError("not_found", msg ?? "No se encontró el comercio o el mensaje. Actualizá la lista.");
  if (st === 403) return new AssignError("forbidden", "Tu usuario no tiene el permiso de Recepción.");
  if (st === 422) return new AssignError("invalid", msg ?? "Los datos no son válidos. Revisá el nombre de «Quién es».");
  return new AssignError("other", msg ?? (e instanceof Error ? e.message : "No se pudo asignar"));
}

async function postAssign(ruta: string, cuerpo: Record<string, string>): Promise<AssignResult> {
  try {
    const res = await authFetch(ruta, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    return (await res.json()) as AssignResult;
  } catch (e) {
    throw traducir(e);
  }
}

/**
 * «Este número es de este comercio». El número NUNCA viaja al panel: se identifica
 * por el mensaje más reciente del renglón y el backend resuelve el teléfono.
 */
export function assignNumber(waMessageId: string, comercioId: string, label: string): Promise<AssignResult> {
  return postAssign(`/admin/whatsapp/inbox/${encodeURIComponent(waMessageId)}/assign`,
    { comercio_id: comercioId, label });
}

/** «Este grupo es de este comercio»: lo ata y reprocesa lo que estaba sin dueño. */
export function assignGroup(groupJid: string, comercioId: string): Promise<AssignResult> {
  return postAssign(`/admin/whatsapp/groups/${encodeURIComponent(groupJid)}/assign`,
    { comercio_id: comercioId });
}
