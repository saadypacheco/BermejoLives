import test from "node:test";
import assert from "node:assert/strict";
import { conFundador, esFresca, fechaLarga } from "../lib/seo-paginas";

test("esFresca: menos de 36 h sí, más no, sin fecha no", () => {
  const ahora = new Date("2026-11-02T12:00:00Z");
  assert.equal(esFresca("2026-11-02T01:00:00Z", ahora), true);
  assert.equal(esFresca("2026-11-01T01:00:00Z", ahora), true);   // 35 h
  assert.equal(esFresca("2026-10-31T23:00:00Z", ahora), false);  // 37 h
  assert.equal(esFresca(null, ahora), false);
  assert.equal(esFresca("basura", ahora), false);
});

test("fechaLarga: día de Bolivia", () => {
  assert.equal(fechaLarga("2026-10-25T20:00:00Z"), "25 de octubre");
  assert.equal(fechaLarga("2026-10-26T02:00:00Z"), "25 de octubre"); // 22:00 en La Paz
  assert.equal(fechaLarga(null), null);
});

test("conFundador: sólo la Organization lleva founder y foundingDate", () => {
  const out = conFundador([{ "@type": "Organization", name: "URUKU" }, { "@type": "WebSite" }]);
  assert.deepEqual(out[0].founder, { "@type": "Person", name: "Saady Pacheco", jobTitle: "Ingeniero de sistemas" });
  assert.equal(out[0].foundingDate, "2026-05");
  assert.equal(out[1].founder, undefined);
});
