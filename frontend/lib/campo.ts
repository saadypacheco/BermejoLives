// Cliente del "modo agente de campo" (alta rápida de comercios).
import { subirConProgreso } from "@/lib/upload";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_agente_token";

export function getAgenteToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function clearAgente() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function agenteLogin(email: string, password: string): Promise<void> {
  const res = await fetch(`${API}/auth/campo/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
}

export async function transcribirAudio(blob: Blob): Promise<string> {
  const fd = new FormData();
  fd.append("audio", blob, "qvende.webm");
  const res = await fetch(`${API}/campo/transcribir`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: fd,
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo transcribir");
  }
  return (await res.json()).texto as string;
}

export async function sugerirRubros(descripcion: string, rubros: { slug: string; nombre: string }[]): Promise<string[]> {
  const res = await fetch(`${API}/campo/sugerir-rubros`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: JSON.stringify({ descripcion, rubros }),
  });
  if (!res.ok) return [];
  return (await res.json()).rubro_slugs as string[];
}

export type AltaCampoResult = { ok: boolean; comercio: { id: string; nombre: string; slug: string; ciudad: string; foto: boolean; gps: boolean } };

// ---- Galería (fotos/videos) del comercio, lado agente ----
export type FotoGaleria = { id: string; url: string; thumb_url: string | null; orden?: number };
export type VideoGaleria = { id: string; url: string; duracion_seg: number | null; orden?: number };

const galH = () => ({ Authorization: `Bearer ${getAgenteToken() ?? ""}` });
export const listarFotosCampo = (cid: string): Promise<FotoGaleria[]> =>
  fetch(`${API}/campo/mis-comercios/${cid}/fotos`, { headers: galH() }).then((r) => r.json()).then((d) => d.items ?? []);
export const listarVideosCampo = (cid: string): Promise<VideoGaleria[]> =>
  fetch(`${API}/campo/mis-comercios/${cid}/videos`, { headers: galH() }).then((r) => r.json()).then((d) => d.items ?? []);
export const borrarFotoCampo = (cid: string, id: string): Promise<void> =>
  fetch(`${API}/campo/mis-comercios/${cid}/fotos/${id}`, { method: "DELETE", headers: galH() }).then(() => undefined);
export const borrarVideoCampo = (cid: string, id: string): Promise<void> =>
  fetch(`${API}/campo/mis-comercios/${cid}/videos/${id}`, { method: "DELETE", headers: galH() }).then(() => undefined);
export const subirFotoCampo = (cid: string, file: File, onP?: (p: number) => void): Promise<FotoGaleria> =>
  subirConProgreso<{ foto: FotoGaleria }>(`${API}/campo/mis-comercios/${cid}/fotos`, "foto", file, getAgenteToken(), {}, onP).then((d) => d.foto);
export const subirVideoCampo = (cid: string, file: File, dur: number | null, onP?: (p: number) => void): Promise<VideoGaleria> =>
  subirConProgreso<{ video: VideoGaleria }>(`${API}/campo/mis-comercios/${cid}/videos`, "video", file, getAgenteToken(), dur != null ? { duracion_seg: String(dur) } : {}, onP).then((d) => d.video);

export async function altaComercioCampo(form: FormData): Promise<AltaCampoResult> {
  const res = await fetch(`${API}/campo/comercio`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: form, // multipart; el browser pone el Content-Type con boundary
  });
  if (res.status === 401) {
    clearAgente();
    throw new Error("Sesión vencida, volvé a entrar");
  }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo guardar");
  }
  return res.json();
}

export type ComercioAgente = {
  id: string; slug: string; nombre: string; whatsapp: string; modalidad: string | null;
  direccion: string | null; portada_url: string | null; verificado: boolean; created_at: string;
  rubros?: { nombre: string; slug: string } | null;
};

/** Comercios que este agente dio de alta, para que vea su propio recorrido. */
export async function misComercios(): Promise<ComercioAgente[]> {
  const res = await fetch(`${API}/campo/mis-comercios`, {
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
  });
  if (res.status === 401) {
    clearAgente();
    throw new Error("Sesión vencida, volvé a entrar");
  }
  if (!res.ok) throw new Error("No se pudo cargar el listado");
  return (await res.json()).items as ComercioAgente[];
}

export type EditarComercioBody = {
  nombre?: string; whatsapp?: string; modalidad?: string; direccion?: string; rubro_slugs?: string[];
};

/** Edita un comercio que este agente cargó (no puede tocar los de otro agente). */
export async function editarComercioAgente(id: string, body: EditarComercioBody): Promise<void> {
  const res = await fetch(`${API}/campo/mis-comercios/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo guardar");
  }
}

/** Re-sube la foto de un comercio que este agente cargó. Devuelve la nueva URL. */
export async function actualizarFotoComercioAgente(id: string, foto: File): Promise<string | null> {
  const form = new FormData();
  form.append("foto", foto);
  const res = await fetch(`${API}/campo/mis-comercios/${id}/foto`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: form,
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo actualizar la foto");
  }
  const data = await res.json();
  return data.comercio?.portada_url ?? null;
}

/** Baja lógica (activo=false) — nunca se borra el registro real. */
export async function eliminarComercioAgente(id: string): Promise<void> {
  const res = await fetch(`${API}/campo/mis-comercios/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) throw new Error("No se pudo eliminar");
}

/** Registra un click de contacto (WhatsApp, teléfono, etc.) para un comercio. */
export async function registrarLead(comercio_id: string, tipo: "whatsapp" | "telefono" | "email" | "web" | "vista" = "whatsapp"): Promise<void> {
  // Fire-and-forget: no bloqueamos la navegación del usuario
  fetch(`${API}/lead`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ comercio_id, tipo }),
  }).catch(() => undefined);
}

/** Loguea una búsqueda para los KPIs (qué se busca / qué no da / a quién encontró). Fire-and-forget. */
export function logBusqueda(query: string, resultados: number, comercios?: string[]): void {
  if (!query || query.trim().length < 2) return;
  fetch(`${API}/busquedas/log`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: query.trim(), resultados, comercios: comercios?.slice(0, 10) }),
  }).catch(() => undefined);
}

/** Deja un reclamo público (sobre un comercio, o sobre la plataforma si comercio_id es undefined). */
export async function crearReclamo(body: { nombre?: string; contacto?: string; comercio_id?: string; mensaje: string }): Promise<void> {
  const res = await fetch(`${API}/reclamos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("No se pudo enviar el reclamo");
}
