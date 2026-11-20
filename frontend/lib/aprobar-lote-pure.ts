// «Aprobar en bloque» en Importados (docs/home-ciudades.md §14): lo puro de la pantalla, sin red ni React, para
// probarlo con `npm test`. El flujo es SIEMPRE: simular → mostrar los números → confirmar en la misma pantalla → aprobar.
// Nada se publica sin que la persona confirme.
//
// El servidor aprueba de a TANDAS: como mucho `TOPE_POR_LLAMADA` (200) por llamada y devuelve cuántas `restantes`
// quedan. La pantalla repite la llamada hasta llegar a lo que la persona confirmó (el N de «Sí, aprobar N») y nunca
// pasa de ahí: lo que aparezca de más después de la simulación no se aprueba sin otra confirmación.
import type { FuenteFiltro } from "./tarjetas-pure";

/** Lo que contesta `POST /admin/importados/aprobar-lote`. */
export type ResultadoLote = {
  aprobados: number;
  salteados: { repetidos: number; sin_rubro: number; sin_punto: number; error: number };
  /** Cuántos quedan por aprobar después de esta llamada (el servidor corta en `max_aprobar`). 0 = no queda nada. */
  restantes: number;
};

export const SIN_SALTEADOS: ResultadoLote["salteados"] = { repetidos: 0, sin_rubro: 0, sin_punto: 0, error: 0 };
export const SIN_RESULTADO: ResultadoLote = { aprobados: 0, salteados: SIN_SALTEADOS, restantes: 0 };

/** Lo máximo que el servidor aprueba por llamada (`max_aprobar` va de 1 a 200). */
export const TOPE_POR_LLAMADA = 200;

/** Las fuentes que el servidor acepta en el lote (otra da 422). */
export const FUENTES_EN_BLOQUE: readonly string[] = ["turismo", "anh", "aduana"];

/** Lo que se le dice a la persona antes de confirmar: la búsqueda por nombre del panel NO filtra el lote. */
export const AVISO_BUSQUEDA_NO_APLICA =
  "La búsqueda por nombre del panel no se aplica: se aprueba todo lo de esta fuente y esta ciudad, no sólo lo que ves en la lista.";

const entero = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) && x > 0 ? Math.floor(x) : 0);

/** Lo que vino del servidor como `ResultadoLote`; los campos que falten cuentan 0 (un servidor más viejo no rompe la pantalla). */
export function resultadoDeRespuesta(d: unknown): ResultadoLote {
  const r = (typeof d === "object" && d !== null ? d : {}) as Record<string, unknown>;
  const s = (typeof r.salteados === "object" && r.salteados !== null ? r.salteados : {}) as Record<string, unknown>;
  return {
    aprobados: entero(r.aprobados),
    salteados: { repetidos: entero(s.repetidos), sin_rubro: entero(s.sin_rubro), sin_punto: entero(s.sin_punto), error: entero(s.error) },
    restantes: entero(r.restantes),
  };
}

/** ¿Sale el botón? Sólo con `turismo`, `anh` o `aduana` puestas, en «Sin revisar». «Turismo › Para visitar» no: es un filtro
 *  por rubro y el servidor aprueba por fuente (aprobaría también los negocios de turismo): se hace con «Turismo». */
export function ofreceAprobarEnBloque(fuente: FuenteFiltro, estado: string): boolean {
  return estado === "nuevo" && FUENTES_EN_BLOQUE.includes(fuente);
}

// ── Las tandas ──────────────────────────────────────────────────────────────

/** El `max_aprobar` de la próxima llamada: lo que falta para llegar a `total`, con tope de 200. 0 = no hay que llamar. */
export function siguienteMaximo(total: number, aprobadosHastaAhora: number): number {
  return Math.max(0, Math.min(TOPE_POR_LLAMADA, total - aprobadosHastaAhora));
}

/** Suma una respuesta al acumulado: los aprobados se suman; los salteados son los de la ÚLTIMA llamada (las filas salteadas
 *  siguen sin revisar y cada llamada las vuelve a contar: sumarlas las repetiría). */
export function acumular(previo: ResultadoLote, r: ResultadoLote): ResultadoLote {
  return { aprobados: previo.aprobados + r.aprobados, salteados: r.salteados, restantes: r.restantes };
}

/** ¿Se vuelve a llamar? Sólo si la última tanda aprobó algo, el servidor dice que quedan y todavía no se llegó al N confirmado.
 *  Una tanda que no aprueba nada corta el ciclo (si no, se llamaría para siempre). */
export function debeSeguir(ultima: ResultadoLote, acumulado: ResultadoLote, total: number): boolean {
  return ultima.aprobados > 0 && ultima.restantes > 0 && acumulado.aprobados < total;
}

/** El ciclo de tandas: llama hasta llegar a `total` (nunca pasa de ahí), mientras la tanda anterior haya aprobado algo y el servidor
 *  diga que quedan. NO lanza: si una llamada falla devuelve lo acumulado hasta ahí y el error, y no vuelve a llamar (no se arranca
 *  un lote nuevo a ciegas: la persona decide). `seguir()` en `false` corta entre tandas (la pantalla se cerró). */
export async function aprobarPorTandas(
  llamar: (maxAprobar: number) => Promise<ResultadoLote>,
  total: number,
  o: { seguir?: () => boolean; alProgreso?: (acumulado: ResultadoLote) => void } = {},
): Promise<{ resultado: ResultadoLote; llamadas: number; error: unknown }> {
  let acumulado = SIN_RESULTADO;
  let llamadas = 0;
  try {
    for (;;) {
      const max = siguienteMaximo(total, acumulado.aprobados);
      if (max <= 0) break;
      llamadas += 1;
      const r = await llamar(max);
      acumulado = acumular(acumulado, r);
      if (!debeSeguir(r, acumulado, total) || o.seguir?.() === false) break;
      o.alProgreso?.(acumulado);
    }
  } catch (error) {
    return { resultado: acumulado, llamadas, error };
  }
  return { resultado: acumulado, llamadas, error: null };
}

/** «Aprobando… 200 de 412». */
export function textoProgreso(hechos: number, total: number): string {
  return `Aprobando… ${hechos} de ${total}`;
}

/** El motivo de un fallo del lote, en palabras. El 409 es «ya hay otro lote corriendo»: no se reintenta solo. */
export function mensajeDeFalloLote(status: number | undefined, mensaje: string, enAprobar: boolean): string {
  if (status === 409) return mensaje || "Ya hay una aprobación en bloque en curso.";
  if (status === undefined) {
    return enAprobar
      ? "Se cortó la conexión mientras se aprobaba. No se reintenta solo: simulá de nuevo para ver cuántos quedan."
      : "No se pudo simular: no hay conexión con el servidor. No se cambió nada.";
  }
  return enAprobar ? `No se pudo seguir aprobando: ${mensaje}` : `No se pudo simular: ${mensaje}. No se cambió nada.`;
}

const plural = (n: number, uno: string, varios: string): string => `${n} ${n === 1 ? uno : varios}`;

/** «3 repetidos, 2 sin rubro, 1 sin punto»: sólo lo que no es cero. Vacío si no se saltea nada. */
export function textoSalteados(s: ResultadoLote["salteados"]): string {
  const partes: string[] = [];
  if (s.repetidos > 0) partes.push(plural(s.repetidos, "repetido", "repetidos"));
  if (s.sin_rubro > 0) partes.push(`${s.sin_rubro} sin rubro`);
  if (s.sin_punto > 0) partes.push(`${s.sin_punto} sin punto en el mapa`);
  if (s.error > 0) partes.push(`${s.error} con error`);
  return partes.join(", ");
}

/** El resultado de la simulación: «Se aprueban 12; se saltean 3 repetidos y 2 sin rubro.» */
export function textoSimulacion(r: ResultadoLote): string {
  const salteados = textoSalteados(r.salteados);
  const aprueba = r.aprobados === 0 ? "No hay nada para aprobar" : `Se ${r.aprobados === 1 ? "aprueba" : "aprueban"} ${r.aprobados}`;
  return salteados ? `${aprueba}; se saltean ${salteados}.` : `${aprueba}.`;
}

/** Lo que pasó de verdad: «Se aprobaron 12; se salteó 3 repetidos…». Si quedan sin aprobar, lo dice. */
export function textoResultado(r: ResultadoLote): string {
  const salteados = textoSalteados(r.salteados);
  const aprobo = r.aprobados === 0 ? "No se aprobó ninguno" : `Se ${r.aprobados === 1 ? "aprobó" : "aprobaron"} ${r.aprobados}`;
  const base = salteados ? `${aprobo}; se salteó ${salteados}.` : `${aprobo}.`;
  return r.restantes > 0 ? `${base} Quedan ${r.restantes} sin revisar: simulá de nuevo para seguir.` : base;
}

// ── El estado de la pantalla ────────────────────────────────────────────────

export type EstadoLote =
  | { tipo: "cerrado" }
  | { tipo: "simulando" }
  /** Se vio la simulación y falta confirmar. */
  | { tipo: "confirmar"; simulado: ResultadoLote }
  /** `hechos` = lo aprobado hasta ahora, sumando las tandas; el total a alcanzar es `simulado.aprobados`. */
  | { tipo: "aprobando"; simulado: ResultadoLote; hechos: ResultadoLote }
  | { tipo: "hecho"; resultado: ResultadoLote }
  /** `en` = desde dónde falló. `parcial` = lo que ya se había aprobado antes de cortarse (sólo al aprobar). */
  | { tipo: "error"; mensaje: string; en: "simular" | "aprobar"; parcial: ResultadoLote | null };

export type EventoLote =
  | { tipo: "abrir" }
  | { tipo: "simulado"; resultado: ResultadoLote }
  | { tipo: "confirmar" }
  /** Terminó una tanda: el acumulado hasta ahora. */
  | { tipo: "progreso"; acumulado: ResultadoLote }
  | { tipo: "aprobado"; resultado: ResultadoLote }
  | { tipo: "fallo"; mensaje: string }
  | { tipo: "cancelar" };

export const LOTE_CERRADO: EstadoLote = { tipo: "cerrado" };

/** Las transiciones. La de aprobar sólo sale de «confirmar» y sólo si la simulación dijo que hay algo para aprobar:
 *  desde cualquier otro estado `confirmar` no hace nada (no se publica sin confirmación explícita). */
export function reducirLote(e: EstadoLote, ev: EventoLote): EstadoLote {
  switch (ev.tipo) {
    case "abrir":
      return e.tipo === "cerrado" || e.tipo === "hecho" || e.tipo === "error" ? { tipo: "simulando" } : e;
    case "simulado":
      return e.tipo === "simulando" ? { tipo: "confirmar", simulado: ev.resultado } : e;
    case "confirmar":
      return e.tipo === "confirmar" && e.simulado.aprobados > 0 ? { tipo: "aprobando", simulado: e.simulado, hechos: SIN_RESULTADO } : e;
    case "progreso":
      return e.tipo === "aprobando" ? { ...e, hechos: ev.acumulado } : e;
    case "aprobado":
      return e.tipo === "aprobando" ? { tipo: "hecho", resultado: ev.resultado } : e;
    case "fallo":
      if (e.tipo === "simulando") return { tipo: "error", mensaje: ev.mensaje, en: "simular", parcial: null };
      if (e.tipo === "aprobando") return { tipo: "error", mensaje: ev.mensaje, en: "aprobar", parcial: e.hechos };
      return e;
    case "cancelar":
      // Mientras aprueba no se puede cancelar: el pedido ya salió.
      return e.tipo === "aprobando" ? e : LOTE_CERRADO;
  }
}
