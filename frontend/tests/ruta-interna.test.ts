// Redirección tras el ingreso: sólo rutas del mismo sitio (lib/ruta-interna).
import test from "node:test";
import assert from "node:assert/strict";
import { rutaInternaSegura } from "../lib/ruta-interna";

test("acepta rutas internas", () => {
  assert.equal(rutaInternaSegura("/tienda"), "/tienda");
  assert.equal(rutaInternaSegura("/tienda/p/1?x=2#y"), "/tienda/p/1?x=2#y");
  assert.equal(rutaInternaSegura("/"), "/");
});

test("rechaza lo que sale del sitio", () => {
  for (const malo of ["//evil.com", "/\\evil.com", "///evil.com", "/\t/evil.com", "/\n/evil.com",
    "https://evil.com", "evil.com", "", "javascript:alert(1)", "/a\\b"]) {
    assert.equal(rutaInternaSegura(malo), null, malo);
  }
  assert.equal(rutaInternaSegura(null), null);
  assert.equal(rutaInternaSegura(undefined), null);
});
