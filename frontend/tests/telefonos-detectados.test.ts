// Tests de «Teléfonos en fotos» (docs/telefonos-en-fotos.md): armado del pedido, regla del
// lote, 409 → reemplazar, lectura defensiva de las respuestas y que los archivos nuevos
// no tengan emojis ni secretos.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  aplicarResultadoALista, alternar, alternarTodos, construirQuery, esConflicto, filaAplicada, idsDelLote,
  motivoLegible, motorActivoLabel, normalizarLote, normalizarPagina, normalizarResumen, numeroParaMostrar,
  partirEnLotes, preguntaReemplazo, puedeEnLote, rangoPagina, resumenLoteTexto, textoCompartido, textoWorker,
  unirResultadosLote, valorActual,
  type TelefonoDetectado,
} from "../lib/telefonos-detectados-pure";

const RAIZ = process.cwd();   // `npm test` corre en frontend/

function fila(p: Partial<TelefonoDetectado> & { wa?: string | null; tel?: string | null } = {}): TelefonoDetectado {
  const { wa = null, tel = null, ...resto } = p;
  return {
    id: "t1",
    comercio: { id: "c1", nombre: "Ferretería Ejemplo", slug: "ferreteria-ejemplo", whatsapp: wa, telefono: tel, ciudad: "bermejo" },
    numero: "+59171234567", numero_visible: "+591 71234567", tipo: "celular",
    texto_leido: "71234567", foto_url: "/media/a.jpg", motor: "tesseract",
    estado: "pendiente", compartido: false, otros_comercios: 0,
    ...resto,
  };
}

test("construirQuery: lo vacío no se manda", () => {
  assert.equal(
    construirQuery({ ciudad: null, estado: "", sinWhatsapp: false, limit: 50, offset: 0 }),
    "limit=50&offset=0",
  );
  const q = new URLSearchParams(construirQuery({ ciudad: "bermejo", estado: "pendiente", sinWhatsapp: true, limit: 50, offset: 100 }));
  assert.equal(q.get("ciudad"), "bermejo");
  assert.equal(q.get("estado"), "pendiente");
  assert.equal(q.get("sin_whatsapp"), "true");
  assert.equal(q.get("offset"), "100");
});

test("construirQuery: el offset nunca es negativo", () => {
  assert.match(construirQuery({ ciudad: null, estado: "", sinWhatsapp: false, limit: 50, offset: -5 }), /offset=0/);
});

test("puedeEnLote: sólo celular, pendiente, no compartido y comercio sin WhatsApp", () => {
  assert.equal(puedeEnLote(fila()), true);
  assert.equal(puedeEnLote(fila({ wa: "   " })), true);
  assert.equal(puedeEnLote(fila({ wa: "+59170000000" })), false);
  assert.equal(puedeEnLote(fila({ tipo: "fijo" })), false);
  assert.equal(puedeEnLote(fila({ compartido: true, otros_comercios: 4 })), false);
  assert.equal(puedeEnLote(fila({ estado: "descartado" })), false);
  assert.equal(puedeEnLote(fila({ estado: "coincide" })), false);
  assert.equal(puedeEnLote(fila({ estado: "aplicado_whatsapp" })), false);
});

test("idsDelLote ignora lo marcado que ya no cumple la regla", () => {
  const a = fila({ id: "a" });
  const b = fila({ id: "b", compartido: true });
  const c = fila({ id: "c" });
  assert.deepEqual(idsDelLote([a, b, c], new Set(["a", "b"])), ["a"]);
  assert.deepEqual(idsDelLote([a, b, c], new Set()), []);
});

test("alternar y alternarTodos no tocan el conjunto original", () => {
  const base = new Set(["a"]);
  const con = alternar(base, "b");
  assert.deepEqual([...con].sort(), ["a", "b"]);
  assert.deepEqual([...base], ["a"]);
  assert.deepEqual([...alternar(con, "a")], ["b"]);

  const items = [fila({ id: "a" }), fila({ id: "b", tipo: "fijo" }), fila({ id: "c" })];
  const todos = alternarTodos(items, new Set());
  assert.deepEqual([...todos].sort(), ["a", "c"]);
  assert.equal(alternarTodos(items, todos).size, 0);
  assert.equal(alternarTodos([fila({ tipo: "fijo" })], new Set()).size, 0);
});

test("partirEnLotes: tandas de a lo sumo 100 y sin repetidos", () => {
  const ids = Array.from({ length: 250 }, (_, i) => `id${i}`);
  const tandas = partirEnLotes([...ids, "id0"]);
  assert.deepEqual(tandas.map((t) => t.length), [100, 100, 50]);
  assert.deepEqual(partirEnLotes([]), []);
});

test("unirResultadosLote suma aplicados y saltados", () => {
  const r = unirResultadosLote([
    { aplicados: ["a"], saltados: [{ id: "x", motivo: "compartido" }] },
    { aplicados: ["b", "c"], saltados: [] },
  ]);
  assert.deepEqual(r.aplicados, ["a", "b", "c"]);
  assert.equal(r.saltados.length, 1);
});

test("409: esConflicto y la pregunta de reemplazo", () => {
  assert.equal(esConflicto(Object.assign(new Error("x"), { status: 409 })), true);
  assert.equal(esConflicto(Object.assign(new Error("x"), { status: 500 })), false);
  assert.equal(esConflicto(new Error("x")), false);
  assert.equal(esConflicto(null), false);

  const t = fila({ wa: "+59170000000" });
  assert.match(preguntaReemplazo(t, "whatsapp"), /ya tiene este WhatsApp: \+59170000000\. ¿Reemplazar por \+591 71234567\?/);
  assert.match(preguntaReemplazo(fila(), "telefono"), /ya tiene otro teléfono\. ¿Reemplazar/);
});

test("valorActual: vacío o en blanco es null", () => {
  assert.equal(valorActual(fila({ wa: "  " }), "whatsapp"), null);
  assert.equal(valorActual(fila({ tel: " 4 123456 " }), "telefono"), "4 123456");
});

test("filaAplicada actualiza el estado y el valor del comercio sin tocar la original", () => {
  const t = fila();
  const w = filaAplicada(t, "whatsapp");
  assert.equal(w.estado, "aplicado_whatsapp");
  assert.equal(w.comercio.whatsapp, "+59171234567");
  assert.equal(t.estado, "pendiente");
  assert.equal(t.comercio.whatsapp, null);
  const p = filaAplicada(t, "telefono");
  assert.equal(p.estado, "aplicado_telefono");
  assert.equal(p.comercio.telefono, "+59171234567");
});

test("aplicarResultadoALista marca sólo los aplicados", () => {
  const lista = aplicarResultadoALista([fila({ id: "a" }), fila({ id: "b" })], { aplicados: ["b"], saltados: [{ id: "a", motivo: "" }] });
  assert.equal(lista[0].estado, "pendiente");
  assert.equal(lista[1].estado, "aplicado_whatsapp");
});

test("motivoLegible: conocidos, frases y vacío", () => {
  assert.equal(motivoLegible("compartido"), "El número aparece en varios comercios");
  assert.equal(motivoLegible("tiene_whatsapp"), "El comercio ya tiene WhatsApp");
  assert.equal(motivoLegible("Ya estaba cargado"), "Ya estaba cargado");
  assert.equal(motivoLegible("algo_raro"), "Algo raro");
  assert.equal(motivoLegible(""), "No se aplicó");
  assert.equal(motivoLegible(null), "No se aplicó");
});

test("resumenLoteTexto singular y plural", () => {
  assert.equal(resumenLoteTexto({ aplicados: ["a"], saltados: [] }), "Se usó 1 número como WhatsApp.");
  assert.equal(
    resumenLoteTexto({ aplicados: ["a", "b"], saltados: [{ id: "c", motivo: "" }, { id: "d", motivo: "" }] }),
    "Se usaron 2 números como WhatsApp. Se saltaron 2.",
  );
  assert.equal(resumenLoteTexto({ aplicados: [], saltados: [{ id: "c", motivo: "" }] }), "Se usaron 0 números como WhatsApp. Se saltó 1.");
});

test("motorActivoLabel: gratis, con costo y desconocido", () => {
  assert.deepEqual(motorActivoLabel("tesseract"), { texto: "Lector gratis", costo: false });
  assert.deepEqual(motorActivoLabel("gemini"), { texto: "Gemini · tiene costo", costo: true });
  assert.equal(motorActivoLabel("").costo, false);
  assert.equal(motorActivoLabel("otro").texto, "otro");
});

test("textoWorker y textoCompartido", () => {
  assert.equal(textoWorker(true), "Lector automático prendido");
  assert.equal(textoWorker(false), "Lector automático apagado");
  assert.equal(textoWorker(null), null);
  assert.equal(textoWorker("  en pausa "), "en pausa");
  assert.equal(textoCompartido({ otros_comercios: 4 }), "Compartido con 5 comercios");
  assert.equal(textoCompartido({ otros_comercios: 0 }), "Compartido con 2 comercios");
});

test("numeroParaMostrar usa el legible y cae al E.164", () => {
  assert.equal(numeroParaMostrar(fila()), "+591 71234567");
  assert.equal(numeroParaMostrar(fila({ numero_visible: " " })), "+59171234567");
});

test("rangoPagina", () => {
  assert.deepEqual(rangoPagina(0, 50, 120), { desde: 1, hasta: 50, hayAnterior: false, haySiguiente: true });
  assert.deepEqual(rangoPagina(100, 20, 120), { desde: 101, hasta: 120, hayAnterior: true, haySiguiente: false });
  assert.deepEqual(rangoPagina(0, 0, 0), { desde: 0, hasta: 0, hayAnterior: false, haySiguiente: false });
});

test("normalizarPagina tolera respuestas rotas", () => {
  assert.deepEqual(normalizarPagina(null), { items: [], total: 0 });
  assert.deepEqual(normalizarPagina({ detail: "boom" }), { items: [], total: 0 });
  const p = normalizarPagina({
    total: 7,
    items: [
      { id: "1", numero: "+59171234567", comercio: { id: "c", nombre: "Uno", slug: "uno", whatsapp: "", telefono: null, ciudad: "bermejo" }, tipo: "fijo", estado: "rarísimo", compartido: true, otros_comercios: 3 },
      { id: "2" },
      "basura",
    ],
  });
  assert.equal(p.items.length, 1);
  assert.equal(p.total, 7);
  assert.equal(p.items[0].tipo, "fijo");
  assert.equal(p.items[0].estado, "pendiente");
  assert.equal(p.items[0].comercio.whatsapp, null);
  assert.equal(p.items[0].numero_visible, "+59171234567");
  assert.equal(p.items[0].otros_comercios, 3);
});

test("normalizarResumen y normalizarLote", () => {
  assert.deepEqual(normalizarResumen({ escaneadas: 10, pendientes_de_escanear: 5, numeros: 3, sin_whatsapp_con_numero: 2, motor_activo: "tesseract", worker: true }), {
    escaneadas: 10, pendientes_de_escanear: 5, numeros: 3, sin_whatsapp_con_numero: 2, motor_activo: "tesseract", worker: true,
  });
  assert.equal(normalizarResumen(undefined).escaneadas, 0);
  assert.equal(normalizarResumen({ worker: 3 }).worker, null);

  const l = normalizarLote({ aplicados: ["a", { id: "b" }, 3], saltados: [{ id: "c", motivo: "compartido" }, "d", {}] });
  assert.deepEqual(l.aplicados, ["a", "b"]);
  assert.deepEqual(l.saltados, [{ id: "c", motivo: "compartido" }, { id: "d", motivo: "" }]);
  assert.deepEqual(normalizarLote(null), { aplicados: [], saltados: [] });
});

test("archivos nuevos: sin emojis ni secretos", () => {
  const emoji = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
  for (const rel of [
    "lib/telefonos-detectados.ts", "lib/telefonos-detectados-pure.ts", "components/admin/telefonos-fotos-panel.tsx",
  ]) {
    const src = readFileSync(resolve(RAIZ, rel), "utf8");
    assert.equal(emoji.test(src), false, `${rel} tiene un emoji`);
    assert.equal(/SERVICE_ROLE|GEMINI_API_KEY/.test(src), false, `${rel} nombra un secreto`);
  }
});
