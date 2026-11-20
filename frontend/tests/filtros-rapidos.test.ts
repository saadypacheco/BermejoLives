// Los interruptores «Abiertos» y «Más cerca» (lib/filtros-rapidos.ts): cómo se guardan y cómo se suman a los enlaces.
import test from "node:test";
import assert from "node:assert/strict";
import {
  CLAVE_FILTROS_RAPIDOS, SIN_FILTROS, conFiltros, hayFiltros, leerFiltros, serializarFiltros,
} from "../lib/filtros-rapidos";

const AMBOS = { abiertos: true, cerca: true };

test("la clave de sessionStorage es la acordada", () => {
  assert.equal(CLAVE_FILTROS_RAPIDOS, "uk-filtros-rapidos");
});

test("serializar y leer son inversos", () => {
  for (const f of [SIN_FILTROS, AMBOS, { abiertos: true, cerca: false }, { abiertos: false, cerca: true }]) {
    assert.deepEqual(leerFiltros(serializarFiltros(f)), f);
  }
  assert.equal(serializarFiltros({ abiertos: true, cerca: false }), '{"abiertos":true,"cerca":false}');
});

test("leerFiltros: nada, texto roto o tipos raros vuelven a todo apagado", () => {
  assert.deepEqual(leerFiltros(null), SIN_FILTROS);
  assert.deepEqual(leerFiltros(""), SIN_FILTROS);
  assert.deepEqual(leerFiltros("{no es json"), SIN_FILTROS);
  assert.deepEqual(leerFiltros("null"), SIN_FILTROS);
  assert.deepEqual(leerFiltros("42"), SIN_FILTROS);
  assert.deepEqual(leerFiltros('{"abiertos":"si","cerca":1}'), SIN_FILTROS);
  assert.deepEqual(leerFiltros('{"abiertos":true}'), { abiertos: true, cerca: false });
});

test("hayFiltros", () => {
  assert.equal(hayFiltros(SIN_FILTROS), false);
  assert.equal(hayFiltros({ abiertos: false, cerca: true }), true);
});

test("conFiltros: sin interruptores prendidos, el enlace no cambia", () => {
  assert.equal(conFiltros("/buscar?rubro=farmacia&vista=mapa", SIN_FILTROS), "/buscar?rubro=farmacia&vista=mapa");
});

test("conFiltros: suma abierto=1 y cerca=1 a los enlaces al buscador y al mapa", () => {
  assert.equal(conFiltros("/buscar?rubro=farmacia&vista=mapa", AMBOS), "/buscar?rubro=farmacia&vista=mapa&abierto=1&cerca=1");
  assert.equal(conFiltros("/buscar", { abiertos: true, cerca: false }), "/buscar?abierto=1");
  assert.equal(conFiltros("/buscar?q=zapatillas", { abiertos: false, cerca: true }), "/buscar?q=zapatillas&cerca=1");
  assert.equal(conFiltros("/mapa", AMBOS), "/mapa?abierto=1&cerca=1");
});

test("conFiltros: no repite lo que el enlace ya trae y conserva el #ancla", () => {
  assert.equal(conFiltros("/buscar?abierto=1&rubro=cajeros", AMBOS), "/buscar?abierto=1&rubro=cajeros&cerca=1");
  assert.equal(conFiltros("/buscar?rubro=x#lista", { abiertos: true, cerca: false }), "/buscar?rubro=x&abierto=1#lista");
});

test("conFiltros: lo que no es buscador ni mapa no se toca", () => {
  for (const href of ["/comercios/zapateria#ficha-encontrar", "/ofertas", "/tarija/farmacias-de-turno", "https://wa.me/591", "/buscador-de-algo", "/"]) {
    assert.equal(conFiltros(href, AMBOS), href);
  }
});
