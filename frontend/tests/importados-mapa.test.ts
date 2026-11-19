// Importados › Mapa: la parte pura (colores, leyenda, filtro por fuentes, resumen, «Ver la ficha»)
// y que el componente no arme HTML con el nombre del comercio (texto de terceros).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  COLOR_FUENTE, COLOR_FUENTE_OTRA, MSG_SIN_MAPA, alternarFuente, busquedaDeFicha, colorFuente, contarPorFuente,
  etiquetaFuente, filtrarPorFuentes, limitesDe, lineasPopup, miles, puntoValido, resumenMapa,
} from "../lib/importados-mapa-pure";

const pt = (fuente: string, repetido = false, lat = -17.78, lng = -63.18) => ({ fuente, repetido, lat, lng });

test("colores: uno por fuente, todos distintos entre sí y distintos del de por defecto", () => {
  const fuentes = ["overture", "turismo", "anh", "aduana", "osm", "tarjeta"];
  const colores = fuentes.map(colorFuente);
  assert.equal(new Set(colores).size, fuentes.length);
  assert.ok(!colores.includes(COLOR_FUENTE_OTRA));
  for (const f of fuentes) assert.match(COLOR_FUENTE[f], /^#[0-9A-F]{6}$/i);
  assert.equal(colorFuente("fuente-nueva"), COLOR_FUENTE_OTRA);
});

test("etiquetaFuente: nombre corto de la leyenda; una fuente desconocida se muestra como viene", () => {
  assert.equal(etiquetaFuente("anh"), "ANH");
  assert.equal(etiquetaFuente("osm"), "OSM");
  assert.equal(etiquetaFuente("otra"), "otra");
  assert.equal(etiquetaFuente(""), "Otras");
});

test("contarPorFuente: de mayor a menor, con los repetidos aparte", () => {
  const r = contarPorFuente([pt("osm"), pt("overture", true), pt("overture"), pt("overture"), pt("anh")]);
  assert.deepEqual(r, [
    { fuente: "overture", n: 3, repetidos: 1 },
    { fuente: "anh", n: 1, repetidos: 0 },
    { fuente: "osm", n: 1, repetidos: 0 },
  ]);
  assert.deepEqual(contarPorFuente([]), []);
});

test("filtrarPorFuentes: saca las destildadas y no toca la lista original", () => {
  const items = [pt("osm"), pt("anh"), pt("overture")];
  assert.equal(filtrarPorFuentes(items, new Set()).length, 3);
  assert.deepEqual(filtrarPorFuentes(items, new Set(["osm", "anh"])).map((i) => i.fuente), ["overture"]);
  assert.equal(items.length, 3);
});

test("alternarFuente: destilda, vuelve a tildar y no muta el conjunto anterior", () => {
  const a = new Set<string>();
  const b = alternarFuente(a, "osm");
  assert.ok(b.has("osm") && !a.has("osm"));
  assert.ok(!alternarFuente(b, "osm").has("osm"));
});

test("limitesDe: esquinas que encierran a los puntos; null sin puntos o con coordenadas rotas", () => {
  assert.deepEqual(limitesDe([{ lat: -17.7, lng: -63.2 }, { lat: -17.9, lng: -63.1 }]), [[-17.9, -63.2], [-17.7, -63.1]]);
  assert.equal(limitesDe([]), null);
  assert.equal(limitesDe([{ lat: NaN, lng: 1 }, { lat: 999, lng: 0 }]), null);
});

test("puntoValido: finito y dentro de rango", () => {
  assert.equal(puntoValido({ lat: -17.78, lng: -63.18 }), true);
  assert.equal(puntoValido({ lat: Infinity, lng: 0 }), false);
  assert.equal(puntoValido({ lat: 0, lng: 181 }), false);
});

test("miles: punto de miles sin depender del ICU", () => {
  assert.equal(miles(18670), "18.670");
  assert.equal(miles(12), "12");
  assert.equal(miles(1234567), "1.234.567");
  assert.equal(miles(0), "0");
});

test("resumenMapa: «18.670 en el mapa · 12 sin punto»; sin «sin punto» si no hay; avisa si el servidor cortó", () => {
  assert.equal(resumenMapa({ total: 18670, sin_punto: 12, truncado: false }, 18670), "18.670 en el mapa · 12 sin punto");
  assert.equal(resumenMapa({ total: 40, sin_punto: 0, truncado: false }, 40), "40 en el mapa");
  const t = resumenMapa({ total: 45000, sin_punto: 3, truncado: true }, 30000);
  assert.match(t, /30\.000 de 45\.000/);
  assert.match(t, /3 sin punto/);
  assert.match(t, /filtrá por fuente/);
});

test("busquedaDeFicha: búsqueda por nombre y la fuente del punto si es una del filtro", () => {
  assert.deepEqual(busquedaDeFicha({ nombre: " Farmacia Sol ", fuente: "overture", rubro_slug: "farmacia" }), { q: "Farmacia Sol", fuente: "overture" });
  assert.deepEqual(busquedaDeFicha({ nombre: null, fuente: "anh", rubro_slug: null }), { q: "", fuente: "anh" });
  assert.deepEqual(busquedaDeFicha({ nombre: "X", fuente: "desconocida", rubro_slug: null }), { q: "X", fuente: null });
  assert.equal(busquedaDeFicha({ nombre: "Plaza", fuente: "turismo", rubro_slug: "para-visitar" }).fuente, "turismo-visitar");
  assert.equal(busquedaDeFicha({ nombre: "Guía", fuente: "turismo", rubro_slug: "turismo" }).fuente, "turismo");
});

test("lineasPopup: nombre, fuente larga, rubro y los dos avisos sólo cuando corresponden", () => {
  const base = lineasPopup({ nombre: "Café <b>X</b>", fuente: "overture", rubro_slug: "cafeteria", repetido: false, ubicacion: null });
  assert.equal(base[0], "Café <b>X</b>"); // texto plano: el componente lo pone con textContent
  assert.match(base[1], /Overture/);
  assert.ok(base.includes("Rubro: cafeteria"));
  assert.equal(base.length, 3);
  const todo = lineasPopup({ nombre: null, fuente: "anh", rubro_slug: null, repetido: true, ubicacion: "aproximada" });
  assert.equal(todo[0], "(sin nombre)");
  assert.ok(todo.includes("Repetido: ya hay uno parecido en URUKU"));
  assert.ok(todo.includes("Punto aproximado: confirmalo"));
});

test("el aviso de versión vieja del mapa es propio", () => {
  assert.match(MSG_SIN_MAPA, /mapa/);
});

test("importados-mapa.tsx: el popup no arma HTML (sin innerHTML ni insertAdjacentHTML) y no usa emojis", () => {
  const raiz = process.cwd();
  for (const rel of ["components/importados-mapa.tsx", "lib/importados-mapa-pure.ts"]) {
    const src = readFileSync(resolve(raiz, rel), "utf8");
    assert.equal(/innerHTML|outerHTML|insertAdjacentHTML|dangerouslySetInnerHTML|document\.write/.test(src), false, `${rel} arma HTML`);
    assert.equal(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(src), false, `${rel} tiene un emoji`);
  }
  const comp = readFileSync(resolve(raiz, "components/importados-mapa.tsx"), "utf8");
  assert.match(comp, /textContent/);
  assert.match(comp, /createElement/);
  assert.match(comp, /preferCanvas: true/);
  assert.match(comp, /circleMarker/);
});
