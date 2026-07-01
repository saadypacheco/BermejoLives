// Cliente del backend FastAPI (ingesta + moderación).
const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "bermejo_admin_token";

export function getToken(): string | null {
  return typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Credenciales incorrectas");
  const data = await res.json();
  setToken(data.access_token);
}

async function authFetch(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: { ...(opts.headers ?? {}), Authorization: `Bearer ${getToken() ?? ""}` },
    cache: "no-store",
  });
  if (res.status === 401) {
    clearToken();
    throw new Error("No autenticado");
  }
  return res;
}

export type PendingPub = {
  id: string;
  tipo: string;
  titulo: string | null;
  descripcion: string | null;
  precio: number | null;
  moneda: string;
  imagen_url: string | null;
  tiktok_url: string | null;
  estado: string;
  created_at: string;
  comercios?: { nombre: string; slug: string; logo_url: string | null };
};

export async function listPendientes(estado = "pendiente"): Promise<PendingPub[]> {
  const res = await authFetch(`/moderacion/publicaciones?estado=${estado}`);
  const data = await res.json();
  return data.items as PendingPub[];
}

export async function moderar(id: string, estado: string, motivo?: string) {
  const res = await authFetch(`/moderacion/publicaciones/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estado, motivo }),
  });
  return res.json();
}

export type ComercioPorVerificar = {
  id: string;
  nombre: string;
  slug: string;
  whatsapp: string;
  modalidad: string;
  descripcion: string | null;
  direccion: string | null;
  lat: number | null;
  lng: number | null;
  portada_url: string | null;
  verificado: boolean;
  suspendido: boolean;
  paga_hasta: string | null;
  created_at: string;
  rubros?: { nombre: string; slug: string };
  ciudades?: { nombre: string; slug: string };
};

export async function listComerciosPorVerificar(): Promise<ComercioPorVerificar[]> {
  const res = await authFetch(`/moderacion/comercios?verificado=false`);
  const data = await res.json();
  return data.items as ComercioPorVerificar[];
}

export async function listTodosComercios(): Promise<ComercioPorVerificar[]> {
  const res = await authFetch(`/moderacion/comercios?todos=true`);
  const data = await res.json();
  return data.items as ComercioPorVerificar[];
}

export async function editarComercio(id: string, patch: Record<string, unknown>) {
  const res = await authFetch(`/admin/comercio/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return res.json();
}

export async function verificarComercio(id: string) {
  const res = await authFetch(`/moderacion/comercios/${id}/verificar`, { method: "POST" });
  return res.json();
}

export async function rechazarComercio(id: string) {
  const res = await authFetch(`/moderacion/comercios/${id}/rechazar`, { method: "POST" });
  return res.json();
}

// ── Suscripciones ──────────────────────────────────────────────────────────

export type EstadoSuscripcion = "activo" | "por_vencer" | "vencido" | "suspendido" | "sin_plan";

export type ComercioSuscripcion = {
  id: string;
  slug: string;
  nombre: string;
  whatsapp: string;
  verificado: boolean;
  suspendido: boolean;
  paga_hasta: string | null;
  suscripcion_estado: EstadoSuscripcion;
  created_at: string;
};

export async function listSuscripciones(): Promise<ComercioSuscripcion[]> {
  const res = await authFetch("/admin/suscripciones");
  const data = await res.json();
  return data.items as ComercioSuscripcion[];
}

export type EstadisticasAdmin = {
  comercios_nuevos_7d: number;
  comercios_nuevos_30d: number;
  alertas: { vencido: number; suspendido: number; por_vencer: number };
  ofertas_total: number;
  ofertas_top_comercios: { comercio_id: string; nombre: string; count: number }[];
  contactos_30d: number;
  contactos_top_comercios: { comercio_id: string; nombre: string; count: number }[];
};

export async function getEstadisticas(): Promise<EstadisticasAdmin> {
  const res = await authFetch("/admin/estadisticas");
  return res.json();
}

// ---- Reclamos (Encontralo) ----
export type Reclamo = {
  id: string;
  nombre: string | null;
  contacto: string | null;
  comercio_id: string | null;
  mensaje: string;
  estado: "pendiente" | "respondido";
  respuesta: string | null;
  respondido_por: string | null;
  respondido_en: string | null;
  created_at: string;
  comercios?: { nombre: string; slug: string } | null;
};

export async function listReclamos(estado?: string): Promise<Reclamo[]> {
  const res = await authFetch(`/admin/reclamos${estado ? `?estado=${estado}` : ""}`);
  const data = await res.json();
  return data.items as Reclamo[];
}

export async function responderReclamo(id: string, respuesta: string) {
  const res = await authFetch(`/admin/reclamos/${id}/responder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ respuesta }),
  });
  return res.json();
}

// ---- Datos de Reservalo (proxy vía /api/admin-sync) ----
export type ReservaloResumen = {
  clientes_nuevos_7d?: number;
  clientes_nuevos_30d?: number;
  reservas_30d_total?: number;
  reservas_30d_por_vendedor?: { vendedor_id: string; count: number }[];
  top_productos_consultados?: { producto_id: number; nombre: string; count: number }[];
};

export async function getReservaloResumen(): Promise<ReservaloResumen> {
  const res = await authFetch("/admin/reservalo/resumen");
  return res.json();
}

export type ConsultaReservalo = {
  id: number;
  nombre: string | null;
  email: string | null;
  tipo: string;
  mensaje: string;
  estado: "pendiente" | "respondida";
  respuesta: string | null;
  respondida_por: string | null;
  respondida_en: string | null;
  created_at: string;
};

export async function getReservaloConsultas(estado?: string): Promise<ConsultaReservalo[]> {
  const res = await authFetch(`/admin/reservalo/consultas${estado ? `?estado=${estado}` : ""}`);
  const data = await res.json();
  return data.items as ConsultaReservalo[];
}

export async function responderReservaloConsulta(id: number, respuesta: string) {
  const res = await authFetch(`/admin/reservalo/consultas/${id}/responder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ respuesta }),
  });
  return res.json();
}

export async function registrarPago(comercioId: string, body: {
  monto: number; moneda: string; metodo: string; referencia?: string; meses: number; notas?: string;
}) {
  const res = await authFetch(`/admin/comercio/${comercioId}/pago`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return res.json();
}

export async function suspenderComercio(id: string) {
  const res = await authFetch(`/admin/comercio/${id}/suspender`, { method: "POST" });
  return res.json();
}

export async function activarComercio(id: string) {
  const res = await authFetch(`/admin/comercio/${id}/activar`, { method: "POST" });
  return res.json();
}

// ---- Pagos self-service pendientes de confirmación ----
export type PagoPendiente = {
  id: string;
  comercio_id: string;
  monto: number;
  moneda: string;
  metodo: string;
  referencia: string | null;
  comprobante_url: string | null;
  created_at: string;
  comercios?: { nombre: string; slug: string } | null;
};

export async function listPagosPendientes(): Promise<PagoPendiente[]> {
  const res = await authFetch("/admin/pagos/pendientes");
  const data = await res.json();
  return data.items as PagoPendiente[];
}

export async function confirmarPago(pagoId: string, meses: number) {
  const res = await authFetch(`/admin/pagos/${pagoId}/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ meses }),
  });
  return res.json();
}

export async function enviarMensajeComercio(comercioId: string, cuerpo: string) {
  const res = await authFetch(`/admin/comercio/${comercioId}/mensaje`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cuerpo }),
  });
  return res.json();
}
