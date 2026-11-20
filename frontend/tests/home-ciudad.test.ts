// El home de las ciudades y los saludos de Dax (lib/home-ciudad-pure.ts): franjas de la hora de Bolivia, orden y
// cartel de los botones de intención, opciones, carrusel de comercios, «Qué podés hacer» y sugerencias de Dax.
import test from "node:test";
import assert from "node:assert/strict";
import {
  candidatosCarrusel, configCarrusel, consultaDeBusqueda, bienvenidaDax, franjaAhora, franjaDe, hrefRubro,
  intencionesDeCiudad, ordenIntenciones, prepararCarrusel, resaltadoDeFranja, saludoDeFranja, sugerenciasDeFranja,
  tilesQueHacer, type ComercioCarrusel, type ComercioDeLaCiudad, type DatosIntenciones, type Franja, type RubroCatalogo,
} from "../lib/home-ciudad-pure";

const FRANJAS: Franja[] = ["madrugada", "manana", "mediodia", "tarde", "noche"];

// ── Franjas ──────────────────────────────────────────────────────────────────

test("franjaDe: 0-6 madrugada, 6-11 mañana, 11-15 mediodía, 15-19 tarde, 19-24 noche (con los bordes)", () => {
  const esperado: [number, Franja][] = [
    [0, "madrugada"], [5, "madrugada"], [5.99, "madrugada"], [6, "manana"], [10, "manana"], [11, "mediodia"], [14, "mediodia"],
    [15, "tarde"], [18, "tarde"], [19, "noche"], [23, "noche"],
  ];
  for (const [h, f] of esperado) assert.equal(franjaDe(h), f, `hora ${h}`);
});

test("franjaAhora usa la hora de BOLIVIA, no la del servidor (UTC)", () => {
  // 01:30 UTC del sábado = 21:30 del viernes en Bolivia (UTC-4).
  assert.equal(franjaAhora(new Date("2026-11-21T01:30:00Z")), "noche");
  // 10:00 UTC = 06:00 en Bolivia: ya es la mañana.
  assert.equal(franjaAhora(new Date("2026-11-20T10:00:00Z")), "manana");
  // 09:59 UTC = 05:59 en Bolivia: todavía madrugada.
  assert.equal(franjaAhora(new Date("2026-11-20T09:59:00Z")), "madrugada");
});

// ── Orden y resaltado de los botones ─────────────────────────────────────────

test("orden de los botones por franja (docs/home-ciudades.md §4)", () => {
  assert.deepEqual(ordenIntenciones("manana"), ["comer", "negocios", "productos", "servicios", "farmacias", "bancos", "dormir"]);
  assert.deepEqual(ordenIntenciones("mediodia"), ["comer", "negocios", "productos", "servicios", "farmacias", "bancos", "dormir"]);
  assert.deepEqual(ordenIntenciones("tarde"), ["negocios", "productos", "servicios", "comer", "farmacias", "bancos", "dormir"]);
  assert.deepEqual(ordenIntenciones("noche"), ["comer", "negocios", "productos", "dormir", "farmacias", "bancos", "servicios"]);
  assert.deepEqual(ordenIntenciones("madrugada"), ["farmacias", "bancos", "dormir", "comer", "negocios", "productos", "servicios"]);
  for (const f of FRANJAS) assert.equal(new Set(ordenIntenciones(f)).size, 7);
});

test("resaltado y cartel por franja", () => {
  assert.deepEqual(resaltadoDeFranja("manana"), { id: "comer", cartel: "Desayunos" });
  assert.deepEqual(resaltadoDeFranja("mediodia"), { id: "comer", cartel: "Almuerzos" });
  assert.deepEqual(resaltadoDeFranja("tarde"), { id: "negocios", cartel: "Abiertos" });
  assert.deepEqual(resaltadoDeFranja("noche"), { id: "comer", cartel: "Cenar" });
  assert.deepEqual(resaltadoDeFranja("madrugada"), { id: "farmacias", cartel: "De turno" });
});

// ── Intenciones de una ciudad ────────────────────────────────────────────────

const CATALOGO: RubroCatalogo[] = [
  { slug: "calzado", nombre: "👟 Calzado" }, { slug: "ropa", nombre: "Ropa" }, { slug: "celulares", nombre: "Celulares" },
  { slug: "cafeteria", nombre: "Cafeterías" }, { slug: "restaurantes", nombre: "Restaurantes" }, { slug: "hospedaje", nombre: "Hospedaje" },
  { slug: "farmacia", nombre: "Farmacias" }, { slug: "cajeros", nombre: "Cajeros", comercial: false }, { slug: "banos", nombre: "Baños", comercial: false },
  { slug: "servicio-tecnico", nombre: "Servicio técnico" }, { slug: "peluqueria", nombre: "Peluquerías" }, { slug: "otros", nombre: "Otros" },
];
const TARIJA = new Set(["calzado", "ropa", "celulares", "cafeteria", "restaurantes", "hospedaje", "farmacia", "cajeros", "servicio-tecnico", "peluqueria", "otros", "banos"]);

const datos = (franja: Franja, extra: Partial<DatosIntenciones> = {}): DatosIntenciones => ({
  franja, ciudadSlug: "tarija", rubros: TARIJA, catalogo: CATALOGO, hayTurnos: true, productosFrecuentes: ["zapatillas", "celulares"], ...extra,
});

test("intenciones: salen en el orden de la franja y el cartel va sólo en el resaltado", () => {
  const noche = intencionesDeCiudad(datos("noche"));
  assert.deepEqual(noche.map((i) => i.id), ["comer", "negocios", "productos", "dormir", "farmacias", "bancos", "servicios"]);
  assert.deepEqual(noche.filter((i) => i.cartel).map((i) => [i.id, i.cartel]), [["comer", "Cenar"]]);
  const madrugada = intencionesDeCiudad(datos("madrugada"));
  assert.equal(madrugada[0].id, "farmacias");
  assert.equal(madrugada[0].cartel, "De turno");
  assert.equal(intencionesDeCiudad(datos("tarde")).find((i) => i.cartel)?.cartel, "Abiertos");
});

test("intenciones: una opción sólo si la ciudad tiene el rubro; un botón sin opciones no aparece", () => {
  const sinComida = intencionesDeCiudad(datos("mediodia", { rubros: new Set(["calzado", "farmacia"]) }));
  const ids = sinComida.map((i) => i.id);
  assert.ok(!ids.includes("comer"), "sin cafeterías ni restaurantes no hay «Comer»");
  assert.ok(!ids.includes("dormir"));
  assert.ok(!ids.includes("bancos"));
  assert.ok(!ids.includes("servicios"));
  assert.ok(ids.includes("farmacias") && ids.includes("negocios"));
  const comer = intencionesDeCiudad(datos("mediodia", { rubros: new Set(["cafeteria", "restaurantes"]) })).find((i) => i.id === "comer");
  assert.deepEqual(comer?.opciones.map((o) => o.href), [hrefRubro("cafeteria"), hrefRubro("restaurantes")]);
  assert.deepEqual(comer?.opciones.map((o) => o.t), ["Cafeterías", "Restaurantes"]);
});

test("intenciones: toda opción de rubro va al mapa de ese rubro", () => {
  for (const i of intencionesDeCiudad(datos("tarde"))) {
    for (const o of i.opciones) {
      if (o.rubro) assert.equal(o.href, `/buscar?rubro=${o.rubro}&vista=mapa`);
      assert.ok(TARIJA.has(o.rubro ?? "farmacia"), "nunca un rubro que la ciudad no tiene");
    }
  }
});

test("Farmacias: «De turno hoy» sólo con turnos cargados, y «Todas las farmacias» siempre que haya farmacias", () => {
  const con = intencionesDeCiudad(datos("madrugada")).find((i) => i.id === "farmacias");
  assert.deepEqual(con?.opciones.map((o) => [o.t, o.href]), [
    ["De turno hoy", "/tarija/farmacias-de-turno"],
    ["Todas las farmacias", "/buscar?rubro=farmacia&vista=mapa"],
  ]);
  const sin = intencionesDeCiudad(datos("madrugada", { hayTurnos: false })).find((i) => i.id === "farmacias");
  assert.deepEqual(sin?.opciones.map((o) => o.t), ["Todas las farmacias"]);
  // Sin farmacias en la ciudad y sin turnos: el botón no aparece.
  assert.ok(!intencionesDeCiudad(datos("madrugada", { hayTurnos: false, rubros: new Set(["calzado"]) })).some((i) => i.id === "farmacias"));
});

test("Bancos y cajeros: cajeros y cambio, sólo los que hay", () => {
  const b = intencionesDeCiudad(datos("tarde", { rubros: new Set(["cajeros", "cambio"]) })).find((i) => i.id === "bancos");
  assert.deepEqual(b?.opciones.map((o) => o.t), ["Cajeros y bancos", "Casas de cambio"]);
  const solo = intencionesDeCiudad(datos("tarde", { rubros: new Set(["cajeros"]) })).find((i) => i.id === "bancos");
  assert.deepEqual(solo?.opciones.map((o) => o.t), ["Cajeros y bancos"]);
});

test("Negocios: los rubros comerciales de la ciudad que no son de comer, dormir ni servicios, ordenados por nombre", () => {
  const n = intencionesDeCiudad(datos("tarde")).find((i) => i.id === "negocios");
  assert.deepEqual(n?.opciones.map((o) => o.t), ["Calzado", "Celulares", "Ropa"]);
  // Sin saber qué hay en la ciudad (falló la lectura) no se inventa una lista.
  assert.ok(!intencionesDeCiudad(datos("tarde", { rubros: null })).some((i) => i.id === "negocios"));
});

test("Servicios: los rubros de oficios que la ciudad tiene", () => {
  const s = intencionesDeCiudad(datos("tarde")).find((i) => i.id === "servicios");
  assert.deepEqual(s?.opciones.map((o) => o.rubro), ["peluqueria", "servicio-tecnico"]);
});

test("Productos: los más frecuentes como chips; sin productos frecuentes no hay botón", () => {
  const p = intencionesDeCiudad(datos("tarde")).find((i) => i.id === "productos");
  assert.equal(p?.tipo, "productos");
  assert.deepEqual(p?.productos, ["zapatillas", "celulares"]);
  assert.ok(!intencionesDeCiudad(datos("tarde", { productosFrecuentes: [] })).some((i) => i.id === "productos"));
});

test("ninguna intención lleva emojis ni números", () => {
  for (const f of FRANJAS) {
    for (const i of intencionesDeCiudad(datos(f))) {
      for (const t of [i.titulo, i.subtitulo, i.cartel ?? "", ...i.opciones.map((o) => o.t)]) {
        assert.doesNotMatch(t, /\p{Extended_Pictographic}/u, t);
        assert.doesNotMatch(t, /\d/, t);
      }
    }
  }
});

// ── Carrusel de comercios ────────────────────────────────────────────────────

const com = (id: string, rubro: string, extra: Partial<ComercioDeLaCiudad> = {}): ComercioDeLaCiudad => ({
  id, slug: id, nombre: id.toUpperCase(), portada_thumb_url: `https://x/${id}.jpg`, portada_pos: null, rubro_slug: rubro, rubro_nombre: rubro,
  horario: "Lun a Dom 8-22", lat: -21.53, lng: -64.73, prod_obs_human: null, prod_det_ia: null, ...extra,
});
const COMERCIALES = new Set(["calzado", "ropa", "cafeteria", "restaurantes", "panaderia", "nocturna", "farmacia", "comida-rapida"]);

test("config del carrusel: rubros, título y bajada por franja", () => {
  assert.deepEqual(configCarrusel("manana", "Tarija").rubros, ["cafeteria", "panaderia"]);
  assert.equal(configCarrusel("manana", "Tarija").titulo, "Para desayunar");
  assert.deepEqual(configCarrusel("mediodia", "Tarija").rubros, ["restaurantes", "comida-rapida"]);
  assert.equal(configCarrusel("mediodia", "Tarija").titulo, "Para almorzar");
  assert.equal(configCarrusel("tarde", "Tarija").rubros, null);
  assert.equal(configCarrusel("tarde", "Tarija").titulo, "Abiertos ahora");
  assert.deepEqual(configCarrusel("noche", "Tarija").rubros, ["nocturna", "restaurantes"]);
  assert.equal(configCarrusel("noche", "Tarija").titulo, "Esta noche en Tarija");
  assert.deepEqual(configCarrusel("madrugada", "Tarija").rubros, ["farmacia"]);
  assert.equal(configCarrusel("madrugada", "Tarija").titulo, "Abiertas ahora");
});

test("candidatos: sólo comercios con foto y de los rubros de la franja", () => {
  const lista = [com("a", "cafeteria"), com("b", "panaderia"), com("c", "cafeteria", { portada_thumb_url: null }), com("d", "calzado")];
  const r = candidatosCarrusel(lista, "manana", "Tarija", COMERCIALES);
  assert.equal(r.titulo, "Para desayunar");
  assert.deepEqual(r.items.map((i) => i.id), ["a", "b"]);
  assert.equal(r.verTodos, "/buscar?rubro=cafeteria&vista=mapa");
});

test("candidatos de la tarde: comerciales que no son de comer", () => {
  const lista = [com("a", "cafeteria"), com("b", "calzado"), com("c", "ropa"), com("d", "banos")];
  const r = candidatosCarrusel(lista, "tarde", "Tarija", COMERCIALES);
  assert.deepEqual(r.items.map((i) => i.id), ["b", "c"]);
  assert.equal(r.verTodos, "/buscar?vista=mapa");
});

test("sin comercios de los rubros de la franja, el respaldo son los comerciales con foto y el título cambia", () => {
  const lista = [com("a", "calzado"), com("b", "ropa"), com("c", "banos")];
  const r = candidatosCarrusel(lista, "madrugada", "Tarija", COMERCIALES);
  assert.equal(r.titulo, "Comercios de Tarija");
  assert.deepEqual(r.items.map((i) => i.id), ["a", "b"]);
  // Sin ninguno (ni de la franja ni comerciales con foto): lista vacía, el carrusel no aparece.
  assert.deepEqual(candidatosCarrusel([com("c", "banos")], "madrugada", "Tarija", COMERCIALES).items, []);
});

const cand = (id: string, extra: Partial<ComercioCarrusel> = {}): ComercioCarrusel => ({
  id, slug: id, nombre: id, foto: "https://x/f.jpg", fotoPos: null, rubro: "cafeteria", rubroNombre: "Cafetería",
  horario: "Lun a Dom 8-22", horarioEstimado: false, lat: -21.5300, lng: -64.7300, estrella: false, plan_orden: 0, ...extra,
});
// Miércoles 20/11... a las 14:00 de Bolivia (el Date ya trae esas horas).
const AHORA = new Date(2026, 10, 18, 14, 0);

test("prepararCarrusel: con «Abiertos» sólo los abiertos (horario ilegible o ausente no cuenta)", () => {
  const lista = [cand("abierto"), cand("cerrado", { horario: "Lun a Dom 16-20" }), cand("sin", { horario: null }), cand("raro", { horario: "a convenir" })];
  assert.deepEqual(prepararCarrusel(lista, { abiertos: true, cerca: false, ubicacion: null, ahora: AHORA }).map((c) => c.id), ["abierto"]);
});

test("prepararCarrusel: orden de «Cerca de mí»: abiertos primero, después la estrella, después la distancia", () => {
  const yo = { lat: -21.5300, lng: -64.7300 };
  const lista = [
    cand("cerrado-cerca", { horario: "Lun a Dom 16-20", lat: -21.5301 }),
    cand("abierto-lejos", { lat: -21.5900 }),
    cand("abierto-cerca", { lat: -21.5302 }),
    cand("abierto-cerca-estrella", { lat: -21.5303, estrella: true, plan_orden: 2 }),
  ];
  const r = prepararCarrusel(lista, { abiertos: false, cerca: true, ubicacion: yo, ahora: AHORA });
  assert.deepEqual(r.map((c) => c.id), ["abierto-cerca-estrella", "abierto-cerca", "abierto-lejos", "cerrado-cerca"]);
});

test("prepararCarrusel: los metros sólo con «Más cerca» y ubicación; sin ubicación, no hay metros", () => {
  const yo = { lat: -21.5300, lng: -64.7300 };
  const lista = [cand("a", { lat: -21.5302 })];
  assert.ok((prepararCarrusel(lista, { abiertos: false, cerca: true, ubicacion: yo, ahora: AHORA })[0].metros ?? 0) > 0);
  assert.equal(prepararCarrusel(lista, { abiertos: false, cerca: false, ubicacion: yo, ahora: AHORA })[0].metros, null);
  assert.equal(prepararCarrusel(lista, { abiertos: false, cerca: true, ubicacion: null, ahora: AHORA })[0].metros, null);
});

test("prepararCarrusel: hasta 12", () => {
  const lista = Array.from({ length: 30 }, (_, i) => cand(`c${i}`));
  assert.equal(prepararCarrusel(lista, { abiertos: false, cerca: false, ubicacion: null, ahora: AHORA }).length, 12);
});

// ── «Qué podés hacer» ────────────────────────────────────────────────────────

const SIN_FOTOS = { visitar: null, nocturna: null, restaurantes: null, plazaParque: [] };

test("tiles: cada uno sale sólo si la ciudad tiene datos; sin ninguno, ninguno", () => {
  assert.deepEqual(tilesQueHacer(new Set(["calzado"]), SIN_FOTOS), []);
  assert.deepEqual(tilesQueHacer(null, SIN_FOTOS), []);
  const t = tilesQueHacer(new Set(["para-visitar", "nocturna", "restaurantes"]), { visitar: "v.jpg", nocturna: "n.jpg", restaurantes: null, plazaParque: [{ sub: "Plaza", foto: "p.jpg" }] });
  assert.deepEqual(t.map((x) => x.id), ["visitar", "nocturna", "comer", "plazas"]);
  assert.deepEqual(t.map((x) => x.foto), ["v.jpg", "n.jpg", null, "p.jpg"]);
  assert.equal(t[0].href, "/buscar?rubro=para-visitar&vista=mapa");
  assert.equal(t[1].href, "/buscar?rubro=nocturna&vista=mapa");
  assert.equal(t[3].href, "/buscar?rubro=para-visitar&sub=Plaza&vista=mapa");
});

test("tiles: «Plazas y parques» sólo con plazas o parques cargados; la foto es siempre de un comercio de ese rubro", () => {
  const sinPlazas = tilesQueHacer(new Set(["para-visitar"]), { ...SIN_FOTOS, visitar: "v.jpg" });
  assert.deepEqual(sinPlazas.map((x) => x.id), ["visitar"]);
  const soloParque = tilesQueHacer(new Set(["para-visitar"]), { ...SIN_FOTOS, plazaParque: [{ sub: "Parque", foto: null }] });
  assert.equal(soloParque.find((x) => x.id === "plazas")?.href, "/buscar?rubro=para-visitar&sub=Parque&vista=mapa");
  assert.equal(soloParque.find((x) => x.id === "plazas")?.foto, null);
  // Sin foto de su rubro: el ícono solo (nunca la foto de otro rubro).
  assert.equal(tilesQueHacer(new Set(["nocturna"]), { ...SIN_FOTOS, restaurantes: "r.jpg" })[0].foto, null);
});

// ── Dax ──────────────────────────────────────────────────────────────────────

test("saludo de Dax por franja", () => {
  assert.equal(saludoDeFranja("manana"), "¡Buen día!");
  assert.equal(saludoDeFranja("mediodia"), "¡Hola!");
  assert.equal(saludoDeFranja("tarde"), "¡Hola!");
  assert.equal(saludoDeFranja("noche"), "¡Buenas noches!");
  assert.equal(saludoDeFranja("madrugada"), "¡Buenas noches!");
  assert.match(bienvenidaDax("manana", "Tarija", false), /^¡Buen día! Soy Dax y conozco Tarija\./);
});

test("sugerencias de Dax por franja, cuando la ciudad tiene todo", () => {
  const todo = new Set(["cafeteria", "panaderia", "farmacia", "para-visitar", "restaurantes", "calzado", "cajeros", "servicio-tecnico", "nocturna", "hospedaje"]);
  assert.deepEqual(sugerenciasDeFranja("manana", todo), ["¿Dónde desayuno?", "Farmacia abierta cerca", "¿Qué visito hoy?"]);
  assert.deepEqual(sugerenciasDeFranja("mediodia", todo), ["¿Dónde almuerzo?", "Busco zapatillas", "Cajero cerca"]);
  assert.deepEqual(sugerenciasDeFranja("tarde", todo), ["Busco zapatillas", "Necesito un servicio técnico", "¿Qué hago hoy?"]);
  assert.deepEqual(sugerenciasDeFranja("noche", todo), ["Boliches abiertos esta noche", "¿Dónde ceno?", "Hotel para esta noche"]);
  assert.deepEqual(sugerenciasDeFranja("madrugada", todo), ["Farmacia de turno", "Cajero cerca", "¿Dónde duermo?"]);
  // Rubros desconocidos (falló la lectura): salen todas.
  assert.equal(sugerenciasDeFranja("noche", null).length, 3);
});

test("sugerencias de Dax: una sugerencia sale sólo si la ciudad tiene el rubro", () => {
  const s = sugerenciasDeFranja("noche", new Set(["restaurantes", "hospedaje"]));
  assert.ok(!s.includes("Boliches abiertos esta noche"));
  assert.ok(s.includes("¿Dónde ceno?") && s.includes("Hotel para esta noche"));
});

test("sugerencias de Dax: con casi nada en la ciudad se completan con dos que valen siempre; nunca el paso ni la aduana", () => {
  const poco = sugerenciasDeFranja("madrugada", new Set(["calzado"]));
  assert.ok(poco.length >= 2);
  assert.ok(poco.includes("¿Qué hay abierto ahora?"));
  for (const f of FRANJAS) {
    for (const t of [...sugerenciasDeFranja(f, null), ...sugerenciasDeFranja(f, new Set())]) {
      assert.doesNotMatch(t, /paso|aduana|peso|frontera|dólar|dolar|cambio/i, t);
    }
  }
});

test("consultaDeBusqueda: la pregunta sin signos ni relleno", () => {
  assert.equal(consultaDeBusqueda("¿Dónde hay una farmacia?"), "farmacia");
  assert.equal(consultaDeBusqueda("Busco zapatillas"), "zapatillas");
  assert.equal(consultaDeBusqueda("Necesito un servicio técnico"), "servicio técnico");
  assert.equal(consultaDeBusqueda("¿Qué hay abierto ahora?"), "");
});
