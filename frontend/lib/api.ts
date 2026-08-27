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

/** Lee `items` de una respuesta de lista.
 *
 * Existe porque el patrón `(await res.json()).items` es una trampa: ante un 500
 * el cuerpo es {"detail": "..."}, así que `items` viene undefined y la función
 * devuelve undefined SIN lanzar. El catch del componente nunca corre, el estado
 * queda en undefined y el primer `.filter()` tira abajo el panel entero — que
 * es exactamente lo que pasó. Acá se falla fuerte y con mensaje.
 */
async function itemsDe<T>(res: Response, que: string): Promise<T[]> {
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? `No se pudo cargar ${que} (HTTP ${res.status})`);
  }
  const data = await res.json().catch(() => ({}));
  return (data.items ?? []) as T[];
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
  // En qué se apoyó la atribución: 'numero' (remitente ya asociado al comercio),
  // 'codigo' (número desconocido + código del local en el mensaje) o 'desconocido'.
  identidad_origen?: string | null;
  codigo_recibido?: string | null;
};

export async function listPendientes(estado = "pendiente"): Promise<PendingPub[]> {
  const res = await authFetch(`/moderacion/publicaciones?estado=${estado}`);
  return itemsDe<PendingPub>(res, "las publicaciones");
}

export async function moderar(id: string, estado: string, motivo?: string) {
  const res = await authFetch(`/moderacion/publicaciones/${id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ estado, motivo }),
  });
  return res.json();
}

export type VeredictoIA = {
  veredicto: "aprobar" | "rechazar" | "dudoso";
  motivo: string;
  confianza: number;
};

/** Asistente IA: sugiere aprobar/rechazar/dudoso. No decide — el moderador confirma. */
export async function revisarConIA(
  id: string,
  titulo: string,
  descripcion: string | null,
): Promise<VeredictoIA> {
  const res = await authFetch(`/moderacion/publicaciones/${id}/revisar-ia`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo, descripcion }),
  });
  return res.json();
}

export type ComercioPorVerificar = {
  id: string;
  nombre: string;
  slug: string;
  whatsapp: string | null;
  telefono: string | null;
  modalidad: string;
  descripcion: string | null;
  prod_obs_human: string | null;
  prod_det_ia: string | null;
  subcategoria: string | null;
  codigo: string | null;
  direccion: string | null;
  lat: number | null;
  lng: number | null;
  portada_url: string | null;
  portada_thumb_url: string | null;
  cargado_por: string | null;
  verificado: boolean;
  suspendido: boolean;
  paga_hasta: string | null;
  created_at: string;
  lugar_id: string | null;
  puesto: string | null;
  rubros?: { nombre: string; slug: string };
  ciudades?: { nombre: string; slug: string };
  lugares?: { nombre: string; tipo: string; lat: number | null; lng: number | null; portada_thumb_url?: string | null } | null;
};

export async function listComerciosPorVerificar(): Promise<ComercioPorVerificar[]> {
  const res = await authFetch(`/moderacion/comercios?verificado=false`);
  return itemsDe<ComercioPorVerificar>(res, "los comercios por verificar");
}

export async function listTodosComercios(): Promise<ComercioPorVerificar[]> {
  const res = await authFetch(`/moderacion/comercios?todos=true`);
  return itemsDe<ComercioPorVerificar>(res, "los comercios");
}

export async function editarComercio(id: string, patch: Record<string, unknown>) {
  const res = await authFetch(`/admin/comercio/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return res.json();
}

/** Igual que `itemsDe` pero para acciones: `authFetch` sólo lanza en 401, así que
 *  un 404/500 devolvía {"detail": "..."} sin lanzar y el catch del componente
 *  nunca corría — el error del server quedaba invisible y la UI mentía. */
async function okDe(res: Response, que: string) {
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? `No se pudo ${que} (HTTP ${res.status})`);
  }
  return res.json().catch(() => ({}));
}

export async function verificarComercio(id: string) {
  const res = await authFetch(`/moderacion/comercios/${id}/verificar`, { method: "POST" });
  return okDe(res, "verificar el negocio");
}

export async function rechazarComercio(id: string) {
  const res = await authFetch(`/moderacion/comercios/${id}/rechazar`, { method: "POST" });
  return okDe(res, "rechazar el negocio");
}

// ── Lugares (mercados / galerías / referencias): ABM desde el admin ──────────
export type LugarAdmin = {
  id: string; nombre: string; tipo: string; lat: number | null; lng: number | null;
  n_comercios?: number; portada_thumb_url?: string | null; video_url?: string | null;
  poligono?: [number, number][] | null;
};

export async function adminListLugares(ciudadSlug = "bermejo"): Promise<LugarAdmin[]> {
  const res = await authFetch(`/admin/lugares?ciudad_slug=${encodeURIComponent(ciudadSlug)}`);
  const items = await itemsDe<LugarAdmin & { comercios?: { count: number }[] }>(res, "los lugares");
  return items.map((l) => ({ ...l, n_comercios: l.comercios?.[0]?.count ?? 0 }));
}

export async function adminCrearLugar(body: { nombre: string; tipo?: string; ciudad_slug?: string; lat?: number | null; lng?: number | null }): Promise<LugarAdmin> {
  const res = await authFetch(`/admin/lugares`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return (await res.json()).lugar as LugarAdmin;
}

export async function adminUpdateLugar(id: string, body: { nombre?: string; tipo?: string; lat?: number | null; lng?: number | null; poligono?: [number, number][] }): Promise<LugarAdmin> {
  const res = await authFetch(`/admin/lugares/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return (await res.json()).lugar as LugarAdmin;
}

export async function adminDeleteLugar(id: string): Promise<void> {
  await authFetch(`/admin/lugares/${id}`, { method: "DELETE" });
}

// ── Catálogo: qué hay cargado y qué falta ───────────────────────────────────
export type Catalogo = {
  comercios: number;
  rubros: { slug: string; nombre: string; comercios: number; descarte: boolean }[];
  rubros_vacios: number;
  productos: { termino: string; comercios: number }[];
  productos_distintos: number;
  productos_unicos: number;
  buscado_sin_resultado: { query: string; n: number }[];
};

export async function adminCatalogo(): Promise<Catalogo> {
  const res = await authFetch(`/admin/catalogo`);
  if (!res.ok) throw new Error("No se pudo cargar el catálogo");
  return res.json();
}

// ── Adornos del mapa (chalanas y lapachos) ──────────────────────────────────
// Pura decoración: no son comercios, no se buscan y no reciben clics. Dónde va
// cada uno hay que decidirlo conociendo la ciudad, así que se marcan haciendo
// clic en el mapa desde el admin en vez de quedar fijos en el código.
export type AdornoAdmin = {
  id: string; tipo: "chalana" | "lapacho" | "bandera";
  /** Sólo para banderas: cuál ('ar', 'bo', …). Ver BANDERAS en lib/adornos.ts. */
  variante?: string | null;
  lat: number; lng: number; giro?: number | null; escala?: number | null;
};

export async function adminListAdornos(ciudadSlug = "bermejo"): Promise<AdornoAdmin[]> {
  const res = await authFetch(`/admin/adornos?ciudad_slug=${encodeURIComponent(ciudadSlug)}`);
  return itemsDe<AdornoAdmin>(res, "los adornos");
}

export async function adminCrearAdorno(body: { tipo: string; lat: number; lng: number; giro?: number; escala?: number; variante?: string | null }): Promise<AdornoAdmin> {
  const res = await authFetch(`/admin/adornos`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return (await res.json()).adorno as AdornoAdmin;
}

export async function adminUpdateAdorno(id: string, body: { tipo?: string; lat?: number; lng?: number; giro?: number; escala?: number; variante?: string | null }): Promise<AdornoAdmin> {
  const res = await authFetch(`/admin/adornos/${id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  return (await res.json()).adorno as AdornoAdmin;
}

export async function adminDeleteAdorno(id: string): Promise<void> {
  await authFetch(`/admin/adornos/${id}`, { method: "DELETE" });
}

// ── Suscripciones ──────────────────────────────────────────────────────────

export type EstadoSuscripcion = "activo" | "por_vencer" | "vencido" | "suspendido" | "sin_plan";

export type ComercioSuscripcion = {
  id: string;
  slug: string;
  nombre: string;
  whatsapp: string;
  verificado: boolean;
  confiable?: boolean;
  plan?: string;
  codigo?: string | null;
  suspendido: boolean;
  paga_hasta: string | null;
  suscripcion_estado: EstadoSuscripcion;
  created_at: string;
};

export async function listSuscripciones(): Promise<ComercioSuscripcion[]> {
  const res = await authFetch("/admin/suscripciones");
  return itemsDe<ComercioSuscripcion>(res, "las suscripciones");
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

export type Kpis = {
  top_busquedas: { query: string; n: number }[];
  sin_resultado: { query: string; n: number }[];
  top_comercios: { comercio_id: string; nombre: string; slug: string | null; eventos: number }[];
  monetizacion: { comercios_activos: number; pagando: number; gratis: number };
};
export async function getKpis(): Promise<Kpis> {
  const res = await authFetch("/admin/kpis");
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
  return itemsDe<Reclamo>(res, "los reclamos");
}

export async function responderReclamo(id: string, respuesta: string) {
  const res = await authFetch(`/admin/reclamos/${id}/responder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ respuesta }),
  });
  return res.json();
}

// ---- Solicitudes de cambio de número (cuenta sin email/pass, perdió el celu) ----
export type SolicitudCambioNumero = {
  id: string;
  comercio_id: string;
  whatsapp_nuevo: string;
  foto_url: string | null;
  lat: number | null;
  lng: number | null;
  mensaje: string | null;
  estado: "pendiente" | "aprobada" | "rechazada";
  created_at: string;
  comercios?: { nombre: string; slug: string; portada_url: string | null; whatsapp: string } | null;
};

export async function listSolicitudesCambioNumero(estado?: string): Promise<SolicitudCambioNumero[]> {
  const res = await authFetch(`/admin/solicitudes-cambio-numero${estado ? `?estado=${estado}` : ""}`);
  return itemsDe<SolicitudCambioNumero>(res, "las solicitudes de cambio de número");
}

export async function aprobarSolicitudCambioNumero(id: string) {
  const res = await authFetch(`/admin/solicitudes-cambio-numero/${id}/aprobar`, { method: "POST" });
  return res.json();
}

export async function rechazarSolicitudCambioNumero(id: string) {
  const res = await authFetch(`/admin/solicitudes-cambio-numero/${id}/rechazar`, { method: "POST" });
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
  return itemsDe<ConsultaReservalo>(res, "las consultas de Reservalo");
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

export type PropuestaIA = {
  productos: string;
  descripcion: string;
  subcategoria: string;
  rubro_slugs: string[];
  confianza: number;
  fotos_analizadas: number;
  error?: string;
  slugs_descartados?: string[];
  /** Respuesta textual del modelo. Distingue "no vio nada" de "la llamada falló". */
  crudo?: string;
  /** Consumo real de esta llamada, para ver el costo por comercio. */
  tokens?: { entrada: number | null; salida: number | null; total: number | null };
};

export type AnalisisIA = {
  comercio: { slug: string; nombre: string; prod_obs_human: string | null };
  fotos_disponibles: number;
  propuesta: PropuestaIA;
  aplicado: boolean;
};

/** aplicar=false devuelve la propuesta sin escribir nada. */
export async function analizarComercio(comercioId: string, aplicar = false): Promise<AnalisisIA> {
  const res = await authFetch(`/admin/comercio/${comercioId}/analizar?aplicar=${aplicar}`, { method: "POST" });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo analizar");
  }
  return res.json();
}

export type ResultadoTanda = {
  slug: string; nombre: string; confianza: number; productos: string;
  subcategoria: string; rubros: string[]; tokens: number | null;
  error?: string; aplicado?: boolean;
};

export type Tanda = {
  procesados: number;
  restantes: number;
  resultados: ResultadoTanda[];
  sin_mas: boolean;
};

export async function pendientesAnalisis(): Promise<number> {
  const res = await authFetch("/admin/comercios/pendientes-analisis");
  if (!res.ok) throw new Error("No se pudo consultar los pendientes");
  return (await res.json()).pendientes ?? 0;
}

export async function analizarTanda(limite = 3, aplicar = true): Promise<Tanda> {
  const res = await authFetch(
    `/admin/comercios/analizar-tanda?limite=${limite}&aplicar=${aplicar}`, { method: "POST" });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo analizar la tanda");
  }
  return res.json();
}

export type FotoComercio = { id: string; url: string; thumb_url: string | null };

export async function adminListarFotos(comercioId: string): Promise<FotoComercio[]> {
  const res = await authFetch(`/admin/comercio/${comercioId}/fotos`);
  return (await res.json()).items ?? [];
}

export async function adminSubirFoto(comercioId: string, file: File): Promise<FotoComercio> {
  const fd = new FormData();
  fd.append("foto", file);
  const res = await authFetch(`/admin/comercio/${comercioId}/fotos`, { method: "POST", body: fd });
  if (!res.ok) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.detail ?? "No se pudo subir la foto");
  }
  return (await res.json()).foto as FotoComercio;
}

export async function adminBorrarFoto(comercioId: string, fotoId: string): Promise<void> {
  await authFetch(`/admin/comercio/${comercioId}/fotos/${fotoId}`, { method: "DELETE" });
}

export async function setConfiable(comercioId: string, confiable: boolean) {
  const res = await authFetch(`/admin/comercio/${comercioId}/confiable`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ confiable }),
  });
  return res.json();
}

export type NumeroComercio = {
  id: string; numero: string; etiqueta: string | null; created_by?: string | null;
};

export async function listarNumeros(comercioId: string): Promise<{ items: NumeroComercio[] }> {
  const res = await authFetch(`/admin/comercio/${comercioId}/numeros`);
  return res.json();
}

export async function agregarNumero(comercioId: string, numero: string, etiqueta?: string) {
  const res = await authFetch(`/admin/comercio/${comercioId}/numeros`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ numero, etiqueta: etiqueta || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "No se pudo autorizar el número");
  }
  return res.json();
}

// El grupo de WhatsApp por el que el comerciante manda sus ofertas.
export type GrupoComercio = {
  grupo_jid: string; nombre: string | null; origen: string;
  created_at?: string; created_by?: string | null;
};

export async function listarGrupos(comercioId: string): Promise<{ items: GrupoComercio[] }> {
  const res = await authFetch(`/admin/comercio/${comercioId}/grupos`);
  return res.json();
}

export async function atarGrupo(comercioId: string, grupoJid: string, nombre?: string) {
  const res = await authFetch(`/admin/comercio/${comercioId}/grupos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ grupo_jid: grupoJid, nombre: nombre || null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "No se pudo atar el grupo");
  }
  return res.json();
}

export async function soltarGrupo(comercioId: string, grupoJid: string) {
  const res = await authFetch(
    `/admin/comercio/${comercioId}/grupos/${encodeURIComponent(grupoJid)}`,
    { method: "DELETE" });
  if (!res.ok) throw new Error("No se pudo soltar el grupo");
  return res.json();
}

// Comercios traídos de fuentes externas (OpenStreetMap). NO son comercios de
// URUKU: son una lista de qué existe y dónde, que pasa al mapa de a uno.
export type ComercioImportado = {
  id: string; fuente: string; fuente_id: string; nombre: string | null;
  categoria: string | null; rubro_slug: string | null;
  lat: number | null; lng: number | null;
  telefono: string | null; whatsapp: string | null; website: string | null;
  horario: string | null; direccion: string | null;
  estado: "nuevo" | "promovido" | "descartado";
  duplicado_de: string | null; comercio_id: string | null; motivo: string | null;
};

export async function listarImportados(
  estado = "nuevo", q?: string, ciudadId?: string,
): Promise<{ items: ComercioImportado[]; total: number; resumen: { ciudad_id: string | null; estado: string; n: number }[] }> {
  const p = new URLSearchParams({ estado });
  if (q) p.set("q", q);
  if (ciudadId) p.set("ciudad_id", ciudadId);
  const res = await authFetch(`/admin/importados?${p}`);
  return res.json();
}

export async function promoverImportado(
  id: string, body: { nombre?: string; rubro_slug?: string; whatsapp?: string },
) {
  const res = await authFetch(`/admin/importados/${id}/promover`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({}));
    throw new Error(e.detail || "No se pudo promover");
  }
  return res.json();
}

export async function descartarImportado(id: string, motivo: string) {
  const res = await authFetch(
    `/admin/importados/${id}/descartar?motivo=${encodeURIComponent(motivo)}`, { method: "POST" });
  if (!res.ok) throw new Error("No se pudo descartar");
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
  return itemsDe<PagoPendiente>(res, "los pagos pendientes");
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
