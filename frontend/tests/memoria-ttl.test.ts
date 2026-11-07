import test from "node:test";
import assert from "node:assert/strict";
import { conMemoriaTtl } from "../lib/memoria-ttl";

/** Deja correr la regeneración que quedó en segundo plano. */
const esperarFondo = () => new Promise((r) => setTimeout(r, 0));

test("recuerda el resultado hasta que vence; vencido, sirve el anterior y regenera en segundo plano", async () => {
  let t = 0;
  let llamadas = 0;
  const leer = conMemoriaTtl(1000, async () => ++llamadas, () => t);
  assert.equal(await leer(), 1);
  t = 999;
  assert.equal(await leer(), 1);
  t = 1000;
  assert.equal(await leer(), 1);
  await esperarFondo();
  assert.equal(llamadas, 2);
  assert.equal(await leer(), 2);
});

test("una regeneración lenta no hace esperar a los pedidos si hay uno bueno", async () => {
  let t = 0;
  let llamadas = 0;
  const leer = conMemoriaTtl(1000, async () => {
    llamadas++;
    if (llamadas > 1) await new Promise(() => {});   // se cuelga para siempre
    return "v1";
  }, () => t);
  assert.equal(await leer(), "v1");
  t = 5000;
  assert.equal(await leer(), "v1");
  assert.equal(await leer(), "v1");
  assert.equal(llamadas, 2);   // la colgada no se repite: un solo cálculo a la vez
});

test("pedidos simultáneos comparten una sola lectura", async () => {
  let llamadas = 0;
  const leer = conMemoriaTtl(1000, async () => { llamadas++; await new Promise((r) => setTimeout(r, 5)); return "ok"; });
  const r = await Promise.all([leer(), leer(), leer()]);
  assert.deepEqual(r, ["ok", "ok", "ok"]);
  assert.equal(llamadas, 1);
});

test("sin resultado previo, una falla sube y NO se recuerda", async () => {
  let llamadas = 0;
  const leer = conMemoriaTtl(1000, async () => {
    llamadas++;
    if (llamadas === 1) throw new Error("base caída");
    return "bien";
  });
  await assert.rejects(leer(), /base caída/);
  assert.equal(await leer(), "bien");
});

test("si falla la regeneración se sirve el último bueno y se reintenta al rato", async () => {
  let t = 0;
  let llamadas = 0;
  const leer = conMemoriaTtl(1000, async () => {
    llamadas++;
    if (llamadas === 2) throw new Error("base caída");
    return `v${llamadas}`;
  }, () => t);
  assert.equal(await leer(), "v1");
  t = 1000;
  assert.equal(await leer(), "v1");
  await esperarFondo();
  assert.equal(llamadas, 2);
  t = 30_000;
  assert.equal(await leer(), "v1");
  assert.equal(llamadas, 2);
  t = 61_000;
  assert.equal(await leer(), "v1");
  await esperarFondo();
  assert.equal(await leer(), "v3");
});
