// Credencial de los agentes de URUKU (docs/credencial-agentes.md).
//
// Dos mitades:
//  - PÚBLICA (`/agentes`, `/agentes/<token>`): se lee en el servidor, sin sesión.
//    Nunca trae token, id, email, teléfono ni roles (y la lista, nunca cuántos son).
//  - ADMIN (Equipo › Credencial y la tarjeta para imprimir): con el JWT del admin,
//    por `authFetch`, que ya lanza con el mensaje en español del backend.

import { authFetch } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Público ────────────────────────────────────────────────────────────────

export type AgentePublico = {
  nombre: string | null;
  apellido: string | null;
  ciudad_nombre: string | null;
  ciudad_slug: string | null;
  photo_url: string | null;
  /** ISO: desde cuándo tiene credencial vigente. */
  desde: string | null;
};

/** La lista pública. `null` = el backend no contestó (la pantalla lo dice,
 *  distinto de «todavía no hay agentes»). */
export async function getAgentesPublicos(): Promise<AgentePublico[] | null> {
  try {
    const res = await fetch(`${API}/public/agents`, { next: { revalidate: 60 } });
    if (!res.ok) return null;
    const d = (await res.json()) as { items?: AgentePublico[] };
    return d.items ?? [];
  } catch {
    return null;
  }
}

export type EstadoCredencial = "valid" | "revoked" | "inactive";

export type VerificacionCredencial = {
  status: EstadoCredencial;
  nombre: string | null;
  apellido: string | null;
  ciudad: string | null;
  photo_url: string | null;
  issued_at: string | null;
  /** ISO del momento en que el servidor comprobó (arranca el reloj de la página). */
  checked_at: string;
};

export type ResultadoVerificacion =
  | { tipo: "ok"; datos: VerificacionCredencial }
  | { tipo: "no_existe" }
  | { tipo: "error" };

/** Lo que abre el QR. Sin caché: una credencial dada de baja tiene que verse al instante. */
export async function verificarCredencial(token: string): Promise<ResultadoVerificacion> {
  try {
    const res = await fetch(`${API}/public/agents/${encodeURIComponent(token)}`, { cache: "no-store" });
    if (res.status === 404) return { tipo: "no_existe" };
    if (!res.ok) return { tipo: "error" };
    return { tipo: "ok", datos: (await res.json()) as VerificacionCredencial };
  } catch {
    return { tipo: "error" };
  }
}

/** «Ana Pérez». Si falta alguna de las dos partes, la que haya. */
export function nombreCompleto(nombre: string | null | undefined, apellido: string | null | undefined): string {
  return [nombre, apellido].map((x) => (x ?? "").trim()).filter(Boolean).join(" ");
}

const MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];

/** «octubre 2026», en hora de Bolivia (UTC-4, sin horario de verano). */
export function mesAnio(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const d = new Date(t - 4 * 3600 * 1000);
  return `${MESES[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

// ── Admin ──────────────────────────────────────────────────────────────────

export type CredencialVigente = {
  token: string;
  issued_at: string;
  scan_count: number;
  last_scan_at: string | null;
};

export type CredencialAdmin = {
  credential: CredencialVigente | null;
  photo_url: string | null;
  nombre: string | null;
  apellido: string | null;
  ciudad_nombre: string | null;
  activo: boolean;
};

const JSON_H = { "Content-Type": "application/json" };

export async function getCredencialAdmin(usuarioId: string): Promise<CredencialAdmin> {
  const res = await authFetch(`/admin/agents/${encodeURIComponent(usuarioId)}/credential`);
  return (await res.json()) as CredencialAdmin;
}

/** Emite una credencial nueva; si había una viva la revoca (motivo «reemitida»). */
export async function emitirCredencial(usuarioId: string): Promise<CredencialAdmin> {
  const res = await authFetch(`/admin/agents/${encodeURIComponent(usuarioId)}/credential`, {
    method: "POST", headers: JSON_H, body: "{}",
  });
  return (await res.json()) as CredencialAdmin;
}

export async function revocarCredencial(usuarioId: string, reason: string, cutAccess: boolean): Promise<void> {
  await authFetch(`/admin/agents/${encodeURIComponent(usuarioId)}/credential/revoke`, {
    method: "POST", headers: JSON_H, body: JSON.stringify({ reason, cut_access: cutAccess }),
  });
}

/** Sube la foto del agente (jpg/png/webp, hasta 8 MB). El servidor la re-codifica. */
export async function subirFotoAgente(usuarioId: string, file: File): Promise<string> {
  const fd = new FormData();
  fd.append("foto", file);
  const res = await authFetch(`/admin/agents/${encodeURIComponent(usuarioId)}/photo`, { method: "POST", body: fd });
  return ((await res.json()) as { photo_url: string }).photo_url;
}
