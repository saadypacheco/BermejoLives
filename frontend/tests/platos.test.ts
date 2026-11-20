// Platos típicos (lib/platos-pure.ts, docs/home-ciudades.md §15) y el catálogo de ilustraciones (components/ilustraciones).
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  SUBCATEGORIAS_COMIDA_TIPICA, agruparPlatos, cambiosDeEdicion, hrefDondeComer, platoDeFila, puedeAprobarPlato, rutaSabores,
  type PlatoTipico,
} from "../lib/platos-pure";
import { ILUSTRACIONES, Ilustracion } from "../components/ilustraciones";

const plato = (extra: Partial<PlatoTipico> = {}): PlatoTipico => ({
  id: "p1", ciudad_id: "c1", tipo: "plato", nombre: "Saice", descripcion: "Un guiso picante de carne con arroz.", fuente_url: "https://tarijaturismo.com/x",
  estado: "aprobado", activo: true, updated_at: null, ...extra,
});

test("agruparPlatos: platos, repostería y bebidas en ese orden, cada grupo por nombre, sin los tipos vacíos", () => {
  const r = agruparPlatos([
    plato({ id: "1", nombre: "Ranga" }), plato({ id: "2", nombre: "Chancho a la cruz" }), plato({ id: "3", tipo: "bebida", nombre: "Singani" }),
    plato({ id: "4", nombre: "Ñandú" }),
  ]);
  assert.deepEqual(r.map((s) => s.tipo), ["plato", "bebida"]);
  assert.deepEqual(r[0].platos.map((p) => p.nombre), ["Chancho a la cruz", "Ñandú", "Ranga"]);
  assert.deepEqual(r.map((s) => s.titulo), ["Platos", "Bebidas"]);
});

test("agruparPlatos: sólo aprobados y activos (pendientes y rechazados no se ven); sin ninguno, la lista es vacía (→ 404)", () => {
  const r = agruparPlatos([plato({ id: "1", estado: "pendiente" }), plato({ id: "2", estado: "rechazado" }), plato({ id: "3", activo: false })]);
  assert.deepEqual(r, []);
  assert.deepEqual(agruparPlatos([]), []);
});

test("platoDeFila: normaliza una fila válida y descarta las rotas", () => {
  const ok = platoDeFila({ id: "x", ciudad_id: "c", tipo: "reposteria", nombre: "  Rollo de nuez ", descripcion: " Dulce. ", fuente_url: "", estado: "pendiente", activo: true, updated_at: "2026-11-20T10:00:00Z" });
  assert.deepEqual(ok, { id: "x", ciudad_id: "c", tipo: "reposteria", nombre: "Rollo de nuez", descripcion: "Dulce.", fuente_url: null, estado: "pendiente", activo: true, updated_at: "2026-11-20T10:00:00Z" });
  assert.equal(platoDeFila(null), null);
  assert.equal(platoDeFila({ id: "x", tipo: "plato", nombre: " ", estado: "aprobado" }), null);
  assert.equal(platoDeFila({ id: "x", tipo: "otro", nombre: "A", estado: "aprobado" }), null);
  assert.equal(platoDeFila({ id: "x", tipo: "plato", nombre: "A", estado: "borrador" }), null);
  assert.equal(platoDeFila({ tipo: "plato", nombre: "A", estado: "aprobado" }), null);
});

test("cambiosDeEdicion: sólo lo que cambió, sin espacios de más; el nombre no puede quedar vacío", () => {
  const p = plato();
  assert.deepEqual(cambiosDeEdicion(p, { nombre: p.nombre, descripcion: p.descripcion }), { cambios: {}, error: null });
  assert.deepEqual(cambiosDeEdicion(p, { nombre: "  Saice tarijeño ", descripcion: p.descripcion }), { cambios: { nombre: "Saice tarijeño" }, error: null });
  assert.deepEqual(cambiosDeEdicion(p, { nombre: p.nombre, descripcion: " Otro texto. " }), { cambios: { descripcion: "Otro texto." }, error: null });
  assert.match(cambiosDeEdicion(p, { nombre: "   ", descripcion: "x" }).error ?? "", /nombre/);
  assert.match(cambiosDeEdicion(p, { nombre: "A".repeat(121), descripcion: "x" }).error ?? "", /120/);
  assert.match(cambiosDeEdicion(p, { nombre: "A", descripcion: "x".repeat(601) }).error ?? "", /600/);
});

test("puedeAprobarPlato: sin texto propio no se aprueba", () => {
  assert.equal(puedeAprobarPlato({ nombre: "Saice", descripcion: "Un guiso." }), true);
  assert.equal(puedeAprobarPlato({ nombre: "Saice", descripcion: "  " }), false);
  assert.equal(puedeAprobarPlato({ nombre: "", descripcion: "Un guiso." }), false);
});

test("«Dónde comer comida típica»: a la subcategoría con locales; si no, a restaurantes; sin restaurantes, sin botón", () => {
  assert.equal(hrefDondeComer("Comida boliviana", true), "/buscar?rubro=restaurantes&sub=Comida%20boliviana&vista=mapa");
  assert.equal(hrefDondeComer(null, true), "/buscar?rubro=restaurantes&vista=mapa");
  assert.equal(hrefDondeComer(null, false), null);
  // Así guarda la importación de turismo `boliviana-regional-criolla` (subcategorias_turismo.py): es la primera que se prueba.
  assert.equal(SUBCATEGORIAS_COMIDA_TIPICA[0], "Comida boliviana");
  assert.equal(rutaSabores("tarija"), "/tarija/sabores");
});

test("ilustraciones: todas decorativas (aria-hidden), con degradés de id único aunque se repitan en la página", () => {
  assert.ok(ILUSTRACIONES.length >= 10);
  for (const id of ["vino", "centro", "miradores", "cascadas", "noche", "sabores", "lagunas", "parques", "museos", "mercados"] as const) {
    assert.ok(ILUSTRACIONES.includes(id), `falta ${id}`);
  }
  for (const id of ILUSTRACIONES) {
    const html = renderToStaticMarkup(createElement(Ilustracion, { id }));
    assert.match(html, /^<svg [^>]*aria-hidden="true"/, id);
    assert.doesNotMatch(html, /<img|<image|href="http/, `${id}: sin fotos ni recursos externos`);
    assert.match(html, /viewBox="0 0 \d+ \d+"/, id);
  }
  const dos = renderToStaticMarkup(createElement("div", null, createElement(Ilustracion, { id: "vino" }), createElement(Ilustracion, { id: "vino" })));
  const ids = [...dos.matchAll(/ id="([^"]+)"/g)].map((m) => m[1]);
  assert.ok(ids.length >= 8);
  assert.equal(new Set(ids).size, ids.length, "ids de degradé repetidos entre dos copias de la misma ilustración");
});

test("ilustraciones: la ruta del vino dice Viñedos, Bodegas y Singani, sin nombres de comercios", () => {
  const html = renderToStaticMarkup(createElement(Ilustracion, { id: "vino" }));
  for (const parada of ["Viñedos", "Bodegas", "Singani"]) assert.ok(html.includes(parada), parada);
});
