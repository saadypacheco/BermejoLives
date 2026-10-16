// Cliente del "modo agente de campo" (alta rápida de comercios).
import {
  postFormData, subirConProgreso, camposOpcionesFoto, listaFotos, respuestaPortada,
  type OpcionesFoto, type ListaFotos, type RespuestaPortada,
} from "@/lib/upload";
import { normalizarCapa, type CapaCalles, type EstadoMarca } from "@/lib/calles";
// El `?ref=` con el que llegó esta persona (lo guarda RefCapture, primer toque,
// y vence a los 30 días: ver lib/ref.ts).
import { refGuardado } from "@/lib/ref";
export { refGuardado };
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_agente_token";

/** El email del agente, sacado del token. Sirve para distinguir en la lista
 *  las fichas propias de las del otro agente de la misma ciudad.
 *
 *  Es sólo para mostrar: lo que decide qué puede tocar lo valida el backend
 *  contra el token firmado, no esto. */
export function getAgenteEmail(): string | null {
  const t = getAgenteToken();
  if (!t) return null;
  try {
    const cuerpo = t.split(".")[1];
    if (!cuerpo) return null;
    const json = JSON.parse(atob(cuerpo.replace(/-/g, "+").replace(/_/g, "/")));
    return (json.sub || json.email || null) as string | null;
  } catch {
    return null;   // token raro: no mostrar nada es mejor que romper la lista
  }
}

/** Lo que el token del agente dice de él: nombre, correo y ciudad (su slug).
 *  Sólo para mostrar —el manual personalizado—; lo que puede tocar lo decide el
 *  backend contra el token firmado, no esto. Si el token no está o es raro,
 *  todo en null. */
export function getAgentePerfil(): { nombre: string | null; email: string | null; ciudad: string | null } {
  const vacio = { nombre: null, email: null, ciudad: null };
  const t = getAgenteToken();
  if (!t) return vacio;
  try {
    const cuerpo = t.split(".")[1];
    if (!cuerpo) return vacio;
    // El nombre puede llevar tildes: atob da bytes, hay que decodificarlos como UTF-8.
    const bytes = Uint8Array.from(atob(cuerpo.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
    const j = JSON.parse(new TextDecoder().decode(bytes)) as { nombre?: unknown; email?: unknown; sub?: unknown; ciudad?: unknown };
    const txt = (x: unknown) => (typeof x === "string" && x.trim() ? x.trim() : null);
    return { nombre: txt(j.nombre), email: txt(j.email) ?? txt(j.sub), ciudad: txt(j.ciudad) };
  } catch {
    return vacio;
  }
}

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
  // El código URUKU-XXXX ya no viaja al agente: lo ve sólo el admin.
  comercio: {
    id: string; nombre: string; slug: string; ciudad: string; foto: boolean; gps: boolean;
  };
  /** La clave del comercio (`BOUTIQUE-K7M2P9`) con la que el dueño entra a su
   *  panel. Viene SÓLO en esta respuesta (el servidor guarda el hash): se
   *  muestra una vez, para dársela en un papel aparte. Nunca va al volante ni a
   *  un WhatsApp, ni a localStorage ni a logs. */
  clave?: string | null;
};

/** Lo que manda el servidor: la clave viaja como `clave` (spec 12/10); se acepta
 *  también `clave_inicial`, el nombre que tenía antes. */
type AltaCampoCrudo = Omit<AltaCampoResult, "clave"> & { clave?: string | null; clave_inicial?: string | null };

// ---- Galería (fotos/videos) del comercio, lado agente ----
export type FotoGaleria = { id: string; url: string; thumb_url: string | null; orden?: number };
export type VideoGaleria = { id: string; url: string; duracion_seg: number | null; orden?: number };

const galH = () => ({ Authorization: `Bearer ${getAgenteToken() ?? ""}` });
export const listarFotosCampo = (cid: string): Promise<ListaFotos<FotoGaleria>> =>
  fetch(`${API}/campo/mis-comercios/${cid}/fotos`, { headers: galH() }).then((r) => r.json()).then((d) => listaFotos<FotoGaleria>(d));
export const listarVideosCampo = (cid: string): Promise<VideoGaleria[]> =>
  fetch(`${API}/campo/mis-comercios/${cid}/videos`, { headers: galH() }).then((r) => r.json()).then((d) => d.items ?? []);
// El agente NO borra fotos (las borra URUKU): por eso acá no hay `borrarFotoCampo`.
/** «Usar como portada»: intercambia la foto elegida con la portada actual (la
 *  anterior entra a la galería). Devuelve la portada nueva y la galería reacomodada. */
export async function usarComoPortadaCampo(cid: string, fotoId: string): Promise<RespuestaPortada<FotoGaleria>> {
  const res = await fetch(`${API}/campo/mis-comercios/${cid}/portada`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...galH() },
    body: JSON.stringify({ foto_id: fotoId }),
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" && d.detail ? d.detail : "No se pudo cambiar la portada");
  }
  return respuestaPortada<FotoGaleria>(await res.json().catch(() => null));
}
// (Sin borrarVideoCampo: el agente no borra videos — el servidor responde 403.)
/** `opts`: cómo reintentar cuando la galería llegó al tope (409). El agente sólo
 *  puede `reemplazar`: no compromete plata del comercio. */
export const subirFotoCampo = (cid: string, file: File, onP?: (p: number) => void, opts?: Pick<OpcionesFoto, "reemplazar">): Promise<FotoGaleria> =>
  subirConProgreso<{ foto: FotoGaleria }>(`${API}/campo/mis-comercios/${cid}/fotos`, "foto", file, getAgenteToken(), camposOpcionesFoto(opts), onP).then((d) => d.foto);
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
    const r = await postFormData<AltaCampoCrudo>(
      `${API}/campo/comercio`, form, getAgenteToken());
    const { clave_inicial, ...resto } = r;
    return { ...resto, clave: resto.clave || clave_inicial || null };
  } catch (e) {
    if ((e as Error & { status?: number })?.status === 401) {
      clearAgente();
      throw new Error("Sesión vencida, volvé a entrar");
    }
    throw e;
  }
}

/** El plan de un comercio como lo ve el agente: sólo el estado, nunca precios ni
 *  fechas de pago. Lo manda `/campo/mis-comercios` (spec docs/que-hay-aca.md). */
export type EstadoPlan = "al_dia" | "cortesia" | "gratis" | "vencido";

export type ComercioAgente = {
  /** Del backend de «Qué hay acá». Opcionales: mientras el servidor no los
   *  mande, la pantalla funciona igual y sólo omite el sello y el conteo de fotos. */
  estado_plan?: EstadoPlan | null;
  /** Fotos de la galería (sin contar la portada). */
  fotos_count?: number | null;
  rubro_slug?: string | null;
  id: string; slug: string; nombre: string; whatsapp: string | null; telefono: string | null; modalidad: string | null;
  direccion: string | null; lat: number | null; lng: number | null;
  /** La calle deducida del GPS (0127). Casi ningún comercio tiene dirección
   *  tipeada, así que en la lista es lo único que dice dónde queda. */
  calle?: string | null;
  horario?: string | null;
  /** Lo que el servidor trae para decidir «Le falta» sin pedir nada más. */
  prod_obs_human?: string | null;
  /** Redes, catálogo, canal y correo: los trae `/campo/mis-comercios`, para
   *  que «Completar comercio» muestre lo que ya está cargado. */
  email?: string | null;
  instagram_url?: string | null; facebook_url?: string | null; tiktok_url?: string | null;
  sitio_web?: string | null; canal_wa_url?: string | null; catalogo_url?: string | null;
  /** «Lo que suma» en la ficha (spec docs/ficha-destacados.md). */
  tiene_pasero?: boolean; envios_internacionales?: boolean; tiene_factura?: boolean; talles_especiales?: boolean;
  pedido_minimo?: string | null;
  sin_cartel?: boolean;
  /** El punto del mapa se calculó desde la dirección (no se tomó con el GPS en la
   *  puerta): puede estar corrido unos metros. El servidor lo pone en `false` al
   *  re-tomar el GPS en «Completar». Opcional: mientras el backend no lo mande,
   *  no se muestra ningún aviso. */
  ubicacion_aproximada?: boolean;
  /** Quién lo dio de alta. Con dos agentes por ciudad, saber que la ficha es
   *  del otro evita la duda de «esto no lo cargué yo, ¿lo puedo tocar?». */
  cargado_por?: string | null;
  /** La ciudad del comercio. Se usa para avisar cuando NO es la del agente:
   *  un agente de Santa Cruz que carga parado en Bermejo tiene que ver ese
   *  comercio en su lista —lo cargó él— pero sabiendo que es de otra ciudad. */
  ciudades?: { nombre: string; slug: string } | null;
  portada_url: string | null; portada_thumb_url: string | null; verificado: boolean; created_at: string;
  lugar_id: string | null; puesto: string | null;
  rubros?: { nombre: string; slug: string } | null;
  /** TODOS los rubros del comercio, no sólo el principal. */
  comercio_rubros?: { rubros: { nombre: string; slug: string } | null }[] | null;
  lugares?: { nombre: string; tipo: string; lat: number | null; lng: number | null; portada_thumb_url?: string | null } | null;
};

/** La ciudad asignada al agente, según la última respuesta del servidor. */
export let ciudadDelAgente: string | null = null;

/** Los comercios de SU CIUDAD, no sólo los que cargó él: parado en una cuadra
 *  tiene que poder ver qué está cargado, mostrárselo al comerciante y
 *  corregirlo, lo haya dado de alta quien sea. */
export async function misComercios(): Promise<ComercioAgente[]> {
  const res = await fetch(`${API}/campo/mis-comercios`, {
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
  });
  if (res.status === 401) {
    clearAgente();
    throw new Error("Sesión vencida, volvé a entrar");
  }
  if (!res.ok) throw new Error("No se pudo cargar el listado");
  const d = await res.json();
  // `ciudad` es la del agente; viene para poder marcar los de otra ciudad.
  ciudadDelAgente = (d.ciudad as string | null) ?? null;
  return d.items as ComercioAgente[];
}

/** Un solo comercio, con lo mismo que trae la lista. Es lo que abre «Completar
 *  comercio» al final del alta, sin bajar la ciudad entera con la señal de la calle. */
export async function miComercio(id: string): Promise<ComercioAgente> {
  const res = await fetch(`${API}/campo/mis-comercios/${encodeURIComponent(id)}`, {
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
  });
  if (res.status === 401) {
    clearAgente();
    throw new Error("Sesión vencida, volvé a entrar");
  }
  if (!res.ok) throw new Error("No se pudo abrir el comercio");
  return (await res.json()).comercio as ComercioAgente;
}

// ---- «Qué hay acá»: ofrecer URUKU a un comercio (spec docs/que-hay-aca.md) ----

/** Un comercio completo de la ciudad, para mostrarle al dueño cómo se ve uno bien cargado. */
export type EjemploCampo = {
  id: string; slug: string; nombre: string;
  rubro_nombre: string | null; portada_thumb_url: string | null;
};

/** Un plan pago que se puede ofrecer. Sólo el nombre: los precios no van en la app. */
export type PlanCampo = { slug: string; nombre: string };

async function getCampo<T>(ruta: string, fallo: string): Promise<T> {
  const res = await fetch(`${API}${ruta}`, { headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` } });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) throw new Error(fallo);
  return res.json() as Promise<T>;
}

/** Hasta 3 comercios completos de la ciudad del agente (prefiere el rubro dado y
 *  deja afuera `excluir`, el comercio que se está ofreciendo). */
export async function ejemplosCampo(rubro?: string | null, excluir?: string | null): Promise<EjemploCampo[]> {
  const q = new URLSearchParams();
  if (rubro) q.set("rubro", rubro);
  if (excluir) q.set("excluir", excluir);
  const d = await getCampo<{ items?: EjemploCampo[] }>(`/campo/ejemplos${q.toString() ? `?${q}` : ""}`, "No se pudieron traer los ejemplos");
  return d.items ?? [];
}

/** Los planes pagos activos, sólo nombres. */
export async function planesCampo(): Promise<PlanCampo[]> {
  const d = await getCampo<{ items?: PlanCampo[] }>("/campo/planes", "No se pudieron traer los planes");
  return d.items ?? [];
}

/** Anota que al comercio le interesa un plan; el admin lo ve en Suscripciones. */
export async function anotarInteresPlan(comercioId: string, plan: string, nota?: string): Promise<void> {
  const body: { plan: string; nota?: string } = { plan };
  if (nota && nota.trim()) body.nota = nota.trim().slice(0, 300);
  const res = await fetch(`${API}/campo/mis-comercios/${encodeURIComponent(comercioId)}/interes`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" && d.detail ? d.detail : "No se pudo anotar el interés");
  }
}

export type EditarComercioBody = {
  nombre?: string; whatsapp?: string; modalidad?: string; direccion?: string | null; rubro_slugs?: string[];
  // La segunda pasada: lo que se carga en la segunda visita, con el dueño
  // presente. `null` BORRA el dato — es lo que permite deshacer una red mal
  // pegada dejando el campo en blanco.
  telefono?: string | null; email?: string | null;
  prod_obs_human?: string | null;
  lugar_id?: string | null; puesto?: string | null;
  instagram_url?: string | null; facebook_url?: string | null;
  tiktok_url?: string | null; sitio_web?: string | null;
  canal_wa_url?: string | null; catalogo_url?: string | null;
  /** «Lo que suma» en la ficha. Los tres tildes son booleanos; el pedido mínimo
   *  es texto y vacío (null) lo borra. */
  tiene_pasero?: boolean; envios_internacionales?: boolean; tiene_factura?: boolean; talles_especiales?: boolean;
  pedido_minimo?: string | null;
  /** El GPS tomado en la puerta. Van juntos (lat y lng); el servidor deja de
   *  marcar la ubicación como aproximada (docs/farmacias-de-turno.md). */
  lat?: number; lng?: number;
  /** El horario como lo dicta el dueño. Vacío (o null) lo borra. */
  horario?: string | null;
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

/** Sube el catálogo en PDF (hasta 8 MB) de un comercio. Devuelve la URL pública
 *  que quedó en `catalogo_url`; el servidor borra el archivo anterior. Si falla,
 *  el catálogo que había queda como estaba. */
export async function subirCatalogoCampo(id: string, file: File, onP?: (pct: number) => void): Promise<string | null> {
  const fd = new FormData();
  fd.append("archivo", file);
  try {
    const d = await postFormData<{ catalogo_url?: string | null }>(
      `${API}/campo/mis-comercios/${encodeURIComponent(id)}/catalogo`, fd, getAgenteToken(), onP);
    return d.catalogo_url ?? null;
  } catch (e) {
    if ((e as Error & { status?: number })?.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
    throw e;
  }
}

/** Quita el catálogo de un comercio: borra el archivo y deja `catalogo_url` en null. */
export async function quitarCatalogoCampo(id: string): Promise<void> {
  const res = await fetch(`${API}/campo/mis-comercios/${encodeURIComponent(id)}/catalogo`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getAgenteToken() ?? ""}` },
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" && d.detail ? d.detail : "No se pudo quitar el catálogo");
  }
}

/** Re-sube la foto de un comercio que este agente cargó. Devuelve la portada
 *  nueva (original y miniatura); la anterior pasa a la galería, no se borra. */
export async function actualizarFotoComercioAgente(id: string, foto: File): Promise<{ portada_url: string | null; portada_thumb_url: string | null }> {
  const form = new FormData();
  form.append("foto", foto);
  try {
    const data = await postFormData<{ comercio?: { portada_url?: string | null; portada_thumb_url?: string | null } }>(
      `${API}/campo/mis-comercios/${id}/foto`, form, getAgenteToken());
    return { portada_url: data.comercio?.portada_url ?? null, portada_thumb_url: data.comercio?.portada_thumb_url ?? null };
  } catch (e) {
    if ((e as Error & { status?: number })?.status === 401) {
      clearAgente();
      throw new Error("Sesión vencida, volvé a entrar");
    }
    throw e;
  }
}

// El agente tampoco da de baja comercios: eso es del admin (Negocios › Dar de baja).

/** Registra un click de contacto (WhatsApp, teléfono, etc.) para un comercio. */
export type TipoLead = "whatsapp" | "telefono" | "email" | "web" | "vista" | "mapa" | "reserva";

/** Una página vista. Sin cookies y sin IP: ver components/contador-visitas.tsx.
 *  Fuego y olvido, igual que el lead. */
export function registrarVisita(v: {
  ruta: string; sesion: string; primera: boolean;
  origen?: string | null; referido?: string | null; ciudad?: string | null;
}): void {
  const body: Record<string, unknown> = { ruta: v.ruta, sesion: v.sesion, primera: v.primera };
  if (v.origen) body.origen = v.origen;
  if (v.referido) body.referido = v.referido;
  if (v.ciudad) body.ciudad = v.ciudad;
  // `keepalive` para que el pedido sobreviva a la navegación: sin esto, el que
  // entra y toca un enlace enseguida —que es lo normal— no se contaría nunca.
  fetch(`${API}/visita`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    keepalive: true,
  }).catch(() => { /* perder un número no puede costar una visita */ });
}


export async function registrarLead(comercio_id: string, tipo: TipoLead = "whatsapp", busqueda_id?: string | null, origen?: string | null, nombre?: string | null): Promise<void> {
  // Fire-and-forget: no bloqueamos la navegación del usuario
  const body: Record<string, string> = { comercio_id, tipo };
  // `busqueda_id` ata el contacto a la búsqueda que lo produjo. Sin ese
  // puente se sabe qué se mostró y qué se contactó, pero no si una cosa llevó
  // a la otra — que es justo lo que dice si el buscador acierta.
  if (busqueda_id) body.busqueda_id = busqueda_id;
  // `origen` es el `?ref=` con el que llegó (volante, mesa, el QR de la ficha).
  // Si quien llama no lo pasa, se toma el guardado: así los botones de
  // WhatsApp, mapa y reserva atribuyen el contacto sin repetir esto en cada uno.
  const ref = origen || refGuardado();
  if (ref) body.origen = ref;
  fetch(`${API}/lead`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(async (r) => {
    // Un contacto de WhatsApp queda anotado para preguntar después «¿te
    // contestó?» (components/pregunta-contesto.tsx). Las vistas, no.
    if (tipo !== "whatsapp" && tipo !== "telefono") return;
    const j = await r.json().catch(() => null);
    if (j?.id) {
      const { anotarContacto } = await import("@/lib/contestaron");
      anotarContacto(j.id, comercio_id, nombre || "el local");
    }
  }).catch(() => undefined);
}

/** «¿Te contestó?»: sí o no sobre un contacto propio. Fire-and-forget. */
export function responderContesto(leadId: string, respondio: boolean): void {
  fetch(`${API}/lead/${encodeURIComponent(leadId)}/respondio`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ respondio }),
  }).catch(() => undefined);
}

/** Loguea una búsqueda para los KPIs (qué se busca / qué no da / a quién encontró). Fire-and-forget. */
/** Loguea una búsqueda y devuelve su id, para poder atarle el contacto que
 *  venga después. Nunca falla hacia arriba ni bloquea: si el registro se cae, la
 *  persona igual busca y contacta — perder una métrica no puede costar una
 *  venta. */
export async function logBusqueda(query: string, resultados: number, comercios?: string[]): Promise<string | null> {
  // Tres, no dos. Con dos entraban "re" y "om" —prefijos de "restaurante" y
  // "comida"— y se leían como demanda. Ninguna búsqueda real de dos letras
  // significa algo en este catálogo.
  if (!query || query.trim().length < 3) return null;
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

// ---- Mapa de calles recorridas, lado agente (spec docs/mapa-calles.md) ----

/** Las calles de la ciudad del agente con su estado. */
export async function campoCalles(): Promise<CapaCalles> {
  return normalizarCapa(await getCampo<unknown>("/campo/calles", "No se pudieron traer las calles"));
}

/** El agente marca un tramo de SU ciudad. */
export async function campoMarcarCalle(id: string, estado: EstadoMarca, nota?: string): Promise<void> {
  const body: { estado: EstadoMarca; nota?: string } = { estado };
  if (nota && nota.trim()) body.nota = nota.trim().slice(0, 200);
  const res = await fetch(`${API}/campo/calles/${encodeURIComponent(id)}/marca`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getAgenteToken() ?? ""}` },
    body: JSON.stringify(body),
  });
  if (res.status === 401) { clearAgente(); throw new Error("Sesión vencida, volvé a entrar"); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(typeof d.detail === "string" && d.detail ? d.detail : "No se pudo marcar la calle");
  }
}
