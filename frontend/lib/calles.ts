/**
 * El mapa de calles recorridas (spec docs/mapa-calles.md): los tipos de lo que
 * manda el backend, cómo se leen sin romper y las cuentas que hace el celular
 * del agente (qué calle pendiente queda más cerca).
 *
 * El servidor decide el estado de cada tramo; acá sólo se dibuja. Todo lo que
 * llega se valida: una capa con un tramo roto no puede tirar abajo el mapa.
 */

/** `parcial` es sólo automático; una marca manual nunca lo produce. */
export type EstadoCalle = "recorrida" | "parcial" | "pendiente" | "sin_comercios";

/** Lo que una persona puede marcar a mano. */
export type EstadoMarca = "recorrida" | "sin_comercios" | "pendiente";

export type PuntoCalle = [number, number];

export type MarcaCalle = {
  estado: EstadoMarca;
  nota: string | null;
  /** Quién marcó. Se muestra al admin; al agente le llega sin el dominio. */
  actor: string | null;
  created_at: string;
};

export type TramoCalle = {
  id: string;
  /** null = la calle no tiene nombre en OpenStreetMap. */
  nombre: string | null;
  tipo: string | null;
  geom: PuntoCalle[];
  longitud_m: number;
  /** 0 a 100: el % de la calle que tiene un comercio a menos de 35 m. */
  cobertura: number;
  estado: EstadoCalle;
  marca: MarcaCalle | null;
  comercios: number;
  /** La carga más reciente sobre el tramo. */
  ultimo: { fecha: string; quien: string | null } | null;
};

export type ResumenCalles = {
  km_total: number;
  km_recorridos: number;
  km_sin_comercios: number;
  /** Lo que queda para recorrer: el total menos las calles «sin comercios».
   *  Es la base del % (así se puede llegar al 100 %). */
  km_a_recorrer: number;
  /** 0 a 100, sobre `km_a_recorrer`. */
  pct: number;
};

export type CapaCalles = { tramos: TramoCalle[]; resumen: ResumenCalles };

export const ESTADOS_CALLE: EstadoCalle[] = ["recorrida", "parcial", "pendiente", "sin_comercios"];

/** Colores de la capa. El mapa base es claro, así que son saturados y oscuros. */
export const COLOR_CALLE: Record<EstadoCalle, string> = {
  recorrida: "#1b9e5a",
  parcial: "#e69a00",
  pendiente: "#e03a3e",
  sin_comercios: "#8791a0",
};

/** Estado = texto + ícono + trazo, no sólo color. */
export const ETIQUETA_CALLE: Record<EstadoCalle, string> = {
  recorrida: "Recorrida",
  parcial: "Parcial",
  pendiente: "Pendiente",
  sin_comercios: "Sin comercios",
};

/** El trazo distingue lo que el color solo no dice (daltonismo, sol en la pantalla). */
export const TRAZO_CALLE: Record<EstadoCalle, string | undefined> = {
  recorrida: undefined,
  parcial: "14 7",
  pendiente: undefined,
  sin_comercios: "3 8",
};

const num = (x: unknown, def = 0): number => (typeof x === "number" && Number.isFinite(x) ? x : def);
const txt = (x: unknown): string | null => (typeof x === "string" && x.trim() ? x.trim() : null);

function estadoDe(x: unknown): EstadoCalle {
  return typeof x === "string" && (ESTADOS_CALLE as string[]).includes(x) ? (x as EstadoCalle) : "pendiente";
}

function geomDe(x: unknown): PuntoCalle[] {
  if (!Array.isArray(x)) return [];
  const r: PuntoCalle[] = [];
  for (const p of x) {
    if (Array.isArray(p) && typeof p[0] === "number" && typeof p[1] === "number" && Number.isFinite(p[0]) && Number.isFinite(p[1])) {
      r.push([p[0], p[1]]);
    }
  }
  return r;
}

function marcaDe(x: unknown): MarcaCalle | null {
  if (!x || typeof x !== "object") return null;
  const m = x as Record<string, unknown>;
  const e = m.estado;
  if (e !== "recorrida" && e !== "sin_comercios" && e !== "pendiente") return null;
  return { estado: e, nota: txt(m.nota), actor: txt(m.actor), created_at: typeof m.created_at === "string" ? m.created_at : "" };
}

/** Lo que contestó el servidor → una capa segura de dibujar. Sin `resumen`, se arma con los tramos. */
export function normalizarCapa(raw: unknown): CapaCalles {
  const o = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>;
  const crudos = Array.isArray(o.tramos) ? o.tramos : [];
  const tramos: TramoCalle[] = [];
  for (const t of crudos) {
    if (!t || typeof t !== "object") continue;
    const r = t as Record<string, unknown>;
    const geom = geomDe(r.geom);
    if (typeof r.id !== "string" || geom.length < 2) continue;
    const u = r.ultimo && typeof r.ultimo === "object" ? (r.ultimo as Record<string, unknown>) : null;
    tramos.push({
      id: r.id, nombre: txt(r.nombre), tipo: txt(r.tipo), geom,
      longitud_m: num(r.longitud_m), cobertura: num(r.cobertura), estado: estadoDe(r.estado),
      marca: marcaDe(r.marca), comercios: num(r.comercios),
      ultimo: u && typeof u.fecha === "string" ? { fecha: u.fecha, quien: txt(u.quien) } : null,
    });
  }
  const s = (o.resumen && typeof o.resumen === "object" ? o.resumen : {}) as Record<string, unknown>;
  const kmTotal = typeof s.km_total === "number" ? s.km_total : tramos.reduce((a, t) => a + t.longitud_m, 0) / 1000;
  const kmRec = typeof s.km_recorridos === "number" ? s.km_recorridos
    : tramos.filter((t) => t.estado === "recorrida").reduce((a, t) => a + t.longitud_m, 0) / 1000;
  const kmSin = typeof s.km_sin_comercios === "number" ? s.km_sin_comercios
    : tramos.filter((t) => t.estado === "sin_comercios").reduce((a, t) => a + t.longitud_m, 0) / 1000;
  const kmARecorrer = typeof s.km_a_recorrer === "number" ? s.km_a_recorrer : Math.max(0, kmTotal - kmSin);
  const pct = typeof s.pct === "number" ? s.pct : (kmARecorrer > 0 ? (kmRec / kmARecorrer) * 100 : 0);
  return { tramos, resumen: { km_total: kmTotal, km_recorridos: kmRec, km_sin_comercios: kmSin, km_a_recorrer: kmARecorrer, pct } };
}

/** El nombre para mostrar. */
export const nombreCalle = (t: TramoCalle): string => t.nombre ?? "Sin nombre";

/** «12,4» — un decimal, con coma como se lee en Bolivia. */
export const kmTxt = (km: number): string => km.toLocaleString("es-BO", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** «62» — sin decimales. */
export const pctTxt = (p: number): string => Math.round(p).toLocaleString("es-BO");

/** Fecha corta para la gente: 14/10/2026. */
export function fechaCalle(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("es-BO", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** De «maria@uruku.bo» queda «maria»: al agente no se le muestra el correo entero. */
export const quienCorto = (q: string | null | undefined): string => (q ?? "").split("@")[0].trim();

/** Metros desde un punto hasta el punto MÁS CERCANO de una línea (no hasta su
 *  centro: una calle larga puede tener la punta a 20 m y el medio a 300).
 *  Plana, igual que `metros` de lib/geo.ts: a esta escala sobra. */
export function distanciaALinea(lat: number, lng: number, geom: PuntoCalle[]): number {
  const kx = 111320 * Math.cos((lat * Math.PI) / 180);
  const ky = 110540;
  let mejor = Infinity;
  for (let i = 0; i < geom.length - 1; i++) {
    const ax = (geom[i][1] - lng) * kx, ay = (geom[i][0] - lat) * ky;
    const bx = (geom[i + 1][1] - lng) * kx, by = (geom[i + 1][0] - lat) * ky;
    const dx = bx - ax, dy = by - ay;
    const l2 = dx * dx + dy * dy;
    // Proyección del origen (el agente) sobre el segmento, acotada a sus extremos.
    const t = l2 === 0 ? 0 : Math.max(0, Math.min(1, -(ax * dx + ay * dy) / l2));
    mejor = Math.min(mejor, Math.hypot(ax + t * dx, ay + t * dy));
  }
  return mejor;
}

export type CalleCerca = { t: TramoCalle; d: number };

/** Las calles en rojo o ámbar más cercanas al agente, para ir a la siguiente. */
export function pendientesCerca(tramos: TramoCalle[], aqui: { lat: number; lng: number }, max = 8): CalleCerca[] {
  const r: CalleCerca[] = [];
  for (const t of tramos) {
    if (t.estado !== "pendiente" && t.estado !== "parcial") continue;
    r.push({ t, d: distanciaALinea(aqui.lat, aqui.lng, t.geom) });
  }
  r.sort((a, b) => a.d - b.d);
  return r.slice(0, max);
}

/** Cuántos tramos y km hay de cada estado: la leyenda. */
export function contarPorEstado(tramos: TramoCalle[]): Record<EstadoCalle, { n: number; km: number }> {
  const r: Record<EstadoCalle, { n: number; km: number }> = {
    recorrida: { n: 0, km: 0 }, parcial: { n: 0, km: 0 }, pendiente: { n: 0, km: 0 }, sin_comercios: { n: 0, km: 0 },
  };
  for (const t of tramos) { r[t.estado].n += 1; r[t.estado].km += t.longitud_m / 1000; }
  return r;
}

/** Aplica una marca a un tramo sin esperar al servidor (que recalcula el estado
 *  automático). `pendiente` vuelve a abrir la calle; lo demás fija el estado. */
export function conMarca(t: TramoCalle, estado: EstadoMarca, nota: string | null, actor: string | null): TramoCalle {
  return {
    ...t,
    estado,
    marca: { estado, nota, actor, created_at: new Date().toISOString() },
  };
}
