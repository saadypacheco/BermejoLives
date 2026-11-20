// Correcciones de la revisión del home de las ciudades: historial de los paneles, enlaces propios de Dax, memoria de las
// lecturas, productos frecuentes, botones sin saber los rubros, turnos cargados, horario «24 horas» y consulta de «Ver comercios».
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { ControlHoja, type HistorialLike } from "../lib/control-hoja";
import { esFotoSegura, esUrlWeb, rutaPropia } from "../lib/enlace-propio";
import { crearMemoPorClave } from "../lib/memo-por-clave";
import {
  MAX_CARACTERES_CONSULTA, MAX_PALABRAS_CONSULTA, RUBROS_DE_FRANJAS, candidatosCarrusel, consultaDeBusqueda, hayTurnosCargados,
  intencionesDeCiudad, type ComercioDeLaCiudad, type DatosIntenciones, type RubroCatalogo,
} from "../lib/home-ciudad-pure";
import { productosFrecuentes, tarjetasDeLocales } from "../lib/home-productos-pure";
import { climaVigente } from "../lib/clima-ciudad-pure";
import { abiertoAhora } from "../lib/horario";

const leer = (ruta: string): string => readFileSync(resolve(process.cwd(), ruta), "utf8").split("\r\n").join("\n");

// ── 1. Historial de los paneles ─────────────────────────────────────────────────────────────────

function historialFalso() {
  const h = { pushes: 0, backs: 0, pushState(_e: unknown, _t: string) { this.pushes += 1; }, back() { this.backs += 1; } };
  return h as HistorialLike & { pushes: number; backs: number };
}

test("ControlHoja (celular): abrir empuja UNA entrada; cerrar hace UN back y el cierre real llega con el popstate", () => {
  const h = historialFalso();
  let cierres = 0;
  const c = new ControlHoja(h, () => { cierres += 1; });
  c.abrir(true);
  assert.equal(h.pushes, 1);
  c.cerrar();
  assert.equal(h.backs, 1);
  assert.equal(cierres, 0, "todavía no: espera al popstate");
  c.alAtras();
  assert.equal(cierres, 1);
  assert.equal(c.conEntrada, false);
});

test("ControlHoja: un doble cierre (Escape sostenido, doble toque en el velo) nunca hace dos back()", () => {
  const h = historialFalso();
  let cierres = 0;
  const c = new ControlHoja(h, () => { cierres += 1; });
  c.abrir(true);
  c.cerrar(); c.cerrar(); c.cerrar();
  assert.equal(h.backs, 1);
  c.alAtras();
  assert.equal(cierres, 1);
});

test("ControlHoja (compu, panel no modal): no toca el historial y cierra en el acto", () => {
  const h = historialFalso();
  let cierres = 0;
  const c = new ControlHoja(h, () => { cierres += 1; });
  c.abrir(false);
  assert.equal(h.pushes, 0);
  c.cerrar();
  assert.equal(h.backs, 0);
  assert.equal(cierres, 1);
});

test("ControlHoja: cerrar(despues) navega DESPUÉS de bajar el panel y de sacar la entrada (sin «atrás» fantasma)", () => {
  const h = historialFalso();
  const orden: string[] = [];
  const c = new ControlHoja(h, () => orden.push("cierra"));
  c.abrir(true);
  c.cerrar(() => orden.push("navega"));
  assert.deepEqual(orden, [], "todavía espera el popstate");
  c.alAtras();
  assert.deepEqual(orden, ["cierra", "navega"]);
  assert.equal(h.backs, 1);
});

test("ControlHoja: el «atrás» del teléfono cierra sin un back() propio; y se puede volver a abrir", () => {
  const h = historialFalso();
  let cierres = 0;
  const c = new ControlHoja(h, () => { cierres += 1; });
  c.abrir(true);
  c.alAtras();
  assert.equal(cierres, 1);
  assert.equal(h.backs, 0);
  c.abrir(true);
  assert.equal(h.pushes, 2);
  c.cerrar();
  assert.equal(h.backs, 1);
});

test("ControlHoja: si pushState falla, se cierra sin historial (sin quedar esperando un popstate que no llega)", () => {
  const h: HistorialLike = { pushState() { throw new Error("no"); }, back() { throw new Error("no debería llamarse"); } };
  let cierres = 0;
  const c = new ControlHoja(h, () => { cierres += 1; });
  c.abrir(true);
  c.cerrar();
  assert.equal(cierres, 1);
});

test("el panel de Dax: sólo el modal (celular) toca el historial y declara aria-modal; los enlaces internos cierran primero (guardas estáticas)", () => {
  const a = leer("components/asistente.tsx");
  assert.match(a, /const MEDIA_CELULAR = "\(max-width: 899px\)"/);
  assert.match(a, /useHoja\(abierto, \(\) => setAbierto\(false\), \(\) => window\.matchMedia\(MEDIA_CELULAR\)\.matches\)/);
  assert.match(a, /aria-modal=\{modal \? "true" : undefined\}/);
  assert.match(a, /cerrar\(\(\) => router\.push\(ruta\)\)/);
  assert.match(a, /e\.metaKey \|\| e\.ctrlKey \|\| e\.shiftKey/);
  // Todos los enlaces del panel pasan por navegar (fuentes, «Ver comercios ›», direcciones del texto).
  assert.match(a, /onClick=\{ruta \? \(e\) => navegar\(e, ruta\) : undefined\}/);
  assert.match(a, /onClick=\{\(e\) => navegar\(e, ver\)\}/);
  assert.match(a, /linkear\(m\.texto, navegar\)/);
  // Una sola frontera de 900 px para todo: la barra de abajo se esconde desde 900 y el flotante sólo se esconde por debajo.
  assert.match(leer("app/styles/home-ciudad.css"), /@media \(max-width: 899px\) \{\s*\.uk-ayuda\.uk-hoja/);
  assert.match(leer("app/styles/home-ciudad.css"), /@media \(min-width: 900px\) \{\s*\.uk-ayuda\.uk-hoja/);
  assert.match(leer("app/globals.css"), /@media \(min-width: 900px\) \{ \.bottomnav \{ display: none; \} \}/);
});

// ── 13. Seguridad de los enlaces de Dax ─────────────────────────────────────────────────────────

test("rutaPropia: sólo es propia https://uruku.bo y su ruta; lo demás no", () => {
  assert.equal(rutaPropia("https://uruku.bo"), "/");
  assert.equal(rutaPropia("https://uruku.bo/"), "/");
  assert.equal(rutaPropia("https://uruku.bo/comercios/x?a=1#y"), "/comercios/x?a=1#y");
  assert.equal(rutaPropia("/buscar?q=zapatillas"), "/buscar?q=zapatillas");
});

test("rutaPropia: //otro-sitio y /\\otro-sitio (que el navegador toma por otro sitio) NO son propias", () => {
  for (const url of [
    "https://uruku.bo//evil.com", "https://uruku.bo/\\evil.com", "https://uruku.bo/\t/evil.com", "//evil.com", "/\\evil.com",
    "https://uruku.bo.evil.com/x", "https://uruku.boevil.com", "http://uruku.bo/x", "https://evil.com/https://uruku.bo/", "javascript:alert(1)", "",
  ]) {
    assert.equal(rutaPropia(url), null, url);
  }
  assert.equal(rutaPropia(null), null);
  assert.equal(rutaPropia(undefined), null);
});

test("esUrlWeb y esFotoSegura: sólo http(s) o una ruta del sitio", () => {
  assert.ok(esUrlWeb("https://wa.me/59170000000"));
  assert.ok(!esUrlWeb("javascript:alert(1)"));
  assert.ok(!esUrlWeb("data:text/html,x"));
  assert.ok(esFotoSegura("https://x/f.jpg") && esFotoSegura("/fotos/a.jpg"));
  assert.ok(!esFotoSegura("//evil.com/a.jpg") && !esFotoSegura("data:image/png;base64,AAAA") && !esFotoSegura("javascript:alert(1)") && !esFotoSegura("/\\evil"));
  assert.ok(!esFotoSegura(null));
});

test("los enlaces externos del panel de Dax llevan noopener noreferrer", () => {
  const a = leer("components/asistente.tsx");
  assert.doesNotMatch(a, /rel=\{[^}]*"noopener"\}/, "ningún rel sin noreferrer");
  assert.ok((a.match(/noopener noreferrer/g) ?? []).length >= 2);
  assert.doesNotMatch(a, /replace\("https:\/\/uruku\.bo", ""\)/, "ya no se le saca el origen a cualquier cosa que empiece así");
});

// ── 15. «Ver comercios ›» ───────────────────────────────────────────────────────────────────────

test("consultaDeBusqueda: hasta 4 palabras y 60 caracteres, aunque la pregunta tenga 500", () => {
  assert.equal(MAX_PALABRAS_CONSULTA, 4);
  assert.equal(MAX_CARACTERES_CONSULTA, 60);
  const larga = "zapatillas deportivas negras livianas baratas para correr en la montaña con mucho amortiguador";
  assert.equal(consultaDeBusqueda(larga), "zapatillas deportivas negras livianas");
  const enorme = Array.from({ length: 80 }, (_, i) => `palabra${i}`).join(" ").slice(0, 500);
  const q = consultaDeBusqueda(enorme);
  assert.ok(q.length <= 60);
  assert.ok(q.split(" ").length <= 4);
  const palabrotas = `${"a".repeat(30)} ${"b".repeat(30)} ${"c".repeat(30)}`;
  assert.equal(consultaDeBusqueda(palabrotas), "a".repeat(30), "corta en límite de palabra");
  assert.equal(consultaDeBusqueda("¿Dónde hay una farmacia?"), "farmacia");
});

// ── 2-4. Memoria de las lecturas ────────────────────────────────────────────────────────────────

test("memoria: dos pedidos simultáneos de la misma clave comparten UNA lectura", async () => {
  const memo = crearMemoPorClave<number>({ ttlMs: 1000 });
  let lecturas = 0;
  let soltar: (n: number) => void = () => {};
  const leer1 = () => { lecturas += 1; return new Promise<number>((r) => { soltar = r; }); };
  const a = memo("tarija", leer1);
  const b = memo("tarija", leer1);
  soltar(7);
  assert.deepEqual(await Promise.all([a, b]), [7, 7]);
  assert.equal(lecturas, 1);
});

test("memoria: recuerda hasta el vencimiento y después vuelve a leer", async () => {
  let ahora = 1000;
  const memo = crearMemoPorClave<number>({ ttlMs: 500, reloj: () => ahora });
  let n = 0;
  const leerN = async () => ++n;
  assert.equal(await memo("k", leerN), 1);
  ahora += 499;
  assert.equal(await memo("k", leerN), 1);
  ahora += 2;
  assert.equal(await memo("k", leerN), 2);
});

test("memoria: una lectura que falla no se recuerda, y la siguiente reintenta", async () => {
  const memo = crearMemoPorClave<number>({ ttlMs: 1000 });
  await assert.rejects(memo("k", async () => { throw new Error("base caída"); }));
  assert.equal(await memo("k", async () => 5), 5);
});

test("memoria: un valor incompleto (catálogo vacío, sin comercios) NO se recuerda (o se recuerda poco) para que no se cachee un fallo", async () => {
  let ahora = 0;
  const memo = crearMemoPorClave<{ comercios: number; catalogo: number }>({
    ttlMs: 5 * 60_000, esCacheable: (d) => d.comercios > 0 && d.catalogo > 0, ttlIncompletoMs: 0, reloj: () => ahora,
  });
  let lecturas = 0;
  assert.deepEqual(await memo("tarija", async () => { lecturas += 1; return { comercios: 40, catalogo: 0 }; }), { comercios: 40, catalogo: 0 });
  assert.deepEqual(await memo("tarija", async () => { lecturas += 1; return { comercios: 40, catalogo: 30 }; }), { comercios: 40, catalogo: 30 });
  assert.equal(lecturas, 2, "el catálogo vacío no quedó guardado 5 minutos");
  ahora += 60_000;
  await memo("tarija", async () => { lecturas += 1; return { comercios: 0, catalogo: 0 }; });
  assert.equal(lecturas, 2, "el completo sigue vigente");
});

test("memoria: un incompleto puede recordarse un rato corto (ttlIncompletoMs)", async () => {
  let ahora = 0;
  const memo = crearMemoPorClave<number | null>({ ttlMs: 300_000, esCacheable: (v) => v !== null, ttlIncompletoMs: 60_000, reloj: () => ahora });
  let n = 0;
  const sinDato = async () => { n += 1; return null; };
  await memo("c", sinDato); await memo("c", sinDato);
  assert.equal(n, 1);
  ahora += 60_001;
  await memo("c", sinDato);
  assert.equal(n, 2);
});

test("memoria: no crece sin límite (tope de claves) y tira las vencidas", async () => {
  let ahora = 0;
  const memo = crearMemoPorClave<number>({ ttlMs: 100, maxClaves: 3, reloj: () => ahora });
  let lecturas = 0;
  const l = async () => { lecturas += 1; return lecturas; };
  for (const k of ["a", "b", "c", "d"]) await memo(k, l);
  assert.equal(lecturas, 4);
  await memo("a", l); // «a» fue la más vieja: se tiró al entrar «d»
  assert.equal(lecturas, 5);
  await memo("d", l); // «d» sigue
  assert.equal(lecturas, 5);
});

test("la memoria de las ciudades se arma por slug (no por el conjunto de rubros) con la memoria compartida (guardas estáticas de data.ts)", () => {
  const data = leer("lib/data.ts");
  const bloque = data.slice(data.indexOf("// ── El home de las ciudades"));
  assert.match(bloque, /memoHomeCiudad\(ciudad\.slug,/, "la clave es sólo el slug");
  assert.match(bloque, /esCacheable: \(d\) => d\.comercios\.length > 0 && d\.catalogo\.length > 0 && d\.completo/);
  assert.match(bloque, /RUBROS_DE_FRANJAS\.map\(\(r\) => pedir\(r\)\)/, "los candidatos de la franja se piden POR RUBRO");
  assert.match(data, /memoClimaCiudad\(ciudadId,/, "el clima del marco tiene su memoria");
  assert.doesNotMatch(bloque, /const memoHomeCiudad = new Map/);
});

// ── 2. Candidatos por rubro de la franja ────────────────────────────────────────────────────────

const com = (id: string, rubro: string, extra: Partial<ComercioDeLaCiudad> = {}): ComercioDeLaCiudad => ({
  id, slug: id, nombre: id, portada_thumb_url: `https://x/${id}.jpg`, portada_pos: null, rubro_slug: rubro, rubro_nombre: rubro,
  horario: null, lat: null, lng: null, prod_obs_human: null, prod_det_ia: null, ...extra,
});

test("candidatos: una ciudad grande cuya muestra de 500 no trae farmacias igual tiene las de la madrugada (se piden por rubro)", () => {
  const muestra = [com("ropa1", "ropa"), com("ropa2", "ropa")];
  const sinPorRubro = candidatosCarrusel(muestra, "madrugada", "Santa Cruz", new Set(["ropa", "farmacia"]));
  assert.equal(sinPorRubro.titulo, "Comercios de Santa Cruz", "sólo con la muestra: el título de respaldo (el problema)");
  const conPorRubro = candidatosCarrusel(muestra, "madrugada", "Santa Cruz", new Set(["ropa", "farmacia"]), { farmacia: [com("f1", "farmacia"), com("f2", "farmacia")] });
  assert.equal(conPorRubro.titulo, "Abiertas ahora");
  assert.deepEqual(conPorRubro.items.map((i) => i.id), ["f1", "f2"]);
  assert.equal(conPorRubro.verTodos, "/buscar?rubro=farmacia&vista=mapa");
});

test("candidatos: sin duplicar si el comercio está en la muestra y en la lista por rubro; sin foto no entra", () => {
  const r = candidatosCarrusel([com("c1", "cafeteria")], "manana", "Tarija", new Set(["cafeteria"]), {
    cafeteria: [com("c1", "cafeteria"), com("c2", "cafeteria", { portada_thumb_url: null })], panaderia: [com("p1", "panaderia")],
  });
  assert.deepEqual(r.items.map((i) => i.id), ["c1", "p1"]);
});

test("los rubros que se piden por separado cubren todas las franjas con rubros fijos", () => {
  for (const r of ["cafeteria", "panaderia", "restaurantes", "comida-rapida", "nocturna", "farmacia"]) assert.ok(RUBROS_DE_FRANJAS.includes(r), r);
});

// ── 9. Turnos cargados ──────────────────────────────────────────────────────────────────────────

const CATALOGO: RubroCatalogo[] = [{ slug: "farmacia", nombre: "Farmacias" }, { slug: "cajeros", nombre: "Cajeros", comercial: false }];
const datos = (extra: Partial<DatosIntenciones>): DatosIntenciones => ({
  franja: "madrugada", ciudadSlug: "tarija", rubros: new Set(["farmacia", "cajeros"]), catalogo: CATALOGO, hayTurnos: true, productosFrecuentes: [], ...extra,
});

test("hayTurnosCargados: cualquier turno cargado (de hoy o de los próximos días) cuenta; sin turnos o sin lectura, no", () => {
  assert.equal(hayTurnosCargados([{ fecha: "2026-11-22" }]), true);
  assert.equal(hayTurnosCargados([]), false);
  assert.equal(hayTurnosCargados(null), false);
  assert.equal(hayTurnosCargados(undefined), false);
});

test("«De turno hoy» no depende de quién está de turno AHORA: el panel lo ofrece mientras haya turnos cargados (guardas estáticas)", () => {
  const f = intencionesDeCiudad(datos({ hayTurnos: true })).find((i) => i.id === "farmacias");
  assert.equal(f?.opciones[0].href, "/tarija/farmacias-de-turno");
  const page = leer("app/page.tsx");
  assert.match(page, /getCiudadTieneTurnos\(ciudad\.id\)/);
  assert.doesNotMatch(page, /hayTurnos: \(turnosHoy/);
  const data = leer("lib/data.ts");
  const fn = data.slice(data.indexOf("export async function getCiudadTieneTurnos"));
  assert.match(fn, /rangoTurnos\(ahora, 30\)/);
  assert.match(fn, /hayTurnosCargados\(turnos\)/);
});

// ── 14. Productos: texto del comerciante sin moderar ────────────────────────────────────────────

const loc = (n: number, obs: string | null, ia: string | null = null) => ({ prod_obs_human: obs, prod_det_ia: ia, id: `c${n}`, slug: `l${n}`, nombre: `L${n}`, portada_thumb_url: `https://x/${n}.jpg` });

test("productosFrecuentes: un término de UN solo comercio (texto editable sin moderar) no llega a la portada", () => {
  assert.deepEqual(productosFrecuentes([loc(1, "Compre bitcoin en mi local, Zapatillas"), loc(2, "Zapatillas")]), ["zapatillas"]);
});

test("productosFrecuentes: dos comercios distintos, o la IA, alcanzan; el mismo comercio repetido no cuenta dos veces", () => {
  assert.deepEqual(productosFrecuentes([loc(1, "Ropa, ropa, ROPA")]), []);
  assert.deepEqual(productosFrecuentes([loc(1, "Ropa"), loc(2, "Ropa")]), ["ropa"]);
  assert.deepEqual(productosFrecuentes([loc(1, null, "Celulares")]), ["celulares"]);
});

test("tarjetasDeLocales: los términos de la IA van primero en la tarjeta", () => {
  const t = tarjetasDeLocales([loc(1, "Visitá mi sitio, Botines", "Zapatillas, Sandalias")], () => 0.5);
  assert.equal(t[0].titulo, "Zapatillas, Sandalias, Visitá mi sitio");
});

// ── 16. Clima ───────────────────────────────────────────────────────────────────────────────────

test("clima: temp_c vacío o en blanco NO es 0 °C; el 0 de verdad sí", () => {
  const ahora = new Date("2026-11-20T15:00:00Z");
  const fecha = new Date(ahora.getTime() - 60_000).toISOString();
  assert.equal(climaVigente({ temp_c: "", actualizado_en: fecha }, ahora), null);
  assert.equal(climaVigente({ temp_c: "   ", actualizado_en: fecha }, ahora), null);
  assert.deepEqual(climaVigente({ temp_c: "0", actualizado_en: fecha }, ahora), { temp_c: 0, descripcion: null });
});

// ── 18. Botones sin saber los rubros ────────────────────────────────────────────────────────────

test("sin saber qué rubros tiene la ciudad (lectura caída), sólo salen Farmacias y Bancos y cajeros", () => {
  for (const franja of ["madrugada", "manana", "mediodia", "tarde", "noche"] as const) {
    const ids = intencionesDeCiudad(datos({ franja, rubros: null, productosFrecuentes: ["zapatillas"] })).map((i) => i.id);
    assert.deepEqual([...ids].sort(), ["bancos", "farmacias"], franja);
  }
});

test("sin saber los rubros, las opciones de Farmacias y Bancos no incluyen rubros nuevos que podrían estar vacíos", () => {
  for (const i of intencionesDeCiudad(datos({ rubros: null }))) {
    for (const o of i.opciones) assert.ok(["farmacia", "cajeros", "cambio", undefined].includes(o.rubro), String(o.rubro));
  }
});

// ── 19. Horario «24 horas» ──────────────────────────────────────────────────────────────────────

test("horario «24 horas», «24hs», «24 h»: abierto a cualquier hora", () => {
  for (const txt of ["24 horas", "24hs", "24 hs", "24 h", "Abierto 24 horas", "Lun a Dom 24 hs", "24 HORAS"]) {
    for (const hora of [0, 3, 12, 23]) {
      const e = abiertoAhora(txt, new Date(2026, 10, 18, hora, 30)); // un miércoles
      assert.equal(e.estado, "abierto", `${txt} a las ${hora}:30`);
    }
  }
});

test("«24 horas» con días: cerrado los días que no están", () => {
  assert.equal(abiertoAhora("Lun a Sáb 24 horas", new Date(2026, 10, 18, 3, 0)).estado, "abierto");
  assert.equal(abiertoAhora("Lun a Sáb 24 horas", new Date(2026, 10, 22, 3, 0)).estado, "cerrado"); // domingo
});

test("el «24» del final de un rango no se confunde con «24 horas»: «8 a 24 hs» sigue siendo de 8 a medianoche", () => {
  assert.equal(abiertoAhora("Lun a Vie 8 a 24 hs", new Date(2026, 10, 18, 3, 0)).estado, "cerrado");
  assert.equal(abiertoAhora("Lun a Vie 8 a 24 hs", new Date(2026, 10, 18, 9, 0)).estado, "abierto");
  assert.equal(abiertoAhora("8-24h", new Date(2026, 10, 18, 3, 0)).estado, "cerrado");
});

test("los horarios de siempre siguen igual", () => {
  assert.equal(abiertoAhora("Lun a Sáb 9-19", new Date(2026, 10, 18, 14, 0)).estado, "abierto");
  assert.equal(abiertoAhora("Lun a Sáb 9-19", new Date(2026, 10, 18, 20, 0)).estado, "cerrado");
  assert.equal(abiertoAhora("consultar", new Date(2026, 10, 18, 14, 0)).estado, "desconocido");
});

// ── 17. Ubicación vencida ───────────────────────────────────────────────────────────────────────

test("ubicacionGuardada borra lo vencido (guarda estática: no hay localStorage en Node)", () => {
  const u = leer("lib/ubicacion.ts");
  assert.match(u, /Date\.now\(\) - u\.en > VIGENCIA_MS\) \{[\s\S]*localStorage\.removeItem\(CLAVE\)/);
});
