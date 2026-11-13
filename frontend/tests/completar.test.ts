// «Comparar y completar» y «Promover sin ubicación» (docs/turismo-home-y-repetidos.md §1 y §2): reglas puras del panel.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  AVISO_PROMOVER_REPETIDO, accionCampo, alternarEleccion, armarBodyCompletar, camposVisibles, esElegible, mensajeComparador,
  nombreRepetido, puedeSumarRubro, repetidoPendiente, resumenAcciones, sumarRubroPorDefecto, textoAccion, textoCompletado,
  textoResumen, textoValor, tituloColumnaNuevo, type CampoComparado,
} from "../lib/completar-pure";
import { AVISO_SIN_UBICACION, admiteSinUbicacion, puedePromoverSinUbicacion } from "../lib/tarjetas-pure";

const direccion: CampoComparado = { campo: "direccion", actual: null, nuevo: "Calle Sucre 123", sugerido: "completar" };
const telefono: CampoComparado = { campo: "telefono", actual: "4661111", nuevo: "4662222", sugerido: "conservar" };
const email: CampoComparado = { campo: "email", actual: "a@b.bo", nuevo: "a@b.bo", sugerido: "igual" };
const horario: CampoComparado = { campo: "horario", actual: "8 a 12", nuevo: null, sugerido: "conservar" };
const puntoExistente: CampoComparado = {
  campo: "punto", actual: { lat: -21.53, lng: -64.73 }, nuevo: { lat: -21.54, lng: -64.74 }, sugerido: "conservar",
};
const puntoVacio: CampoComparado = { campo: "punto", actual: null, nuevo: { lat: -21.5, lng: -64.7 }, sugerido: "completar" };
const web: CampoComparado = { campo: "sitio_web", actual: "", nuevo: null, sugerido: "igual" };
const todos = [direccion, telefono, email, horario, puntoExistente, web];

test("qué acción le toca a cada campo", () => {
  assert.equal(accionCampo(direccion), "completa");
  assert.equal(accionCampo(telefono), "conserva");
  assert.equal(accionCampo(email), "igual");
  assert.equal(accionCampo(horario), "sin-dato");
  assert.equal(accionCampo(puntoExistente), "punto-fijo");
  assert.equal(accionCampo(puntoVacio), "completa");
});

test("el punto existente nunca se puede pisar, ni aunque el servidor sugiera otra cosa", () => {
  const raro: CampoComparado = { ...puntoExistente, sugerido: "completar" };
  assert.equal(accionCampo(raro), "punto-fijo");
  assert.equal(esElegible(raro), false);
  assert.equal(esElegible(puntoExistente), false);
  const body = armarBodyCompletar("c1", [raro], { punto: true }, false);
  assert.deepEqual(body.usar, {});
});

test("sólo se puede elegir «usar el nuevo» cuando los dos tienen dato distinto", () => {
  assert.equal(esElegible(telefono), true);
  assert.equal(esElegible(direccion), false);   // vacío: se completa solo
  assert.equal(esElegible(email), false);       // iguales
  assert.equal(esElegible(horario), false);     // nada nuevo
});

test("los campos vacíos en los dos lados no se muestran", () => {
  assert.deepEqual(camposVisibles(todos).map((c) => c.campo), ["direccion", "telefono", "email", "horario", "punto"]);
});

test("el body de completar: por defecto se conserva todo, y sólo viajan los campos elegidos", () => {
  assert.deepEqual(armarBodyCompletar("c1", todos, {}, true), { comercio_id: "c1", usar: {}, sumar_rubro: true });
  const e = alternarEleccion({}, "telefono");
  assert.deepEqual(armarBodyCompletar("c1", todos, e, false), { comercio_id: "c1", usar: { telefono: "nuevo" }, sumar_rubro: false });
  // lo marcado en un campo que no es elegible (vacío, igual) no se manda
  assert.deepEqual(armarBodyCompletar("c1", todos, { direccion: true, email: true, telefono: true }, false).usar, { telefono: "nuevo" });
  // apagar el interruptor lo saca
  assert.deepEqual(armarBodyCompletar("c1", todos, alternarEleccion(e, "telefono"), false).usar, {});
});

test("alternarEleccion no muta lo anterior", () => {
  const a = Object.freeze({});
  const b = alternarEleccion(a, "telefono");
  assert.deepEqual(a, {});
  assert.deepEqual(b, { telefono: true });
});

test("el rubro sugerido: marcado por defecto sólo si hay y el comercio no lo tiene", () => {
  assert.equal(sumarRubroPorDefecto("turismo", ["otros"]), true);
  assert.equal(sumarRubroPorDefecto("turismo", ["turismo", "taxis"]), false);
  assert.equal(sumarRubroPorDefecto(null, []), false);
  assert.equal(sumarRubroPorDefecto("", undefined), false);
  assert.equal(puedeSumarRubro("taxis", ["otros"]), true);
  assert.equal(puedeSumarRubro("taxis", ["taxis"]), false);
});

test("el resumen de lo que va a pasar", () => {
  const r = resumenAcciones(todos, {});
  assert.deepEqual(r, { completa: ["dirección"], reemplaza: [] });
  assert.equal(textoResumen(r, true), "Se completa: dirección. Se suma el rubro.");
  const r2 = resumenAcciones(todos, { telefono: true });
  assert.equal(textoResumen(r2, false), "Se completa: dirección. Se reemplaza por el nuevo: teléfono.");
  assert.match(textoResumen({ completa: [], reemplaza: [] }, false), /No hay nada para cambiar/);
});

test("el texto de cada acción dice la verdad sobre el interruptor", () => {
  assert.equal(textoAccion("conserva", false), "Se conserva el actual");
  assert.equal(textoAccion("conserva", true), "Se reemplaza por el nuevo");
  assert.equal(textoAccion("completa"), "Se completa");
  assert.equal(textoAccion("igual"), "Igual");
  assert.match(textoAccion("punto-fijo"), /punto actual no se pisa/);
});

test("el valor del punto se muestra con 5 decimales y lo vacío es null", () => {
  assert.equal(textoValor({ lat: -21.53, lng: -64.7312345 }), "-21.53000, -64.73123");
  assert.equal(textoValor("  Calle Sucre "), "Calle Sucre");
  assert.equal(textoValor(""), null);
  assert.equal(textoValor(null), null);
});

test("el mensaje de lo completado: nombre y campos cambiados, sin claves técnicas", () => {
  assert.equal(textoCompletado("Hotel Plaza", ["direccion", "sitio_web", "punto"]),
    "Se completó Hotel Plaza: dirección, web, punto en el mapa.");
  assert.equal(textoCompletado("Hotel Plaza", []), "Se completó Hotel Plaza: no había nada para cambiar.");
  assert.equal(textoCompletado(null, ["telefono"]), "Se completó el comercio: teléfono.");
  assert.equal(textoCompletado("X", undefined), "Se completó X: no había nada para cambiar.");
});

test("columna de lo importado y nombre del repetido (nunca el código)", () => {
  assert.equal(tituloColumnaNuevo("turismo"), "Lo que trae turismo");
  assert.equal(tituloColumnaNuevo("tarjeta"), "Lo que trae la tarjeta");
  assert.equal(nombreRepetido({ duplicado_nombre: " Hotel Plaza " }), "Hotel Plaza");
  assert.equal(nombreRepetido({ duplicado_nombre: null }), "un comercio ya cargado");
  assert.equal(nombreRepetido({}), "un comercio ya cargado");
});

test("el repetido está pendiente sólo en un importado nuevo con duplicado_de", () => {
  assert.equal(repetidoPendiente({ estado: "nuevo", duplicado_de: "c1" }), true);
  assert.equal(repetidoPendiente({ estado: "nuevo", duplicado_de: null }), false);
  assert.equal(repetidoPendiente({ estado: "promovido", duplicado_de: "c1" }), false);
  assert.match(AVISO_PROMOVER_REPETIDO, /segundo comercio/);
});

test("mensajes del comparador según el estado HTTP", () => {
  assert.match(mensajeComparador({ status: 409 }, "x"), /ya no está pendiente/);
  assert.match(mensajeComparador({ status: 404 }, "x"), /No se encontró el comercio/);
  assert.equal(mensajeComparador(new Error("Se venció la sesión"), "x"), "Se venció la sesión");
  assert.equal(mensajeComparador(null, "por defecto"), "por defecto");
});

// ── §2 Promover sin ubicación ────────────────────────────────────────────────

test("«Promover sin ubicación» sólo para tarjeta y turismo, y sólo si falta el punto", () => {
  const sinPunto = { lat: null, lng: null };
  const conPunto = { lat: -21.5, lng: -64.7 };
  assert.equal(admiteSinUbicacion({ fuente: "turismo" }), true);
  assert.equal(admiteSinUbicacion({ fuente: "tarjeta" }), true);
  assert.equal(admiteSinUbicacion({ fuente: "osm" }), false);
  assert.deepEqual(puedePromoverSinUbicacion({ fuente: "turismo", ...sinPunto }, { nombre: "Guía Pérez" }, false),
    { visible: true, ok: true, motivo: "" });
  assert.equal(puedePromoverSinUbicacion({ fuente: "tarjeta", ...sinPunto }, { nombre: "X" }, false).visible, true);
  assert.equal(puedePromoverSinUbicacion({ fuente: "turismo", ...conPunto }, { nombre: "X" }, false).visible, false);
  assert.equal(puedePromoverSinUbicacion({ fuente: "osm", ...sinPunto }, { nombre: "X" }, false).visible, false);
});

test("sin ubicación: visible pero bloqueado si falta el nombre o hay cambios sin guardar", () => {
  const f = { fuente: "turismo", lat: null, lng: null };
  const sinNombre = puedePromoverSinUbicacion(f, { nombre: "  " }, false);
  assert.deepEqual([sinNombre.visible, sinNombre.ok], [true, false]);
  assert.match(sinNombre.motivo, /nombre/);
  const sinGuardar = puedePromoverSinUbicacion(f, { nombre: "X" }, true);
  assert.deepEqual([sinGuardar.visible, sinGuardar.ok], [true, false]);
  assert.match(sinGuardar.motivo, /Guardá/);
  assert.equal(AVISO_SIN_UBICACION, "No va a aparecer en el mapa; sí en su ficha, la búsqueda y las listas");
});

// ── Cableado de la ficha ─────────────────────────────────────────────────────

test("la ficha usa el nombre del repetido, abre el comparador y manda sin_ubicacion; el panel avisa lo completado", () => {
  const ficha = readFileSync(resolve(process.cwd(), "components/importados-tarjetas.tsx"), "utf8");
  assert.match(ficha, /nombreRepetido\(it\)/);
  assert.doesNotMatch(ficha, /\{it\.duplicado_de\}<\/code>/);
  assert.match(ficha, /Comparar y completar/);
  assert.match(ficha, /Promover sin ubicación/);
  assert.match(ficha, /sin_ubicacion: true/);
  const cmp = readFileSync(resolve(process.cwd(), "components/importados-comparar.tsx"), "utf8");
  assert.match(cmp, /Completar el existente/);
  assert.match(cmp, /No es el mismo/);
  assert.match(cmp, /Sumar el rubro/);
  const panel = readFileSync(resolve(process.cwd(), "components/importados-panel.tsx"), "utf8");
  assert.match(panel, /onCompletado=/);
});

test("el cliente llama a las rutas del contrato", () => {
  const api = readFileSync(resolve(process.cwd(), "lib/api.ts"), "utf8");
  assert.match(api, /\/admin\/importados\/\$\{encodeURIComponent\(id\)\}\/comparar/);
  assert.match(api, /\/admin\/importados\/\$\{encodeURIComponent\(id\)\}\/completar/);
  assert.match(api, /\/admin\/importados\/\$\{encodeURIComponent\(id\)\}\/no-es-repetido/);
  assert.match(api, /sin_ubicacion\?: boolean/);
});
