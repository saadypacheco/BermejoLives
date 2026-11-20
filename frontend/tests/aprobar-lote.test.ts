// «Aprobar en bloque» en Importados (lib/aprobar-lote-pure.ts, docs/home-ciudades.md §14): simular → confirmar → aprobar.
import test from "node:test";
import assert from "node:assert/strict";
import {
  AVISO_BUSQUEDA_NO_APLICA, LOTE_CERRADO, TOPE_POR_LLAMADA, aprobarPorTandas, debeSeguir, mensajeDeFalloLote, ofreceAprobarEnBloque, reducirLote,
  resultadoDeRespuesta, siguienteMaximo, textoProgreso, textoResultado, textoSalteados, textoSimulacion,
  type EstadoLote, type EventoLote, type ResultadoLote,
} from "../lib/aprobar-lote-pure";
import type { FuenteFiltro } from "../lib/tarjetas-pure";

const R = (aprobados: number, s: Partial<ResultadoLote["salteados"]> = {}, restantes = 0): ResultadoLote => ({
  aprobados, salteados: { repetidos: 0, sin_rubro: 0, sin_punto: 0, error: 0, ...s }, restantes,
});
const correr = (eventos: EventoLote[], inicio: EstadoLote = LOTE_CERRADO): EstadoLote => eventos.reduce(reducirLote, inicio);

test("el botón sale sólo con turismo, anh o aduana en «Sin revisar»; el resto (osm, tarjeta, overture, «Para visitar») no", () => {
  assert.equal(ofreceAprobarEnBloque("todas", "nuevo"), false);
  for (const f of ["turismo", "anh", "aduana"] as FuenteFiltro[]) assert.equal(ofreceAprobarEnBloque(f, "nuevo"), true, f);
  for (const f of ["osm", "tarjeta", "overture"] as FuenteFiltro[]) assert.equal(ofreceAprobarEnBloque(f, "nuevo"), false, f);
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
  assert.deepEqual(e, { tipo: "aprobando", simulado: R(12, { repetidos: 3 }), hechos: R(0) });
  e = reducirLote(e, { tipo: "progreso", acumulado: R(5) });
  assert.equal(e.tipo === "aprobando" ? e.hechos.aprobados : -1, 5);
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
  assert.deepEqual(alSimular, { tipo: "error", mensaje: "sin conexión", en: "simular", parcial: null });
  const alAprobar = correr([{ tipo: "abrir" }, { tipo: "simulado", resultado: R(3) }, { tipo: "confirmar" }, { tipo: "fallo", mensaje: "500" }]);
  assert.deepEqual(alAprobar, { tipo: "error", mensaje: "500", en: "aprobar", parcial: R(0) });
  // Si ya se habían aprobado tandas, el error las conserva (para mostrar el resultado parcial).
  const cortado = correr([{ tipo: "abrir" }, { tipo: "simulado", resultado: R(400) }, { tipo: "confirmar" }, { tipo: "progreso", acumulado: R(200) }, { tipo: "fallo", mensaje: "409" }]);
  assert.deepEqual(cortado, { tipo: "error", mensaje: "409", en: "aprobar", parcial: R(200) });
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
  assert.equal(textoResultado(R(200, {}, 212)), "Se aprobaron 200. Quedan 212 sin revisar: simulá de nuevo para seguir.");
  assert.equal(textoProgreso(200, 412), "Aprobando… 200 de 412");
});

test("resultadoDeRespuesta: tolera respuestas incompletas o raras (cuenta 0 en lo que falta)", () => {
  assert.deepEqual(resultadoDeRespuesta(null), R(0));
  assert.deepEqual(resultadoDeRespuesta({}), R(0));
  assert.deepEqual(resultadoDeRespuesta({ aprobados: 7 }), R(7));
  assert.equal(resultadoDeRespuesta({ aprobados: 7, restantes: 30 }).restantes, 30);
  assert.equal(resultadoDeRespuesta({ aprobados: 7, restantes: -1 }).restantes, 0);
  assert.deepEqual(resultadoDeRespuesta({ aprobados: "7", salteados: { repetidos: -2, sin_rubro: 1.9, sin_punto: NaN } }), R(0, { sin_rubro: 1 }));
  assert.deepEqual(resultadoDeRespuesta({ aprobados: 3, salteados: { repetidos: 1, sin_rubro: 2, sin_punto: 3, error: 4 } }), R(3, { repetidos: 1, sin_rubro: 2, sin_punto: 3, error: 4 }));
});

test("la confirmación avisa que la búsqueda por nombre del panel no se aplica", () => {
  assert.match(AVISO_BUSQUEDA_NO_APLICA, /búsqueda/);
  assert.match(AVISO_BUSQUEDA_NO_APLICA, /no se aplica/);
  assert.match(AVISO_BUSQUEDA_NO_APLICA, /fuente/);
  assert.match(AVISO_BUSQUEDA_NO_APLICA, /ciudad/);
});

test("siguienteMaximo: lo que falta para N, con tope de 200 por llamada, y nunca negativo", () => {
  assert.equal(TOPE_POR_LLAMADA, 200);
  assert.equal(siguienteMaximo(412, 0), 200);
  assert.equal(siguienteMaximo(412, 200), 200);
  assert.equal(siguienteMaximo(412, 400), 12);
  assert.equal(siguienteMaximo(412, 412), 0);
  assert.equal(siguienteMaximo(412, 500), 0);
  assert.equal(siguienteMaximo(50, 0), 50);
});

test("debeSeguir: sólo si la tanda aprobó algo, quedan y no se llegó a N", () => {
  assert.equal(debeSeguir(R(200, {}, 212), R(200, {}, 212), 412), true);
  assert.equal(debeSeguir(R(0, {}, 212), R(200, {}, 212), 412), false, "una tanda sin aprobar corta el ciclo");
  assert.equal(debeSeguir(R(200, {}, 0), R(200, {}, 0), 412), false, "sin restantes");
  assert.equal(debeSeguir(R(12, {}, 30), R(412, {}, 30), 412), false, "ya se llegó a N: no pasa de lo confirmado");
});

const fingir = (respuestas: (ResultadoLote | Error)[]) => {
  const maximos: number[] = [];
  const llamar = async (max: number): Promise<ResultadoLote> => {
    maximos.push(max);
    const r = respuestas[maximos.length - 1];
    if (!r) throw new Error("se llamó de más");
    if (r instanceof Error) throw r;
    return r;
  };
  return { llamar, maximos };
};

test("tandas: 412 se aprueban en 3 llamadas (200, 200, 12), con progreso, sin pasar de N", async () => {
  const f = fingir([R(200, { repetidos: 3 }, 212), R(200, { repetidos: 3 }, 12), R(12, { repetidos: 3 }, 0)]);
  const progreso: number[] = [];
  const r = await aprobarPorTandas(f.llamar, 412, { alProgreso: (a) => progreso.push(a.aprobados) });
  assert.deepEqual(f.maximos, [200, 200, 12]);
  assert.deepEqual(progreso, [200, 400]);
  assert.equal(r.resultado.aprobados, 412);
  assert.equal(r.resultado.restantes, 0);
  assert.deepEqual(r.resultado.salteados, R(0, { repetidos: 3 }).salteados, "los salteados son los de la última tanda, no una suma");
  assert.equal(r.error, null);
});

test("tandas: si el servidor devuelve más de lo confirmado igual se corta en N (no se pide otra tanda)", async () => {
  const f = fingir([R(200, {}, 500)]);
  const r = await aprobarPorTandas(f.llamar, 200);
  assert.equal(f.maximos.length, 1);
  assert.equal(r.resultado.aprobados, 200);
});

test("tandas: una tanda que no aprueba nada corta (no llama para siempre) y queda dicho cuántos restan", async () => {
  const f = fingir([R(200, {}, 300), R(0, { error: 5 }, 300)]);
  const r = await aprobarPorTandas(f.llamar, 412);
  assert.equal(f.maximos.length, 2);
  assert.equal(r.resultado.aprobados, 200);
  assert.equal(r.resultado.restantes, 300);
  assert.match(textoResultado(r.resultado), /Quedan 300 sin revisar/);
});

test("tandas: un 409 (otro lote en curso) o un corte de red frena el ciclo: devuelve lo aprobado, el error, y NO vuelve a llamar", async () => {
  const conflicto = Object.assign(new Error("Ya hay una aprobación en bloque en curso."), { status: 409 });
  const f = fingir([R(200, {}, 212), conflicto]);
  const r = await aprobarPorTandas(f.llamar, 412);
  assert.equal(f.maximos.length, 2, "no hay reintento");
  assert.equal(r.resultado.aprobados, 200, "lo ya aprobado queda a la vista");
  assert.equal(r.error, conflicto);
  const red = fingir([new TypeError("Failed to fetch")]);
  const r2 = await aprobarPorTandas(red.llamar, 412);
  assert.equal(red.maximos.length, 1);
  assert.equal(r2.resultado.aprobados, 0);
  assert.ok(r2.error instanceof TypeError);
});

test("tandas: si la pantalla se cierra (seguir() en falso) después de una tanda, no se piden más", async () => {
  const f = fingir([R(200, {}, 212), R(200, {}, 12)]);
  const r = await aprobarPorTandas(f.llamar, 412, { seguir: () => false });
  assert.equal(f.maximos.length, 1);
  assert.equal(r.resultado.aprobados, 200);
});

test("mensajes de fallo: el 409 se dice tal cual; un corte de red no se reintenta solo; el resto lleva su motivo", () => {
  assert.equal(mensajeDeFalloLote(409, "Ya hay una aprobación en bloque en curso.", true), "Ya hay una aprobación en bloque en curso.");
  assert.match(mensajeDeFalloLote(409, "", false), /en curso/);
  assert.match(mensajeDeFalloLote(undefined, "Failed to fetch", true), /simulá de nuevo/);
  assert.match(mensajeDeFalloLote(undefined, "Failed to fetch", false), /No se cambió nada/);
  assert.match(mensajeDeFalloLote(500, "boom", true), /boom/);
  assert.match(mensajeDeFalloLote(422, "fuente", false), /No se cambió nada/);
});
