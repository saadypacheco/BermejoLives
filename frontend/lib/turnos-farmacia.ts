/**
 * Farmacias de turno (spec docs/farmacias-de-turno.md).
 *
 * En Bolivia el turno farmacéutico dura 24 horas: de las 08:00 del día
 * indicado a las 08:00 del día siguiente (DS 25235, art. 74). La base guarda
 * `inicio` y `fin` como timestamptz, así que «de turno ahora» es comparar
 * instantes: `inicio <= ahora < fin`. No depende de la hora del aparato ni de
 * la del servidor (que corre en UTC).
 *
 * Lo que SÍ necesita la hora de Bolivia es mostrarla («hasta mañana 08:00») y
 * decidir qué día es «hoy» para los próximos turnos. Bolivia es UTC−4 todo el
 * año, sin horario de verano, así que alcanza con un corrimiento fijo y no hace
 * falta `Intl` (que en un navegador sin husos fallaría).
 *
 * Este archivo no toca la base: son sólo funciones puras y tipos. La consulta
 * vive en `lib/data.ts` (`getTurnosFarmacia`).
 */

/** La farmacia, con las columnas del comercio que ya son públicas. */
export type FarmaciaTurno = {
  id: string; slug: string; nombre: string;
  direccion: string | null; telefono: string | null; whatsapp: string | null;
  lat: number | null; lng: number | null; portada_thumb_url: string | null;
};

export type TurnoFarmacia = {
  id: string;
  comercio_id: string;
  /** El día en que EMPIEZA el turno (YYYY-MM-DD, día de Bolivia). */
  fecha: string;
  /** timestamptz ISO. */
  inicio: string;
  fin: string;
  comercios: FarmaciaTurno | null;
};

const MS_HORA = 3600 * 1000;
const MS_DIA = 24 * MS_HORA;
/** Bolivia = UTC−4, sin horario de verano. */
const OFFSET_BOLIVIA_MS = -4 * MS_HORA;

/** El reloj de Bolivia como un Date en UTC: los `getUTC*` devuelven la hora de allá. */
function relojBolivia(base: Date): Date {
  return new Date(base.getTime() + OFFSET_BOLIVIA_MS);
}

/** La fecha de hoy en Bolivia, como `YYYY-MM-DD`. */
export function fechaBolivia(base: Date = new Date()): string {
  return relojBolivia(base).toISOString().slice(0, 10);
}

/** Suma días a una fecha `YYYY-MM-DD` (sin husos: es aritmética de calendario). */
export function sumarDias(fecha: string, dias: number): string {
  const [a, m, d] = fecha.split("-").map(Number);
  return new Date(Date.UTC(a, m - 1, d + dias)).toISOString().slice(0, 10);
}

/** El rango a pedir a la base para tener el turno vigente y los próximos `dias`.
 *  `desde` es AYER: a las 03:00 de Bolivia el turno vigente es el de ayer. */
export function rangoTurnos(ahora: Date = new Date(), dias = 8): { desde: string; hasta: string } {
  const hoy = fechaBolivia(ahora);
  return { desde: sumarDias(hoy, -1), hasta: sumarDias(hoy, dias) };
}

/** ¿Está de turno en este instante? `inicio <= ahora < fin`. */
export function estaDeTurno(t: Pick<TurnoFarmacia, "inicio" | "fin">, ahora: Date = new Date()): boolean {
  const ms = ahora.getTime();
  return Date.parse(t.inicio) <= ms && ms < Date.parse(t.fin);
}

/** Los turnos vigentes ahora (normalmente dos farmacias), en orden de nombre. */
export function turnosAhora(turnos: TurnoFarmacia[], ahora: Date = new Date()): TurnoFarmacia[] {
  return turnos
    .filter((t) => t.comercios && estaDeTurno(t, ahora))
    .sort((a, b) => (a.comercios?.nombre ?? "").localeCompare(b.comercios?.nombre ?? "", "es"));
}

/** Los turnos que todavía no empezaron, del más próximo al más lejano. */
export function turnosFuturos(turnos: TurnoFarmacia[], ahora: Date = new Date()): TurnoFarmacia[] {
  return turnos
    .filter((t) => Date.parse(t.inicio) > ahora.getTime())
    .sort((a, b) => Date.parse(a.inicio) - Date.parse(b.inicio));
}

/** Los turnos futuros agrupados por día de inicio, hasta `dias` días desde hoy. */
export function proximosPorDia(turnos: TurnoFarmacia[], ahora: Date = new Date(), dias = 7): { fecha: string; turnos: TurnoFarmacia[] }[] {
  const tope = sumarDias(fechaBolivia(ahora), dias);
  const grupos = new Map<string, TurnoFarmacia[]>();
  for (const t of turnosFuturos(turnos, ahora)) {
    if (!t.comercios || t.fecha > tope) continue;
    const g = grupos.get(t.fecha) ?? [];
    g.push(t);
    grupos.set(t.fecha, g);
  }
  return [...grupos.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([fecha, ts]) => ({ fecha, turnos: ts.sort((a, b) => (a.comercios?.nombre ?? "").localeCompare(b.comercios?.nombre ?? "", "es")) }));
}

/** «08:00» — la hora de Bolivia de un instante. */
export function horaBolivia(iso: string): string {
  const d = relojBolivia(new Date(iso));
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
}

/** «hasta mañana 08:00» (o «hasta hoy 08:00» si ya pasó la medianoche del turno). */
export function etiquetaHasta(fin: string, ahora: Date = new Date()): string {
  const dia = fechaBolivia(new Date(fin));
  const hoy = fechaBolivia(ahora);
  const cuando = dia === hoy ? "hoy " : dia === sumarDias(hoy, 1) ? "mañana " : `el ${fechaCorta(dia)} `;
  return `hasta ${cuando}${horaBolivia(fin)}`;
}

/** «22/10» (sin ceros a la izquierda, como se dice). */
export function fechaCorta(fecha: string): string {
  const [, m, d] = fecha.split("-").map(Number);
  return `${d}/${m}`;
}

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];

/** «Hoy», «Mañana» o «jueves 22/10». */
export function fechaLarga(fecha: string, ahora: Date = new Date()): string {
  const hoy = fechaBolivia(ahora);
  if (fecha === hoy) return "Hoy";
  if (fecha === sumarDias(hoy, 1)) return "Mañana";
  const [a, m, d] = fecha.split("-").map(Number);
  return `${DIAS[new Date(Date.UTC(a, m - 1, d)).getUTCDay()]} ${fechaCorta(fecha)}`;
}

/** «Ángeles» en vez de «Farmacia Ángeles»: para las tarjetas angostas. */
export function nombreCorto(nombre: string): string {
  return nombre.replace(/^\s*farmacia\s+/i, "").trim() || nombre.trim();
}

/** «A», «A y B», «A, B y C». */
export function listaNombres(nombres: string[]): string {
  if (nombres.length <= 1) return nombres.join("");
  return `${nombres.slice(0, -1).join(", ")} y ${nombres[nombres.length - 1]}`;
}

/** El número para `tel:`, tal como está cargado: sin prefijos ni suposiciones.
 *  Si el campo trae varios («72920000 / 6963456»), el primero: pegarlos
 *  armaría un número que no existe. */
export function telHref(telefono: string | null | undefined): string | null {
  const primero = (telefono ?? "").split(/[\/,;]| y /)[0] ?? "";
  const limpio = primero.replace(/[^\d+]/g, "");
  return limpio ? `tel:${limpio}` : null;
}
