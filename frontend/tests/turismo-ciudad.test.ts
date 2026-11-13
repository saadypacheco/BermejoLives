// «Visitá {ciudad}» (docs/turismo-home-y-repetidos.md §3): cuándo aparece la banda, cómo se parten guías / agencias /
// moverse, el orden del carrusel, los accesos grandes (sin números), los botones de contacto, el «Cómo llegar» de la
// ficha de un comercio sin punto y la forma de la página (ISR, sin select("*"), sin emojis).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  SUBCATEGORIAS_VISITAR,
} from "../lib/para-visitar";
import {
  SUBCAT_GUIA, accesosVisita, bajadaVisita, contactoDe, enlaceLlamar, filtrarMoverse, iconoDeLugar, lugaresParaCarrusel,
  mostrarVisitaCiudad, navegacionTurismo, normalizarEtiqueta, numeroWhatsapp, partirTurismo, rutaTurismo, tieneRubro,
  tituloPaginaTurismo, type LocalTurismo,
} from "../lib/turismo-ciudad-pure";
import { atiendeSinLocal, destinoComoLlegar, textoDondeAtiende, tienePunto } from "../lib/ficha-ubicacion-pure";
import { touristDestinationNode } from "../lib/seo";

const leer = (ruta: string) => readFileSync(resolve(process.cwd(), ruta), "utf8");

// `components/ic.tsx` importa con el alias `@/`, que Node no resuelve: se lee como texto el catálogo ICONOS.
const BLOQUE_ICONOS = leer("components/ic.tsx").split("export const ICONOS = {")[1].split("} as const;")[0];
const tieneIcono = (clave: string) => BLOQUE_ICONOS.includes(`"${clave}": "`) || new RegExp(`[\\s,{]${clave}: "`).test(BLOQUE_ICONOS);

const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;

const par = (city_slug: string, category_slug: string) => ({ city_slug, category_slug });
const PARES_TARIJA = [
  par("tarija", "para-visitar"), par("tarija", "turismo"), par("tarija", "taxis"), par("tarija", "hospedaje"),
  par("tarija", "restaurantes"), par("tarija", "bebidas"), par("bermejo", "farmacia"), par("bermejo", "taxis"),
];

const local = (nombre: string, subcategoria: string | null, extra: Partial<LocalTurismo> = {}): LocalTurismo => ({
  id: nombre, slug: nombre.toLowerCase().replace(/\s+/g, "-"), nombre, subcategoria, whatsapp: null, telefono: null, foto: null, ...extra,
});

// ── Cuándo aparece ──────────────────────────────────────────────────────────

test("la banda sólo sale en una ciudad con lugares para visitar (nada hardcodeado a Tarija)", () => {
  assert.equal(mostrarVisitaCiudad(PARES_TARIJA, "tarija"), true);
  assert.equal(mostrarVisitaCiudad(PARES_TARIJA, "bermejo"), false);
  assert.equal(mostrarVisitaCiudad([par("sucre", "para-visitar")], "sucre"), true);
  assert.equal(mostrarVisitaCiudad([], "tarija"), false);
  assert.equal(mostrarVisitaCiudad(null, "tarija"), false);
  assert.equal(mostrarVisitaCiudad(PARES_TARIJA, null), false);
  assert.equal(tieneRubro(PARES_TARIJA, "tarija", "bebidas"), true);
  assert.equal(tieneRubro(PARES_TARIJA, "bermejo", "bebidas"), false);
});

// ── Guías / agencias / moverse ──────────────────────────────────────────────

test("turismo se parte en guías y el resto (agencias, operadoras, complejos), cada grupo por nombre", () => {
  const { guias, agencias } = partirTurismo([
    local("Zeta Operadora", "Operadora de turismo"),
    local("Ana Guía", "Guía de turismo"),
    local("Bruno Guía", "guia de turismo "),       // sin tilde ni mayúscula: sigue siendo guía
    local("Alfa Viajes", "Agencia de viajes"),
    local("Complejo Sol", null),
  ]);
  assert.deepEqual(guias.map((g) => g.nombre), ["Ana Guía", "Bruno Guía"]);
  assert.deepEqual(agencias.map((g) => g.nombre), ["Alfa Viajes", "Complejo Sol", "Zeta Operadora"]);
  assert.equal(normalizarEtiqueta(SUBCAT_GUIA), "guia de turismo");
});

test("cómo moverse: sólo radio móviles y transporte a los alrededores (no los taxis de parada)", () => {
  const r = filtrarMoverse([
    local("Radio Sur", "Radio móvil"),
    local("Taxi Plaza", "Taxi de parada"),
    local("Radio Norte", "radio movil"),
    local("Traslados Valle", "Transporte a los alrededores"),
    local("Sin tipo", null),
  ]);
  assert.deepEqual(r.map((x) => x.nombre), ["Radio Norte", "Radio Sur", "Traslados Valle"]);
});

// ── El carrusel ─────────────────────────────────────────────────────────────

test("carrusel: primero los que tienen foto, y los tipos se alternan (no ocho iglesias seguidas)", () => {
  const lugares = [
    local("Iglesia A", "Iglesia"), local("Iglesia B", "Iglesia", { foto: "https://x/b.jpg" }),
    local("Iglesia C", "Iglesia", { foto: "https://x/c.jpg" }), local("Mirador A", "Mirador", { foto: "https://x/m.jpg" }),
    local("Plaza A", "Plaza", { foto: "https://x/p.jpg" }), local("Museo A", "Museo"),
  ];
  const orden = lugaresParaCarrusel(lugares, 12).map((l) => l.nombre);
  // Con foto: Plaza, Mirador, Iglesia B, Iglesia C (por la lista fija: Plaza, Parque, Mirador, Museo, …, Iglesia…).
  assert.deepEqual(orden.slice(0, 4), ["Plaza A", "Mirador A", "Iglesia B", "Iglesia C"]);
  // Sin foto, después: Museo e Iglesia, alternados.
  assert.deepEqual(orden.slice(4), ["Museo A", "Iglesia A"]);
});

test("carrusel: respeta el máximo y no pierde ni repite lugares", () => {
  const lugares = Array.from({ length: 30 }, (_, i) => local(`Lugar ${String(i).padStart(2, "0")}`, SUBCATEGORIAS_VISITAR[i % SUBCATEGORIAS_VISITAR.length]));
  const r = lugaresParaCarrusel(lugares, 12);
  assert.equal(r.length, 12);
  assert.equal(new Set(r.map((l) => l.id)).size, 12);
  assert.equal(lugaresParaCarrusel(lugares, 100).length, 30);
  assert.deepEqual(lugaresParaCarrusel([], 12), []);
  assert.equal(lugaresParaCarrusel(lugares, 0).length, 0);
});

test("cada tipo de lugar de la lista fija tiene su ícono, y existe en el catálogo", () => {
  for (const s of SUBCATEGORIAS_VISITAR) {
    const clave = iconoDeLugar(s);
    assert.notEqual(clave, "para-visitar", `${s} cae en el ícono genérico`);
    assert.ok(tieneIcono(clave), `falta el ícono ${clave} en components/ic.tsx`);
  }
  assert.equal(iconoDeLugar("Algo nuevo"), "para-visitar");
  assert.equal(iconoDeLugar(null), "para-visitar");
  assert.equal(iconoDeLugar("área protegida"), "visita_area");
});

// ── Los accesos ─────────────────────────────────────────────────────────────

test("accesos con todo cargado: guías, agencias, dormir, comer, vinos, moverse (en ese orden)", () => {
  const a = accesosVisita("tarija", PARES_TARIJA, { guias: true, agencias: true, moverse: true });
  assert.deepEqual(a.map((x) => x.clave), ["guias", "agencias", "dormir", "comer", "vinos", "moverse"]);
  assert.deepEqual(a.map((x) => x.href), [
    "/tarija/turismo#guias", "/tarija/turismo#agencias", "/tarija/hospedaje", "/tarija/restaurantes",
    "/buscar?rubro=bebidas&sub=Bodega", "/tarija/turismo#moverse",
  ]);
  for (const x of a) assert.ok(tieneIcono(x.i), `falta el ícono ${x.i}`);
});

test("un acceso sale sólo si hay algo detrás: sin guías no hay «Guías», sin hospedaje no hay «Dónde dormir»", () => {
  const a = accesosVisita("tarija", [par("tarija", "para-visitar"), par("tarija", "restaurantes")], { guias: false, agencias: true, moverse: false });
  assert.deepEqual(a.map((x) => x.clave), ["agencias", "comer"]);
  assert.deepEqual(accesosVisita("sucre", [par("sucre", "para-visitar")], { guias: false, agencias: false, moverse: false }), []);
});

test("si no se pudo leer lo cargado (resumen null), guías y agencias salen por el rubro turismo y moverse por taxis", () => {
  const a = accesosVisita("tarija", PARES_TARIJA, null);
  assert.deepEqual(a.map((x) => x.clave), ["guias", "agencias", "dormir", "comer", "vinos", "moverse"]);
  const sin = accesosVisita("tarija", [par("tarija", "para-visitar")], null);
  assert.deepEqual(sin, []);
  // Los taxis de OTRA ciudad no cuentan.
  assert.equal(accesosVisita("tarija", [par("tarija", "para-visitar"), par("bermejo", "taxis")], null).some((x) => x.clave === "moverse"), false);
});

test("ni los accesos ni los textos llevan números (nunca «22 guías» ni «49 hoteles»)", () => {
  const a = accesosVisita("tarija", PARES_TARIJA, { guias: true, agencias: true, moverse: true });
  for (const x of a) assert.equal(/\d/.test(`${x.t} ${x.d}`), false, `${x.t} / ${x.d}`);
  assert.equal(/\d/.test(bajadaVisita("Tarija") + tituloPaginaTurismo("Tarija")), false);
  assert.equal(tituloPaginaTurismo("Tarija"), "Tarija para el que la visita");
  assert.match(bajadaVisita("Tarija"), /Tarija/);
  assert.equal(EMOJI.test(JSON.stringify(a) + bajadaVisita("Tarija")), false);
});

test("el índice de la página: sólo las anclas con algo detrás, las listas propias primero", () => {
  const nav = navegacionTurismo("tarija", PARES_TARIJA, { guias: true, agencias: false, moverse: true });
  assert.deepEqual(nav.map((n) => n.id), ["visitar", "guias", "dormir", "comer", "vinos", "moverse"]);
  assert.deepEqual(navegacionTurismo("tarija", [par("tarija", "para-visitar")], { guias: false, agencias: false, moverse: false }).map((n) => n.id), ["visitar"]);
  assert.equal(rutaTurismo("tarija"), "/tarija/turismo");
  assert.equal(rutaTurismo("tarija", "guias"), "/tarija/turismo#guias");
});

// ── Contacto ────────────────────────────────────────────────────────────────

test("WhatsApp y llamar: cada botón sólo si hay número de verdad", () => {
  assert.equal(numeroWhatsapp("591 7123-4567"), "59171234567");
  assert.equal(numeroWhatsapp("123"), null);
  assert.equal(numeroWhatsapp(null), null);
  assert.equal(enlaceLlamar("(4) 664-1234"), "tel:46641234");
  assert.equal(enlaceLlamar("+591 4 664 1234"), "tel:+59146641234");
  assert.equal(enlaceLlamar("12"), null);
  assert.equal(enlaceLlamar(""), null);
  assert.deepEqual(contactoDe({ whatsapp: "59171234567", telefono: "4 664 1234" }), { whatsapp: "59171234567", llamar: "tel:46641234" });
  assert.deepEqual(contactoDe({ whatsapp: null, telefono: "4 664 1234" }), { whatsapp: null, llamar: "tel:46641234" });
  assert.deepEqual(contactoDe({ whatsapp: null, telefono: null }), { whatsapp: null, llamar: null });
});

test("si el teléfono es el mismo número que el WhatsApp, no se ofrece dos veces", () => {
  assert.deepEqual(contactoDe({ whatsapp: "59171234567", telefono: "71234567" }), { whatsapp: "59171234567", llamar: null });
  assert.deepEqual(contactoDe({ whatsapp: "59171234567", telefono: "+591 71234567" }), { whatsapp: "59171234567", llamar: null });
});

// ── La ficha de un comercio sin punto ───────────────────────────────────────

test("sin punto, sin dirección y sin enlace no hay «Cómo llegar» (antes abría el mapa en el centro de la ciudad)", () => {
  assert.equal(destinoComoLlegar({ lat: null, lng: null, direccion: null, como_llegar: null }, "Tarija"), null);
  assert.equal(destinoComoLlegar({ lat: null, lng: null, direccion: "  ", calle: "" }, "Tarija"), null);
  assert.equal(destinoComoLlegar({}, "Tarija"), null);
});

test("«Cómo llegar»: el enlace propio, después el punto, después la dirección con la ciudad", () => {
  assert.equal(destinoComoLlegar({ como_llegar: "https://maps.app.goo.gl/abc", lat: -21.5, lng: -64.7 }, "Tarija"), "https://maps.app.goo.gl/abc");
  assert.equal(destinoComoLlegar({ como_llegar: "javascript:alert(1)", lat: -21.5, lng: -64.7 }, "Tarija"),
    "https://www.google.com/maps/search/?api=1&query=-21.5,-64.7");
  assert.equal(destinoComoLlegar({ lat: 0, lng: 0 }, "Tarija"), "https://www.google.com/maps/search/?api=1&query=0,0");
  assert.equal(destinoComoLlegar({ direccion: "Calle Bolívar 123" }, "Tarija"),
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent("Calle Bolívar 123, Tarija")}`);
  assert.equal(destinoComoLlegar({ calle: "Calle Sucre" }, "Tarija"),
    `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent("Calle Sucre, Tarija")}`);
});

test("tienePunto: null, undefined y NaN no son un punto; el cero sí", () => {
  assert.equal(tienePunto({ lat: null, lng: null }), false);
  assert.equal(tienePunto({ lat: -21.5, lng: null }), false);
  assert.equal(tienePunto({ lat: Number.NaN, lng: 1 }), false);
  assert.equal(tienePunto({ lat: -21.5, lng: -64.7 }), true);
  assert.equal(tienePunto({ lat: 0, lng: 0 }), true);
});

test("guías y radio móviles sin local: «Dónde atiende» en vez de un mapa vacío", () => {
  assert.equal(atiendeSinLocal({ lat: null, lng: null }, "turismo"), true);
  assert.equal(atiendeSinLocal({ lat: null, lng: null }, "taxis"), true);
  assert.equal(atiendeSinLocal({ lat: null, lng: null, direccion: "Calle 1" }, "turismo"), false);
  assert.equal(atiendeSinLocal({ lat: -21.5, lng: -64.7 }, "turismo"), false);
  assert.equal(atiendeSinLocal({ lat: null, lng: null }, "ropa"), false);
  assert.match(textoDondeAtiende("turismo", true), /WhatsApp o por teléfono/);
  assert.match(textoDondeAtiende("taxis", false), /^En toda la ciudad: no tiene parada fija, se pide por WhatsApp\.$/);
});

test("la ficha usa esas reglas y ya no arma el enlace a la ciudad", () => {
  const ficha = leer("app/comercios/[slug]/page.tsx");
  assert.match(ficha, /destinoComoLlegar\(comercio, ciudadNombre\)/);
  assert.match(ficha, /mapsHref && !sinParada/);
  assert.match(ficha, /\{mapsHref && \(\s*<LeadLink/);
  assert.equal(/query=\$\{encodeURIComponent\(comercio\.direccion \?\? ciudadNombre\)\}/.test(ficha), false);
});

// ── La forma de la home y de la página ──────────────────────────────────────

test("la home pone la banda debajo del hero y antes de farmacias de turno, sólo si la ciudad la tiene", () => {
  const home = leer("app/page.tsx");
  const hero = home.indexOf('className="uk-hero uk-home-hero"');
  const banda = home.indexOf("<VisitaCiudad");
  const turno = home.indexOf("<TarjetaTurnoHoy");
  assert.ok(hero > 0 && banda > hero && turno > banda, "orden: hero, Visitá, turnos");
  assert.match(home, /conVisita && ciudad && \(/);
  assert.match(home, /mostrarVisitaCiudad\(paresCiudad, ciudad\.slug\)/);
  // La home es dinámica: lee por la memoria, no directo.
  assert.match(home, /cargarVisitaCiudadOpcional/);
  assert.equal(/buscarComerciosOrNull/.test(home), false);
});

test("la página /{ciudad}/turismo: ISR, sin pre-render, 404, JSON-LD y sin números", () => {
  const pag = leer("app/[city]/turismo/page.tsx");
  assert.match(pag, /export const revalidate = 3600/);
  assert.match(pag, /export const dynamic = "force-static"/);
  assert.match(pag, /generateStaticParams[\s\S]{0,80}return \[\];/);
  assert.match(pag, /notFound\(\)/);
  for (const t of ["breadcrumbNode", "collectionPageNode", "touristDestinationNode"]) assert.match(pag, new RegExp(t));
  for (const id of ["visitar", "guias", "agencias", "dormir", "comer", "vinos", "moverse"]) assert.match(pag, new RegExp(`id="${id}`), `falta el ancla #${id}`);
  assert.equal(/\.length\}/.test(pag), false, "no se imprime ninguna cantidad");
  assert.equal(/numberOfItems/.test(pag), false);
  assert.equal(EMOJI.test(pag), false);
});

test("las lecturas: columnas explícitas, nunca select(\"*\"), sin service_role", () => {
  const lib = leer("lib/turismo-ciudad.ts");
  assert.equal(/select\(\s*["'`]\*["'`]/.test(lib), false);
  assert.match(lib, /select\("id, telefono"\)/);
  assert.equal(/service_role|SERVICE_ROLE/i.test(lib), false);
  assert.match(lib, /conMemoriaTtl\(DIEZ_MIN_MS/);
  assert.equal(EMOJI.test(lib + leer("components/visita-ciudad.tsx") + leer("app/styles/turismo.css")), false);
});

test("el sitemap suma /{ciudad}/turismo para la ciudad con lugares, sin repetirla", () => {
  const s = leer("app/sitemap.ts");
  assert.match(s, /mostrarVisitaCiudad\(pares, slug\)/);
  assert.match(s, /yaEstan\.has\(url\)/);
});

test("TouristDestination: sin números de comercios y con el punto de la ciudad si lo tiene", () => {
  const n = touristDestinationNode({ nombre: "Tarija", departamento: "Tarija", pais: "Bolivia", path: "/tarija/turismo", lat: -21.53, lng: -64.73, description: "x" });
  assert.equal(n["@type"], "TouristDestination");
  assert.equal(n["@id"], "https://uruku.bo/tarija/turismo#destino");
  assert.deepEqual(n.geo, { "@type": "GeoCoordinates", latitude: -21.53, longitude: -64.73 });
  assert.equal("numberOfItems" in n, false);
  assert.equal("geo" in touristDestinationNode({ nombre: "Sucre", path: "/sucre/turismo" }), false);
});
