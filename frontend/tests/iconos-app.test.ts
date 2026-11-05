// Íconos del sitio y de la app instalada: existen, miden lo que dicen, y el
// manifest separa `any` de `maskable` (un solo dibujo no sirve para los dos).
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import manifest from "../app/manifest";

// Los tests corren desde `frontend/` (npm test): `public/` está al lado.
const publico = (f: string) => join(process.cwd(), "public", f);

function medidaPng(f: string): { w: number; h: number } {
  const b = readFileSync(publico(f));
  assert.equal(b.subarray(1, 4).toString("ascii"), "PNG", `${f} no es un PNG`);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

test("favicon.ico existe y trae 16, 32 y 48 px", () => {
  assert.ok(existsSync(publico("favicon.ico")), "falta public/favicon.ico (da 404 y lo piden los robots)");
  const b = readFileSync(publico("favicon.ico"));
  assert.equal(b.readUInt16LE(0), 0, "cabecera ICO");
  assert.equal(b.readUInt16LE(2), 1, "tipo ICO");
  const n = b.readUInt16LE(4);
  const lados = Array.from({ length: n }, (_, i) => b[6 + i * 16] || 256).sort((a, c) => a - c);
  assert.deepEqual(lados, [16, 32, 48]);
});

test("ícono de la app: 192, 512, maskable 512 y apple-touch 180, cuadrados", () => {
  assert.deepEqual(medidaPng("icon-192.png"), { w: 192, h: 192 });
  assert.deepEqual(medidaPng("icon-512.png"), { w: 512, h: 512 });
  assert.deepEqual(medidaPng("icon-maskable-512.png"), { w: 512, h: 512 });
  assert.deepEqual(medidaPng("apple-touch-icon.png"), { w: 180, h: 180 });
});

test("manifest: `any` y `maskable` en entradas separadas, cada una con su archivo", () => {
  const icons = manifest().icons ?? [];
  const maskable = icons.filter((i) => i.purpose === "maskable");
  const cualquiera = icons.filter((i) => i.purpose === "any");
  assert.equal(icons.filter((i) => String(i.purpose).includes(" ")).length, 0, "nada de «any maskable» juntos");
  assert.equal(maskable.length, 1);
  assert.equal(maskable[0].src, "/icon-maskable-512.png");
  assert.deepEqual(cualquiera.map((i) => i.src).sort(), ["/icon-192.png", "/icon-512.png"]);
  for (const i of icons) assert.ok(existsSync(publico(i.src.replace(/^\//, ""))), `${i.src} no existe`);
  assert.notEqual(maskable[0].src, "/icon-512.png", "el maskable no puede ser el mismo dibujo que `any`");
});
