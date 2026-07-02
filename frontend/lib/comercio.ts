// Cliente del panel del COMERCIO logueado (login + chatbot de publicación).
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_comercio_token";
const COMERCIO_KEY = "bermejo_comercio";

export type ComercioSession = { id: string; nombre: string; slug: string; confiable: boolean };

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

export async function comercioLogin(email: string, password: string): Promise<ComercioSession> {
  const res = await fetch(`${API}/auth/comercio/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(COMERCIO_KEY, JSON.stringify(data.comercio));
  return data.comercio as ComercioSession;
}

export async function generarDescripcion(nombre: string, que_vende: string, rubros: { slug: string; nombre: string }[]): Promise<{ descripcion: string; rubro_slugs: string[] }> {
  const res = await fetch(`${API}/comercio/generar-descripcion`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre, que_vende, rubros }),
  });
  return res.json();
}

export async function comercioRecuperar(whatsapp: string): Promise<void> {
  await fetch(`${API}/auth/comercio/recuperar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp }),
  });
}

export async function comercioRecuperarConfirmar(whatsapp: string, codigo: string, nueva_password: string): Promise<ComercioSession> {
  const res = await fetch(`${API}/auth/comercio/recuperar/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ whatsapp, codigo, nueva_password }),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo cambiar la contraseña");
  }
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(COMERCIO_KEY, JSON.stringify(data.comercio));
  return data.comercio as ComercioSession;
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

export async function comercioRegistro(payload: RegistroPayload): Promise<ComercioSession> {
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
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail ?? "No se pudo crear la cuenta");
  }
  const data = await res.json();
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(COMERCIO_KEY, JSON.stringify(data.comercio));
  return data.comercio as ComercioSession;
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

export type PublicarResult = { ok: boolean; estado: string; publicado_directo: boolean };

export async function publicar(payload: PublicarPayload): Promise<PublicarResult> {
  const res = await fetch(`${API}/comercio/publicar`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${getCToken() ?? ""}` },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("No se pudo publicar");
  return res.json();
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
    throw new Error(data.detail ?? "Error en la solicitud");
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
  lat?: number | null;
  lng?: number | null;
  rubro_slugs?: string[];
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
  contactos_por_tipo: Record<string, number>;
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

// Público (sin login): un cliente le deja un mensaje al comercio desde su ficha.
export async function dejarMensaje(b: {
  comercio_id: string; nombre: string; cuerpo: string; contacto?: string;
}): Promise<{ ok: boolean }> {
  const res = await fetch(`${API}/mensaje`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(b),
  });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo enviar el mensaje");
  }
  return res.json();
}

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
