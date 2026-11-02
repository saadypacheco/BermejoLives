// Tests de la tarea FB1: el párrafo de /{ciudad}/{rubro} se arma sólo con datos
// y nunca lleva un número de comercios. `npm test` (tsc → node --test).
import test from "node:test";
import assert from "node:assert/strict";
import {
  callesFrecuentes, cortarEnPalabra, enLista, parrafoCategoria, productosFrecuentes,
} from "../lib/contenido-categoria";

test("callesFrecuentes: sólo calles con 3 locales o más, sin número de puerta ni tildes", () => {
  const calles = ["Av. Bolivia 123", "av bolivia 45", "Av. Bolívia", "Comercio 10", "Comercio", "Sucre", null, undefined, ""];
  assert.deepEqual(callesFrecuentes(calles, 3, 3), ["Av. Bolivia"]);
  assert.deepEqual(callesFrecuentes(calles, 2, 3), ["Av. Bolivia", "Comercio"]);
});

test("callesFrecuentes: ordena por cantidad y corta en `max`", () => {
  const calles = ["A calle", "B calle", "B calle", "C calle", "C calle", "C calle", "D calle", "D calle", "D calle", "D calle"];
  assert.deepEqual(callesFrecuentes(calles, 2, 2), ["D calle", "C calle"]);
});

test("productosFrecuentes: cuenta locales, no repeticiones dentro de un local", () => {
  const filas = [
    { prod_obs_human: "Zapatillas, remeras", prod_det_ia: "zapatillas urbanas" },
    { prod_obs_human: "zapatillas", prod_det_ia: null },
    { prod_obs_human: "Remeras, camperas", prod_det_ia: null },
  ];
  const p = productosFrecuentes(filas, 2);
  assert.deepEqual(p, ["Zapatillas", "remeras"]);
  assert.deepEqual(productosFrecuentes([], 6), []);
});

test("enLista y cortarEnPalabra", () => {
  assert.equal(enLista([]), "");
  assert.equal(enLista(["a"]), "a");
  assert.equal(enLista(["a", "b", "c"]), "a, b y c");
  const largo = "palabra ".repeat(40);
  const cortado = cortarEnPalabra(largo, 50);
  assert.ok(cortado.length <= 50 && cortado.endsWith("…"));
  assert.equal(cortarEnPalabra("corto", 50), "corto");
});

test("parrafoCategoria: cada frase aparece sólo si hay dato; ningún número de comercios", () => {
  const completo = parrafoCategoria({ ciudad: "Bermejo", rubro: "Ropa", calles: ["Comercio", "Sucre"], productos: ["jeans", "buzos"] });
  assert.match(completo, /^En Bermejo, los locales de ropa están sobre Comercio y Sucre\./);
  assert.match(completo, /Entre lo que venden: jeans y buzos\./);
  assert.match(completo, /Tocá cada uno para ver dónde queda y cómo llegar\.$/);

  const sinDatos = parrafoCategoria({ ciudad: "Tarija", rubro: "Farmacias", calles: [], productos: [] });
  assert.equal(sinDatos, "En Tarija encontrás locales de farmacias. Tocá cada uno para ver dónde queda y cómo llegar.");
  assert.ok(!/\d+\s+(comercios|locales|negocios)/i.test(completo + sinDatos));
});
