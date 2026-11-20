// QA independiente de la parte 2 del home de ciudades (docs/home-ciudades.md §11 a §16), en el front.
// Complementa a planes-ciudad / home-ciudad-fotos / aprobar-lote / platos (de quien implementó) con otro ángulo:
// tablas del spec leídas literal, propiedades del orden de los carruseles, el reductor de «Aprobar en bloque» recorrido
// por TODAS las secuencias de eventos, contratos con el backend leídos del código y chequeos de fuente (sin navegador).
// `{ todo }` = bug encontrado por QA (BUG-n del reporte): el test describe lo que dice el spec, falla hoy y no corta la suite.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { Ilustracion, ILUSTRACIONES } from "../components/ilustraciones";
import { MENU } from "../components/admin/secciones";
import {
  LOTE_CERRADO, ofreceAprobarEnBloque, reducirLote, resultadoDeRespuesta, textoResultado, textoSimulacion,
  type EstadoLote, type EventoLote, type ResultadoLote,
} from "../lib/aprobar-lote-pure";
import {
  candidatosCarrusel, fotoDeTarjeta, ordenarCarrusel, prepararCarrusel, MAX_CARRUSEL, type ComercioCarrusel, type ComercioDeLaCiudad,
} from "../lib/home-ciudad-pure";
import { MAX_GRILLA_PLANES, nocheDe, planesDeCiudad, saboresDe, tituloSabores, type DatosPlanes, type PlanId } from "../lib/planes-ciudad-pure";
import {
  MAX_DESCRIPCION_PLATO, MAX_NOMBRE_PLATO, agruparPlatos, cambiosDeEdicion, hrefDondeComer, platoDeFila, puedeAprobarPlato, type PlatoTipico,
} from "../lib/platos-pure";
import { paramFuente, type FuenteFiltro } from "../lib/tarjetas-pure";

// `tests/` se compila a build/test/tests: la raíz del front queda tres carpetas más arriba.
const RAIZ = resolve(__dirname, "..", "..", "..");
const leer = (...ruta: string[]): string => readFileSync(resolve(RAIZ, ...ruta), "utf8");
const BACK = (...ruta: string[]): string => readFileSync(resolve(RAIZ, "..", "backend", ...ruta), "utf8");

// ═════════════════════════════════════════════════ §12 · PLANES POR DATOS

const datos = (extra: Partial<DatosPlanes> = {}): DatosPlanes => ({
  ciudadSlug: "tarija", ciudadNombre: "Tarija", rubros: new Set<string>(), subcategorias: [], hayPlatos: false, ...extra,
});
const todosLosPlanes = (d: DatosPlanes) => {
  const p = planesDeCiudad(d);
  return [...(p.grande ? [p.grande] : []), ...p.grilla];
};
const ids = (d: DatosPlanes): string[] => todosLosPlanes(d).map((p) => p.id);

/** La tabla del spec §12: plan, destino y con qué dato sale. */
const TABLA: { plan: PlanId; destino: (sub: string) => string; dato: Partial<DatosPlanes> }[] = [
  { plan: "vino", destino: () => "/buscar?rubro=bodegas&vista=mapa", dato: { rubros: new Set(["bodegas"]) } },
  { plan: "centro", destino: (s) => `/buscar?rubro=para-visitar&sub=${encodeURIComponent(s)}&vista=mapa`, dato: { rubros: new Set(["para-visitar"]), subcategorias: ["Plaza"] } },
  { plan: "miradores", destino: () => "/buscar?rubro=para-visitar&sub=Mirador&vista=mapa", dato: { rubros: new Set(["para-visitar"]), subcategorias: ["Mirador"] } },
  { plan: "parques", destino: () => "/buscar?rubro=para-visitar&sub=Parque&vista=mapa", dato: { rubros: new Set(["para-visitar"]), subcategorias: ["Parque"] } },
  { plan: "museos", destino: () => "/buscar?rubro=para-visitar&sub=Museo&vista=mapa", dato: { rubros: new Set(["para-visitar"]), subcategorias: ["Museo"] } },
  { plan: "cascadas", destino: () => `/buscar?rubro=para-visitar&sub=${encodeURIComponent("Excursión")}&vista=mapa`, dato: { rubros: new Set(["para-visitar"]), subcategorias: ["Excursión"] } },
  { plan: "lagunas", destino: () => `/buscar?rubro=para-visitar&sub=${encodeURIComponent("Área protegida")}&vista=mapa`, dato: { rubros: new Set(["para-visitar"]), subcategorias: ["Área protegida"] } },
  { plan: "noche", destino: () => "/buscar?rubro=nocturna&vista=mapa", dato: { rubros: new Set(["nocturna"]) } },
  { plan: "sabores", destino: () => "/tarija/sabores", dato: { hayPlatos: true } },
];

test("QA §12: cada plan sale con su dato y SOLO con su dato, y lleva al destino del spec", () => {
  for (const { plan, destino, dato } of TABLA) {
    const solo = todosLosPlanes(datos(dato));
    assert.deepEqual(solo.map((p) => p.id), [plan], `con su dato sale ${plan} y nada más`);
    const sub = String([...(dato.subcategorias ?? [])][0] ?? "Plaza");
    assert.equal(solo[0].href, destino(sub), plan);
    // y sin el dato, no sale
    assert.equal(ids(datos()).includes(plan), false, `${plan} sin datos`);
  }
});

test("QA §12: la ruta del vino sale en Tarija sólo con bodegas, y es la tarjeta grande", () => {
  assert.equal(planesDeCiudad(datos()).grande, null);
  const p = planesDeCiudad(datos({ rubros: new Set(["bodegas", "nocturna", "para-visitar"]), subcategorias: ["Plaza", "Mirador"], hayPlatos: true }));
  assert.equal(p.grande?.id, "vino");
  assert.equal(p.grande?.href, "/buscar?rubro=bodegas&vista=mapa");
  assert.equal(p.grande?.titulo, "La ruta del vino y el singani");
  assert.ok(!p.grilla.some((x) => x.id === "vino"), "la grande no se repite en la grilla");
});

test("QA §12: la grande es la primera con datos entre vino, centro y noche", () => {
  assert.equal(planesDeCiudad(datos({ rubros: new Set(["para-visitar", "nocturna"]), subcategorias: ["Iglesia"] })).grande?.id, "centro");
  assert.equal(planesDeCiudad(datos({ rubros: new Set(["nocturna"]) })).grande?.id, "noche");
  // sin ninguno de los tres, hay grilla pero no grande
  const sinGrande = planesDeCiudad(datos({ rubros: new Set(["para-visitar"]), subcategorias: ["Mirador"], hayPlatos: true }));
  assert.equal(sinGrande.grande, null);
  assert.deepEqual(sinGrande.grilla.map((x) => x.id), ["miradores", "sabores"]);
});

test("QA §12: centro histórico usa la primera de Plaza, Iglesia, Patrimonio que haya (en ese orden de preferencia)", () => {
  const rv = new Set(["para-visitar"]);
  const href = (subs: string[]) => planesDeCiudad(datos({ rubros: rv, subcategorias: subs })).grande?.href;
  assert.match(href(["Patrimonio", "Iglesia", "Plaza"]) ?? "", /sub=Plaza&/);
  assert.match(href(["Patrimonio", "Iglesia"]) ?? "", /sub=Iglesia&/);
  assert.match(href(["Patrimonio"]) ?? "", /sub=Patrimonio&/);
  assert.equal(href(["Cine"]), undefined);
});

test("QA §12: las subcategorías se reconocen sin mirar mayúsculas, tildes ni espacios", () => {
  const rv = new Set(["para-visitar"]);
  const r = ids(datos({ rubros: rv, subcategorias: ["  excursion ", "AREA PROTEGIDA", "centro cultural", "MIRADOR"] }));
  assert.deepEqual(r.sort(), ["cascadas", "lagunas", "miradores", "museos"]);
});

test("QA §12: una subcategoría sin el rubro «para-visitar» en la ciudad no arma plan (no hay a dónde ir)", () => {
  assert.deepEqual(ids(datos({ rubros: new Set(["bares"]), subcategorias: ["Plaza", "Mirador", "Parque", "Museo"] })), []);
  assert.equal(planesDeCiudad(datos({ rubros: new Set(["bares"]), subcategorias: ["Plaza"] })).verTodos, null);
});

test("QA §12: «Ver todos» sólo si hay para-visitar; la grilla no pasa de 6 y mantiene el orden de la maqueta", () => {
  const todo = datos({
    rubros: new Set(["bodegas", "para-visitar", "nocturna"]),
    subcategorias: ["Plaza", "Mirador", "Parque", "Museo", "Excursión", "Área protegida"], hayPlatos: true,
  });
  const p = planesDeCiudad(todo);
  assert.equal(MAX_GRILLA_PLANES, 6);
  assert.equal(p.grilla.length, 6);
  assert.deepEqual(p.grilla.map((x) => x.id), ["centro", "miradores", "cascadas", "noche", "sabores", "lagunas"]);
  assert.equal(p.verTodos, "/buscar?rubro=para-visitar&vista=mapa");
  assert.equal(planesDeCiudad(datos({ rubros: new Set(["bodegas"]) })).verTodos, null);
});

test("QA §12: nunca un número en lo que se muestra, los ids no se repiten y todos llevan a una ruta interna", () => {
  const p = todosLosPlanes(datos({
    rubros: new Set(["bodegas", "para-visitar", "nocturna"]),
    subcategorias: ["Plaza", "Mirador", "Parque", "Museo", "Excursión", "Área protegida"], hayPlatos: true,
  }));
  assert.equal(new Set(p.map((x) => x.id)).size, p.length);
  for (const x of p) {
    assert.doesNotMatch(`${x.titulo} ${x.bajada} ${x.etiqueta} ${x.cta}`, /\d/, x.id);
    assert.match(x.href, /^\/[a-z]/, x.id);
    assert.ok(ILUSTRACIONES.includes(x.ilustracion), `${x.id}: la ilustración ${x.ilustracion} no está en el catálogo`);
  }
});

test("QA §12: las ilustraciones son decorativas (aria-hidden) y no cargan imágenes de terceros ni fotos", () => {
  for (const id of ILUSTRACIONES) {
    const html = renderToStaticMarkup(createElement(Ilustracion, { id }));
    assert.match(html, /^<svg[^>]*aria-hidden="true"/, id);
    assert.doesNotMatch(html, /<image|<img|href="http|xlink:href|<script|onload|onerror/i, id);
  }
});

test("QA §12: el plan «Sabores» sólo con platos aprobados, y con nombre de ciudad hostil no se rompe el texto", () => {
  assert.equal(ids(datos({ hayPlatos: false })).includes("sabores"), false);
  const t = planesDeCiudad(datos({ hayPlatos: true, ciudadNombre: "<b>Tarija</b>" })).grilla[0];
  assert.equal(t.href, "/tarija/sabores");                           // la ruta sale del slug, nunca del nombre
});

// ═════════════════════════════════════════════════ §12/§15 · GENTILICIOS

test("QA gentilicios: chapaca / chapacos para Tarija y el resto del mapa del spec", () => {
  assert.equal(`Noche ${nocheDe("tarija", "Tarija")}`, "Noche chapaca");
  assert.equal(tituloSabores("tarija", "Tarija"), "Sabores chapacos");
  assert.equal(`Noche ${nocheDe("santa-cruz", "Santa Cruz")}`, "Noche cruceña");
  assert.equal(tituloSabores("potosi", "Potosí"), "Sabores potosinos");
  assert.equal(`Noche ${nocheDe("sucre", "Sucre")}`, "Noche sucrense");
  assert.equal(saboresDe("sucre", "Sucre"), "sucrenses");
});

test("QA gentilicios: una ciudad sin gentilicio usa «de {ciudad}» y el slug no se confunde por mayúsculas", () => {
  assert.equal(`Noche ${nocheDe("trinidad", "Trinidad")}`, "Noche de Trinidad");
  assert.equal(tituloSabores("tarija-norte", "Tarija Norte"), "Sabores de Tarija Norte");
  assert.equal(tituloSabores("TARIJA", "Tarija"), "Sabores de Tarija", "los slugs son minúsculas: uno raro no inventa gentilicio");
});

test("QA gentilicios: el plan «Noche» y «Sabores» de Tarija llevan el gentilicio en el título", () => {
  const p = todosLosPlanes(datos({ rubros: new Set(["nocturna"]), hayPlatos: true }));
  assert.deepEqual(p.map((x) => x.titulo), ["Noche chapaca", "Sabores chapacos"]);
});

// ═════════════════════════════════════════════════ §11 · LA FOTO DE LA TARJETA

test("QA §11: la foto del carrusel es tarjeta → miniatura y sólo la miniatura lleva object-position", () => {
  assert.deepEqual(fotoDeTarjeta({ portada_card_url: "c.jpg", portada_thumb_url: "t.jpg" }), { url: "c.jpg", recortada: true });
  assert.deepEqual(fotoDeTarjeta({ portada_card_url: null, portada_thumb_url: "t.jpg" }), { url: "t.jpg", recortada: false });
  assert.deepEqual(fotoDeTarjeta({ portada_card_url: undefined, portada_thumb_url: "t.jpg" }), { url: "t.jpg", recortada: false });
  assert.equal(fotoDeTarjeta({ portada_card_url: "", portada_thumb_url: "" }), null);
  const base: ComercioDeLaCiudad = {
    id: "a", slug: "a", nombre: "A", portada_thumb_url: "t.jpg", portada_pos: 80, rubro_slug: "cafeteria", rubro_nombre: "Cafetería",
    horario: null, lat: null, lng: null, prod_obs_human: null, prod_det_ia: null,
  };
  const comerciales = new Set(["cafeteria"]);
  const conTarjeta = candidatosCarrusel([{ ...base, portada_card_url: "c.jpg" }], "manana", "Tarija", comerciales).items[0];
  const conMini = candidatosCarrusel([base], "manana", "Tarija", comerciales).items[0];
  assert.equal(conTarjeta.fotoPos, null, "la tarjeta ya viene recortada: aplicarle object-position la correría dos veces");
  assert.equal(conMini.fotoPos, 80);
});

test("QA §11: una portada de diseño gana a la tarjeta (spec §11: «si el comercio tiene portada de diseño, se usa esa»)",
  { todo: "BUG-4: fotoDeTarjeta prioriza la tarjeta (hecha de la foto ORIGINAL) sobre la portada de diseño" }, () => {
    const r = fotoDeTarjeta({ portada_card_url: "c.jpg", portada_diseno_url: "d.jpg", portada_thumb_url: "t.jpg" });
    assert.equal(r?.url, "d.jpg");
  });

test("QA §11: la portada de diseño llega al home (buscar_comercios devuelve portada_diseno_url)",
  { todo: "BUG-4: la RPC buscar_comercios (0202) no devuelve portada_diseno_url: la rama de diseño de fotoDeTarjeta nunca se alimenta en el home" }, () => {
    assert.match(leer("..", "supabase", "migrations", "0202_fotos_planes_platos.sql"), /portada_diseno_url/);
  });

// ═════════════════════════════════════════════════ §11 · ORDEN DE LOS CARRUSELES (propiedades)

const cand = (id: string, extra: Partial<ComercioCarrusel> = {}): ComercioCarrusel => ({
  id, slug: id, nombre: id, foto: "f.jpg", fotoPos: null, rubro: "cafeteria", rubroNombre: "Cafetería",
  horario: "Lun a Dom 8-22", horarioEstimado: false, lat: -21.53, lng: -64.73, estrella: false, plan_orden: 0, ...extra,
});
const AHORA = new Date(2026, 10, 18, 14, 0);          // miércoles 14:00 (Bolivia)

function aleatorio(semilla: number): () => number {
  let s = semilla >>> 0;
  return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 2 ** 32);
}

test("QA §11 orden: para 300 listas al azar el resultado respeta abiertos > estrella > plan > calidad y es una permutación", () => {
  const rnd = aleatorio(42);
  for (let corrida = 0; corrida < 300; corrida++) {
    const n = 1 + Math.floor(rnd() * 25);
    const lista = Array.from({ length: n }, (_, i) => cand(`c${i}`, {
      horario: rnd() < 0.3 ? "Lun a Dom 16-20" : "Lun a Dom 8-22",           // a las 14:00: cerrado / abierto
      estrella: rnd() < 0.25, plan_orden: Math.floor(rnd() * 4),
      calidad: rnd() < 0.2 ? null : Math.floor(rnd() * 101),
    }));
    const r = ordenarCarrusel(lista, null, AHORA);
    assert.deepEqual([...r.map((c) => c.id)].sort(), lista.map((c) => c.id).sort(), "permutación");
    const clave = (c: ComercioCarrusel) => [c.horario === "Lun a Dom 16-20" ? 1 : 0, c.estrella ? 0 : 1, c.estrella ? -c.plan_orden : 0, -(c.calidad ?? -1)];
    for (let i = 1; i < r.length; i++) {
      const a = clave(r[i - 1]), b = clave(r[i]);
      let cmp = 0;
      for (let k = 0; k < a.length && cmp === 0; k++) cmp = a[k] - b[k];
      assert.ok(cmp <= 0, `desordenado en ${i}: ${JSON.stringify(a)} antes de ${JSON.stringify(b)}`);
    }
  }
});

test("QA §11 orden: con empate total se queda el orden de entrada (estable) y es idempotente", () => {
  const lista = ["d", "a", "c", "b"].map((id) => cand(id, { calidad: 50 }));
  const r1 = ordenarCarrusel(lista, null, AHORA);
  assert.deepEqual(r1.map((c) => c.id), ["d", "a", "c", "b"]);
  assert.deepEqual(ordenarCarrusel(r1, null, AHORA).map((c) => c.id), r1.map((c) => c.id));
});

test("QA §11 orden: los 12 del carrusel son los 12 de mayor calidad entre iguales, aunque lleguen desordenados", () => {
  const lista = Array.from({ length: 40 }, (_, i) => cand(`c${i}`, { calidad: (i * 37) % 101 }));
  const r = prepararCarrusel(lista, { abiertos: false, cerca: false, ubicacion: null, ahora: AHORA });
  assert.equal(r.length, MAX_CARRUSEL);
  const mejores = [...lista].sort((a, b) => (b.calidad ?? 0) - (a.calidad ?? 0)).slice(0, MAX_CARRUSEL).map((c) => c.calidad);
  assert.deepEqual(r.map((c) => c.calidad), mejores);
});

test("QA §11 orden: una calidad rara (negativa, enorme, NaN) no rompe el comparador ni pierde tarjetas", () => {
  const lista = [cand("neg", { calidad: -7 }), cand("big", { calidad: 1e9 }), cand("ok", { calidad: 50 }), cand("nan", { calidad: NaN })];
  const r = ordenarCarrusel(lista, null, AHORA);
  assert.deepEqual([...r.map((c) => c.id)].sort(), ["big", "nan", "neg", "ok"]);
  const sinNaN = r.filter((c) => c.id !== "nan").map((c) => c.id);
  assert.deepEqual(sinNaN, ["big", "ok", "neg"]);
});

test("QA §11 orden: «Abiertos» no deja pasar cerrados aunque tengan la mejor calidad", () => {
  const lista = [cand("cerrado", { horario: "Lun a Dom 16-20", calidad: 100 }), cand("abierto", { calidad: 1 })];
  assert.deepEqual(prepararCarrusel(lista, { abiertos: true, cerca: false, ubicacion: null, ahora: AHORA }).map((c) => c.id), ["abierto"]);
});

// ═════════════════════════════════════════════════ §14 · APROBAR EN BLOQUE: EL REDUCTOR, SIN ATAJOS

const R = (aprobados: number): ResultadoLote => ({ aprobados, salteados: { repetidos: 0, sin_rubro: 0, sin_punto: 0, error: 0 } });
const EVENTOS: EventoLote[] = [
  { tipo: "abrir" }, { tipo: "simulado", resultado: R(0) }, { tipo: "simulado", resultado: R(5) }, { tipo: "confirmar" },
  { tipo: "aprobado", resultado: R(5) }, { tipo: "fallo", mensaje: "x" }, { tipo: "cancelar" },
];

test("QA §14: recorriendo TODAS las secuencias de hasta 7 eventos, «aprobando» sólo se alcanza simulando antes, con algo para aprobar y confirmando", () => {
  let alcanzados = 0;
  const recorrer = (estado: EstadoLote, camino: EventoLote[]): void => {
    if (camino.length === 7) return;
    for (const ev of EVENTOS) {
      const siguiente = reducirLote(estado, ev);
      const nuevo = [...camino, ev];
      if (siguiente.tipo === "aprobando" && estado.tipo !== "aprobando") {
        alcanzados++;
        // la transición a «aprobando» es siempre `confirmar` desde «confirmar» con simulación > 0
        assert.equal(ev.tipo, "confirmar", JSON.stringify(nuevo));
        assert.equal(estado.tipo, "confirmar");
        assert.ok(estado.tipo === "confirmar" && estado.simulado.aprobados > 0, JSON.stringify(nuevo));
      }
      // «confirmar» (la pantalla de los números) sólo se alcanza desde «simulando» con el resultado de la simulación,
      // y «simulando» sólo se alcanza abriendo: no hay forma de llegar a aprobar sin haber visto una simulación.
      if (siguiente.tipo === "confirmar" && estado.tipo !== "confirmar") {
        assert.equal(estado.tipo, "simulando", JSON.stringify(nuevo));
        assert.equal(ev.tipo, "simulado", JSON.stringify(nuevo));
      }
      if (siguiente.tipo === "simulando" && estado.tipo !== "simulando") {
        assert.equal(ev.tipo, "abrir", JSON.stringify(nuevo));
        assert.ok(["cerrado", "hecho", "error"].includes(estado.tipo), JSON.stringify(nuevo));
      }
      recorrer(siguiente, nuevo);
    }
  };
  recorrer(LOTE_CERRADO, []);
  assert.ok(alcanzados > 0, "el recorrido tiene que alcanzar «aprobando» alguna vez (si no, el test no prueba nada)");
});

test("QA §14: «confirmar» fuera de «confirmar», con simulación de 0, o repetido, no aprueba", () => {
  for (const e of [LOTE_CERRADO, { tipo: "simulando" } as EstadoLote, { tipo: "hecho", resultado: R(3) } as EstadoLote,
                   { tipo: "error", mensaje: "m", en: "simular" } as EstadoLote]) {
    assert.equal(reducirLote(e, { tipo: "confirmar" }).tipo, e.tipo);
  }
  const cero: EstadoLote = { tipo: "confirmar", simulado: R(0) };
  assert.equal(reducirLote(cero, { tipo: "confirmar" }), cero);
  const aprobando = reducirLote({ tipo: "confirmar", simulado: R(2) }, { tipo: "confirmar" });
  assert.equal(aprobando.tipo, "aprobando");
  assert.equal(reducirLote(aprobando, { tipo: "confirmar" }), aprobando, "doble toque: no vuelve a pedir");
});

test("QA §14: una simulación o un resultado que llega tarde (la persona canceló o cambió de fuente) no cambia la pantalla", () => {
  const cerrado = reducirLote(reducirLote(LOTE_CERRADO, { tipo: "abrir" }), { tipo: "cancelar" });
  assert.equal(cerrado.tipo, "cerrado");
  assert.equal(reducirLote(cerrado, { tipo: "simulado", resultado: R(9) }).tipo, "cerrado");
  assert.equal(reducirLote(cerrado, { tipo: "aprobado", resultado: R(9) }).tipo, "cerrado");
  assert.equal(reducirLote(cerrado, { tipo: "fallo", mensaje: "x" }).tipo, "cerrado");
});

test("QA §14: tras un resultado o un error, volver a empezar obliga a simular otra vez (no reusa la simulación vieja)", () => {
  const hecho: EstadoLote = { tipo: "hecho", resultado: R(5) };
  const otra = reducirLote(hecho, { tipo: "abrir" });
  assert.equal(otra.tipo, "simulando");
  assert.equal(reducirLote(otra, { tipo: "confirmar" }).tipo, "simulando");
});

test("QA §14: el botón sale para toda fuente que el servidor acepta y manda el valor que el servidor espera", () => {
  const literal = /fuente: Literal\[([^\]]*)\]\s*\n\s*ciudad_id/.exec(BACK("app", "api", "moderacion.py"));
  assert.ok(literal, "no se encontró el Literal de AprobarLoteBody.fuente");
  const aceptadas = [...literal![1].matchAll(/"([a-z]+)"/g)].map((m) => m[1]);
  const filtros: FuenteFiltro[] = ["todas", "osm", "tarjeta", "turismo", "turismo-visitar", "overture", "anh", "aduana"];
  for (const f of filtros) {
    if (!ofreceAprobarEnBloque(f, "nuevo")) continue;
    assert.ok(aceptadas.includes(paramFuente(f) ?? ""), `el filtro ${f} ofrece el botón pero el servidor contestaría 422 a «${paramFuente(f)}»`);
  }
  assert.equal(ofreceAprobarEnBloque("turismo-visitar", "nuevo"), false);
});

test("QA §14: la pantalla sólo manda `simular: false` desde el botón «Sí, aprobar», que sólo se dibuja en «confirmar» con algo para aprobar", () => {
  const fuente = leer("components", "admin", "aprobar-lote.tsx");
  assert.equal((fuente.match(/simular: false/g) ?? []).length, 1);
  assert.equal((fuente.match(/simular: true/g) ?? []).length, 1);
  assert.equal((fuente.match(/onClick=\{aprobar\}/g) ?? []).length, 1);
  const i = fuente.indexOf("onClick={aprobar}");
  const antes = fuente.slice(0, i);
  assert.ok(antes.lastIndexOf('estado.tipo === "confirmar"') > antes.lastIndexOf('estado.tipo === "simulando"'));
  assert.ok(antes.lastIndexOf("estado.simulado.aprobados > 0") > antes.lastIndexOf('estado.tipo === "confirmar"'));
  assert.doesNotMatch(fuente, /window\.confirm\(|confirm\(/, "la confirmación va en la misma pantalla");
  assert.doesNotMatch(fuente, /dangerouslySetInnerHTML/);
});

test("QA §14: el panel monta el lote con key de ciudad+fuente+estado (cambiar cualquiera reinicia el flujo)", () => {
  const panel = leer("components", "importados-panel.tsx");
  assert.match(panel, /<AprobarLote key=\{`\$\{ciudadId \?\? "todas"\}\|\$\{fuente\}\|\$\{estado\}`\}/);
});

test("QA §14: una respuesta hostil o rota del servidor se lee como ceros, nunca como números inventados", () => {
  const raros: unknown[] = [null, undefined, "x", 5, [], { aprobados: "9" }, { aprobados: -3 }, { aprobados: NaN }, { aprobados: Infinity },
    { aprobados: 2.9, salteados: null }, { salteados: { repetidos: "7", sin_rubro: -1, sin_punto: {}, error: [] } },
    JSON.parse('{"__proto__":{"aprobados":99},"salteados":{"__proto__":{"repetidos":99}}}')];
  for (const raro of raros) {
    const r = resultadoDeRespuesta(raro);
    for (const n of [r.aprobados, ...Object.values(r.salteados)]) assert.ok(Number.isInteger(n) && n >= 0, JSON.stringify(raro));
  }
  assert.equal(resultadoDeRespuesta({ aprobados: 2.9 }).aprobados, 2);
  assert.equal(resultadoDeRespuesta(JSON.parse('{"__proto__":{"aprobados":99}}')).aprobados, 0);
  assert.doesNotMatch(textoSimulacion(resultadoDeRespuesta({ aprobados: "9" })), /NaN|undefined/);
  assert.doesNotMatch(textoResultado(resultadoDeRespuesta(null)), /NaN|undefined/);
});

// ═════════════════════════════════════════════════ §15 · PLATOS: PERMISO, 404 Y VISIBILIDAD

test("QA §15: la sección «Platos típicos» del admin pide el MISMO permiso que el backend (`contenido`)", () => {
  const back = [...BACK("app", "api", "platos.py").matchAll(/require_permiso\("([^"]+)"\)/g)].map((m) => m[1]);
  assert.ok(back.length >= 2, "listar y editar");
  assert.deepEqual([...new Set(back)], ["contenido"]);
  const seccion = MENU.flatMap((g) => g.secciones).find((i) => i.id === "platos");
  assert.ok(seccion, "la sección platos está en el menú");
  assert.equal(seccion!.permiso, back[0]);
  // el montaje en la página del admin respeta la misma compuerta que las demás secciones
  assert.match(leer("app", "admin", "page.tsx"), /permitida && seccion === "platos" && ciudadLista && <PlatosPanel ciudad=\{ciudad\} \/>/);
});

test("QA §15: «Importados» (donde vive aprobar en bloque) sigue pidiendo `datos`, igual que el endpoint", () => {
  const seccion = MENU.flatMap((g) => g.secciones).find((i) => i.id === "importados");
  assert.equal(seccion?.permiso, "datos");
  assert.match(BACK("app", "api", "moderacion.py"), /def aprobar_lote_importados\([\s\S]*?require_permiso\("datos"\)/);
});

const plato = (extra: Partial<PlatoTipico> = {}): PlatoTipico => ({
  id: "p", ciudad_id: "c", tipo: "plato", nombre: "Saice", descripcion: "Un guiso.", fuente_url: null, estado: "aprobado", activo: true, updated_at: null, ...extra,
});

test("QA §15: /tarija/sabores muestra SOLO aprobados y activos; con todo pendiente, rechazado o inactivo no hay secciones (→ 404)", () => {
  const mezcla = [
    plato({ id: "1", nombre: "A" }), plato({ id: "2", nombre: "B", estado: "pendiente" }), plato({ id: "3", nombre: "C", estado: "rechazado" }),
    plato({ id: "4", nombre: "D", activo: false }), plato({ id: "5", nombre: "E", tipo: "bebida", estado: "pendiente" }),
  ];
  const visibles = agruparPlatos(mezcla).flatMap((s) => s.platos.map((p) => p.nombre));
  assert.deepEqual(visibles, ["A"]);
  assert.deepEqual(agruparPlatos(mezcla.slice(1)), []);
  assert.deepEqual(agruparPlatos([]), []);
});

test("QA §15: filas rotas de la base no tumban la página ni se cuelan", () => {
  const filas: unknown[] = [null, 1, "x", {}, { id: "1" }, { id: "1", nombre: "  ", tipo: "plato", estado: "aprobado" },
    { id: "1", nombre: "X", tipo: "sopa", estado: "aprobado" }, { id: "1", nombre: "X", tipo: "plato", estado: "publicado" }];
  for (const f of filas) assert.equal(platoDeFila(f), null, JSON.stringify(f));
  const ok = platoDeFila({ id: "1", nombre: " X ", tipo: "plato", estado: "aprobado", descripcion: null, fuente_url: "  " });
  assert.equal(ok?.nombre, "X");
  assert.equal(ok?.descripcion, "");
  assert.equal(ok?.fuente_url, null);
});

test("QA §15: la página responde 404 sin platos aprobados y NO cachea un 404 por un fallo de lectura (ISR)", () => {
  const pagina = leer("app", "[city]", "sabores", "page.tsx");
  assert.match(pagina, /const secciones = agruparPlatos\(platos\);\s*\n\s*if \(secciones\.length === 0\) notFound\(\);/);
  assert.match(pagina, /if \(!ciudad\) notFound\(\);/);
  assert.match(pagina, /if \(platos\.length === 0\) return NO_ENCONTRADA;/);
  assert.match(pagina, /NO_ENCONTRADA: Metadata = \{ title: "No encontrada", robots: \{ index: false, follow: false \} \}/);
  assert.match(pagina, /export const revalidate = 3600;/);
  assert.match(pagina, /async function generateStaticParams[\s\S]*?\{\s*return \[\];/);
  const datosTs = leer("lib", "data.ts");
  const i = datosTs.indexOf("export async function getPlatosAprobados");
  const fn = datosTs.slice(i, datosTs.indexOf("\n}\n", i));
  assert.match(datosTs, /TABLA_AUSENTE = new Set\(\["PGRST205", "PGRST200", "42P01"\]\)/);
  assert.match(fn, /if \(TABLA_AUSENTE\.has\(error\.code \?\? ""\)\) return \[\];\s*\n\s*throw new Error/);     // tabla ausente → [] → 404
  assert.match(fn, /\.eq\("estado", "aprobado"\)\.eq\("activo", true\)/);                                    // y la consulta filtra igual que la RLS
  assert.match(fn, /if \(!hasSupabase\) return \[\];/);
});

test("QA §15: el plan «Sabores» del home no lanza ni aparece si la tabla falta o la lectura falla", () => {
  const datosTs = leer("lib", "data.ts");
  const i = datosTs.indexOf("async function ciudadTienePlatos");
  const fn = datosTs.slice(i, datosTs.indexOf("\n}\n", i));
  assert.match(fn, /return !error && \(data \?\? \[\]\)\.length > 0;/);
  assert.match(fn, /catch \{\s*\n\s*return false;/);
});

test("QA §15: lo que escribe el admin (o Gemini) se pinta como texto: ni la página ni el panel usan innerHTML", () => {
  for (const f of [["app", "[city]", "sabores", "page.tsx"], ["components", "admin", "platos-panel.tsx"], ["components", "admin", "aprobar-lote.tsx"],
                   ["components", "home-ciudad", "que-hacer.tsx"], ["components", "ilustraciones", "index.tsx"]]) {
    assert.doesNotMatch(leer(...f), /dangerouslySetInnerHTML|innerHTML|insertAdjacentHTML/, f.join("/"));
  }
});

test("QA §15: «Dónde comer comida típica» no apunta a un rubro que la ciudad no tiene y codifica la subcategoría", () => {
  assert.equal(hrefDondeComer(null, false), null);
  assert.equal(hrefDondeComer(null, true), "/buscar?rubro=restaurantes&vista=mapa");
  assert.equal(hrefDondeComer("Comida boliviana", true), "/buscar?rubro=restaurantes&sub=Comida%20boliviana&vista=mapa");
  assert.equal(hrefDondeComer("a&b=c", true)?.includes("sub=a%26b%3Dc"), true);
});

test("QA §15: los topes del panel no superan los del backend (si no, el servidor contestaría 422 a algo que el panel dejó pasar)", () => {
  const back = BACK("app", "api", "platos.py");
  assert.ok(MAX_NOMBRE_PLATO <= Number(/MAX_NOMBRE = (\d+)/.exec(back)![1]));
  assert.ok(MAX_DESCRIPCION_PLATO <= Number(/MAX_DESCRIPCION = (\d+)/.exec(back)![1]));
  const original = plato({ nombre: "Saice", descripcion: "Un guiso." });
  assert.equal(cambiosDeEdicion(original, { nombre: "x".repeat(MAX_NOMBRE_PLATO + 1), descripcion: "ok" }).error !== null, true);
  assert.equal(cambiosDeEdicion(original, { nombre: "Saice", descripcion: "y".repeat(MAX_DESCRIPCION_PLATO + 1) }).error !== null, true);
  assert.deepEqual(cambiosDeEdicion(original, { nombre: "  Saice ", descripcion: " Un guiso. " }), { cambios: {}, error: null });
});

test("QA §15: no se puede aprobar un plato sin texto desde el panel (la página mostraría un nombre pelado)", () => {
  assert.equal(puedeAprobarPlato({ nombre: "Saice", descripcion: "   " }), false);
  assert.equal(puedeAprobarPlato({ nombre: " ", descripcion: "ok" }), false);
  assert.equal(puedeAprobarPlato({ nombre: "Saice", descripcion: "ok" }), true);
  const panel = leer("components", "admin", "platos-panel.tsx");
  assert.match(panel, /puedeAprobarPlato\(/);
});

// ═════════════════════════════════════════════════ §11 · FLECHAS Y PUNTITOS (sólo lo verificable sin navegador)

test("QA §11: las flechas quedan FUERA de la foto con mouse y desaparecen en pantallas táctiles; los puntitos sólo en táctiles", () => {
  const css = leer("app", "styles", "home-ciudad.css");
  const base = leer("app", "uruku.css");
  assert.match(base, /@media \(hover: none\) \{ \.uk-carrusel-flecha \{ display: none; \} \}/);
  assert.match(css, /@media \(hover: hover\) and \(pointer: fine\) \{[^}]*\.uk-hc-carrusel \{ padding-inline: 52px; \}[^}]*flecha\.izq \{ left: 0; \}[^}]*flecha\.der \{ right: 0; \}/s);
  assert.match(css, /\.uk-hc-puntos \{ display: none;/);
  assert.match(css, /@media \(hover: none\) \{ \.uk-hc-puntos \{ display: flex; \} \}/);
  // la flecha mide 40 px y el margen es de 52: no pisa la foto
  assert.match(base, /\.uk-carrusel-flecha \{[^}]*width: 40px; height: 40px;/s);
});

test("QA §11: el nombre va ENCIMA de la foto (posición absoluta sobre un degradé) y el «Abierto» arriba a la izquierda, en blanco",
  () => {
    const css = leer("app", "styles", "home-ciudad.css");
    assert.match(css, /\.uk-hc-com-txt \{ position: absolute; left: 14px; right: 14px; bottom: 12px;/);
    assert.match(css, /\.uk-hc-com::after \{[^}]*linear-gradient\(180deg, rgba\(10,17,13,0\) 45%, rgba\(10,17,13,\.88\) 100%\)/s);
    assert.match(css, /\.uk-hc-com \.uk-open \{ position: absolute; left: 10px; top: 10px;/);
    assert.match(css, /\.uk-hc-com \.uk-open\.is-open \{ background: rgba\(255,255,255,\.94\);/);
    assert.match(css, /\.uk-hc-com img \{[^}]*aspect-ratio: 4 \/ 3;/);
    const jsx = leer("components", "home-ciudad", "carrusel-comercios.tsx");
    assert.ok(jsx.indexOf("<img") < jsx.indexOf("uk-hc-com-txt"), "la foto y el texto son hermanos dentro del mismo enlace");
  });
