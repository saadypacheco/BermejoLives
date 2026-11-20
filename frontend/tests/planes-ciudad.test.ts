// «Qué podés hacer»: los planes ilustrados salen sólo si la ciudad tiene datos, la tarjeta grande y los gentilicios
// (lib/planes-ciudad-pure.ts, docs/home-ciudades.md §12).
import test from "node:test";
import assert from "node:assert/strict";
import { MAX_GRILLA_PLANES, hayPlanes, nocheDe, planesDeCiudad, saboresDe, tituloSabores, type DatosPlanes } from "../lib/planes-ciudad-pure";
import { conFiltros } from "../lib/filtros-rapidos";

const datos = (extra: Partial<DatosPlanes> = {}): DatosPlanes => ({
  ciudadSlug: "tarija", ciudadNombre: "Tarija", rubros: new Set<string>(), subcategorias: [], hayPlatos: false, ...extra,
});
const ids = (d: DatosPlanes): string[] => {
  const p = planesDeCiudad(d);
  return [p.grande?.id, ...p.grilla.map((x) => x.id)].filter((x): x is NonNullable<typeof x> => Boolean(x)).map(String);
};

test("gentilicios: el mapa del spec, y «de {ciudad}» para el resto", () => {
  const esperado: [string, string, string][] = [
    ["tarija", "chapaca", "chapacos"], ["santa-cruz", "cruceña", "cruceños"], ["la-paz", "paceña", "paceños"],
    ["cochabamba", "cochabambina", "cochabambinos"], ["oruro", "orureña", "orureños"], ["sucre", "sucrense", "sucrenses"],
    ["potosi", "potosina", "potosinos"], ["bermejo", "bermejeña", "bermejeños"],
  ];
  for (const [slug, f, mp] of esperado) {
    assert.equal(nocheDe(slug, "X"), f, slug);
    assert.equal(saboresDe(slug, "X"), mp, slug);
  }
  assert.equal(nocheDe("trinidad", "Trinidad"), "de Trinidad");
  assert.equal(saboresDe("trinidad", "Trinidad"), "de Trinidad");
  assert.equal(tituloSabores("tarija", "Tarija"), "Sabores chapacos");
  assert.equal(tituloSabores("trinidad", "Trinidad"), "Sabores de Trinidad");
});

test("sin datos no sale ningún plan, y sin saber qué rubros hay (null) tampoco", () => {
  assert.equal(hayPlanes(planesDeCiudad(datos())), false);
  assert.equal(hayPlanes(planesDeCiudad(datos({ rubros: null, subcategorias: ["Plaza"], hayPlatos: true }))), false);
  assert.equal(planesDeCiudad(datos()).verTodos, null);
});

test("cada plan sale sólo con su dato (rubro o subcategoría de «para-visitar»)", () => {
  const visitar = new Set(["para-visitar"]);
  assert.deepEqual(ids(datos({ rubros: new Set(["bodegas"]) })), ["vino"]);
  assert.deepEqual(ids(datos({ rubros: new Set(["nocturna"]) })), ["noche"]);
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Mirador"] })), ["miradores"]);
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Parque"] })), ["parques"]);
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Museo"] })), ["museos"]);
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Centro cultural"] })), ["museos"]);
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Excursión"] })), ["cascadas"]);
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Área protegida"] })), ["lagunas"]);
  for (const sub of ["Plaza", "Iglesia", "Patrimonio"]) assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: [sub] })), ["centro"], sub);
  assert.deepEqual(ids(datos({ hayPlatos: true, rubros: new Set(["restaurantes"]) })), ["sabores"]);
  // Una subcategoría sin el rubro «para-visitar» en la ciudad no alcanza (el mapa saldría vacío).
  assert.deepEqual(ids(datos({ rubros: new Set(["nocturna"]), subcategorias: ["Mirador"] })), ["noche"]);
  // Una subcategoría que no es de ningún plan no genera nada.
  assert.deepEqual(ids(datos({ rubros: visitar, subcategorias: ["Biblioteca o archivo"] })), []);
});

test("las subcategorías se comparan sin tildes ni mayúsculas", () => {
  assert.deepEqual(ids(datos({ rubros: new Set(["para-visitar"]), subcategorias: ["excursion", "AREA PROTEGIDA"] })).sort(), ["cascadas", "lagunas"]);
});

test("destinos: apuntan al mapa con el rubro o la subcategoría exacta; «Sabores» a su página", () => {
  const p = planesDeCiudad(datos({
    rubros: new Set(["bodegas", "para-visitar", "nocturna"]), subcategorias: ["Iglesia", "Mirador", "Museo", "Parque", "Excursión", "Área protegida"], hayPlatos: true,
  }));
  const todos = [p.grande, ...p.grilla].filter((x): x is NonNullable<typeof x> => x !== null);
  const href = (id: string) => todos.find((x) => x.id === id)?.href;
  assert.equal(href("vino"), "/buscar?rubro=bodegas&vista=mapa");
  assert.equal(href("miradores"), "/buscar?rubro=para-visitar&sub=Mirador&vista=mapa");
  assert.equal(href("lagunas"), "/buscar?rubro=para-visitar&sub=%C3%81rea%20protegida&vista=mapa");
  assert.equal(href("cascadas"), "/buscar?rubro=para-visitar&sub=Excursi%C3%B3n&vista=mapa");
  assert.equal(href("noche"), "/buscar?rubro=nocturna&vista=mapa");
  assert.equal(href("sabores"), "/tarija/sabores");
  // La «Iglesia» es la primera de Plaza/Iglesia/Patrimonio que hay.
  assert.equal(href("centro"), "/buscar?rubro=para-visitar&sub=Iglesia&vista=mapa");
  assert.equal(p.verTodos, "/buscar?rubro=para-visitar&vista=mapa");
});

test("la tarjeta grande es la primera con datos: ruta del vino, centro histórico, noche; el resto va a la grilla", () => {
  const visitar = new Set(["para-visitar"]);
  const conVino = planesDeCiudad(datos({ rubros: new Set(["bodegas", "para-visitar", "nocturna"]), subcategorias: ["Plaza", "Mirador"] }));
  assert.equal(conVino.grande?.id, "vino");
  assert.deepEqual(conVino.grilla.map((x) => x.id), ["centro", "miradores", "noche"]);
  const sinVino = planesDeCiudad(datos({ rubros: new Set(["para-visitar", "nocturna"]), subcategorias: ["Plaza", "Mirador"] }));
  assert.equal(sinVino.grande?.id, "centro");
  assert.deepEqual(sinVino.grilla.map((x) => x.id), ["miradores", "noche"]);
  const soloNoche = planesDeCiudad(datos({ rubros: new Set(["nocturna"]), hayPlatos: true }));
  assert.equal(soloNoche.grande?.id, "noche");
  assert.deepEqual(soloNoche.grilla.map((x) => x.id), ["sabores"]);
  // Los miradores solos NO son tarjeta grande: sin vino/centro/noche, no hay grande y todo va a la grilla.
  const soloMiradores = planesDeCiudad(datos({ rubros: visitar, subcategorias: ["Mirador"] }));
  assert.equal(soloMiradores.grande, null);
  assert.deepEqual(soloMiradores.grilla.map((x) => x.id), ["miradores"]);
});

test("la grilla llega a 6 como máximo, en el orden de la maqueta", () => {
  const p = planesDeCiudad(datos({
    rubros: new Set(["bodegas", "para-visitar", "nocturna"]),
    subcategorias: ["Plaza", "Mirador", "Parque", "Museo", "Excursión", "Área protegida"], hayPlatos: true,
  }));
  assert.equal(p.grande?.id, "vino");
  assert.equal(p.grilla.length, MAX_GRILLA_PLANES);
  assert.deepEqual(p.grilla.map((x) => x.id), ["centro", "miradores", "cascadas", "noche", "sabores", "lagunas"]);
});

test("títulos: «Noche chapaca», «Sabores chapacos» y «de {ciudad}» sin gentilicio", () => {
  const t = planesDeCiudad(datos({ rubros: new Set(["nocturna"]), hayPlatos: true }));
  assert.equal(t.grande?.titulo, "Noche chapaca");
  assert.equal(t.grilla[0].titulo, "Sabores chapacos");
  const trinidad = planesDeCiudad(datos({ ciudadSlug: "trinidad", ciudadNombre: "Trinidad", rubros: new Set(["nocturna"]) }));
  assert.equal(trinidad.grande?.titulo, "Noche de Trinidad");
});

test("«Sabores» sólo si la ciudad tiene platos aprobados", () => {
  assert.equal(ids(datos({ rubros: new Set(["nocturna"]), hayPlatos: false })).includes("sabores"), false);
  assert.equal(ids(datos({ rubros: new Set(["nocturna"]), hayPlatos: true })).includes("sabores"), true);
});

test("«Ver todos los planes en el mapa» sólo si la ciudad tiene lugares para visitar", () => {
  assert.equal(planesDeCiudad(datos({ rubros: new Set(["nocturna"]) })).verTodos, null);
  assert.equal(planesDeCiudad(datos({ rubros: new Set(["para-visitar"]) })).verTodos, "/buscar?rubro=para-visitar&vista=mapa");
});

test("ningún plan lleva números ni cantidades, y los filtros rápidos se suman una sola vez a los enlaces del mapa", () => {
  const p = planesDeCiudad(datos({ rubros: new Set(["bodegas", "para-visitar", "nocturna"]), subcategorias: ["Plaza", "Mirador"], hayPlatos: true }));
  for (const plan of [p.grande, ...p.grilla]) {
    assert.ok(plan);
    assert.doesNotMatch(`${plan.titulo} ${plan.bajada} ${plan.etiqueta} ${plan.cta}`, /\d/);
    const con = new URL(conFiltros(plan.href, { abiertos: true, cerca: true }), "https://uruku.test");
    if (plan.href.startsWith("/buscar")) {
      assert.equal(con.searchParams.getAll("abierto").length, 1);
      assert.equal(con.searchParams.get("vista"), "mapa");
    } else {
      assert.equal(conFiltros(plan.href, { abiertos: true, cerca: true }), plan.href);
    }
  }
});
