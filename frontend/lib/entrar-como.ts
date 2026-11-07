// «Entrar como este comercio»: un admin con permiso `equipo` abre «Mi comercio» de CUALQUIER negocio con un
// token de comerciante de 30 minutos (POST /admin/comercios/{id}/entrar). Acá viven las piezas PURAS (sin
// window ni imports con alias, para poder probarlas con `npm test`): leer la respuesta, vencimiento, texto del
// aviso fijo y la lista de acciones que el backend rechaza con 403 mientras se entra como admin.

/** Lo que devuelve `POST /admin/comercios/{id}/entrar` (ya validado). */
export type EntradaAdmin = {
  accessToken: string;
  comercio: { id: string; nombre: string; slug: string };
  /** ISO. El token de comerciante dura 30 minutos. */
  expiraEn: string;
  /** Email del admin que entró: queda registrado a su nombre. */
  porAdmin: string;
};

/** Lee y valida la respuesta del endpoint. Lanza si falta algo: sin token o sin vencimiento no se abre la sesión. */
export function leerEntradaAdmin(d: unknown): EntradaAdmin {
  const o = (typeof d === "object" && d !== null ? d : {}) as Record<string, unknown>;
  const c = (typeof o.comercio === "object" && o.comercio !== null ? o.comercio : {}) as Record<string, unknown>;
  const texto = (v: unknown): string => (typeof v === "string" ? v : "");
  const accessToken = texto(o.access_token);
  const id = texto(c.id);
  const expiraEn = texto(o.expira_en);
  if (!accessToken || !id || !Number.isFinite(Date.parse(expiraEn))) {
    throw new Error("La respuesta del servidor no es válida. Probá de nuevo.");
  }
  return {
    accessToken,
    comercio: { id, nombre: texto(c.nombre) || "este comercio", slug: texto(c.slug) },
    expiraEn,
    porAdmin: texto(o.por_admin) || "admin",
  };
}

/** Lo que de la sesión de comerciante importa para esta función. */
export type SesionConEntrada = { id?: string; nombre?: string; porAdmin?: string | null; expiraEn?: string | null };

/** Milisegundos que faltan (0 si ya pasó o la fecha no se entiende). */
export function msRestantes(expiraEn: string | null | undefined, ahora: number): number {
  const t = expiraEn ? Date.parse(expiraEn) : NaN;
  return Number.isFinite(t) ? Math.max(0, t - ahora) : 0;
}

/** Minutos que faltan, redondeando para arriba (a los 20 s todavía se ve «1 min»). */
export function minutosRestantes(expiraEn: string | null | undefined, ahora: number): number {
  return Math.ceil(msRestantes(expiraEn, ahora) / 60000);
}

/** ¿Es una sesión abierta por un admin? */
export function esEntradaAdmin(s: SesionConEntrada | null | undefined): boolean {
  return !!s && typeof s.porAdmin === "string" && s.porAdmin.length > 0;
}

/** ¿Una sesión de admin que ya pasó su hora? Una sesión común (sin vencimiento propio) nunca «vence» acá. */
export function entradaVencida(s: SesionConEntrada | null | undefined, ahora: number): boolean {
  if (!esEntradaAdmin(s)) return false;
  const t = s?.expiraEn ? Date.parse(s.expiraEn) : NaN;
  // Sin vencimiento legible se trata como vencida: no queda una sesión de admin sin reloj.
  return !Number.isFinite(t) || t <= ahora;
}

/** El texto del aviso fijo de arriba. */
export function textoAviso(nombre: string, email: string): string {
  return `Estás dentro de «${nombre}» como admin (${email}). Lo que cambies queda registrado a tu nombre.`;
}

/** «Quedan 12 min» / «Queda menos de 1 min». */
export function textoRestante(minutos: number): string {
  if (minutos <= 1) return "Queda 1 min o menos";
  return `Quedan ${minutos} min`;
}

export const MENSAJE_VENCIDA =
  "Pasaron los 30 minutos de la entrada como admin y la sesión se cerró. Volvé al panel y entrá de nuevo si hace falta.";

/** El 403 que el backend contesta en las acciones que no se pueden hacer entrando como admin. */
export const MENSAJE_NO_DISPONIBLE = "No disponible entrando como admin";

/** ¿El error es ese 403? (se compara sin tildes ni mayúsculas, por si el backend ajusta el texto.) */
export function esBloqueoAdmin(mensaje: unknown): boolean {
  return typeof mensaje === "string" && /no disponible entrando como admin/i.test(mensaje);
}

/** El texto que se le muestra a quien ve ese 403: el del servidor, completado con el porqué. Cualquier otro
 *  mensaje pasa sin tocar. */
export function suavizarBloqueo(mensaje: string): string {
  return esBloqueoAdmin(mensaje)
    ? `${MENSAJE_NO_DISPONIBLE}: esto lo hace el dueño del negocio, no se puede desde una entrada de admin.`
    : mensaje;
}

/** Acciones que el backend rechaza (403) con una sesión de admin. Cada una trae la explicación corta que se
 *  muestra donde estaría el botón. `id` es estable para las pruebas y para los componentes. */
export const ACCIONES_BLOQUEADAS = [
  { id: "clave", nombre: "Generar clave nueva", motivo: "La clave la maneja el dueño: no se genera desde una entrada de admin." },
  { id: "whatsapp", nombre: "Cambiar el número de WhatsApp o recuperar la cuenta", motivo: "El número es la llave de la cuenta: se cambia con el trámite normal." },
  { id: "baja", nombre: "Pedir la baja del comercio", motivo: "La baja la pide el dueño." },
  { id: "pagos", nombre: "Registrar o subir pagos y comprobantes", motivo: "Los pagos los registra el dueño o se cargan desde el panel de admin." },
  { id: "acceso", nombre: "Cambiar el email o la contraseña de ingreso", motivo: "Los datos de ingreso son del dueño." },
] as const;

export type AccionBloqueada = (typeof ACCIONES_BLOQUEADAS)[number]["id"];

/** El texto corto de una acción bloqueada, con el aviso de que es por entrar como admin. */
export function motivoBloqueo(id: AccionBloqueada): string {
  const a = ACCIONES_BLOQUEADAS.find((x) => x.id === id);
  return `${a?.motivo ?? MENSAJE_NO_DISPONIBLE} (${MENSAJE_NO_DISPONIBLE.toLowerCase()}).`;
}

/** Si ya hay una sesión de comerciante en este navegador que esta entrada va a pisar, devuelve el nombre del
 *  negocio para avisar antes. null si no hay sesión, o si ya es una entrada de admin al mismo comercio (se
 *  renueva sin drama). Una sesión real del dueño del MISMO comercio sí se avisa: se pierde. */
export function sesionAjena(actual: SesionConEntrada | null | undefined, comercioId: string): string | null {
  if (!actual || !actual.id) return null;
  if (actual.id === comercioId && esEntradaAdmin(actual)) return null;
  return actual.nombre || "otro negocio";
}
