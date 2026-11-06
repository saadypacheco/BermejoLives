// Las líneas de /planes que salen de los números del plan (lib/planes-pure).
import test from "node:test";
import assert from "node:assert/strict";
import { lineaCuota, lineaFotos } from "../lib/planes-pure";

test("las fotos de un plan pago: las que sube por día y las que se ven siempre", () => {
  assert.deepEqual(lineaFotos(60), [
    "Publicás hasta 50 fotos por día",
    "En tu página se ven siempre 60 fotos: las 10 de tu local + 50 que cambiás cuando quieras",
  ]);
  assert.equal(lineaFotos(130)[0], "Publicás hasta 120 fotos por día");
  assert.equal(lineaFotos(510)[1], "En tu página se ven siempre 510 fotos: las 10 de tu local + 500 que cambiás cuando quieras");
});

test("el gratis sólo lleva portada; un tope chico no promete fotos por día", () => {
  assert.deepEqual(lineaFotos(0), ["Sólo foto de portada"]);
  assert.deepEqual(lineaFotos(1), ["1 foto de tu local"]);
  assert.deepEqual(lineaFotos(10), ["10 fotos de tu local"]);
  assert.deepEqual(lineaFotos(null), []);
});

test("el gratis no muestra la cuota de publicaciones; los pagos sí", () => {
  assert.equal(lineaCuota({ publicaciones_mes: 50, esGratis: true }), null);
  assert.equal(lineaCuota({ publicaciones_mes: 25, esGratis: false }), "Hasta 25 publicaciones por mes");
  assert.equal(lineaCuota({ publicaciones_mes: null, esGratis: false }), "Publicaciones sin límite");
});
