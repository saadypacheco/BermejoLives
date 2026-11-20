// El clima por ciudad (lib/clima-ciudad-pure.ts): un dato de más de 3 horas, o sin fecha, no se muestra.
import test from "node:test";
import assert from "node:assert/strict";
import { VIGENCIA_CLIMA_MS, climaVigente } from "../lib/clima-ciudad-pure";

const AHORA = new Date("2026-11-20T15:00:00Z");
const hace = (min: number) => new Date(AHORA.getTime() - min * 60_000).toISOString();

test("un dato reciente se muestra, con temperatura y descripción", () => {
  assert.deepEqual(climaVigente({ temp_c: 22.4, descripcion: "Despejado", actualizado_en: hace(20) }, AHORA), { temp_c: 22.4, descripcion: "Despejado" });
});

test("la vigencia es de 3 horas: justo en el límite se muestra, un minuto después no", () => {
  assert.equal(VIGENCIA_CLIMA_MS, 3 * 60 * 60 * 1000);
  assert.notEqual(climaVigente({ temp_c: 20, descripcion: null, actualizado_en: hace(180) }, AHORA), null);
  assert.equal(climaVigente({ temp_c: 20, descripcion: null, actualizado_en: hace(181) }, AHORA), null);
});

test("sin fila, sin temperatura o sin fecha: nada", () => {
  assert.equal(climaVigente(null, AHORA), null);
  assert.equal(climaVigente(undefined, AHORA), null);
  assert.equal(climaVigente({ temp_c: null, descripcion: "x", actualizado_en: hace(1) }, AHORA), null);
  assert.equal(climaVigente({ temp_c: "calor", descripcion: "x", actualizado_en: hace(1) }, AHORA), null);
  assert.equal(climaVigente({ temp_c: 20, descripcion: "x" }, AHORA), null);
  assert.equal(climaVigente({ temp_c: 20, descripcion: "x", actualizado_en: "ayer" }, AHORA), null);
});

test("una fecha en el futuro (reloj corrido) tampoco se confía", () => {
  assert.equal(climaVigente({ temp_c: 20, descripcion: null, actualizado_en: hace(-60) }, AHORA), null);
});

test("numeric llega como texto desde PostgREST: se acepta; la descripción vacía queda en null", () => {
  assert.deepEqual(climaVigente({ temp_c: "18.5", descripcion: "  ", actualizado_en: hace(5) }, AHORA), { temp_c: 18.5, descripcion: null });
  assert.deepEqual(climaVigente({ temp_c: 0, descripcion: "Helado", actualizado_en: hace(5) }, AHORA), { temp_c: 0, descripcion: "Helado" });
});
