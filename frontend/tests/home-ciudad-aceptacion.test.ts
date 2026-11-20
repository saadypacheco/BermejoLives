// QA de aceptación del home de las ciudades (docs/home-ciudades.md §10, criterios 1 a 9), sobre la lógica pura y
// sobre el código fuente (guardas estáticas) donde hace falta un navegador para verlo de verdad.
//
// Complementa a home-ciudad.test.ts, home-productos.test.ts, filtros-rapidos.test.ts y clima-ciudad.test.ts del
// dev: acá van los bordes de las franjas (5:59/6:00/…/23:59/0:00 en hora de Bolivia, con el servidor en cualquier
// huso), las propiedades «nunca un acceso a un rubro vacío» sobre muchos conjuntos de rubros, el umbral de 4
// productos, la vigencia del clima y las guardas de que Bermejo conserva su home.
import test from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import {
  RUBROS_COMER, RUBROS_DORMIR, bienvenidaDax, candidatosCarrusel, franjaAhora, franjaDe, hrefRubro, intencionesDeCiudad,
  ordenIntenciones, resaltadoDeFranja, sugerenciasDeFranja, tilesQueHacer,
  type ComercioDeLaCiudad, type DatosIntenciones, type Franja, type RubroCatalogo,
} from "../lib/home-ciudad-pure";
import { conFiltros, SIN_FILTROS, type FiltrosRapidos } from "../lib/filtros-rapidos";
import { climaVigente, VIGENCIA_CLIMA_MS } from "../lib/clima-ciudad-pure";
import {
  MIN_PRODUCTOS_CARGADOS, tarjetasDeLocales, tarjetasDeProductos, type FilaProducto, type LocalConProductos,
} from "../lib/home-productos-pure";

const RAIZ = process.cwd(); // `npm test` corre en frontend/
const leer = (ruta: string): string => readFileSync(resolve(RAIZ, ruta), "utf8").split("\r\n").join("\n");
const FRANJAS: Franja[] = ["madrugada", "manana", "mediodia", "tarde", "noche"];

/** Un instante que en Bolivia (UTC-4, sin horario de verano) es el `h:m` del día 20/11/2026 (con `dia` se corre). */
const bo = (h: number, m: number, dia = 20): Date => new Date(Date.UTC(2026, 10, dia, h + 4, m));

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 4: botones según la hora (franjas de Bolivia, bordes, orden, cartel)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

const BORDES: { h: number; m: number; franja: Franja; primero: string; cartel: string }[] = [
  { h: 0, m: 0, franja: "madrugada", primero: "farmacias", cartel: "De turno" },
  { h: 5, m: 59, franja: "madrugada", primero: "farmacias", cartel: "De turno" },
  { h: 6, m: 0, franja: "manana", primero: "comer", cartel: "Desayunos" },
  { h: 10, m: 59, franja: "manana", primero: "comer", cartel: "Desayunos" },
  { h: 11, m: 0, franja: "mediodia", primero: "comer", cartel: "Almuerzos" },
  { h: 14, m: 59, franja: "mediodia", primero: "comer", cartel: "Almuerzos" },
  { h: 15, m: 0, franja: "tarde", primero: "negocios", cartel: "Abiertos" },
  { h: 18, m: 59, franja: "tarde", primero: "negocios", cartel: "Abiertos" },
  { h: 19, m: 0, franja: "noche", primero: "comer", cartel: "Cenar" },
  { h: 23, m: 59, franja: "noche", primero: "comer", cartel: "Cenar" },
];

const TODOS_LOS_RUBROS = new Set([
  "calzado", "ropa", "celulares", "cafeteria", "restaurantes", "comida-rapida", "panaderia", "hospedaje", "farmacia", "cajeros",
  "cambio", "servicio-tecnico", "peluqueria", "taller-mecanico", "nocturna", "para-visitar",
]);
const CATALOGO: RubroCatalogo[] = [...TODOS_LOS_RUBROS].map((slug) => ({
  slug, nombre: slug, comercial: slug === "cajeros" || slug === "para-visitar" ? false : true,
}));
const datos = (franja: Franja, extra: Partial<DatosIntenciones> = {}): DatosIntenciones => ({
  franja, ciudadSlug: "tarija", rubros: TODOS_LOS_RUBROS, catalogo: CATALOGO, hayTurnos: true,
  productosFrecuentes: ["zapatillas", "celulares"], ...extra,
});

test("C4 · franjaAhora en los bordes (5:59, 6:00, 10:59, 11:00, 14:59, 15:00, 18:59, 19:00, 23:59, 0:00) en hora de Bolivia", () => {
  for (const b of BORDES) {
    // El día 21 a las 0:00 también es madrugada (cambio de día).
    assert.equal(franjaAhora(bo(b.h, b.m)), b.franja, `${b.h}:${String(b.m).padStart(2, "0")}`);
  }
  assert.equal(franjaAhora(bo(0, 0, 21)), "madrugada");
  // Con segundos y milisegundos: 5:59:59.999 sigue siendo madrugada, 6:00:00.000 ya es mañana.
  assert.equal(franjaAhora(new Date(bo(6, 0).getTime() - 1)), "madrugada");
  assert.equal(franjaAhora(bo(6, 0)), "manana");
  assert.equal(franjaAhora(new Date(bo(19, 0).getTime() - 1)), "tarde");
});

test("C4 · franjaDe: no deja huecos ni se pisa en las 24 horas (y la fracción no cambia de franja antes de tiempo)", () => {
  const vistas = new Map<Franja, number[]>();
  for (let h = 0; h < 24; h++) vistas.set(franjaDe(h), [...(vistas.get(franjaDe(h)) ?? []), h]);
  assert.deepEqual([...vistas.keys()], ["madrugada", "manana", "mediodia", "tarde", "noche"]);
  assert.deepEqual(vistas.get("madrugada"), [0, 1, 2, 3, 4, 5]);
  assert.deepEqual(vistas.get("manana"), [6, 7, 8, 9, 10]);
  assert.deepEqual(vistas.get("mediodia"), [11, 12, 13, 14]);
  assert.deepEqual(vistas.get("tarde"), [15, 16, 17, 18]);
  assert.deepEqual(vistas.get("noche"), [19, 20, 21, 22, 23]);
});

test("C4 · la franja es la de Bolivia aunque el servidor (o el navegador) esté en otro huso horario", () => {
  const script = `
    const h = require(${JSON.stringify(resolve(__dirname, "../lib/home-ciudad-pure.js"))});
    const t = ${JSON.stringify(BORDES.map((b) => bo(b.h, b.m).toISOString()))};
    console.log(JSON.stringify(t.map((s) => h.franjaAhora(new Date(s)))));`;
  for (const tz of ["UTC", "America/La_Paz", "Asia/Tokyo", "America/New_York", "Pacific/Auckland", "Europe/Madrid"]) {
    const out = execFileSync(process.execPath, ["-e", script], { env: { ...process.env, TZ: tz }, encoding: "utf8" });
    assert.deepEqual(JSON.parse(out), BORDES.map((b) => b.franja), `TZ=${tz}`);
  }
});

test("C4 · en cada borde, el orden de los botones y el cartel son los de la tabla de §4", () => {
  for (const b of BORDES) {
    const f = franjaAhora(bo(b.h, b.m));
    const botones = intencionesDeCiudad(datos(f));
    assert.equal(botones.length, 7, "con todos los rubros salen los 7 botones");
    assert.equal(botones[0].id, b.primero, `${b.h}:${b.m}`);
    assert.deepEqual(botones.map((x) => x.id), ordenIntenciones(f));
    assert.deepEqual(botones.filter((x) => x.cartel).map((x) => x.cartel), [b.cartel]);
    assert.equal(resaltadoDeFranja(f).cartel, b.cartel);
  }
});

test("C4 · el cartel de una franja no se pierde si el botón resaltado no existe (queda sin cartel, sin romper)", () => {
  // De noche el resaltado es «Comer»; sin rubros de comida, no hay botón ni cartel.
  const sinComida = intencionesDeCiudad(datos("noche", { rubros: new Set(["calzado", "farmacia"]) }));
  assert.ok(!sinComida.some((x) => x.id === "comer"));
  assert.equal(sinComida.filter((x) => x.cartel).length, 0);
});

test("C4 · el tamaño de los botones: el CSS de las intenciones calza con el de los accesos de hoy (9px 14px, 14px, 600)", () => {
  const css = leer("app/styles/home-ciudad.css");
  const regla = css.match(/\.uk-intenciones button \{[^}]*\}/)?.[0] ?? "";
  assert.match(regla, /padding:\s*9px 14px/);
  assert.match(regla, /font-size:\s*14px/);
  assert.match(regla, /font-weight:\s*600/);
  assert.match(regla, /border-radius:\s*var\(--uk-radius-sm\)/);
  // El cartel va dentro del botón y es chico: no agranda el botón.
  assert.match(css, /\.uk-int-cartel \{[^}]*font-size:\s*11px/);
  const tsx = leer("components/home-ciudad/intenciones-ciudad.tsx");
  assert.match(tsx, /<Ic n=\{i\.icono\} s=\{18\} \/>/, "ícono de 18 px");
  assert.match(tsx, /\{i\.cartel && <span className="uk-int-cartel">/, "el cartel está dentro del <button>");
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 2: sin bloques vacíos (propiedades sobre muchos conjuntos de rubros)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

/** Generador pseudoaleatorio determinista (mulberry32): los tests no pueden ser intermitentes. */
function azarSemilla(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
function subconjuntos(n: number, semilla = 7): Set<string>[] {
  const azar = azarSemilla(semilla);
  const universo = [...TODOS_LOS_RUBROS];
  const out: Set<string>[] = [new Set(), new Set(universo)];
  for (const r of universo) out.push(new Set([r]));
  while (out.length < n) out.push(new Set(universo.filter(() => azar() < 0.4)));
  return out;
}

test("C2 · ningún botón ni opción lleva a un rubro que la ciudad no tiene (400 combinaciones de rubros × 5 franjas)", () => {
  for (const rubros of subconjuntos(400)) {
    for (const f of FRANJAS) {
      for (const hayTurnos of [false, true]) {
        const botones = intencionesDeCiudad(datos(f, { rubros, hayTurnos }));
        assert.equal(new Set(botones.map((b) => b.id)).size, botones.length, "sin botones repetidos");
        for (const b of botones) {
          // Un botón sin nada adentro no aparece.
          assert.ok(b.tipo === "productos" ? b.productos.length > 0 : b.opciones.length > 0, `${b.id} vacío`);
          for (const o of b.opciones) {
            if (o.rubro) {
              assert.ok(rubros.has(o.rubro), `${b.id} ofrece «${o.rubro}» y la ciudad sólo tiene ${[...rubros].join(",")}`);
              assert.equal(o.href, hrefRubro(o.rubro));
            } else {
              // La única opción sin rubro es «De turno hoy», y sólo con turnos cargados.
              assert.equal(o.href, "/tarija/farmacias-de-turno");
              assert.ok(hayTurnos);
            }
          }
        }
        if (!rubros.has("farmacia") && !hayTurnos) assert.ok(!botones.some((b) => b.id === "farmacias"));
        if (!rubros.has("cajeros") && !rubros.has("cambio")) assert.ok(!botones.some((b) => b.id === "bancos"));
        if (!rubros.has("hospedaje")) assert.ok(!botones.some((b) => b.id === "dormir"));
      }
    }
  }
});

test("C2 · «Negocios» sólo trae rubros comerciales de la ciudad que no son de comer ni de dormir; ciudad vacía = sin botones salvo productos", () => {
  for (const rubros of subconjuntos(200, 11)) {
    const n = intencionesDeCiudad(datos("tarde", { rubros })).find((b) => b.id === "negocios");
    for (const o of n?.opciones ?? []) {
      assert.ok(rubros.has(o.rubro as string));
      assert.ok(!RUBROS_COMER.includes(o.rubro as string) && !RUBROS_DORMIR.includes(o.rubro as string), o.rubro);
      assert.notEqual(o.rubro, "cajeros", "un rubro no comercial no es un negocio");
    }
  }
  const vacia = intencionesDeCiudad(datos("tarde", { rubros: new Set(), hayTurnos: false }));
  assert.deepEqual(vacia.map((b) => b.id), ["productos"]);
  assert.deepEqual(intencionesDeCiudad(datos("tarde", { rubros: new Set(), hayTurnos: false, productosFrecuentes: [] })), []);
});

test("C2 · «Qué podés hacer»: cada tarjeta sólo con su rubro (y plazas sólo con «para-visitar»), nunca la foto de otro rubro", () => {
  const FOTOS = { visitar: "v.jpg", nocturna: "n.jpg", restaurantes: "r.jpg", plazaParque: [{ sub: "Plaza" as const, foto: "p.jpg" }] };
  for (const rubros of subconjuntos(200, 3)) {
    const t = tilesQueHacer(rubros, FOTOS);
    const ids = t.map((x) => x.id);
    assert.equal(ids.includes("visitar"), rubros.has("para-visitar"));
    assert.equal(ids.includes("plazas"), rubros.has("para-visitar"));
    assert.equal(ids.includes("nocturna"), rubros.has("nocturna"));
    assert.equal(ids.includes("comer"), rubros.has("restaurantes"));
    for (const x of t) {
      const propia: Record<string, string> = { visitar: "v.jpg", nocturna: "n.jpg", comer: "r.jpg", plazas: "p.jpg" };
      assert.equal(x.foto, propia[x.id], `la foto de «${x.id}» tiene que ser de su rubro`);
      assert.ok(x.href.startsWith("/buscar?rubro="));
    }
  }
  assert.deepEqual(tilesQueHacer(new Set(), FOTOS), [], "sin ninguna tarjeta el bloque no aparece");
});

test("C2 · carrusel de comercios: items sólo con foto y de los rubros de la franja; si no hay, respaldo comercial; si tampoco, vacío", () => {
  const azar = azarSemilla(99);
  const rubrosPosibles = ["cafeteria", "panaderia", "restaurantes", "comida-rapida", "nocturna", "farmacia", "calzado", "ropa", "banos", "cajeros"];
  const comerciales = new Set(["cafeteria", "panaderia", "restaurantes", "comida-rapida", "nocturna", "farmacia", "calzado", "ropa"]);
  for (let i = 0; i < 300; i++) {
    const lista: ComercioDeLaCiudad[] = Array.from({ length: Math.floor(azar() * 8) }, (_, k) => ({
      id: `c${k}`, slug: `c${k}`, nombre: `C${k}`, portada_thumb_url: azar() < 0.7 ? `https://x/${k}.jpg` : null, portada_pos: null,
      rubro_slug: rubrosPosibles[Math.floor(azar() * rubrosPosibles.length)], rubro_nombre: "x", horario: null, lat: null, lng: null,
      prod_obs_human: null, prod_det_ia: null,
    }));
    for (const f of FRANJAS) {
      const r = candidatosCarrusel(lista, f, "Tarija", comerciales);
      for (const it of r.items) {
        assert.ok(it.foto, "con foto");
        if (r.titulo.startsWith("Comercios de ")) assert.ok(comerciales.has(it.rubro), "el respaldo es comercial");
      }
      if (r.items.length === 0) assert.ok(lista.every((c) => !c.portada_thumb_url || !comerciales.has(c.rubro_slug as string)));
    }
  }
});

test("C2 · sin productos ni locales con productos detectados el carrusel de productos no aparece (lo que usa app/page.tsx)", () => {
  const elegir = (filas: FilaProducto[], locales: LocalConProductos[]) => {
    const desdeTabla = tarjetasDeProductos(filas);
    return desdeTabla.length > 0 ? desdeTabla : tarjetasDeLocales(locales);
  };
  assert.deepEqual(elegir([], []), []);
  assert.deepEqual(elegir([], [{ id: "1", slug: "a", nombre: "A", portada_thumb_url: "x.jpg", prod_obs_human: null, prod_det_ia: null }]), []);
  assert.deepEqual(elegir([], [{ id: "1", slug: "a", nombre: "A", portada_thumb_url: null, prod_obs_human: "ropa", prod_det_ia: null }]), []);
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 2/5 (carrusel de productos): umbral de 4
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

const fila = (n: number, extra: Partial<FilaProducto> = {}): FilaProducto => ({
  id: `p${n}`, nombre: `Producto ${n}`, precio: 10, moneda: "BOB", foto_url: `https://x/${n}.jpg`, comercio: { slug: `l${n}`, nombre: `L${n}` }, ...extra,
});

test("C2 · umbral del carrusel de productos: 3 útiles → respaldo; 4 → tabla; las filas inútiles no cuentan para el 4", () => {
  assert.equal(MIN_PRODUCTOS_CARGADOS, 4);
  const filas = (n: number) => Array.from({ length: n }, (_, i) => fila(i + 1));
  assert.equal(tarjetasDeProductos(filas(0)).length, 0);
  assert.equal(tarjetasDeProductos(filas(3)).length, 0);
  assert.equal(tarjetasDeProductos(filas(4)).length, 4);
  assert.equal(tarjetasDeProductos(filas(5)).length, 5);
  // 5 filas pero 2 inútiles (sin foto, sin comercio, nombre vacío): quedan 3 → no alcanza.
  assert.equal(tarjetasDeProductos([fila(1), fila(2), fila(3), fila(4, { foto_url: null }), fila(5, { comercio: null })]).length, 0);
  assert.equal(tarjetasDeProductos([fila(1), fila(2), fila(3), fila(4, { nombre: "   " })]).length, 0);
  assert.equal(tarjetasDeProductos([fila(1), fila(2), fila(3), fila(4, { foto_url: "" })]).length, 0);
  // Con 4 útiles y otras inútiles mezcladas, sí.
  assert.equal(tarjetasDeProductos([fila(1), fila(2, { foto_url: null }), fila(3), fila(4), fila(5), fila(6, { comercio: null })]).length, 4);
});

test("C2 · con menos de 4 productos en la tabla se arma con los textos de los locales, con tope de 12", () => {
  const locales: LocalConProductos[] = Array.from({ length: 20 }, (_, i) => ({
    id: `c${i}`, slug: `s${i}`, nombre: `N${i}`, portada_thumb_url: `https://x/${i}.jpg`, prod_obs_human: "Zapatillas, botines, sandalias, medias", prod_det_ia: null,
  }));
  const desdeTabla = tarjetasDeProductos([fila(1), fila(2), fila(3)]);
  const tarjetas = desdeTabla.length > 0 ? desdeTabla : tarjetasDeLocales(locales);
  assert.equal(tarjetas.length, 12);
  assert.equal(tarjetas[0].titulo.split(", ").length, 3, "los dos o tres primeros productos");
  for (const t of tarjetas) assert.match(t.href, /^\/comercios\/s\d+#ficha-encontrar$/);
});

test("C2 · el precio sólo sale si está cargado (la tarjeta no inventa ni muestra 0)", () => {
  const t = tarjetasDeProductos([fila(1, { precio: null }), fila(2, { precio: 0 }), fila(3, { precio: "" }), fila(4, { precio: 25 })]);
  assert.deepEqual(t.map((x) => x.precio), [null, null, null, "Bs 25"]);
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 3: interruptores (conFiltros)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

const COMBOS: FiltrosRapidos[] = [
  { abiertos: false, cerca: false }, { abiertos: true, cerca: false }, { abiertos: false, cerca: true }, { abiertos: true, cerca: true },
];
const esBusqueda = (h: string): boolean => /^\/(buscar|mapa)(?:[/?#]|$)/.test(h);

test("C3 · conFiltros sobre TODOS los enlaces que genera el home: busca/mapa llevan cada parámetro una sola vez, el resto no se toca", () => {
  const hrefs = new Set<string>(["/buscar", "/buscar?q=zapatillas", "/mapa", "/buscar?vista=mapa", "/comercios/x#ficha-encontrar", "/ofertas", "/tarija/farmacias-de-turno"]);
  for (const f of FRANJAS) {
    for (const b of intencionesDeCiudad(datos(f))) {
      for (const o of b.opciones) hrefs.add(o.href);
      for (const p of b.productos) hrefs.add(`/buscar?q=${encodeURIComponent(p)}`);
    }
    hrefs.add(candidatosCarrusel([], f, "Tarija", new Set()).verTodos);
  }
  for (const t of tilesQueHacer(TODOS_LOS_RUBROS, { visitar: null, nocturna: null, restaurantes: null, plazaParque: [{ sub: "Parque", foto: null }] })) hrefs.add(t.href);
  for (const h of hrefs) {
    for (const f of COMBOS) {
      const r = conFiltros(h, f);
      if (!esBusqueda(h) || (!f.abiertos && !f.cerca)) { assert.equal(r, h, `no se toca: ${h}`); continue; }
      const u = new URL(r, "https://uruku.test");
      const antes = new URL(h, "https://uruku.test");
      assert.equal(u.pathname, antes.pathname);
      assert.equal(u.searchParams.getAll("abierto").length, f.abiertos ? 1 : 0, r);
      assert.equal(u.searchParams.getAll("cerca").length, f.cerca ? 1 : 0, r);
      for (const [k, v] of antes.searchParams) assert.equal(u.searchParams.get(k), v, `se conserva ${k} en ${r}`);
      assert.equal(conFiltros(r, f), r, `idempotente: ${r}`);
    }
  }
});

test("C3 · conFiltros: bordes de forma (ancla con «?», sin consulta, barra final, rutas parecidas, URLs absolutas)", () => {
  const A: FiltrosRapidos = { abiertos: true, cerca: true };
  assert.equal(conFiltros("/buscar#x?y", A), "/buscar?abierto=1&cerca=1#x?y");
  assert.equal(conFiltros("/buscar?", A), "/buscar?abierto=1&cerca=1");
  assert.equal(conFiltros("/buscar?q=a#b", A), "/buscar?q=a&abierto=1&cerca=1#b");
  assert.equal(conFiltros("/buscar?q=a&abierto=1&cerca=1", A), "/buscar?q=a&abierto=1&cerca=1");
  assert.equal(conFiltros("/buscar?cerca=1", { abiertos: true, cerca: true }), "/buscar?cerca=1&abierto=1");
  for (const h of ["/mapas", "/mapa-del-sitio", "/buscarx", "/Buscar", "//buscar", "https://uruku.bo/buscar?q=1", "mailto:a@b.c", "", "#buscar", "/comercios/buscar"]) {
    assert.equal(conFiltros(h, A), h, `no se toca «${h}»`);
  }
  // Un valor que se parece al parámetro, pero no lo es, no cuenta como «ya lo trae».
  assert.equal(conFiltros("/buscar?q=abierto%3D1", { abiertos: true, cerca: false }), "/buscar?q=abierto%3D1&abierto=1");
  assert.equal(conFiltros("/buscar?nabierto=1", { abiertos: true, cerca: false }), "/buscar?nabierto=1&abierto=1");
});

test("C3 · «Abiertos» y «Más cerca» se pintan de verde y se recuerdan en la sesión (guardas estáticas del código y del CSS)", () => {
  const toggles = leer("components/home-ciudad/filtros-rapidos-toggles.tsx");
  assert.match(toggles, /aria-pressed=\{f\.abiertos\}/);
  assert.match(toggles, /aria-pressed=\{f\.cerca\}/);
  const css = leer("app/styles/home-ciudad.css");
  assert.match(css, /\.uk-tog\[aria-pressed="true"\] \{[^}]*background:\s*var\(--uk-green-2\)/);
  const store = leer("components/home-ciudad/use-filtros-rapidos.ts");
  assert.match(store, /sessionStorage\.getItem\(CLAVE_FILTROS_RAPIDOS\)/);
  assert.match(store, /sessionStorage\.setItem\(CLAVE_FILTROS_RAPIDOS/);
  assert.doesNotMatch(store, /localStorage/, "se guarda por sesión, no para siempre");
  // «Más cerca» se apaga solo si no dan la ubicación, y avisa.
  assert.match(toggles, /cambiar\(\{ cerca: false \}\)[\s\S]*avisar\(/);
});

test("C3 · todo enlace al buscador o al mapa del home pasa por conFiltros (barra de rubros, intenciones, «Qué podés hacer», «Ver todos», buscador)", () => {
  assert.match(leer("components/catnav.tsx"), /href=\{href\("\/buscar"\)\}[\s\S]*href=\{href\(`\/buscar\?rubro=\$\{r\.slug\}`\)\}/);
  assert.match(leer("components/catnav.tsx"), /conFiltros=\{!esBermejo\}|const href = \(h: string\) => \(conFiltros \? sumarFiltros\(h, rapidos\) : h\)/);
  assert.match(leer("components/uruku-shell.tsx"), /<CatNav [^>]*conFiltros=\{!esBermejo\}/);
  assert.match(leer("components/home-ciudad/intenciones-ciudad.tsx"), /conFiltros\(o\.href, filtros\)/);
  assert.match(leer("components/home-ciudad/intenciones-ciudad.tsx"), /conFiltros\(href, filtros\)/);
  assert.match(leer("components/home-ciudad/que-hacer.tsx"), /<EnlaceFiltrado /);
  assert.match(leer("components/home-ciudad/carrusel-comercios.tsx"), /conFiltros\(verTodos, filtros\)/);
  assert.match(leer("components/uruku-shell.tsx"), /\{!esBermejo && <CamposFiltrosBusqueda \/>\}/);
  assert.match(leer("components/bottom-nav.tsx"), /conFiltros\(it\.href, rapidos\)/);
});

test("C3 · /buscar: el parámetro abierto=1 se lee, se escribe en la URL y hay chip «Abiertos» junto a «Cerca de mí»", () => {
  const b = leer("components/buscar-client.tsx");
  // Una sola fuente de verdad: la URL sólo PRENDE el filtro (y el interruptor de la sesión); el chip y el encabezado lo apagan.
  assert.match(b, /if \(g\("abierto"\) === "1"\) setAbiertos\(true\)/);
  assert.match(b, /const abiertos = conInterruptores \? rapidos\.abiertos : abiertosLocal;/);
  assert.match(b, /if \(abiertos\) p\.set\("abierto", "1"\)/);
  assert.match(b, /soloAbiertos\(/);
  assert.ok(b.indexOf("uk-chip-abiertos") > -1 && b.indexOf("uk-chip-abiertos") < b.indexOf("uk-chip-cerca"), "chip Abiertos antes que Cerca");
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 1: orden del home sin Bermejo, y Bermejo intacto (guardas estáticas sobre app/page.tsx y el marco)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

function partesDelHome(): { nuevo: string; bermejo: string } {
  const txt = leer("app/page.tsx");
  const ini = txt.indexOf("if (!conGuia && ciudad && datosCiudad) {");
  assert.ok(ini > 0, "existe el bloque del home de las ciudades");
  const finRel = txt.slice(ini).search(/\n {2}\}\n\n {2}return \(\n {4}<UrukuShell/);
  assert.ok(finRel > 0, "el bloque nuevo termina antes del return de Bermejo");
  return { nuevo: txt.slice(ini, ini + finRel), bermejo: txt.slice(ini + finRel) };
}

test("C1 · la regla del home y la del encabezado es la misma: slug !== «bermejo»", () => {
  assert.match(leer("app/page.tsx"), /const conGuia = \(ciudad\?\.slug \?\? "bermejo"\) === "bermejo";/);
  assert.match(leer("components/uruku-shell.tsx"), /const esBermejo = \(ciudad\?\.slug \?\? "bermejo"\) === "bermejo";/);
});

test("C1 · el home de las ciudades sigue el orden de §2 (intenciones, nuevos, productos/qué hacer, comercios, ofertas, vencen, destacados, novedades, videos, contacto, ciudades)", () => {
  const { nuevo } = partesDelHome();
  const orden = ["<IntencionesCiudad", "uk-home-nuevos", "bloqueProductos}", "<CarruselComercios", "{seccionOfertas}", "{seccionVencen}",
    "{seccionDestacados}", "{seccionNovedades}", "<VideosUruku", "<ContactoUruku", "{seccionCiudades}"];
  let pos = -1;
  for (const marca of orden) {
    const i = nuevo.indexOf(marca, pos + 1);
    assert.ok(i > pos, `«${marca}» fuera de orden`);
    pos = i;
  }
  // A la noche, «Qué podés hacer» pasa arriba de los productos; el resto del día, abajo.
  assert.match(nuevo, /franja === "noche" \? <>\{bloqueQueHacer\}\{bloqueProductos\}<\/> : <>\{bloqueProductos\}\{bloqueQueHacer\}<\/>/);
});

test("C1/C2 · lo que sale del home de las ciudades no está en el bloque nuevo (hero, «Hoy en», visita, turno, servicios, herramientas, accesos, aviso sin ofertas)", () => {
  const { nuevo } = partesDelHome();
  for (const fuera of ["AccesosCiudad", "TarjetaTurnoHoy", "VisitaCiudad", "Servicios útiles", "Herramientas útiles", "en un solo lugar", "Hoy en",
    "Todavía no hay ofertas", "UnirmeComunidad", "uk-home-hero"]) {
    assert.ok(!nuevo.includes(fuera), `«${fuera}» no debería estar en el home de las ciudades`);
  }
});

test("C1 · Bermejo conserva su home: no usa ninguno de los componentes nuevos y mantiene los suyos", () => {
  const { bermejo } = partesDelHome();
  for (const nuevoC of ["IntencionesCiudad", "CarruselProductos", "CarruselComercios", "<QueHacer", "bloqueProductos", "tilesQueHacer", "datosCiudad"]) {
    assert.ok(!bermejo.includes(nuevoC), `Bermejo no debe usar ${nuevoC}`);
  }
  for (const suyo of ["<AccesosCiudad", "Todavía no hay ofertas", "{seccionOfertas}", "{seccionNovedades}", "{seccionCiudades}", "<VideosUruku", "<ContactoUruku"]) {
    assert.ok(bermejo.includes(suyo), `Bermejo conserva ${suyo}`);
  }
});

test("C1 · Bermejo conserva el encabezado, la barra de abajo y el botón flotante (todo lo nuevo cuelga de !esBermejo)", () => {
  const shell = leer("components/uruku-shell.tsx");
  assert.match(shell, /<header className=\{`uk-header\$\{esBermejo \? "" : " uk-header-ciudad"\}`\}>/);
  assert.match(shell, /const hayTira = esBermejo && /);
  // El clima se pide EN PARALELO con el resto (no en serie), y sólo si la ciudad no es Bermejo.
  assert.match(shell, /c && c\.slug !== "bermejo" \? getClimaCiudad\(c\.id\) : null/);
  assert.match(shell, /rubrosNav, climaCiudad\] = await Promise\.all\(/);
  assert.match(shell, /\{!esBermejo && \(\s*<div className="uk-head-fila2">/);
  assert.match(shell, /\{!esBermejo && climaCiudad && \(/);
  assert.match(shell, /conDax=\{!esBermejo && asistente !== false\}/);
  assert.match(shell, /flotanteMovil=\{esBermejo\}/);
  // La barra de Bermejo (Inicio, Mapa, Ofertas, Guía, Cambio) no cambió.
  const nav = leer("components/bottom-nav.tsx");
  for (const k of ['key: "Inicio"', 'key: "Mapa"', 'key: "Ofertas"', 'key: "Guía"', 'key: "Cambio"']) assert.ok(nav.includes(k), k);
  assert.match(nav, /export function BottomNav\(\{ active = "Mapa", conGuia = true, conDax = false, conLocal = false \}/, "conDax apagado por defecto");
});

test("C1 · la barra de abajo sin Bermejo es Inicio · Mapa · Dax · Novedades · Guardados, con Dax al centro", () => {
  const nav = leer("components/bottom-nav.tsx");
  const bloque = nav.slice(nav.indexOf("const ITEMS_CON_DAX"), nav.indexOf("export function BottomNav"));
  const orden = ["ITEMS[0]", "ITEMS[1]", "null", '"Novedades"', '"Guardados"'];
  let pos = -1;
  for (const m of orden) { const i = bloque.indexOf(m, pos + 1); assert.ok(i > pos, m); pos = i; }
  assert.match(nav, /new CustomEvent\("uk-abrir-ayuda"\)/);
});

test("C1 · sin emojis en los componentes y módulos nuevos (todo ícono sale de components/ic.tsx)", () => {
  const archivos = [
    ...readdirSync(resolve(RAIZ, "components/home-ciudad")).map((f) => `components/home-ciudad/${f}`),
    "lib/home-productos-pure.ts", "lib/filtros-rapidos.ts", "lib/clima-ciudad-pure.ts", "components/asistente.tsx", "components/bottom-nav.tsx",
  ];
  for (const a of archivos) assert.doesNotMatch(leer(a), /\p{Extended_Pictographic}/u, a);
  // lib/home-ciudad-pure.ts trae «👟 Calzado» sólo en un comentario de ejemplo: ningún literal de texto lleva emoji.
  const sinComentarios = leer("lib/home-ciudad-pure.ts").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
  assert.doesNotMatch(sinComentarios, /\p{Extended_Pictographic}/u);
});

test("C1 · nunca select(\"*\") sobre comercios en el código nuevo de lecturas (regla crítica 11)", () => {
  const data = leer("lib/data.ts");
  const nuevo = data.slice(data.indexOf("// ── El home de las ciudades"));
  assert.doesNotMatch(nuevo, /from\("comercios"\)\.select\("\*"\)/);
  assert.doesNotMatch(nuevo, /select\("\*"\)/);
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 5: panel de Dax en el celular (lo que se puede ver sin navegador: guardas estáticas)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

test("C5 · el panel de Dax: hoja desde abajo con «× Cerrar», velo, rayita, Escape y «atrás»; el flotante se esconde al abrir (estático; la prueba real es con navegador)", () => {
  const a = leer("components/asistente.tsx");
  assert.match(a, /\{!abierto && \(\s*<button type="button" className=\{`uk-ayuda-btn/, "el botón flotante no se dibuja con el panel abierto");
  assert.match(a, /className="uk-hoja-velo uk-ayuda-velo" onClick=\{\(\) => cerrar\(\)\}/, "tocar el velo cierra");
  assert.match(a, /className="uk-hoja-tirador"[^>]*onClick=\{\(\) => cerrar\(\)\}/, "tocar la rayita cierra");
  assert.match(a, /className="uk-hoja-cerrar" onClick=\{\(\) => cerrar\(\)\}><Ic n="cerrar" s=\{15\} \/> Cerrar<\/button>/, "botón con la palabra «Cerrar»");
  assert.doesNotMatch(a, /aria-label=\{abierto \? "Cerrar la ayuda"/, "la «×» del botón flotante ya no existe");
  assert.match(a, /window\.dispatchEvent|addEventListener\("uk-abrir-ayuda"/, "el evento uk-abrir-ayuda se sigue usando");
  assert.match(a, /visualViewport/, "el teclado no tapa el campo");
  const hoja = leer("components/home-ciudad/use-hoja.ts");
  assert.match(leer("lib/control-hoja.ts"), /pushState\(\{ ukHoja: true \}, ""\)/);
  assert.match(hoja, /addEventListener\("popstate", alAtras\)/);
  assert.match(hoja, /e\.key === "Escape"/);
  const css = leer("app/styles/home-ciudad.css");
  assert.match(css, /@media \(max-width: 899px\) \{\s*\.uk-ayuda\.uk-hoja \{[^}]*bottom: var\(--uk-teclado, 0px\);[^}]*height: 64vh/, "64 % del alto en el celular");
  assert.match(css, /\.uk-ayuda-btn-compu \{ display: none; \}/, "sin Bermejo, en el celular no hay botón flotante");
});

test("C5 · el botón flotante no queda marcado como abierto ni se dibuja a la vez que el panel (un solo render condicional por estado)", () => {
  const a = leer("components/asistente.tsx");
  // Hay exactamente un <button ... uk-ayuda-btn ...> y está bajo !abierto.
  assert.equal((a.match(/<button[^>]*uk-ayuda-btn/g) ?? []).length, 1);
  assert.ok(a.indexOf("{!abierto && (") < a.indexOf("uk-ayuda-btn") && a.indexOf("uk-ayuda-btn") < a.indexOf("{abierto && ("));
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 6: Dax en Tarija (frontend)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

const PROHIBIDO = /paso|aduana|peso|frontera|d[oó]lar|cambio|cruz|chalana/i;

test("C6 · sugerencias y bienvenida de Dax sin guía: nunca paso, aduana ni pesos, con cualquier conjunto de rubros y a cualquier hora", () => {
  for (const f of FRANJAS) {
    for (const rubros of [...subconjuntos(150, 5), null]) {
      const s = sugerenciasDeFranja(f, rubros);
      assert.ok(s.length >= 2 && s.length <= 3, `${f}: ${s.length} sugerencias`);
      assert.equal(new Set(s).size, s.length);
      for (const t of s) assert.doesNotMatch(t, PROHIBIDO, t);
    }
    assert.doesNotMatch(bienvenidaDax(f, "Tarija", false), PROHIBIDO, f);
  }
});

test("C6 · una sugerencia sale sólo si la ciudad tiene el rubro (los completadores genéricos valen en cualquier ciudad)", () => {
  const GENERICAS = ["¿Qué hay abierto ahora?", "¿Cómo publico mi negocio?"];
  const EXIGE: Record<string, string[]> = {
    "¿Dónde desayuno?": ["cafeteria", "panaderia"], "Farmacia abierta cerca": ["farmacia"], "¿Qué visito hoy?": ["para-visitar"],
    "¿Dónde almuerzo?": ["restaurantes", "comida-rapida"], "Busco zapatillas": ["calzado", "zapatillas"], "Cajero cerca": ["cajeros"],
    "Necesito un servicio técnico": ["servicio-tecnico"], "¿Qué hago hoy?": ["para-visitar"], "Boliches abiertos esta noche": ["nocturna"],
    "¿Dónde ceno?": ["restaurantes", "comida-rapida"], "Hotel para esta noche": ["hospedaje"], "Farmacia de turno": ["farmacia"], "¿Dónde duermo?": ["hospedaje"],
  };
  for (const f of FRANJAS) {
    for (const rubros of subconjuntos(200, 21)) {
      for (const t of sugerenciasDeFranja(f, rubros)) {
        if (GENERICAS.includes(t)) continue;
        assert.ok(EXIGE[t], `sugerencia desconocida «${t}»`);
        assert.ok(EXIGE[t].some((r) => rubros.has(r)), `«${t}» en ${f} sin ninguno de ${EXIGE[t]} en la ciudad`);
      }
    }
  }
});

test("C6 · el saludo cambia con la franja de Bolivia en los bordes (Buen día 6:00-10:59; Hola 11:00-18:59; Buenas noches 19:00-5:59)", () => {
  const saludo = (h: number, m: number) => bienvenidaDax(franjaAhora(bo(h, m)), "Tarija", false).split(" Soy Dax")[0];
  assert.equal(saludo(5, 59), "¡Buenas noches!");
  assert.equal(saludo(6, 0), "¡Buen día!");
  assert.equal(saludo(10, 59), "¡Buen día!");
  assert.equal(saludo(11, 0), "¡Hola!");
  assert.equal(saludo(18, 59), "¡Hola!");
  assert.equal(saludo(19, 0), "¡Buenas noches!");
  assert.equal(saludo(0, 0), "¡Buenas noches!");
  assert.match(bienvenidaDax("manana", "Tarija", false), /Soy Dax y conozco Tarija\./);
});

test("C6 · el panel usa las sugerencias por franja sólo sin guía; con guía (Bermejo y fronteras con guía) siguen las de frontera", () => {
  const a = leer("components/asistente.tsx");
  assert.match(a, /sugerencias: conGuia \? SUGERENCIAS : sugerenciasDeFranja\(franja, rubros \? new Set\(rubros\) : null\)/);
  assert.match(a, /bienvenidaDax\(franja, nombreCiudad, conGuia\)/);
  assert.match(leer("components/uruku-shell.tsx"), /rubros=\{rubrosAsistente\}/);
  // Cambio de ciudad con el panel abierto.
  assert.match(a, /Ahora te ayudo con \$\{ciudad\.nombre\}\./);
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 7: clima de la ciudad
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

const AHORA = new Date("2026-11-20T15:00:00Z");
const hace = (min: number, ms = 0) => new Date(AHORA.getTime() - min * 60_000 - ms).toISOString();

test("C7 · clima: 3 h justas se muestra; 3 h y 1 ms ya no; formatos de fecha de PostgREST (microsegundos, +00, offset) se entienden", () => {
  assert.notEqual(climaVigente({ temp_c: 20, actualizado_en: new Date(AHORA.getTime() - VIGENCIA_CLIMA_MS).toISOString() }, AHORA), null);
  assert.equal(climaVigente({ temp_c: 20, actualizado_en: new Date(AHORA.getTime() - VIGENCIA_CLIMA_MS - 1).toISOString() }, AHORA), null);
  assert.equal(climaVigente({ temp_c: 20, actualizado_en: hace(60 * 24) }, AHORA), null, "de ayer");
  for (const f of ["2026-11-20T14:00:00.123456+00:00", "2026-11-20 14:00:00.5+00", "2026-11-20T10:00:00-04:00", "2026-11-20T14:00:00Z"]) {
    assert.deepEqual(climaVigente({ temp_c: "19.5", descripcion: "Despejado", actualizado_en: f }, AHORA), { temp_c: 19.5, descripcion: "Despejado" }, f);
  }
  // Un offset que lo hace viejo: 08:00-04:00 = 12:00Z → 3 h justas; 07:59-04:00 → viejo.
  assert.equal(climaVigente({ temp_c: 20, actualizado_en: "2026-11-20T07:59:00-04:00" }, AHORA), null);
});

test("C7 · clima: sin fila, sin temperatura, con temperatura rara o sin fecha válida no se muestra nada (y nunca tira)", () => {
  for (const f of [null, undefined, {}, { temp_c: null }, { temp_c: NaN, actualizado_en: hace(1) }, { temp_c: Infinity, actualizado_en: hace(1) },
    { temp_c: true, actualizado_en: hace(1) }, { temp_c: [], actualizado_en: hace(1) }, { temp_c: "abc", actualizado_en: hace(1) },
    { temp_c: 20 }, { temp_c: 20, actualizado_en: null }, { temp_c: 20, actualizado_en: 12345 }, { temp_c: 20, actualizado_en: "" },
    { temp_c: 20, actualizado_en: "2026-11-20T14:00:00" /* sin huso: no se adivina */ }]) {
    assert.equal(climaVigente(f as never, AHORA), null, JSON.stringify(f));
  }
});

test("C7 · temperaturas negativas y cero son datos válidos (0° no es «sin dato»)", () => {
  assert.deepEqual(climaVigente({ temp_c: -3.5, descripcion: "Helada", actualizado_en: hace(1) }, AHORA), { temp_c: -3.5, descripcion: "Helada" });
  assert.deepEqual(climaVigente({ temp_c: 0, descripcion: null, actualizado_en: hace(1) }, AHORA), { temp_c: 0, descripcion: null });
});

// BUG (bajo, endurecimiento): un texto vacío o de espacios en `temp_c` se lee como 0°C porque Number("") === 0.
// PostgREST nunca manda "" para un numeric, así que hoy no se dispara; pero «0°» inventado es peor que nada.
test("C7 · temp_c vacío o en blanco NO es 0 °C", () => {
  assert.equal(climaVigente({ temp_c: "", descripcion: "x", actualizado_en: hace(1) }, AHORA), null);
  assert.equal(climaVigente({ temp_c: "   ", descripcion: "x", actualizado_en: hace(1) }, AHORA), null);
});

test("C7 · el encabezado dibuja el clima sólo si hay dato vigente y sólo sin Bermejo (guarda estática)", () => {
  const shell = leer("components/uruku-shell.tsx");
  assert.match(shell, /\{!esBermejo && climaCiudad && \(/);
  assert.match(shell, /climaIcono\(climaCiudad\.descripcion\)/);
  const data = leer("lib/data.ts");
  const fn = data.slice(data.indexOf("export async function getClimaCiudad"), data.indexOf("export async function getRedes"));
  assert.match(fn, /climaVigente\(/);
  assert.match(fn, /from\("clima_ciudades"\)/);
  assert.match(fn, /catch \{\s*return null;/, "si la tabla no existe todavía, null");
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 8: admin, selector de ciudad del saber local
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

test("C8 · el selector de ciudad de «Saber local» lista TODAS las ciudades activas, no sólo las de frontera", () => {
  const p = leer("components/asistente-panel.tsx");
  const fn = p.slice(p.indexOf("function SelectCiudad"), p.indexOf("function SelectCiudad") + 900);
  assert.match(fn, /cs\.filter\(\(c\) => c\.activa\)/);
  assert.doesNotMatch(fn, /es_frontera/);
  assert.match(fn, /Todas las ciudades/);
  assert.doesNotMatch(fn, /Todas las fronteras/);
  // Los dos lugares donde se usa (Dax y Respuestas de los locales) comparten ese componente.
  assert.equal((p.match(/<SelectCiudad /g) ?? []).length, 2);
});

// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════
// Criterio 9: calidad (las guardas de que los tests nuevos existen para la lógica pura)
// ═══════════════════════════════════════════════════════════════════════════════════════════════════════════

test("C9 · hay tests para la lógica pura nueva: franjas, orden, filtros, sugerencias, tarjetas y clima", () => {
  const archivos = readdirSync(resolve(RAIZ, "tests"));
  for (const t of ["home-ciudad.test.ts", "home-productos.test.ts", "filtros-rapidos.test.ts", "clima-ciudad.test.ts", "buscar-filtros.test.ts"]) {
    assert.ok(archivos.includes(t), t);
  }
  assert.ok(SIN_FILTROS.abiertos === false && SIN_FILTROS.cerca === false);
  assert.ok(join("a", "b").length > 0);
});
