// La línea «comercios nuevos» del home (lib/comercios-nuevos-pure).
import test from "node:test";
import assert from "node:assert/strict";
import { CONTAR_DESDE, desdeConteo, lineaComerciosNuevos } from "../lib/comercios-nuevos-pure";

test("la ventana son las últimas 24 horas, pero nunca antes del 7/11", () => {
  assert.equal(desdeConteo(new Date("2026-11-06T20:00:00-04:00")), new Date(CONTAR_DESDE).toISOString());
  assert.equal(desdeConteo(new Date("2026-11-07T10:00:00-04:00")), new Date(CONTAR_DESDE).toISOString());
  assert.equal(desdeConteo(new Date("2026-11-10T10:00:00-04:00")), new Date("2026-11-09T10:00:00-04:00").toISOString());
});

test("con número dice cuántos; sin número no inventa uno", () => {
  assert.equal(lineaComerciosNuevos(512), "512 comercios nuevos en las últimas 24 horas");
  assert.equal(lineaComerciosNuevos(1), "1 comercio nuevo en las últimas 24 horas");
  assert.equal(lineaComerciosNuevos(1500), "1.500 comercios nuevos en las últimas 24 horas");
  assert.equal(lineaComerciosNuevos(0), "Cada día se suman comercios nuevos");
  assert.equal(lineaComerciosNuevos(null), "Cada día se suman comercios nuevos");
});
