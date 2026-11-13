// Fuente «turismo» de Importados (docs/importar-turismo.md): filtro, ficha editable y enlace de origen.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { esTarjeta, paramFuente, urlDeOrigen, usaFichaEditable, type FuenteFiltro } from "../lib/tarjetas-pure";

test("el filtro turismo manda fuente=turismo", () => {
  const f: FuenteFiltro = "turismo";
  assert.equal(paramFuente(f), "turismo");
  assert.equal(paramFuente("todas"), undefined);
});

test("usaFichaEditable: tarjeta y turismo sí, osm no; esTarjeta sigue siendo sólo tarjeta", () => {
  assert.equal(usaFichaEditable({ fuente: "tarjeta" }), true);
  assert.equal(usaFichaEditable({ fuente: "turismo" }), true);
  assert.equal(usaFichaEditable({ fuente: "osm" }), false);
  assert.equal(usaFichaEditable({ fuente: "" }), false);
  assert.equal(esTarjeta({ fuente: "turismo" }), false);
  assert.equal(esTarjeta({ fuente: "tarjeta" }), true);
});

test("urlDeOrigen toma la primera URL del texto leído", () => {
  const texto = "Fuente: https://tarijaturismo.com/hoteles/\nHotel Plaza\nhttps://facebook.com/hotelplaza";
  assert.equal(urlDeOrigen(texto), "https://tarijaturismo.com/hoteles/");
  assert.equal(urlDeOrigen("ver (http://ejemplo.bo/a)."), "http://ejemplo.bo/a");
  assert.equal(urlDeOrigen("sin enlace acá"), null);
  assert.equal(urlDeOrigen(""), null);
  assert.equal(urlDeOrigen(null), null);
  assert.equal(urlDeOrigen(undefined), null);
});

test("urlDeOrigen no devuelve esquemas raros", () => {
  assert.equal(urlDeOrigen("javascript:alert(1) ftp://x.com"), null);
  assert.equal(urlDeOrigen("https://"), null);
});

test("la ficha no pide la foto si no hay (tiene_foto) y el panel lista la fuente turismo", () => {
  const ficha = readFileSync(resolve(process.cwd(), "components/importados-tarjetas.tsx"), "utf8");
  assert.match(ficha, /tiene_foto === true && <FotoTarjeta/);
  assert.match(ficha, /De la página de turismo/);
  const panel = readFileSync(resolve(process.cwd(), "components/importados-panel.tsx"), "utf8");
  assert.match(panel, /key: "turismo", label: "Turismo"/);
  assert.equal(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(ficha + panel), false);
});
