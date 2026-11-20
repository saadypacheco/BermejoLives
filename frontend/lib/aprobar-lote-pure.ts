// «Aprobar en bloque» en Importados (docs/home-ciudades.md §14): lo puro de la pantalla, sin red ni React, para
// probarlo con `npm test`. El flujo es SIEMPRE: simular → mostrar los números → confirmar en la misma pantalla → aprobar.
// Nada se publica sin que la persona confirme.
import type { FuenteFiltro } from "./tarjetas-pure";

/** Lo que contesta `POST /admin/importados/aprobar-lote`. */
export type ResultadoLote = {
  aprobados: number;
  salteados: { repetidos: number; sin_rubro: number; sin_punto: number; error: number };
};

export const SIN_SALTEADOS: ResultadoLote["salteados"] = { repetidos: 0, sin_rubro: 0, sin_punto: 0, error: 0 };

const entero = (x: unknown): number => (typeof x === "number" && Number.isFinite(x) && x > 0 ? Math.floor(x) : 0);

/** Lo que vino del servidor como `ResultadoLote`; los campos que falten cuentan 0 (un servidor más viejo no rompe la pantalla). */
export function resultadoDeRespuesta(d: unknown): ResultadoLote {
  const r = (typeof d === "object" && d !== null ? d : {}) as Record<string, unknown>;
  const s = (typeof r.salteados === "object" && r.salteados !== null ? r.salteados : {}) as Record<string, unknown>;
  return {
    aprobados: entero(r.aprobados),
    salteados: { repetidos: entero(s.repetidos), sin_rubro: entero(s.sin_rubro), sin_punto: entero(s.sin_punto), error: entero(s.error) },
  };
}

/** ¿Sale el botón? Con un filtro de fuente puesto, en «Sin revisar». «Turismo › Para visitar» NO: es un filtro por rubro
 *  y el servidor aprueba por fuente (aprobaría también los negocios de turismo): se hace con «Turismo». */
export function ofreceAprobarEnBloque(fuente: FuenteFiltro, estado: string): boolean {
  return estado === "nuevo" && fuente !== "todas" && fuente !== "turismo-visitar";
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

/** Lo que pasó de verdad: «Se aprobaron 12; se salteó 3 repetidos…». */
export function textoResultado(r: ResultadoLote): string {
  const salteados = textoSalteados(r.salteados);
  const aprobo = r.aprobados === 0 ? "No se aprobó ninguno" : `Se ${r.aprobados === 1 ? "aprobó" : "aprobaron"} ${r.aprobados}`;
  return salteados ? `${aprobo}; se salteó ${salteados}.` : `${aprobo}.`;
}

// ── El estado de la pantalla ────────────────────────────────────────────────

export type EstadoLote =
  | { tipo: "cerrado" }
  | { tipo: "simulando" }
  /** Se vio la simulación y falta confirmar. */
  | { tipo: "confirmar"; simulado: ResultadoLote }
  | { tipo: "aprobando"; simulado: ResultadoLote }
  | { tipo: "hecho"; resultado: ResultadoLote }
  | { tipo: "error"; mensaje: string; /** Desde dónde se reintenta: `simular` o `aprobar`. */ en: "simular" | "aprobar" };

export type EventoLote =
  | { tipo: "abrir" }
  | { tipo: "simulado"; resultado: ResultadoLote }
  | { tipo: "confirmar" }
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
      return e.tipo === "confirmar" && e.simulado.aprobados > 0 ? { tipo: "aprobando", simulado: e.simulado } : e;
    case "aprobado":
      return e.tipo === "aprobando" ? { tipo: "hecho", resultado: ev.resultado } : e;
    case "fallo":
      if (e.tipo === "simulando") return { tipo: "error", mensaje: ev.mensaje, en: "simular" };
      if (e.tipo === "aprobando") return { tipo: "error", mensaje: ev.mensaje, en: "aprobar" };
      return e;
    case "cancelar":
      // Mientras aprueba no se puede cancelar: el pedido ya salió.
      return e.tipo === "aprobando" ? e : LOTE_CERRADO;
  }
}
