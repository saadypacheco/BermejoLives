// «Aprobar en bloque» en Importados (lib/aprobar-lote-pure.ts, docs/home-ciudades.md §14): simular → confirmar → aprobar.
import test from "node:test";
import assert from "node:assert/strict";
import {
  LOTE_CERRADO, ofreceAprobarEnBloque, reducirLote, resultadoDeRespuesta, textoResultado, textoSalteados, textoSimulacion,
  type EstadoLote, type EventoLote, type ResultadoLote,
} from "../lib/aprobar-lote-pure";
import type { FuenteFiltro } from "../lib/tarjetas-pure";

const R = (aprobados: number, s: Partial<ResultadoLote["salteados"]> = {}): ResultadoLote => ({
  aprobados, salteados: { repetidos: 0, sin_rubro: 0, sin_punto: 0, error: 0, ...s },
});
const correr = (eventos: EventoLote[], inicio: EstadoLote = LOTE_CERRADO): EstadoLote => eventos.reduce(reducirLote, inicio);

test("el botón sale sólo con una fuente puesta y en «Sin revisar»; «Turismo › Para visitar» no (el servidor aprueba por fuente)", () => {
  assert.equal(ofreceAprobarEnBloque("todas", "nuevo"), false);
  for (const f of ["osm", "tarjeta", "turismo", "overture", "anh", "aduana"] as FuenteFiltro[]) assert.equal(ofreceAprobarEnBloque(f, "nuevo"), true, f);
  assert.equal(ofreceAprobarEnBloque("turismo-visitar", "nuevo"), false);
  assert.equal(ofreceAprobarEnBloque("turismo", "promovido"), false);
  assert.equal(ofreceAprobarEnBloque("turismo", "descartado"), false);
});

test("flujo feliz: abrir → simulando → confirmar (se ven los números) → aprobando → hecho", () => {
  let e = reducirLote(LOTE_CERRADO, { tipo: "abrir" });
  assert.equal(e.tipo, "simulando");
  e = reducirLote(e, { tipo: "simulado", resultado: R(12, { repetidos: 3 }) });
  assert.equal(e.tipo, "confirmar");
  e = reducirLote(e, { tipo: "confirmar" });
  assert.equal(e.tipo, "aprobando");
  e = reducirLote(e, { tipo: "aprobado", resultado: R(12, { repetidos: 3 }) });
  assert.deepEqual(e, { tipo: "hecho", resultado: R(12, { repetidos: 3 }) });
});

test("NADA se aprueba sin confirmar: confirmar sólo funciona desde la simulación vista y con algo para aprobar", () => {
  for (const e of [LOTE_CERRADO, { tipo: "simulando" } as EstadoLote, { tipo: "hecho", resultado: R(1) } as EstadoLote, { tipo: "error", mensaje: "x", en: "simular" } as EstadoLote]) {
    assert.equal(reducirLote(e, { tipo: "confirmar" }).tipo, e.tipo, `desde ${e.tipo} no se aprueba`);
  }
  // Simulación con 0 para aprobar: no hay nada que confirmar.
  const vacio = correr([{ tipo: "abrir" }, { tipo: "simulado", resultado: R(0, { sin_rubro: 4 }) }]);
  assert.equal(reducirLote(vacio, { tipo: "confirmar" }).tipo, "confirmar");
  // Y una respuesta de aprobación que llega sin haber pedido aprobar se ignora.
  assert.equal(reducirLote(LOTE_CERRADO, { tipo: "aprobado", resultado: R(5) }).tipo, "cerrado");
  assert.equal(reducirLote({ tipo: "simulando" }, { tipo: "aprobado", resultado: R(5) }).tipo, "simulando");
});

test("cancelar cierra desde la simulación, pero no mientras se está aprobando (el pedido ya salió)", () => {
  const confirmando = correr([{ tipo: "abrir" }, { tipo: "simulado", resultado: R(2) }]);
  assert.equal(reducirLote(confirmando, { tipo: "cancelar" }).tipo, "cerrado");
  const aprobando = reducirLote(confirmando, { tipo: "confirmar" });
  assert.equal(reducirLote(aprobando, { tipo: "cancelar" }).tipo, "aprobando");
});

test("un fallo al simular o al aprobar queda a la vista con su motivo; se reintenta desde cero (simulando de nuevo)", () => {
  const alSimular = correr([{ tipo: "abrir" }, { tipo: "fallo", mensaje: "sin conexión" }]);
  assert.deepEqual(alSimular, { tipo: "error", mensaje: "sin conexión", en: "simular" });
  const alAprobar = correr([{ tipo: "abrir" }, { tipo: "simulado", resultado: R(3) }, { tipo: "confirmar" }, { tipo: "fallo", mensaje: "500" }]);
  assert.deepEqual(alAprobar, { tipo: "error", mensaje: "500", en: "aprobar" });
  assert.equal(reducirLote(alAprobar, { tipo: "abrir" }).tipo, "simulando");
  // Un fallo fuera de un pedido en vuelo no inventa un error.
  assert.equal(reducirLote(LOTE_CERRADO, { tipo: "fallo", mensaje: "x" }).tipo, "cerrado");
});

test("textos: sólo se nombra lo que no es cero, con singular y plural", () => {
  assert.equal(textoSalteados(R(0).salteados), "");
  assert.equal(textoSalteados(R(0, { repetidos: 1 }).salteados), "1 repetido");
  assert.equal(textoSalteados(R(0, { repetidos: 3, sin_rubro: 2, sin_punto: 1, error: 4 }).salteados), "3 repetidos, 2 sin rubro, 1 sin punto en el mapa, 4 con error");
  assert.equal(textoSimulacion(R(12, { repetidos: 3, sin_rubro: 2 })), "Se aprueban 12; se saltean 3 repetidos, 2 sin rubro.");
  assert.equal(textoSimulacion(R(1)), "Se aprueba 1.");
  assert.equal(textoSimulacion(R(0, { sin_punto: 5 })), "No hay nada para aprobar; se saltean 5 sin punto en el mapa.");
  assert.equal(textoResultado(R(12, { repetidos: 3 })), "Se aprobaron 12; se salteó 3 repetidos.");
  assert.equal(textoResultado(R(1)), "Se aprobó 1.");
  assert.equal(textoResultado(R(0)), "No se aprobó ninguno.");
});

test("resultadoDeRespuesta: tolera respuestas incompletas o raras (cuenta 0 en lo que falta)", () => {
  assert.deepEqual(resultadoDeRespuesta(null), R(0));
  assert.deepEqual(resultadoDeRespuesta({}), R(0));
  assert.deepEqual(resultadoDeRespuesta({ aprobados: 7 }), R(7));
  assert.deepEqual(resultadoDeRespuesta({ aprobados: "7", salteados: { repetidos: -2, sin_rubro: 1.9, sin_punto: NaN } }), R(0, { sin_rubro: 1 }));
  assert.deepEqual(resultadoDeRespuesta({ aprobados: 3, salteados: { repetidos: 1, sin_rubro: 2, sin_punto: 3, error: 4 } }), R(3, { repetidos: 1, sin_rubro: 2, sin_punto: 3, error: 4 }));
});
