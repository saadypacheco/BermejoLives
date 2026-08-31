// Cliente del "modo agente de campo" (alta rápida de comercios).
import { postFormData, subirConProgreso } from "@/lib/upload";
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
  // XHR y no fetch: Safari de iOS con service worker manda el FormData sin
  // cuerpo. Ver lib/upload.ts.
  const d = await postFormData<{ texto: string }>(
    `${API}/campo/transcribir`, fd, getAgenteToken());
  return d.texto;
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

export type AltaCampoResult = {
  ok: boolean;
  comercio: {
    id: string; nombre: string; slug: string; ciudad: string; foto: boolean; gps: boolean;
    // Código del local, ya formateado como 'URUKU-K7M2'. Se le deja al dueño en
    // papel: con eso publica por WhatsApp sin número propio, cuenta ni pago.
    codigo?: string | null;
    codigo_formateado?: string | null;
  };
};

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

// ---- Lugares (mercados / galerías / paseos: contenedores de puestos) ----
export type Lugar = { id: string; nombre: string; tipo: string; lat: number | null; lng: number | null; ciudad_id?: string | null; n_comercios?: number; portada_url?: string | null; portada_thumb_url?: string | null; video_url?: string | null };

export async function editarLugar(id: string, body: { nombre?: string; tipo?: string }): Promise<Lugar> {
  const res = await fetch(`${API}/campo/lugares/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? "No se pudo editar"); }
  return (await res.json()).lugar as Lugar;
}

export async function subirPortadaLugar(id: string, foto: File): Promise<Lugar> {
  const fd = new FormData(); fd.append("foto", foto);
  const d = await postFormData<{ lugar: Lugar }>(
    `${API}/campo/lugares/${id}/portada`, fd, getAgenteToken());
  return d.lugar;
}

export async function subirVideoLugar(id: string, video: File): Promise<Lugar> {
  const fd = new FormData(); fd.append("video", video);
  const d = await postFormData<{ lugar: Lugar }>(
    `${API}/campo/lugares/${id}/video`, fd, getAgenteToken());
  return d.lugar;
}

export async function listarLugares(ciudadSlug = "bermejo"): Promise<Lugar[]> {
  const res = await fetch(`${API}/campo/lugares?ciudad_slug=${encodeURIComponent(ciudadSlug)}`, { headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` } });
  if (!res.ok) return [];
  const items = (await res.json()).items as (Lugar & { comercios?: { count: number }[] })[];
  // PostgREST devuelve el conteo como comercios:[{count}] → lo aplanamos a n_comercios.
  return items.map((l) => ({ ...l, n_comercios: l.comercios?.[0]?.count ?? 0 }));
}

export async function crearLugar(body: { nombre: string; tipo?: string; ciudad_slug?: string; lat?: number | null; lng?: number | null }): Promise<Lugar> {
  const res = await fetch(`${API}/campo/lugares`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.detail ?? "No se pudo crear el lugar"); }
  return (await res.json()).lugar as Lugar;
}

export async function altaComercioCampo(form: FormData): Promise<AltaCampoResult> {
  // Va por XHR y no por fetch: en Safari de iOS, con un service worker
  // registrado, fetch manda el FormData SIN CUERPO. Ver lib/upload.ts.
  try {
    return await postFormData<AltaCampoResult>(
      `${API}/campo/comercio`, form, getAgenteToken());
  } catch (e) {
    if ((e as Error & { status?: number })?.status === 401) {
      clearAgente();
      throw new Error("Sesión vencida, volvé a entrar");
    }
    throw e;
  }
}

export type ComercioAgente = {
  id: string; slug: string; nombre: string; whatsapp: string | null; telefono: string | null; modalidad: string | null;
  direccion: string | null; lat: number | null; lng: number | null;
  portada_url: string | null; portada_thumb_url: string | null; verificado: boolean; created_at: string;
  lugar_id: string | null; puesto: string | null;
  rubros?: { nombre: string; slug: string } | null;
  lugares?: { nombre: string; tipo: string; lat: number | null; lng: number | null; portada_thumb_url?: string | null } | null;
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
  try {
    const data = await postFormData<{ comercio?: { portada_url?: string | null } }>(
      `${API}/campo/mis-comercios/${id}/foto`, form, getAgenteToken());
    return data.comercio?.portada_url ?? null;
  } catch (e) {
    if ((e as Error & { status?: number })?.status === 401) {
      clearAgente();
      throw new Error("Sesión vencida, volvé a entrar");
    }
    throw e;
  }
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
export type TipoLead = "whatsapp" | "telefono" | "email" | "web" | "vista" | "mapa";

export async function registrarLead(comercio_id: string, tipo: TipoLead = "whatsapp", busqueda_id?: string | null): Promise<void> {
  // Fire-and-forget: no bloqueamos la navegación del usuario
  fetch(`${API}/lead`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // `busqueda_id` ata el contacto a la búsqueda que lo produjo. Sin ese
    // puente se sabe qué se mostró y qué se contactó, pero no si una cosa llevó
    // a la otra — que es justo lo que dice si el buscador acierta.
    body: JSON.stringify(busqueda_id ? { comercio_id, tipo, busqueda_id } : { comercio_id, tipo }),
  }).catch(() => undefined);
}

/** Loguea una búsqueda para los KPIs (qué se busca / qué no da / a quién encontró). Fire-and-forget. */
/** Loguea una búsqueda y devuelve su id, para poder atarle el contacto que
 *  venga después. Nunca falla hacia arriba ni bloquea: si el registro se cae, la
 *  persona igual busca y contacta — perder una métrica no puede costar una
 *  venta. */
export async function logBusqueda(query: string, resultados: number, comercios?: string[]): Promise<string | null> {
  if (!query || query.trim().length < 2) return null;
  try {
    const res = await fetch(`${API}/busquedas/log`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query.trim(), resultados, comercios: comercios?.slice(0, 10) }),
    });
    if (!res.ok) return null;
    return (await res.json()).busqueda_id ?? null;
  } catch {
    return null;
  }
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
