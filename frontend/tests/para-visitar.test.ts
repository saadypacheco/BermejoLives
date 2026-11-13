// «Para visitar» (docs/lugares-turismo.md): lo puro del frontend. Subcategorías, encuadre del mapa a 30 km,
// «nuevos en 24 h» sin los rubros no comerciales, el acceso del home (sólo con el par ciudad/rubro), los textos de
// la ficha pública, el enlace de origen, el tipo de schema.org y la búsqueda «qué visitar».
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  AVISO_PUNTO_ENTRADA, HREF_PARA_VISITAR, RADIO_ENCUADRE_KM, RUBRO_PARA_VISITAR, SUBCATEGORIAS_VISITAR, distanciaKm,
  dominioFuente, esLugarParaVisitar, esNoComercial, esParaVisitar, esSubcategoriaVisitar, hayParaVisitar, pideAvisoPunto,
  pinesParaEncuadre, selloParaVisitar, textoMasInformacion, textoVerEnOrigen, urlFuente,
} from "../lib/para-visitar";
import { filtroSinNoComerciales, idsRubrosNoComerciales } from "../lib/comercios-nuevos-pure";
import { listaAccesos } from "../lib/accesos-ciudad";
import { textosFicha } from "../lib/ficha-seo";
import { detectarServicio, servicioDeRubro, SERVICIOS } from "../lib/servicios";
import { CATEGORY_STYLE, FAMILIAS } from "../lib/mapa-visual";
import { RUBRO_SCHEMA_TYPE, SCHEMA_TYPE_WHITELIST, localBusinessNode, schemaTypeForRubro } from "../lib/seo";
import {
  CAMPOS_EDITABLES, diffPatch, formDeItem, paramFuente, paramRubroImportados, usaFichaEditable, type FuenteFiltro,
} from "../lib/tarjetas-pure";

// `components/ic.tsx` importa con el alias `@/`, que Node no resuelve: se lee como texto el catálogo ICONOS.
const IC = readFileSync(resolve(process.cwd(), "components/ic.tsx"), "utf8");
const BLOQUE_ICONOS = IC.split("export const ICONOS = {")[1].split("} as const;")[0];
const tieneIcono = (clave: string) => BLOQUE_ICONOS.includes(`"${clave}": "`) || BLOQUE_ICONOS.includes(` ${clave}: "`);

// Tarija (centro aproximado) y puntos de referencia.
const TARIJA: [number, number] = [-21.5355, -64.7296];
const PLAZA: [number, number] = [-21.5340, -64.7300];       // a unos 200 m
const SAN_LORENZO: [number, number] = [-21.4440, -64.7640]; // ~11 km
const CHAGUAYA: [number, number] = [-21.9, -64.3];          // lejos, > 50 km
const TAJZARA: [number, number] = [-21.7, -64.0];           // lejos, > 70 km

test("subcategorías: la lista fija de la spec, en orden y sin repetidos", () => {
  assert.deepEqual([...SUBCATEGORIAS_VISITAR], [
    "Plaza", "Parque", "Mirador", "Museo", "Biblioteca o archivo", "Iglesia", "Patrimonio",
    "Centro cultural", "Excursión", "Área protegida",
  ]);
  assert.equal(new Set(SUBCATEGORIAS_VISITAR).size, SUBCATEGORIAS_VISITAR.length);
  assert.equal(esSubcategoriaVisitar("Museo"), true);
  assert.equal(esSubcategoriaVisitar(" Mirador "), true);
  assert.equal(esSubcategoriaVisitar("Bar"), false);
  assert.equal(esSubcategoriaVisitar(""), false);
  assert.equal(esSubcategoriaVisitar(null), false);
});

test("el aviso del punto en la entrada sale sólo para Excursión y Área protegida", () => {
  assert.equal(pideAvisoPunto("Excursión"), true);
  assert.equal(pideAvisoPunto("Área protegida"), true);
  for (const s of SUBCATEGORIAS_VISITAR.filter((x) => x !== "Excursión" && x !== "Área protegida")) {
    assert.equal(pideAvisoPunto(s), false, s);
  }
  assert.equal(pideAvisoPunto(null), false);
  assert.match(AVISO_PUNTO_ENTRADA, /entrada o en el centro de visitantes/);
});

test("el sello de la ficha de revisión: «Para visitar · Museo»", () => {
  assert.equal(selloParaVisitar("Museo"), "Para visitar · Museo");
  assert.equal(selloParaVisitar("  "), "Para visitar");
  assert.equal(selloParaVisitar(null), "Para visitar");
});

test("la ficha de lugar sólo es de turismo con rubro para-visitar; si quien revisa cambia el rubro, vuelve a ser un negocio", () => {
  assert.equal(esLugarParaVisitar({ fuente: "turismo", rubro_slug: "para-visitar" }), true);
  assert.equal(esLugarParaVisitar({ fuente: "turismo", rubro_slug: "para-visitar" }, "para-visitar"), true);
  assert.equal(esLugarParaVisitar({ fuente: "turismo", rubro_slug: "para-visitar" }, "restaurantes"), false);
  assert.equal(esLugarParaVisitar({ fuente: "turismo", rubro_slug: "para-visitar" }, ""), false);
  assert.equal(esLugarParaVisitar({ fuente: "turismo", rubro_slug: "hospedaje" }), false);
  assert.equal(esLugarParaVisitar({ fuente: "tarjeta", rubro_slug: "para-visitar" }), false);
  assert.equal(esLugarParaVisitar({ fuente: "osm" }), false);
  assert.equal(esParaVisitar(RUBRO_PARA_VISITAR), true);
  assert.equal(esParaVisitar("banos"), false);
});

test("esNoComercial: sólo `comercial === false`; ausente es comercial", () => {
  assert.equal(esNoComercial({ comercial: false }), true);
  assert.equal(esNoComercial({ comercial: true }), false);
  assert.equal(esNoComercial({}), false);
  assert.equal(esNoComercial({ comercial: null }), false);
  assert.equal(esNoComercial(null), false);
});

// ── Encuadre del mapa ────────────────────────────────────────────────────────

test("distanciaKm: haversine razonable (Tarija–San Lorenzo ~11 km; mismo punto 0)", () => {
  assert.equal(distanciaKm(TARIJA, TARIJA), 0);
  const d = distanciaKm(TARIJA, SAN_LORENZO);
  assert.ok(d > 9 && d < 13, `San Lorenzo a ${d} km`);
  assert.ok(distanciaKm(TARIJA, TAJZARA) > 50);
});

test("encuadre: el corte es de 30 km desde el centro de la ciudad", () => {
  assert.equal(RADIO_ENCUADRE_KM, 30);
  const pines = [PLAZA, SAN_LORENZO, CHAGUAYA, TAJZARA];
  assert.deepEqual(pinesParaEncuadre(pines, TARIJA), [PLAZA, SAN_LORENZO]);
});

test("encuadre: una excursión lejana no entra en el encuadre; ni siquiera si es el único pin extra", () => {
  const enCiudad: [number, number][] = [PLAZA, [-21.54, -64.73], [-21.53, -64.72]];
  const conExcursion = [...enCiudad, CHAGUAYA];
  assert.deepEqual(pinesParaEncuadre(conExcursion, TARIJA), enCiudad);
});

test("encuadre: justo en el borde cuenta (30 km o menos) y un punto un poco más allá no", () => {
  // Un punto a ~30 km al norte: 30 km son ~0,2698 grados de latitud.
  const justo: [number, number] = [TARIJA[0] + 29.9 / 111.195, TARIJA[1]];
  const pasado: [number, number] = [TARIJA[0] + 30.5 / 111.195, TARIJA[1]];
  assert.ok(distanciaKm(TARIJA, justo) <= 30);
  assert.ok(distanciaKm(TARIJA, pasado) > 30);
  assert.deepEqual(pinesParaEncuadre([justo, pasado], TARIJA), [justo]);
});

test("encuadre: sin centro, o si todos quedan lejos, valen todos (no se encuadra el vacío)", () => {
  assert.deepEqual(pinesParaEncuadre([CHAGUAYA, TAJZARA], TARIJA), [CHAGUAYA, TAJZARA]);
  assert.deepEqual(pinesParaEncuadre([PLAZA, CHAGUAYA], null), [PLAZA, CHAGUAYA]);
  assert.deepEqual(pinesParaEncuadre([], TARIJA), []);
});

// ── «N nuevos en 24 h» ───────────────────────────────────────────────────────

test("nuevos en 24 h: los rubros no comerciales se excluyen del conteo", () => {
  const rubros = [
    { id: "11111111-1111-1111-1111-111111111111", comercial: true },
    { id: "22222222-2222-2222-2222-222222222222", comercial: false },   // para-visitar
    { id: "33333333-3333-3333-3333-333333333333" },                    // sin dato: comercial
    { id: "44444444-4444-4444-4444-444444444444", comercial: false },   // baños
  ];
  const ids = idsRubrosNoComerciales(rubros);
  assert.deepEqual(ids, ["22222222-2222-2222-2222-222222222222", "44444444-4444-4444-4444-444444444444"]);
  const f = filtroSinNoComerciales(ids);
  // Sin rubro (null) SÍ cuenta: un `not in` solo lo descartaría.
  assert.equal(f, "rubro_id.is.null,rubro_id.not.in.(22222222-2222-2222-2222-222222222222,44444444-4444-4444-4444-444444444444)");
});

test("nuevos en 24 h: sin rubros no comerciales no hay filtro; un id raro no se cuela en el filtro", () => {
  assert.equal(filtroSinNoComerciales([]), null);
  assert.equal(filtroSinNoComerciales(idsRubrosNoComerciales([{ id: "a", comercial: true }])), null);
  assert.equal(filtroSinNoComerciales(["abc),rubro_id.is.null,(x"]), null, "caracteres de la sintaxis de PostgREST no entran");
});

test("nuevos en 24 h: data.ts usa el filtro y falla (sin número) si no puede leer los rubros", () => {
  const src = readFileSync(resolve(process.cwd(), "lib/data.ts"), "utf8");
  const i = src.indexOf("const contarComerciosNuevos");
  const bloque = src.slice(i, src.indexOf("export async function getComerciosNuevos"));
  assert.match(bloque, /idsRubrosNoComerciales/);
  assert.match(bloque, /filtroSinNoComerciales/);
  assert.match(bloque, /\.or\(filtro\)/);
  assert.match(bloque, /if \(errRubros\) throw errRubros/);
});

// ── Acceso «Para visitar» ────────────────────────────────────────────────────

test("el acceso sale sólo si existe el par (ciudad, para-visitar)", () => {
  const pares = [
    { city_slug: "tarija", category_slug: "para-visitar" },
    { city_slug: "tarija", category_slug: "banos" },
    { city_slug: "bermejo", category_slug: "banos" },
  ];
  assert.equal(hayParaVisitar(pares, "tarija"), true);
  assert.equal(hayParaVisitar(pares, "bermejo"), false, "Bermejo no tiene lugares");
  assert.equal(hayParaVisitar(pares, null), false);
  assert.equal(hayParaVisitar(pares, undefined), false);
  assert.equal(hayParaVisitar([], "tarija"), false);
  assert.equal(hayParaVisitar(null, "tarija"), false, "si la lectura de los pares falló, no sale");
});

test("la fila de accesos: con el par suma «Para visitar» antes de las guías; sin el par queda como estaba", () => {
  const sin = listaAccesos(true, false);
  const con = listaAccesos(true, true);
  assert.equal(sin.some((a) => a.href === HREF_PARA_VISITAR), false);
  assert.equal(con.length, sin.length + 1);
  const i = con.findIndex((a) => a.href === HREF_PARA_VISITAR);
  assert.ok(i > 0);
  assert.equal(con[i].t, "Para visitar");
  assert.equal(con[i].i, "para-visitar");
  assert.ok(con[i + 1].href.startsWith("/guia"), "va antes de Transporte y Frontera");
  assert.equal(HREF_PARA_VISITAR, "/buscar?rubro=para-visitar&vista=mapa");
  // Ciudad sin guía (Tarija): al final, sin romper el orden del resto.
  const sinGuia = listaAccesos(false, true);
  assert.equal(sinGuia[sinGuia.length - 1].href, HREF_PARA_VISITAR);
  assert.equal(listaAccesos(false, false).length, sinGuia.length - 1);
  // Todos los íconos existen en el catálogo (si no, el acceso saldría con el paquete genérico).
  for (const a of con) assert.ok(tieneIcono(a.i), `falta el ícono ${a.i}`);
});

test("el acceso no lleva números ni emojis", () => {
  const a = listaAccesos(false, true).find((x) => x.href === HREF_PARA_VISITAR);
  assert.ok(a);
  assert.doesNotMatch(a.t, /\d/);
  assert.doesNotMatch(a.t, /\p{Extended_Pictographic}/u);
});

// ── Buscador: «qué visitar» ──────────────────────────────────────────────────

test("el buscador manda «qué visitar», «lugares turísticos», «museos» y «miradores» al rubro", () => {
  for (const q of ["qué visitar", "Que visitar en Tarija", "lugares turísticos", "lugar turistico", "museos", "Museo", "miradores", "atractivos turísticos", "para visitar"]) {
    assert.equal(detectarServicio(q), "para-visitar", q);
  }
  assert.equal(SERVICIOS["para-visitar"].rubro, "para-visitar");
  assert.equal(servicioDeRubro("para-visitar"), "para-visitar");
  assert.equal(tieneIcono(SERVICIOS["para-visitar"].icono), true);
});

test("el buscador no secuestra una búsqueda por nombre ni toca los otros servicios", () => {
  assert.equal(detectarServicio("museo san roque"), null);
  assert.equal(detectarServicio("mirador de la loma"), null);
  assert.equal(detectarServicio("plaza"), null, "«plaza» es una palabra de negocios («Comercial Plaza»)");
  assert.equal(detectarServicio("baño público"), "baño");
  assert.equal(detectarServicio("hospital"), "emergencias");
  assert.equal(detectarServicio("zapatillas"), null);
});

// ── Pin del mapa ─────────────────────────────────────────────────────────────

test("el rubro tiene ícono propio y color de una familia nueva", () => {
  assert.ok(tieneIcono("para-visitar"));
  assert.match(BLOQUE_ICONOS, /"para-visitar": "Binoculars"/);
  const color = CATEGORY_STYLE["para-visitar"].color;
  assert.ok(color);
  const familia = FAMILIAS.find((f) => f.nombre === "Para visitar");
  assert.ok(familia, "la referencia de colores tiene su familia");
  assert.equal(familia.color, color);
  // Ninguna otra familia usa ese color: es lo que hace legible el mapa por zonas.
  assert.equal(FAMILIAS.filter((f) => f.color === color).length, 1);
  const otros = Object.entries(CATEGORY_STYLE).filter(([slug, st]) => st.color === color && slug !== "para-visitar");
  assert.deepEqual(otros, []);
});

test("el dibujo del pin existe en el generado (npm run iconos corrido)", () => {
  const src = readFileSync(resolve(process.cwd(), "lib/iconos-dibujos.ts"), "utf8");
  assert.match(src, /"para-visitar": \d+/);
});

test("el globo del mapa de un lugar no lleva modalidad ni WhatsApp: «Cómo llegar» y «Ver lugar»", () => {
  const src = readFileSync(resolve(process.cwd(), "components/map-results.tsx"), "utf8");
  const i = src.indexOf("esParaVisitar(r.rubro_slug) ? `");
  assert.ok(i > 0, "el globo tiene una rama para los lugares");
  const rama = src.slice(i, src.indexOf("` : `", i));
  assert.match(rama, /Cómo llegar/);
  assert.match(rama, /Ver lugar/);
  assert.doesNotMatch(rama, /WhatsApp|waLink|MODALIDAD_LABEL/);
  assert.match(src, /pinesParaEncuadre\(/, "el encuadre usa el corte de 30 km");
});

// ── Ficha pública ────────────────────────────────────────────────────────────

test("la ficha de un lugar público no habla de WhatsApp ni de «negocio»", () => {
  const lugar = textosFicha(true);
  assert.equal(lugar.sinContactoTitulo, "Es un lugar público");
  assert.match(lugar.sinContactoDetalle, /cómo llegar/);
  assert.equal(lugar.qr, "El QR de este lugar");
  for (const t of Object.values(lugar)) assert.doesNotMatch(t, /WhatsApp|negocio|local/i, t);
});

test("la ficha de un comercio queda igual que siempre", () => {
  const c = textosFicha(false);
  assert.equal(c.sinContactoTitulo, "Este local no tiene WhatsApp cargado");
  assert.equal(c.qr, "El QR de este negocio");
  assert.equal(c.informacion, "Información del negocio");
});

test("la página usa los textos, muestra la fuente y esconde lo que es de un local", () => {
  const src = readFileSync(resolve(process.cwd(), "app/comercios/[slug]/page.tsx"), "utf8");
  assert.match(src, /textosFicha\(lugarPublico\)/);
  assert.match(src, /textos\.sinContactoTitulo/);
  assert.match(src, /textos\.qr/);
  assert.match(src, /urlFuente\(comercio\.fuente_url\)/);
  assert.match(src, /textoMasInformacion\(fuenteHref\)/);
  assert.match(src, /rel="noopener noreferrer"/);
  assert.doesNotMatch(src, /Este local no tiene WhatsApp cargado/, "ese texto vive en textosFicha");
});

test("JSON-LD de un lugar para visitar: TouristAttraction, en la lista blanca", () => {
  assert.equal(RUBRO_SCHEMA_TYPE["para-visitar"], "TouristAttraction");
  assert.equal(schemaTypeForRubro("para-visitar"), "TouristAttraction");
  assert.ok(SCHEMA_TYPE_WHITELIST.includes("TouristAttraction"));
  const nodo = localBusinessNode({
    comercio: { slug: "museo-san-roque", nombre: "Museo San Roque", lat: -21.53, lng: -64.73 },
    ciudad: { nombre: "Tarija", departamento: "Tarija" },
    rubroSlug: "para-visitar",
  });
  assert.equal(nodo["@type"], "TouristAttraction");
});

test("la fuente: sólo URLs http(s); el texto de la spec para la página de Turismo de Tarija", () => {
  assert.equal(urlFuente("https://tarijaturismo.com/plaza-uriondo/"), "https://tarijaturismo.com/plaza-uriondo/");
  assert.equal(urlFuente("javascript:alert(1)"), null);
  assert.equal(urlFuente("tarijaturismo.com"), null);
  assert.equal(urlFuente(""), null);
  assert.equal(urlFuente(null), null);
  assert.equal(dominioFuente("https://www.tarijaturismo.com/x"), "tarijaturismo.com");
  assert.equal(textoVerEnOrigen("https://tarijaturismo.com/x"), "Ver en tarijaturismo.com");
  assert.equal(textoVerEnOrigen(null), "Ver la página de origen");
  assert.equal(textoMasInformacion("https://tarijaturismo.com/x"), "Más información en la página de Turismo de Tarija");
  assert.equal(textoMasInformacion("https://otro.com/x"), "Más información en la página de origen");
});

// ── Importados ───────────────────────────────────────────────────────────────

test("filtro «Turismo › Para visitar»: fuente=turismo más rubro=para-visitar", () => {
  const f: FuenteFiltro = "turismo-visitar";
  assert.equal(paramFuente(f), "turismo");
  assert.equal(paramRubroImportados(f), "para-visitar");
  assert.equal(paramRubroImportados("turismo"), undefined);
  assert.equal(paramRubroImportados("todas"), undefined);
  assert.equal(paramFuente("turismo"), "turismo");
});

test("los lugares de turismo usan la ficha editable (como las tarjetas)", () => {
  assert.equal(usaFichaEditable({ fuente: "turismo" }), true);
});

test("el PATCH de un lugar manda sólo la subcategoría y el horario si cambiaron", () => {
  assert.ok((CAMPOS_EDITABLES as readonly string[]).includes("subcategoria"));
  assert.ok((CAMPOS_EDITABLES as readonly string[]).includes("horario"));
  const fila = { nombre: "Plaza Uriondo", direccion: "Calle Bolívar", subcategoria: "Plaza", horario: "Abierto 24 horas", rubro_slug: "para-visitar" };
  const form = formDeItem(fila);
  assert.equal(form.subcategoria, "Plaza");
  assert.deepEqual(diffPatch(fila, form), {});
  assert.deepEqual(diffPatch(fila, { ...form, subcategoria: "Parque" }), { subcategoria: "Parque" });
  assert.deepEqual(diffPatch(fila, { ...form, horario: " 8 a 20 " }), { horario: "8 a 20" });
  // Una tarjeta (sin esos datos) no manda nada de eso.
  const tarjeta = { nombre: "Ferretería", direccion: null, subcategoria: null, horario: null };
  assert.deepEqual(diffPatch(tarjeta, formDeItem(tarjeta)), {});
});

// ── App del agente ───────────────────────────────────────────────────────────

test("«Qué hay acá»: un lugar público no lleva sello de plan, «Le falta» ni «Ofrecer»", () => {
  const ficha = readFileSync(resolve(process.cwd(), "components/ficha-agente.tsx"), "utf8");
  assert.match(ficha, /const publico = esNoComercial\(c\)/);
  assert.match(ficha, /\{!publico && \(\s*<OfrecerComercio/);
  assert.match(ficha, /\{!publico && \(\s*<section role="region" aria-label="Lo que le falta al comercio"/);
  const lista = readFileSync(resolve(process.cwd(), "components/que-hay-aca.tsx"), "utf8");
  assert.match(lista, /faltan: publico \? null/);
  assert.match(lista, /plan: publico \? null/);
});

test("los archivos nuevos no llevan emojis", () => {
  for (const f of ["lib/para-visitar.ts", "lib/accesos-ciudad.ts", "tests/para-visitar.test.ts"]) {
    assert.doesNotMatch(readFileSync(resolve(process.cwd(), f), "utf8"), /\p{Extended_Pictographic}/u, f);
  }
});
