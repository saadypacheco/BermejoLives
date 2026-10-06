// Cliente del panel del COMERCIO logueado (login + chatbot de publicación).
import { subirConProgreso } from "@/lib/upload";
import { detalleDeError } from "@/lib/acceso";
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_comercio_token";
const COMERCIO_KEY = "bermejo_comercio";

export type ComercioSession = { id: string; nombre: string; slug: string; confiable: boolean; lugar_nombre?: string | null;
  /** Sólo lo trae el alta: el código `URUKU-XXXX` del negocio (mandado en un
   *  WhatsApp sirve para publicar 1 a 1 o atar su grupo). */
  codigo?: string; codigo_formateado?: string;
};

export function getCToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function getComercioSession(): ComercioSession | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(COMERCIO_KEY);
  return raw ? (JSON.parse(raw) as ComercioSession) : null;
}
export function clearComercio() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(COMERCIO_KEY);
}

/** Campos que NUNCA se guardan en el navegador: una clave en localStorage la lee
 *  cualquier script de la página. El backend ya no las manda dentro de `comercio`
 *  (`clave_inicial` viaja sólo en la raíz), pero acá se sacan igual. */
const CAMPOS_SECRETOS = ["clave", "clave_inicial", "clave_nueva", "password", "pass", "contrasena"];

/** Copia de `comercio` sin ninguna clave. */
function sinClaves(comercio: unknown): ComercioSession {
  const limpio: Record<string, unknown> = { ...(comercio as Record<string, unknown>) };
  for (const k of CAMPOS_SECRETOS) delete limpio[k];
  return limpio as ComercioSession;
}

/** Guarda token + sesión (sin claves) y devuelve la sesión guardada. */
function guardarSesion(data: { access_token: string; comercio: unknown }): ComercioSession {
  const sesion = sinClaves(data.comercio);
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(COMERCIO_KEY, JSON.stringify(sesion));
  return sesion;
}

/** Una clave que vino en la respuesta: sólo si es un texto no vacío. */
function leerClave(v: unknown): string | null {
  return typeof v === "string" && v ? v : null;
}

export async function comercioLogin(email: string, password: string): Promise<ComercioSession> {
  const res = await fetch(`${API}/auth/comercio/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  return guardarSesion(await res.json());
}

export async function generarDescripcion(nombre: string, que_vende: string, rubros: { slug: string; nombre: string }[]): Promise<{ descripcion: string; rubro_slugs: string[] }> {
  const res = await fetch(`${API}/comercio/generar-descripcion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre, que_vende, rubros }),
  });
  return res.json();
}

/** El backend ANULÓ la clave por demasiados fallos (401 «Por seguridad tu clave
 *  se anuló. Entrá con tu WhatsApp…»): la clave ya no sirve y la única salida es
 *  entrar con el WhatsApp. Se distingue del 401 común para ofrecer ese camino. */
export class ClaveAnulada extends Error {
  constructor(detalle: string) { super(detalle); this.name = "ClaveAnulada"; }
}

/** Entra con celular + clave de 6 números. 401 («Celular o clave incorrectos»),
 *  401 de clave anulada y 429 («Demasiados intentos…») traen su motivo en
 *  `detail`: se muestra tal cual. */
export async function comercioIngresar(whatsapp: string, clave: string): Promise<ComercioSession> {
  const res = await fetch(`${API}/auth/comercio/ingresar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp, clave }),
  });
  if (!res.ok) {
    const detalle = await detalleDeError(res, "No se pudo entrar. Probá de nuevo.");
    if (res.status === 401 && /se anul/i.test(detalle)) throw new ClaveAnulada(detalle);
    throw new Error(detalle);
  }
  return guardarSesion(await res.json());
}

export type SolicitudRecuperar = { codigo: string; wa_link: string };

/** Un negocio de los que comparten el número (para que la persona elija cuál). */
export type NegocioDelNumero = { id: string; nombre: string; direccion: string | null };

/** El número está en varios negocios (409): nunca se elige uno en silencio. La
 *  persona elige y se repite el pedido con `comercio_id`. */
export class VariosNegocios extends Error {
  negocios: NegocioDelNumero[];
  constructor(mensaje: string, negocios: NegocioDelNumero[]) {
    super(mensaje); this.name = "VariosNegocios"; this.negocios = negocios;
  }
}

function leerNegocios(d: unknown): NegocioDelNumero[] {
  if (typeof d !== "object" || d === null) return [];
  const lista = (d as Record<string, unknown>).negocios;
  if (!Array.isArray(lista)) return [];
  const salida: NegocioDelNumero[] = [];
  for (const n of lista) {
    if (typeof n !== "object" || n === null) continue;
    const o = n as Record<string, unknown>;
    if (typeof o.id !== "string" || typeof o.nombre !== "string") continue;
    salida.push({ id: o.id, nombre: o.nombre, direccion: typeof o.direccion === "string" && o.direccion ? o.direccion : null });
  }
  return salida;
}

/** Ya no manda nada por WhatsApp — devuelve el código y el link wa.me para
 * que el dueño mande "CONFIRMAR-XXXXXX" él mismo (sin riesgo de ban por
 * envío saliente automatizado). Con el número en varios negocios tira
 * `VariosNegocios`; se repite con `comercioId`. */
export async function comercioRecuperar(whatsapp: string, comercioId?: string): Promise<SolicitudRecuperar> {
  const res = await fetch(`${API}/auth/comercio/recuperar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(comercioId ? { whatsapp, comercio_id: comercioId } : { whatsapp }),
  });
  const data: unknown = await res.json().catch(() => ({}));
  if (res.status === 409) {
    const negocios = leerNegocios(data);
    if (negocios.length > 0) {
      const detail = (data as Record<string, unknown>).detail;
      throw new VariosNegocios(typeof detail === "string" && detail ? detail : "Ese número está en más de un negocio. Elegí el tuyo.", negocios);
    }
  }
  // 404: ese número no es de ningún negocio; 400: número inválido; 429: demasiados
  // pedidos. El `detail` del backend lo explica y se muestra tal cual, en vez de
  // quedarse esperando.
  if (!res.ok) {
    const detail = typeof data === "object" && data !== null ? (data as Record<string, unknown>).detail : null;
    throw new Error(typeof detail === "string" && detail ? detail : "No se pudo generar el código. Probá de nuevo.");
  }
  const ok = data as Record<string, unknown>;
  return { codigo: typeof ok.codigo === "string" ? ok.codigo : "", wa_link: typeof ok.wa_link === "string" ? ok.wa_link : "" };
}

/** Para pollear mientras se espera que llegue el mensaje de confirmación. */
export async function comercioRecuperarEstado(whatsapp: string, codigo: string): Promise<boolean> {
  const res = await fetch(`${API}/auth/comercio/recuperar/estado?whatsapp=${encodeURIComponent(whatsapp)}&codigo=${encodeURIComponent(codigo)}`);
  if (!res.ok) return false;
  return (await res.json()).confirmado === true;
}

/** Lo que devuelve entrar por WhatsApp: la sesión y, si el negocio todavía no
 *  tenía clave (o se la cambió), la clave nueva. Es la ÚNICA vez que se ve. */
export type EntradaConfirmada = { sesion: ComercioSession; claveNueva: string | null };

/** Entra con el número ya confirmado por WhatsApp. */
export async function comercioRecuperarConfirmar(whatsapp: string, codigo: string): Promise<EntradaConfirmada> {
  const res = await fetch(`${API}/auth/comercio/recuperar/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp, codigo }),
  });
  if (!res.ok) throw new Error(await detalleDeError(res, "No se pudo entrar"));
  const data = await res.json();
  // La clave nueva va sólo a la pantalla (en memoria): nunca al navegador.
  return { sesion: guardarSesion(data), claveNueva: leerClave(data.clave_nueva) };
}

/** Genera una clave nueva (la anterior deja de servir). Devuelve la clave en
 *  claro: es la única vez que se ve, el servidor sólo guarda el hash. Se puede
 *  pedir hasta 3 veces por hora: el 429 trae su motivo y se muestra tal cual. */
export async function generarClaveNueva(): Promise<string> {
  const d = await cFetch("/comercio/clave", { method: "POST" }) as { clave?: unknown };
  if (typeof d.clave !== "string" || !d.clave) throw new Error("No se pudo generar la clave. Probá de nuevo.");
  return d.clave;
}

export type ComercioBusqueda = { id: string; slug: string; nombre: string; portada_url: string | null; direccion: string | null };

export async function buscarComercioPorNombre(q: string): Promise<ComercioBusqueda[]> {
  const res = await fetch(`${API}/comercio/buscar?q=${encodeURIComponent(q)}`);
  if (!res.ok) return [];
  return (await res.json()).items as ComercioBusqueda[];
}

export async function solicitarCambioNumero(comercioId: string, whatsappNuevo: string, lat: number, lng: number, mensaje: string | undefined, foto: File): Promise<void> {
  const fd = new FormData();
  fd.append("whatsapp_nuevo", whatsappNuevo);
  fd.append("lat", String(lat));
  fd.append("lng", String(lng));
  if (mensaje) fd.append("mensaje", mensaje);
  fd.append("foto", foto);
  const res = await fetch(`${API}/comercio/${comercioId}/solicitar-cambio-numero`, { method: "POST", body: fd });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo enviar la solicitud");
  }
}

export type RegistroPayload = {
  nombre: string;
  whatsapp: string;
  modalidad: "mayorista" | "minorista" | "ambos";
  rubro_slugs?: string[];
  descripcion?: string;
  direccion?: string;
  lat: number;
  lng: number;
  foto: File;
};

/** Ese número ya tiene un negocio activo (409): no se puede crear otro encima.
 *  El único camino es entrar con ese WhatsApp. `message` es el `detail` del backend. */
export class NumeroYaRegistrado extends Error {
  constructor(detalle: string) { super(detalle); this.name = "NumeroYaRegistrado"; }
}

/** Lo que devuelve el alta: la sesión (sin claves) y la clave de entrada, que el
 *  backend manda SÓLO en la raíz de la respuesta. Se muestra una vez al dueño y
 *  vive sólo en memoria. */
export type RegistroResult = { sesion: ComercioSession; claveInicial: string | null };

export async function comercioRegistro(payload: RegistroPayload): Promise<RegistroResult> {
  const fd = new FormData();
  fd.append("nombre", payload.nombre);
  fd.append("whatsapp", payload.whatsapp);
  fd.append("modalidad", payload.modalidad);
  (payload.rubro_slugs ?? []).forEach((r) => fd.append("rubro_slugs", r));
  if (payload.descripcion) fd.append("descripcion", payload.descripcion);
  if (payload.direccion) fd.append("direccion", payload.direccion);
  fd.append("lat", String(payload.lat));
  fd.append("lng", String(payload.lng));
  fd.append("foto", payload.foto);

  const res = await fetch(`${API}/auth/comercio/registro`, { method: "POST", body: fd });
  if (!res.ok) {
    const detalle = await detalleDeError(res, "No se pudo crear la cuenta");
    if (res.status === 409) throw new NumeroYaRegistrado(detalle);
    throw new Error(detalle);
  }
  const data = await res.json();
  return { sesion: guardarSesion(data), claveInicial: leerClave(data.clave_inicial) };
}

export type PublicarPayload = {
  tipo: "oferta" | "video" | "novedad";
  titulo?: string;
  descripcion?: string;
  precio?: number | null;
  moneda?: "BOB" | "USD" | "ARS";
  imagen_url?: string;
  tiktok_url?: string;
  descuento_pct?: number | null;
  vence_el?: string | null;        // "YYYY-MM-DD"
};

export type PublicarResult = {
  ok: boolean; estado: string; publicado_directo: boolean;
  /** Texto del backend cuando la publicación salió pero pasó algo que el
   *  comerciante tiene que saber (típico: se cobró una extra por pasarse de la
   *  cuota). null = nada que avisar. */
  aviso: string | null;
};

/** El backend se negó a publicar (402: plan sin extras o período vencido).
 *  Se distingue de un error de red porque su mensaje ya explica qué pasa y qué
 *  hacer, y hay que mostrarlo tal cual. */
export class PublicarBloqueado extends Error {
  constructor(detalle: string) { super(detalle); this.name = "PublicarBloqueado"; }
}

export async function publicar(payload: PublicarPayload): Promise<PublicarResult> {
  const res = await fetch(`${API}/comercio/publicar`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getCToken() ?? ""}` },
    body: JSON.stringify(payload),
  });
  if (res.status === 402) {
    const d = await res.json().catch(() => ({}));
    throw new PublicarBloqueado(typeof d.detail === "string" && d.detail ? d.detail : "Tu plan no te deja publicar ahora. Escribinos por WhatsApp y lo resolvemos.");
  }
  if (!res.ok) throw new Error("No se pudo publicar");
  const data = await res.json();
  return { ...data, aviso: typeof data.aviso === "string" && data.aviso ? data.aviso : null } as PublicarResult;
}

// ---- Panel "Mi comercio" ----
async function cFetch(path: string, init?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getCToken() ?? ""}`,
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    clearComercio();
    throw new Error("Tu sesión venció, volvé a entrar.");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    // 429 (p. ej. «Generar clave nueva»: 3 por hora) trae su motivo; si no, uno propio.
    const respaldo = res.status === 429 ? "Hiciste demasiados pedidos seguidos. Esperá un rato y probá de nuevo." : "Error en la solicitud";
    throw new Error(typeof data.detail === "string" && data.detail ? data.detail : respaldo);
  }
  return res.json();
}

export type Perfil = {
  id: string;
  slug: string;
  nombre: string;
  descripcion?: string | null;
  whatsapp?: string | null;
  telefono?: string | null;
  email?: string | null;
  facebook_url?: string | null;
  instagram_url?: string | null;
  tiktok_url?: string | null;
  sitio_web?: string | null;
  logo_url?: string | null;
  portada_url?: string | null;
  direccion?: string | null;
  como_llegar?: string | null;
  horario?: string | null;
  pedido_minimo?: string | null;
  modalidad?: string | null;
  plan?: string | null;
  verificado?: boolean;
  confiable?: boolean;
  acepta_reservas?: boolean;
  lat?: number | null;
  lng?: number | null;
  rubro_slugs?: string[];
  /** El código del negocio (`KPXN`) y su forma para mostrar (`URUKU-KPXN`). */
  codigo?: string | null;
  codigo_formateado?: string | null;
};

export type Suscripcion = {
  plan: string;
  paga_hasta: string | null;
  dias_restantes: number | null;
  suspendido: boolean;
  estado: "gratis" | "activo" | "por_vencer" | "vencido" | "suspendido" | "sin_pago";
  cargos_pendientes: { id: string; titulo: string | null; costo: number | null }[];
  total_cargos: number;
};

export type Metricas = {
  contactos_30d: number;
  contactos_7d?: number;
  visitas_30d?: number;
  visitas_7d?: number;
  contactos_por_tipo: Record<string, number>;
  terminos_busqueda?: { query: string; n: number }[];
  publicaciones_total: number;
  publicaciones_por_estado: Record<string, number>;
};

export const getPerfil = (): Promise<Perfil> => cFetch("/comercio/perfil");
export const updatePerfil = (patch: Partial<Perfil>): Promise<Perfil> =>
  cFetch("/comercio/perfil", { method: "PUT", body: JSON.stringify(patch) });

export async function subirFotoPerfil(foto: File): Promise<Perfil> {
  const fd = new FormData();
  fd.append("foto", foto);
  const res = await fetch(`${API}/comercio/perfil/foto`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${getCToken() ?? ""}` },
    body: fd,
  });
  if (res.status === 401) { clearComercio(); throw new Error("Tu sesión venció, volvé a entrar."); }
  if (!res.ok) { const data = await res.json().catch(() => ({})); throw new Error(data.detail ?? "No se pudo subir la foto"); }
  return res.json();
}
export const getSuscripcion = (): Promise<Suscripcion> => cFetch("/comercio/suscripcion");
export const getMetricas = (): Promise<Metricas> => cFetch("/comercio/metricas");

// ---- Publicaciones / ofertas del comercio ----
export type Publicacion = {
  id: string;
  tipo: "oferta" | "video" | "novedad";
  titulo: string | null;
  descripcion: string | null;
  precio: number | null;
  moneda: string | null;
  imagen_url: string | null;
  tiktok_url: string | null;
  descuento_pct: number | null;
  vence_el: string | null;          // "YYYY-MM-DD"
  estado: string;                   // pendiente | aprobado | rechazado | cambios
};

export type PublicacionPatch = Partial<Pick<Publicacion,
  "titulo" | "descripcion" | "precio" | "moneda" | "imagen_url" | "tiktok_url" | "descuento_pct" | "vence_el">>;

export const getMisPublicaciones = (): Promise<{ items: Publicacion[]; total: number }> =>
  cFetch("/comercio/mis-publicaciones");

export const editarPublicacion = (id: string, patch: PublicacionPatch): Promise<{ ok: boolean; estado: string; item: Publicacion }> =>
  cFetch(`/comercio/publicaciones/${id}`, { method: "PATCH", body: JSON.stringify(patch) });

export const bajaPublicacion = (id: string): Promise<{ ok: boolean }> =>
  cFetch(`/comercio/publicaciones/${id}`, { method: "DELETE" });

// ---- Galería (fotos/videos) del comercio logueado ----
export type FotoGaleria = { id: string; url: string; thumb_url: string | null };
export type VideoGaleria = { id: string; url: string; duracion_seg: number | null };

export const listarFotosComercio = (): Promise<FotoGaleria[]> => cFetch("/comercio/fotos").then((d) => d.items ?? []);
export const listarVideosComercio = (): Promise<VideoGaleria[]> => cFetch("/comercio/videos").then((d) => d.items ?? []);
export const borrarFotoComercio = (id: string): Promise<void> => cFetch(`/comercio/fotos/${id}`, { method: "DELETE" }).then(() => undefined);
export const borrarVideoComercio = (id: string): Promise<void> => cFetch(`/comercio/videos/${id}`, { method: "DELETE" }).then(() => undefined);
export const subirFotoGaleriaComercio = (file: File, onP?: (p: number) => void): Promise<FotoGaleria> =>
  subirConProgreso<{ foto: FotoGaleria }>(`${API}/comercio/fotos`, "foto", file, getCToken(), {}, onP).then((d) => d.foto);
export const subirVideoGaleriaComercio = (file: File, dur: number | null, onP?: (p: number) => void): Promise<VideoGaleria> =>
  subirConProgreso<{ video: VideoGaleria }>(`${API}/comercio/videos`, "video", file, getCToken(), dur != null ? { duracion_seg: String(dur) } : {}, onP).then((d) => d.video);

export async function pagarSuscripcion(
  fields: { monto: number; moneda: string; metodo: string; referencia?: string },
  comprobante: File | null,
): Promise<{ ok: boolean; estado: string; pago_id: string }> {
  const fd = new FormData();
  fd.append("monto", String(fields.monto));
  fd.append("moneda", fields.moneda);
  fd.append("metodo", fields.metodo);
  if (fields.referencia) fd.append("referencia", fields.referencia);
  if (comprobante) fd.append("comprobante", comprobante);
  const res = await fetch(`${API}/comercio/pago`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getCToken() ?? ""}` },
    body: fd,
  });
  if (res.status === 401) { clearComercio(); throw new Error("Tu sesión venció, volvé a entrar."); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo enviar el pago");
  }
  return res.json();
}

// ---- Productos (marketplace) ----
export type Categoria = { slug: string; nombre: string };
export type ProductoDraft = {
  titulo: string;
  descripcion: string | null;
  precio: number | null;
  moneda: string;
  categoria_slug: string | null;
  categoria_nombre: string | null;
  categorias: Categoria[];
};
export type ProductoRef = {
  id: string;
  tienda_producto_id?: string | null;
  url?: string | null;
  foto_url?: string | null;
  titulo?: string | null;
  precio?: number | null;
  moneda?: string | null;
  estado: string;
  destacado_pub_id?: string | null;
  cargado_por?: string | null;
  created_at?: string;
};

export const draftProducto = (b: {
  titulo: string; descripcion?: string; precio?: number | null; moneda?: string;
}): Promise<ProductoDraft> =>
  cFetch("/comercio/productos/draft", { method: "POST", body: JSON.stringify(b) });

export const listProductos = (): Promise<{ items: ProductoRef[]; total: number }> =>
  cFetch("/comercio/productos");

export const borrarProducto = (refId: string): Promise<{ ok: boolean }> =>
  cFetch(`/comercio/productos/${refId}`, { method: "DELETE" });

export const destacarProducto = (refId: string): Promise<{ ok: boolean; estado: string; costo: number }> =>
  cFetch(`/comercio/productos/${refId}/destacar`, { method: "POST" });

// ---- Mensajes ----
export type Mensaje = {
  id: string;
  autor: "admin" | "cliente" | "comercio";
  nombre: string | null;
  contacto: string | null;
  cuerpo: string;
  leido: boolean;
  created_at: string;
};

export const getMensajes = (): Promise<{ items: Mensaje[]; no_leidos: number }> => cFetch("/comercio/mensajes");
export const marcarLeido = (id: string): Promise<{ ok: boolean }> =>
  cFetch(`/comercio/mensajes/${id}/leido`, { method: "POST" });

export async function crearProducto(
  fields: { titulo: string; precio: number; moneda: string; categoria_slug: string; descripcion?: string },
  fotos: File[],
): Promise<{ ok: boolean; url?: string; producto_ref: ProductoRef }> {
  const fd = new FormData();
  fd.append("titulo", fields.titulo);
  fd.append("precio", String(fields.precio));
  fd.append("moneda", fields.moneda);
  fd.append("categoria_slug", fields.categoria_slug);
  if (fields.descripcion) fd.append("descripcion", fields.descripcion);
  fotos.forEach((f) => fd.append("fotos", f));
  const res = await fetch(`${API}/comercio/productos`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getCToken() ?? ""}` },  // sin Content-Type: lo pone FormData
    body: fd,
  });
  if (res.status === 401) { clearComercio(); throw new Error("Tu sesión venció, volvé a entrar."); }
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo publicar el producto");
  }
  return res.json();
}

/** Lo que los clientes le preguntaron al asistente de este local. Las que
 *  quedaron sin respuesta son las que el dueño tiene que mirar. */
export type PreguntaDelAsistente = {
  id: string; pregunta: string; respuesta: string; nivel: number; sin_respuesta: boolean;
  /** Cuándo el dueño la contestó. Con fecha, ya no está pendiente aunque
   *  `sin_respuesta` siga en true (así quedó registrada la conversación). */
  resuelta_en: string | null; created_at: string;
};

/** `sin_respuesta` es el total de pendientes, ya sin las resueltas. */
export const getPreguntasDelAsistente = (): Promise<{ items: PreguntaDelAsistente[]; sin_respuesta: number }> =>
  cFetch("/comercio/asistente/preguntas");

/** Una pregunta frecuente del local con su respuesta: lo que el chatbot
 *  contesta solo, sin IA y sin costo, cuando alguien pregunta algo parecido. */
export type RespuestaDelLocal = { id: string; pregunta: string; respuesta: string; updated_at: string };

export const getRespuestasDelChatbot = (): Promise<{ items: RespuestaDelLocal[] }> =>
  cFetch("/comercio/asistente/respuestas");

/** Con `conversacion_id` el servidor marca esa pregunta como resuelta: así
 *  sale de la lista de «sin respuesta» en el mismo paso. */
export const crearRespuestaDelChatbot = (
  b: { pregunta: string; respuesta: string; conversacion_id?: string | null },
): Promise<{ item: RespuestaDelLocal }> =>
  cFetch("/comercio/asistente/respuestas", {
    method: "POST",
    body: JSON.stringify({ pregunta: b.pregunta, respuesta: b.respuesta, conversacion_id: b.conversacion_id ?? null }),
  });

export const editarRespuestaDelChatbot = (
  id: string, patch: { pregunta?: string; respuesta?: string },
): Promise<{ item: RespuestaDelLocal }> =>
  cFetch(`/comercio/asistente/respuestas/${id}`, { method: "PUT", body: JSON.stringify(patch) });

export const borrarRespuestaDelChatbot = (id: string): Promise<{ ok: boolean }> =>
  cFetch(`/comercio/asistente/respuestas/${id}`, { method: "DELETE" });
