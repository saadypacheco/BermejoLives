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
  /** Clave estable del renglón (`phone:<dígitos>`, `group:<jid>`, `member:<uuid>`). */
  key: string;
  at: string;
};

/** Fotos 1-a-1 de un número que ningún comercio tiene. */
export type UnknownPhone = UnknownBase & {
  kind: "phone";
  /** Dígitos completos: es lo que va en la ruta de `assign`. Sólo para el panel.
   *  `null` cuando el remitente llegó como LID (identificador oculto de WhatsApp)
   *  y todavía no se sabe su número: se ve, pero no se puede asignar. */
  phone: string | null;
  phone_masked: string | null;
  lid?: string | null;
  count: number;
  messages: UnknownMessage[];
};

/** Mensajes de un grupo que no está atado a ningún comercio. */
export type UnknownGroup = UnknownBase & {
  kind: "group";
  group_jid: string;
  group_name?: string | null;
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
  numero: string;
  /** Mensajes `sin_comercio` de los últimos 30 días que se volvieron a procesar. */
  reprocessed: number;
  published: number;
  ignored: number;
};

/** Por qué falló «Es de…», ya traducido a algo que se pueda leer. */
export type AssignErrorKind = "owned_by_other" | "own_number" | "not_found" | "forbidden" | "other";

export class AssignError extends Error {
  constructor(public kind: AssignErrorKind, message: string) {
    super(message);
  }
}

export function statusDe(e: unknown): number | null {
  const s = (e as { status?: unknown } | null)?.status;
  return typeof s === "number" ? s : null;
}

function mensajeDe(e: unknown): string | null {
  const det = (e as { detail?: unknown } | null)?.detail;
  if (det && typeof det === "object" && typeof (det as { mensaje?: unknown }).mensaje === "string") {
    return (det as { mensaje: string }).mensaje;
  }
  return null;
}

function codigoDe(e: unknown): string | null {
  const det = (e as { detail?: unknown } | null)?.detail;
  if (det && typeof det === "object" && typeof (det as { codigo?: unknown }).codigo === "string") {
    return (det as { codigo: string }).codigo;
  }
  return null;
}

/** «Este número es de este comercio»: lo autoriza y reprocesa las fotos que estaban sin dueño. */
export async function assignNumber(phone: string, comercioId: string, label: string): Promise<AssignResult> {
  try {
    const res = await authFetch(`/admin/whatsapp/numbers/${encodeURIComponent(phone)}/assign`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ comercio_id: comercioId, label }),
    });
    return (await res.json()) as AssignResult;
  } catch (e) {
    const st = statusDe(e);
    const cod = codigoDe(e);
    if (st === 409 || cod === "phone_owned_by_other") {
      throw new AssignError("owned_by_other",
        "Ese número ya es de otro comercio. No se movió nada: primero hay que soltarlo desde la ficha del otro.");
    }
    if (st === 400) {
      throw new AssignError("own_number",
        "Es un número de URUKU, no de un comercio. No se puede asignar a ninguno.");
    }
    if (st === 404) throw new AssignError("not_found", "No se encontró el comercio. Buscalo de nuevo.");
    if (st === 403) throw new AssignError("forbidden", "Tu usuario no tiene el permiso de Recepción.");
    throw new AssignError("other", mensajeDe(e) ?? (e instanceof Error ? e.message : "No se pudo asignar"));
  }
}
