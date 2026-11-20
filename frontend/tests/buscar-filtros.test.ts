// La primera tanda de /buscar se arma en el servidor (HTML para rastreadores sin
// JavaScript) y el cliente NO la repite si coincide. Estas pruebas fijan que los
// dos lados calculen la MISMA consulta a partir de la URL.
import test from "node:test";
import assert from "node:assert/strict";
import { claveBusqueda, filtrosDeBusqueda, paramsDeUrl } from "../lib/buscar-filtros";

test("paramsDeUrl: sin parámetros, la ciudad es la del selector", () => {
  const p = paramsDeUrl({}, "bermejo");
  assert.deepEqual(p, { q: "", rubro: "", subcategoria: "", modalidad: "", zona: "", ciudad: "bermejo", precioMax: "" });
  assert.deepEqual(filtrosDeBusqueda(p), { q: "", rubro: "", subcategoria: "", modalidad: "", zona: "", ciudad: "bermejo", precioMax: undefined });
});

test("paramsDeUrl: ?ciudad= de la URL pisa a la del selector; q, rubro y sub se leen", () => {
  const p = paramsDeUrl({ ciudad: "tarija", q: "jeans", rubro: "ropa", sub: "mujer", precio_max: "100" }, "bermejo");
  assert.equal(p.ciudad, "tarija");
  assert.equal(p.q, "jeans");
  assert.equal(p.rubro, "ropa");
  assert.equal(p.subcategoria, "mujer");
  assert.equal(filtrosDeBusqueda(p).precioMax, 100);
});

test("paramsDeUrl: un parámetro repetido toma el primero (no rompe)", () => {
  assert.equal(paramsDeUrl({ q: ["a", "b"] }, "").q, "a");
});

test("filtrosDeBusqueda: un servicio escrito se busca por su rubro, no por texto", () => {
  const f = filtrosDeBusqueda(paramsDeUrl({ q: "baño público" }, "bermejo"));
  assert.equal(f.rubro, "banos");
  assert.equal(f.q, "");
});

test("filtrosDeBusqueda: con un rubro elegido, el texto sigue siendo texto", () => {
  const f = filtrosDeBusqueda(paramsDeUrl({ q: "baño", rubro: "ropa" }, "bermejo"));
  assert.equal(f.rubro, "ropa");
  assert.equal(f.q, "baño");
});

test("claveBusqueda: igual para la misma búsqueda, distinta si cambia algo", () => {
  const a = paramsDeUrl({ q: "jeans", rubro: "ropa" }, "bermejo");
  const b = paramsDeUrl({ rubro: "ropa", q: "jeans" }, "bermejo");
  assert.equal(claveBusqueda(a), claveBusqueda(b));
  assert.notEqual(claveBusqueda(a), claveBusqueda(paramsDeUrl({ q: "jeans" }, "bermejo")));
  assert.notEqual(claveBusqueda(a), claveBusqueda(paramsDeUrl({ q: "jeans", rubro: "ropa" }, "tarija")));
});

// ── «Abiertos» (?abierto=1) ──────────────────────────────────────────────────
import { soloAbiertos } from "../lib/buscar-filtros";

test("soloAbiertos: deja sólo los abiertos ahora; sin horario o ilegible no cuenta como abierto", () => {
  // Miércoles 14:00 (hora de Bolivia: el Date ya trae esos getHours/getDay).
  const ahora = new Date(2026, 10, 18, 14, 0);
  const lista = [
    { id: "abierto", horario: "Lun a Sáb 9-19" },
    { id: "cerrado", horario: "Lun a Sáb 16-20" },
    { id: "sin-horario", horario: null },
    { id: "ilegible", horario: "consultar por WhatsApp" },
    { id: "domingo", horario: "Dom 9-13" },
  ];
  assert.deepEqual(soloAbiertos(lista, ahora).map((c) => c.id), ["abierto"]);
});

test("soloAbiertos: un boliche que cruza la medianoche está abierto a la 1 de la mañana de su noche", () => {
  const ahora = new Date(2026, 10, 21, 1, 0); // sábado 1:00 = la noche del viernes
  assert.deepEqual(soloAbiertos([{ horario: "Vie 22-4" }, { horario: "Sáb 22-4" }], ahora).length, 1);
});
