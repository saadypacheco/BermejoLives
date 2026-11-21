// La foto grande de la ficha recorta igual que la tarjeta de los resultados (lib/ficha-foto-pure.ts).
import { test } from "node:test";
import assert from "node:assert/strict";
import { proporcionFicha, PROP_MIN, PROP_MAX } from "../lib/ficha-foto-pure";

test("una vertical de celular va en 4:3, como la tarjeta, y no en un cuadrado", () => {
  assert.equal(proporcionFicha(720, 1280), PROP_MIN);
  assert.equal(proporcionFicha(960, 1280), PROP_MIN);
  assert.equal(proporcionFicha(1000, 1000), PROP_MIN);
});

test("una horizontal se ve entera hasta 2:1", () => {
  assert.equal(proporcionFicha(1280, 720), 1280 / 720);
  assert.equal(proporcionFicha(1600, 1200), 4 / 3);
  assert.equal(proporcionFicha(3000, 1000), PROP_MAX);
});

test("sin medidas (la imagen todavía no cargó) queda en 4:3", () => {
  assert.equal(proporcionFicha(0, 0), PROP_MIN);
  assert.equal(proporcionFicha(NaN, 500), PROP_MIN);
});
