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
