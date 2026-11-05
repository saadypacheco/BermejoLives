// Lógica pura de «Teléfonos en fotos» (docs/telefonos-en-fotos.md): tipos del contrato,
// armado del pedido, reglas de qué filas entran al lote, lectura defensiva de las
// respuestas y textos del panel. Sin red ni React, para poder probarla con `npm test`.
// El cliente HTTP (que usa `authFetch`) vive en `lib/telefonos-detectados.ts`.

/* ─── Contrato de la API (docs/telefonos-en-fotos.md › API) ─────────────── */

export type EstadoTelefono =
  | "pendiente" | "coincide" | "aplicado_whatsapp" | "aplicado_telefono" | "descartado";

export type TipoTelefono = "celular" | "fijo";

export type ComercioDeTelefono = {
  id: string;
  nombre: string;
  slug: string;
  whatsapp: string | null;
  telefono: string | null;
  ciudad: string | null;
};

export type TelefonoDetectado = {
  id: string;
  comercio: ComercioDeTelefono;
  /** E.164 (+591…, +54…). */
  numero: string;
  /** El mismo número como se lee en voz alta («+591 7xx xx xxx»). */
  numero_visible: string;
  tipo: TipoTelefono;
  texto_leido: string;
  foto_url: string;
  motor: string;
  estado: EstadoTelefono;
  compartido: boolean;
  /** En cuántos comercios más aparece el mismo número. */
  otros_comercios: number;
};

export type PaginaTelefonos = { items: TelefonoDetectado[]; total: number };

export type ResumenTelefonos = {
  escaneadas: number;
  pendientes_de_escanear: number;
  numeros: number;
  sin_whatsapp_con_numero: number;
  motor_activo: string;
  worker: boolean | string | null;
};

export type ComoAplicar = "whatsapp" | "telefono";

export type SaltadoLote = { id: string; motivo: string };
export type ResultadoLote = { aplicados: string[]; saltados: SaltadoLote[] };

export type FiltroTelefonos = {
  /** Slug de la ciudad; null = todas. */
  ciudad: string | null;
  /** "" = todos los estados. */
  estado: EstadoTelefono | "";
  sinWhatsapp: boolean;
  limit: number;
  offset: number;
};

/** El backend acepta hasta 100 ids por lote. */
export const MAX_LOTE = 100;
export const TAMANO_PAGINA = 50;

/* ─── Textos ─────────────────────────────────────────────────────────────── */

export const ESTADO_LABEL: Record<EstadoTelefono, string> = {
  pendiente: "Pendiente",
  coincide: "Coincide con la ficha",
  aplicado_whatsapp: "Usado como WhatsApp",
  aplicado_telefono: "Usado como teléfono",
  descartado: "Descartado",
};

/** Opciones del filtro «Estado» (el primero es el de entrada). */
export const ESTADOS_FILTRO: ReadonlyArray<{ valor: EstadoTelefono | ""; label: string }> = [
  { valor: "pendiente", label: "Pendientes" },
  { valor: "coincide", label: "Coinciden con la ficha" },
  { valor: "aplicado_whatsapp", label: "Usados como WhatsApp" },
  { valor: "aplicado_telefono", label: "Usados como teléfono" },
  { valor: "descartado", label: "Descartados" },
  { valor: "", label: "Todos" },
];

const MOTIVOS_LOTE: Record<string, string> = {
  tiene_whatsapp: "El comercio ya tiene WhatsApp",
  con_whatsapp: "El comercio ya tiene WhatsApp",
  ya_tiene_whatsapp: "El comercio ya tiene WhatsApp",
  compartido: "El número aparece en varios comercios",
  no_celular: "Es un teléfono fijo, no un celular",
  fijo: "Es un teléfono fijo, no un celular",
  no_pendiente: "Ya estaba resuelto",
  ya_resuelto: "Ya estaba resuelto",
  no_encontrado: "Ya no existe en la lista",
  inexistente: "Ya no existe en la lista",
  inactivo: "El comercio está dado de baja",
  comercio_inactivo: "El comercio está dado de baja",
  sin_permiso: "No tenés permiso para ese comercio",
  fuera_de_ciudad: "Es de una ciudad que no te toca",
  otra_ciudad: "Es de una ciudad que no te toca",
  no_existe: "Ya no existe en la lista o el comercio está de baja",
  numero_en_uso: "Ese número ya es de otro negocio",
  whatsapp_invalido: "No es un WhatsApp válido",
  error: "No se pudo guardar",
};

/** El motivo de un salto, en castellano. Un motivo que no conocemos se muestra tal
 *  cual (si el backend ya manda una frase) o con los guiones bajos como espacios. */
export function motivoLegible(motivo: string | null | undefined): string {
  const m = (motivo ?? "").trim();
  if (!m) return "No se aplicó";
  const conocido = MOTIVOS_LOTE[m.toLowerCase()];
  if (conocido) return conocido;
  const llano = m.replace(/_/g, " ");
  return llano.charAt(0).toUpperCase() + llano.slice(1);
}

/** «Lector gratis» o «Gemini · tiene costo». El backend dice el motor activo
 *  (`tesseract` / `gemini`); lo que no entendemos se muestra tal cual y sin tono de costo. */
export function motorActivoLabel(motor: string | null | undefined): { texto: string; costo: boolean } {
  const m = (motor ?? "").trim().toLowerCase();
  if (!m) return { texto: "Sin dato del lector", costo: false };
  if (m.includes("gemini")) return { texto: "Gemini · tiene costo", costo: true };
  if (m.includes("tesseract") || m.includes("gratis") || m.includes("local")) return { texto: "Lector gratis", costo: false };
  return { texto: motor as string, costo: false };
}

export function textoWorker(worker: ResumenTelefonos["worker"]): string | null {
  if (worker === true) return "Lector automático prendido";
  if (worker === false) return "Lector automático apagado";
  if (typeof worker === "string" && worker.trim()) return worker.trim();
  return null;
}

/** El número que se muestra grande: el legible si vino, si no el E.164. */
export function numeroParaMostrar(t: Pick<TelefonoDetectado, "numero" | "numero_visible">): string {
  return t.numero_visible?.trim() || t.numero;
}

/** «Compartido con 5 comercios» (otros_comercios + el propio). */
export function textoCompartido(t: Pick<TelefonoDetectado, "otros_comercios">): string {
  const n = Math.max(1, t.otros_comercios) + 1;
  return `Compartido con ${n} comercios`;
}

/* ─── Pedido ─────────────────────────────────────────────────────────────── */

/** La query del listado. Lo vacío no se manda (ciudad null = todas; estado "" = todos). */
export function construirQuery(f: FiltroTelefonos): string {
  const p = new URLSearchParams();
  if (f.ciudad) p.set("ciudad", f.ciudad);
  if (f.estado) p.set("estado", f.estado);
  if (f.sinWhatsapp) p.set("sin_whatsapp", "true");
  p.set("limit", String(f.limit));
  p.set("offset", String(Math.max(0, f.offset)));
  return p.toString();
}

/** Parte la selección en tandas de a lo sumo `max` ids (el backend rechaza más de 100). */
export function partirEnLotes(ids: readonly string[], max: number = MAX_LOTE): string[][] {
  const unicos = Array.from(new Set(ids));
  const out: string[][] = [];
  for (let i = 0; i < unicos.length; i += max) out.push(unicos.slice(i, i + max));
  return out;
}

export function unirResultadosLote(partes: readonly ResultadoLote[]): ResultadoLote {
  return {
    aplicados: partes.flatMap((p) => p.aplicados),
    saltados: partes.flatMap((p) => p.saltados),
  };
}

/* ─── Reglas de la fila ──────────────────────────────────────────────────── */

function vacio(v: string | null | undefined): boolean {
  return !v || !v.trim();
}

/** ¿Se resuelve todavía? (pendiente o ya coincidente se puede tocar; lo aplicado o descartado no). */
export function esAccionable(t: Pick<TelefonoDetectado, "estado">): boolean {
  return t.estado === "pendiente";
}

/** La regla del lote del backend, para marcar sólo lo que sirve: comercio SIN
 *  WhatsApp, número celular, no compartido, y todavía pendiente. */
export function puedeEnLote(t: TelefonoDetectado): boolean {
  return esAccionable(t) && t.tipo === "celular" && !t.compartido && vacio(t.comercio.whatsapp);
}

export function idsDelLote(items: readonly TelefonoDetectado[], marcados: ReadonlySet<string>): string[] {
  return items.filter((t) => marcados.has(t.id) && puedeEnLote(t)).map((t) => t.id);
}

export function alternar(marcados: ReadonlySet<string>, id: string): Set<string> {
  const n = new Set(marcados);
  if (n.has(id)) n.delete(id); else n.add(id);
  return n;
}

/** Marca (o desmarca) todas las filas que entran al lote. */
export function alternarTodos(items: readonly TelefonoDetectado[], marcados: ReadonlySet<string>): Set<string> {
  const validos = items.filter(puedeEnLote).map((t) => t.id);
  const todos = validos.length > 0 && validos.every((id) => marcados.has(id));
  return todos ? new Set() : new Set(validos);
}

/** Lo que ya tiene el comercio en el campo donde se quiere escribir. null = vacío. */
export function valorActual(t: Pick<TelefonoDetectado, "comercio">, como: ComoAplicar): string | null {
  const v = como === "whatsapp" ? t.comercio.whatsapp : t.comercio.telefono;
  return vacio(v) ? null : (v as string).trim();
}

export function campoLabel(como: ComoAplicar): string {
  return como === "whatsapp" ? "WhatsApp" : "teléfono";
}

/** La pregunta cuando el backend contesta 409 (el comercio ya tenía otro valor). */
export function preguntaReemplazo(t: TelefonoDetectado, como: ComoAplicar): string {
  const actual = valorActual(t, como);
  const donde = campoLabel(como);
  return actual
    ? `${t.comercio.nombre} ya tiene este ${donde}: ${actual}. ¿Reemplazar por ${numeroParaMostrar(t)}?`
    : `${t.comercio.nombre} ya tiene otro ${donde}. ¿Reemplazar por ${numeroParaMostrar(t)}?`;
}

export function esConflicto(ex: unknown): boolean {
  return typeof ex === "object" && ex !== null && (ex as { status?: unknown }).status === 409;
}

export function mensajeDeError(ex: unknown, porDefecto: string): string {
  if (ex instanceof Error && ex.message.trim()) return ex.message;
  return porDefecto;
}

/** La fila después de aplicarse: el estado nuevo y, en el comercio, el valor que quedó. */
export function filaAplicada(t: TelefonoDetectado, como: ComoAplicar): TelefonoDetectado {
  return {
    ...t,
    estado: como === "whatsapp" ? "aplicado_whatsapp" : "aplicado_telefono",
    comercio: como === "whatsapp"
      ? { ...t.comercio, whatsapp: t.numero }
      : { ...t.comercio, telefono: t.numero },
  };
}

export function filaDescartada(t: TelefonoDetectado): TelefonoDetectado {
  return { ...t, estado: "descartado" };
}

/** Aplica el resultado de un lote a la lista cargada: los aplicados pasan a «Usado como WhatsApp». */
export function aplicarResultadoALista(items: readonly TelefonoDetectado[], r: ResultadoLote): TelefonoDetectado[] {
  const hechos = new Set(r.aplicados);
  return items.map((t) => (hechos.has(t.id) ? filaAplicada(t, "whatsapp") : t));
}

/** «Se usaron 12 como WhatsApp. Se saltaron 3.» */
export function resumenLoteTexto(r: ResultadoLote): string {
  const a = r.aplicados.length;
  const s = r.saltados.length;
  const partes: string[] = [];
  partes.push(a === 1 ? "Se usó 1 número como WhatsApp." : `Se usaron ${a} números como WhatsApp.`);
  if (s > 0) partes.push(s === 1 ? "Se saltó 1." : `Se saltaron ${s}.`);
  return partes.join(" ");
}

/* ─── Paginación ─────────────────────────────────────────────────────────── */

export function rangoPagina(offset: number, cantidad: number, total: number): { desde: number; hasta: number; hayAnterior: boolean; haySiguiente: boolean } {
  if (cantidad <= 0 || total <= 0) return { desde: 0, hasta: 0, hayAnterior: offset > 0, haySiguiente: false };
  const hasta = offset + cantidad;
  return { desde: offset + 1, hasta, hayAnterior: offset > 0, haySiguiente: hasta < total };
}

/* ─── Lectura defensiva de las respuestas ────────────────────────────────── */

function esObjeto(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function texto(v: unknown, def = ""): string {
  return typeof v === "string" ? v : def;
}
function textoONull(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}
function entero(v: unknown, def = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? Math.trunc(v) : def;
}

const ESTADOS: readonly EstadoTelefono[] = ["pendiente", "coincide", "aplicado_whatsapp", "aplicado_telefono", "descartado"];

function filaDe(raw: unknown): TelefonoDetectado | null {
  if (!esObjeto(raw)) return null;
  const id = texto(raw.id);
  const numero = texto(raw.numero);
  const c = esObjeto(raw.comercio) ? raw.comercio : null;
  if (!id || !numero || !c) return null;
  const estado = ESTADOS.find((e) => e === raw.estado) ?? "pendiente";
  return {
    id,
    comercio: {
      id: texto(c.id), nombre: texto(c.nombre, "Comercio sin nombre"), slug: texto(c.slug),
      whatsapp: textoONull(c.whatsapp), telefono: textoONull(c.telefono), ciudad: textoONull(c.ciudad),
    },
    numero,
    numero_visible: texto(raw.numero_visible, numero),
    tipo: raw.tipo === "fijo" ? "fijo" : "celular",
    texto_leido: texto(raw.texto_leido),
    foto_url: texto(raw.foto_url),
    motor: texto(raw.motor),
    estado,
    compartido: raw.compartido === true,
    otros_comercios: entero(raw.otros_comercios),
  };
}

/** Una respuesta rara (sin `items`, filas rotas) da una lista vacía, no una pantalla caída. */
export function normalizarPagina(raw: unknown): PaginaTelefonos {
  const o = esObjeto(raw) ? raw : {};
  const items = (Array.isArray(o.items) ? o.items : []).map(filaDe).filter((x): x is TelefonoDetectado => x !== null);
  return { items, total: Math.max(entero(o.total, items.length), items.length) };
}

export function normalizarResumen(raw: unknown): ResumenTelefonos {
  const o = esObjeto(raw) ? raw : {};
  const w = o.worker;
  return {
    escaneadas: entero(o.escaneadas),
    pendientes_de_escanear: entero(o.pendientes_de_escanear),
    numeros: entero(o.numeros),
    sin_whatsapp_con_numero: entero(o.sin_whatsapp_con_numero),
    motor_activo: texto(o.motor_activo),
    worker: typeof w === "boolean" || typeof w === "string" ? w : null,
  };
}

/** `saltados` puede venir como [{id, motivo}] o, por descuido, como ids sueltos. */
export function normalizarLote(raw: unknown): ResultadoLote {
  const o = esObjeto(raw) ? raw : {};
  const aplicados = (Array.isArray(o.aplicados) ? o.aplicados : [])
    .map((a) => (typeof a === "string" ? a : esObjeto(a) ? texto(a.id) : ""))
    .filter(Boolean);
  const saltados = (Array.isArray(o.saltados) ? o.saltados : [])
    .map((s): SaltadoLote | null => {
      if (typeof s === "string") return { id: s, motivo: "" };
      if (esObjeto(s) && texto(s.id)) return { id: texto(s.id), motivo: texto(s.motivo) };
      return null;
    })
    .filter((x): x is SaltadoLote => x !== null);
  return { aplicados, saltados };
}
