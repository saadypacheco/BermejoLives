// Los accesos de debajo del buscador (lib/accesos-ciudad.ts): hoteles y boliches al mapa, y ningún
// acceso que abra un mapa vacío.
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  HREF_HOTELES, HREF_NOCTURNA, accesoConComercios, listaAccesos, rubroDeHref, rubrosDeCiudad,
} from "../lib/accesos-ciudad";

const PARES = [
  { city_slug: "tarija", category_slug: "hospedaje" },
  { city_slug: "tarija", category_slug: "nocturna" },
  { city_slug: "tarija", category_slug: "farmacia" },
  { city_slug: "bermejo", category_slug: "banos" },
  { city_slug: "bermejo", category_slug: "cambio" },
];

test("hoteles y boliches van al mapa, filtrados por su rubro", () => {
  assert.equal(HREF_HOTELES, "/buscar?rubro=hospedaje&vista=mapa");
  assert.equal(HREF_NOCTURNA, "/buscar?rubro=nocturna&vista=mapa");
});

test("con hoteles y boliches en la ciudad, son los dos primeros accesos", () => {
  const lista = listaAccesos(false, rubrosDeCiudad(PARES, "tarija"));
  assert.deepEqual(lista.slice(0, 2).map((a) => a.t), ["Hoteles", "Boliches y karaoke"]);
  for (const a of lista) {
    assert.doesNotMatch(a.t, /\d/, "sin números");
    assert.doesNotMatch(a.t, /\p{Extended_Pictographic}/u, "sin emojis");
  }
});

test("un acceso a un rubro sin comercios en la ciudad no sale", () => {
  // Tarija: hay hoteles, boliches y farmacias; no hay baños, cajeros, taxis, wifi, cambio…
  const tarija = listaAccesos(false, rubrosDeCiudad(PARES, "tarija")).map((a) => a.href);
  assert.deepEqual(tarija, [HREF_HOTELES, HREF_NOCTURNA, "/buscar?rubro=farmacia&vista=mapa"]);
  // Bermejo (con guía): baños, y las guías y /cambio, que no son rubros y salen siempre.
  const bermejo = listaAccesos(true, rubrosDeCiudad(PARES, "bermejo")).map((a) => a.href);
  assert.deepEqual(bermejo, ["/buscar?rubro=banos&vista=mapa", "/cambio", "/guia#transporte", "/guia#frontera"]);
  // Bermejo sin guía: el cambio pasa a ser el rubro, y sale porque hay casas de cambio.
  assert.ok(listaAccesos(false, rubrosDeCiudad(PARES, "bermejo")).some((a) => a.href === "/buscar?rubro=cambio&vista=mapa"));
});

test("ciudad sin nada cargado: sólo los accesos que no son rubros", () => {
  const lista = listaAccesos(true, rubrosDeCiudad(PARES, "oruro"));
  assert.deepEqual(lista.map((a) => a.href), ["/cambio", "/guia#transporte", "/guia#frontera"]);
  assert.deepEqual(listaAccesos(false, rubrosDeCiudad(PARES, "oruro")), []);
});

test("si la lectura falló, salen los de siempre pero no hoteles, boliches ni «Para visitar»", () => {
  assert.equal(rubrosDeCiudad([], "tarija"), null, "la RPC devuelve [] ante un error");
  assert.equal(rubrosDeCiudad(null, "tarija"), null);
  assert.equal(rubrosDeCiudad(PARES, null), null);
  const lista = listaAccesos(true, null).map((a) => a.href);
  assert.ok(lista.includes("/buscar?rubro=banos&vista=mapa"));
  assert.ok(!lista.includes(HREF_HOTELES));
  assert.ok(!lista.includes(HREF_NOCTURNA));
  assert.ok(!lista.some((h) => h.includes("para-visitar")));
});

test("rubroDeHref y accesoConComercios", () => {
  assert.equal(rubroDeHref("/buscar?rubro=banos&vista=mapa"), "banos");
  assert.equal(rubroDeHref("/buscar?vista=mapa"), null);
  assert.equal(rubroDeHref("/cambio"), null);
  assert.equal(rubroDeHref("/guia#frontera"), null);
  assert.equal(rubroDeHref("/ofertas?rubro=ropa"), null, "sólo los accesos al buscador");
  assert.equal(accesoConComercios("/cambio", new Set()), true);
  assert.equal(accesoConComercios("/buscar?rubro=taxis&vista=mapa", new Set()), false);
  assert.equal(accesoConComercios("/buscar?rubro=taxis&vista=mapa", new Set(["taxis"])), true);
  assert.equal(accesoConComercios("/buscar?rubro=taxis&vista=mapa", null), true);
  assert.equal(accesoConComercios(HREF_HOTELES, null), false);
});
