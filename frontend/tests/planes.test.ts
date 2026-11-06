// Las líneas de /planes que salen de los números del plan (lib/planes-pure).
import test from "node:test";
import assert from "node:assert/strict";
import { lineaCuota, lineaFotos } from "../lib/planes-pure";

test("la línea de fotos separa las 10 del local de las que se cambian", () => {
  assert.equal(lineaFotos(60), "10 fotos de tu local + 50 fotos que podés cambiar todos los días");
  assert.equal(lineaFotos(130), "10 fotos de tu local + 120 fotos que podés cambiar todos los días");
  assert.equal(lineaFotos(510), "10 fotos de tu local + 500 fotos que podés cambiar todos los días");
});

test("el gratis sólo lleva portada; un tope chico no promete fotos para cambiar", () => {
  assert.equal(lineaFotos(0), "Sólo foto de portada");
  assert.equal(lineaFotos(1), "1 foto de tu local");
  assert.equal(lineaFotos(10), "10 fotos de tu local");
  assert.equal(lineaFotos(null), null);
});

test("la cuota del gratis dice cuántos meses dura", () => {
  assert.equal(lineaCuota({ publicaciones_mes: 50, publica_meses: 2, esGratis: true }),
    "Hasta 50 publicaciones por mes durante los primeros 2 meses");
  assert.equal(lineaCuota({ publicaciones_mes: 25, publica_meses: null, esGratis: false }), "Hasta 25 publicaciones por mes");
  assert.equal(lineaCuota({ publicaciones_mes: null, publica_meses: null, esGratis: false }), "Publicaciones sin límite");
});
