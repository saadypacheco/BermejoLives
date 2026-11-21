// Tests de «Pedir un video» y los interruptores de costo (docs/contenido-redes-tecnico.md §17.4).
// Cubren las funciones puras de `lib/content-pure.ts`. Se corren con `npm test` (tsc → node --test).
import test from "node:test";
import assert from "node:assert/strict";
import {
  armarPedidoDeVideo, avisoOtraPropuesta, bodyDeInterruptor, geminiContentPrendido, insigniaSinGemini, chipsEditables, detalleDePieza, esPiezaPedida, estadoDeInterruptor,
  etiquetaDePilar, faseVideoNegocio, normalizarBusquedaComercio, opcionDeRubro, resumenRequestCheck, tienePermiso, tituloDePieza,
  validateVideoTexts, type VideoTextsEditable,
} from "../lib/content-pure";

test("pilar rubro: «Repaso de rubro», aunque el backend mande otra etiqueta", () => {
  assert.equal(etiquetaDePilar({ pillar: "rubro", pillar_label: "Rubro" }), "Repaso de rubro");
  assert.equal(etiquetaDePilar({ pillar: "ofertas", pillar_label: "Ofertas de la semana" }), "Ofertas de la semana");
  assert.equal(etiquetaDePilar({ pillar: "ofertas" }), "Ofertas de la semana");
  assert.equal(etiquetaDePilar({ pillar: "otro_nuevo" }), "otro_nuevo");
});

test("título de la pieza: rubro «{rubro} en {ciudad}», comercio por nombre, ofertas sin detalle", () => {
  assert.equal(
    tituloDePieza({ pillar: "rubro", pillar_label: "Repaso de rubro", rubro: { nombre: "Zapatillas", slug: "zapatillas" }, ciudad_nombre: "Bermejo" }),
    "Repaso de rubro · Zapatillas en Bermejo");
  assert.equal(
    tituloDePieza({ pillar: "comercio_del_dia", pillar_label: "Comercio del día", comercio: { nombre: "Casa Pérez" } }),
    "Comercio del día · Casa Pérez");
  assert.equal(tituloDePieza({ pillar: "ofertas", pillar_label: "Ofertas de la semana", comercio: null }), "Ofertas de la semana");
  assert.equal(detalleDePieza({ pillar: "rubro", rubro: { nombre: "Celulares", slug: "celulares" } }), "Celulares");
  assert.equal(detalleDePieza({ pillar: "rubro" }), "Repaso de rubro");
});

test("insignia «Pedido» sólo para origin = pedido", () => {
  assert.equal(esPiezaPedida("pedido"), true);
  assert.equal(esPiezaPedida("selector"), false);
  assert.equal(esPiezaPedida(undefined), false);
  assert.equal(esPiezaPedida(null), false);
});

test("chips: no se editan ni se validan en ofertas ni en rubro", () => {
  assert.equal(chipsEditables("comercio_del_dia"), true);
  assert.equal(chipsEditables("ofertas"), false);
  assert.equal(chipsEditables("rubro"), false);
  const textos: VideoTextsEditable = { kick: "EN BERMEJO", title1: "Zapatillas", title2: "en Bermejo", subtitle: null, search_term: "zapatillas" };
  // Un nombre de comercio de una sola palabra rompería la regla de 2 a 5 palabras: en rubro no se valida.
  assert.deepEqual(validateVideoTexts(textos, ["Nike"], "rubro"), []);
  assert.equal(validateVideoTexts(textos, ["Nike"], "comercio_del_dia").length, 1);
});

test("buscador: el código URUKU se normaliza, el nombre queda como está", () => {
  assert.equal(normalizarBusquedaComercio("uruku-ab12"), "URUKU-AB12");
  assert.equal(normalizarBusquedaComercio("  Uruku 1234 "), "URUKU-1234");
  assert.equal(normalizarBusquedaComercio("URUKU-9876"), "URUKU-9876");
  assert.equal(normalizarBusquedaComercio("uruku"), "uruku");
  assert.equal(normalizarBusquedaComercio("  Casa Pérez "), "Casa Pérez");
  assert.equal(normalizarBusquedaComercio(""), "");
});

test("request-check: dice qué falta con las palabras del backend", () => {
  assert.deepEqual(resumenRequestCheck({ consent: true, usable_photos: 5, ok: true, reason: null }),
    { tono: "ok", texto: "Tiene autorización y 5 fotos que sirven." });
  assert.equal(resumenRequestCheck({ consent: true, usable_photos: 1, ok: true, reason: null }).texto, "Tiene autorización y 1 foto que sirve.");
  assert.deepEqual(resumenRequestCheck({ consent: true, usable_photos: 2, ok: false, reason: "Tiene 2 fotos que sirven: subí al menos 4 en Banco de contenido" }),
    { tono: "error", texto: "Tiene 2 fotos que sirven: subí al menos 4 en Banco de contenido" });
  assert.equal(resumenRequestCheck({ consent: false, usable_photos: 6, ok: false, reason: null }).texto, "No tiene la autorización para redes vigente.");
  assert.equal(resumenRequestCheck({ consent: true, usable_photos: 3, ok: false, reason: "  " }).tono, "error");
});

test("rubros: el que no es elegible se deshabilita y lo explica", () => {
  assert.deepEqual(opcionDeRubro({ slug: "ropa", nombre: "Ropa", eligible: true }), { texto: "Ropa", deshabilitada: false, ayuda: null });
  const no = opcionDeRubro({ slug: "optica", nombre: "Óptica", eligible: false });
  assert.equal(no.deshabilitada, true);
  assert.match(no.ayuda ?? "", /menos de 4 comercios/);
});

test("pedido: el body sólo existe cuando está todo elegido", () => {
  assert.deepEqual(armarPedidoDeVideo("comercio", { comercioId: "abc" }), { kind: "comercio", comercio_id: "abc" });
  assert.equal(armarPedidoDeVideo("comercio", { comercioId: null }), null);
  assert.deepEqual(armarPedidoDeVideo("rubro", { ciudadSlug: "bermejo", rubroSlug: "zapatillas" }),
    { kind: "rubro", rubro_slug: "zapatillas", ciudad_slug: "bermejo" });
  assert.equal(armarPedidoDeVideo("rubro", { ciudadSlug: "bermejo", rubroSlug: "" }), null);
  assert.equal(armarPedidoDeVideo("rubro", { ciudadSlug: "", rubroSlug: "zapatillas" }), null);
  // Lo que sobra del otro modo no se cuela en el body.
  assert.deepEqual(armarPedidoDeVideo("comercio", { comercioId: "abc", ciudadSlug: "bermejo", rubroSlug: "x" }), { kind: "comercio", comercio_id: "abc" });
});

test("permiso `equipo`: sólo con él (o con `*`) se ven los botones de los interruptores", () => {
  assert.equal(tienePermiso(["difusion"], "equipo"), false);
  assert.equal(tienePermiso(["difusion", "equipo"], "equipo"), true);
  assert.equal(tienePermiso(["*"], "equipo"), true);
  assert.equal(tienePermiso([], "equipo"), false);
});

test("interruptores: estado en palabras y body de la llamada", () => {
  assert.deepEqual(estadoDeInterruptor(false), { texto: "Apagado · costo cero", tono: "ok", icono: "listo" });
  assert.deepEqual(estadoDeInterruptor(true), { texto: "Prendido · tiene costo", tono: "aviso", icono: "aviso" });
  assert.deepEqual(bodyDeInterruptor(true, true), { enabled: true, confirm_cost: true });
  assert.deepEqual(bodyDeInterruptor(true, false), { enabled: true, confirm_cost: false });
  // Apagar nunca pide confirmación: confirm_cost va en false aunque la casilla haya quedado marcada.
  assert.deepEqual(bodyDeInterruptor(false, true), { enabled: false, confirm_cost: false });
});

/* ─── Gemini y su interruptor (`gemini_content`) ─────────────────────────── */

test("geminiContentPrendido lee el interruptor gemini_content; sin él, null", () => {
  assert.equal(geminiContentPrendido([{ key: "otro", enabled: true }, { key: "gemini_content", enabled: false }]), false);
  assert.equal(geminiContentPrendido([{ key: "gemini_content", enabled: true }]), true);
  assert.equal(geminiContentPrendido([{ key: "otro", enabled: true }]), null);
  assert.equal(geminiContentPrendido([]), null);
});

test("avisoOtraPropuesta dice la verdad según el interruptor", () => {
  assert.equal(
    avisoOtraPropuesta(false, true),
    "Gemini está apagado: se vuelven a poner los textos fijos y se pisan las frases que escribiste. ¿Seguir?",
  );
  assert.equal(avisoOtraPropuesta(false, false), avisoOtraPropuesta(false, true));
  assert.match(avisoOtraPropuesta(true, false), /^¿Pedir otra propuesta a Gemini\?/);
  assert.ok(!avisoOtraPropuesta(true, false).includes("escribiste"));
  assert.match(avisoOtraPropuesta(true, true), /incluido lo que escribiste vos/);
  // Si no se pudo leer el interruptor, no se afirma que esté apagado.
  assert.match(avisoOtraPropuesta(null, false), /^¿Pedir otra propuesta a Gemini\?/);
});

test("insigniaSinGemini: falta la key, interruptor apagado, o nada", () => {
  assert.equal(insigniaSinGemini(false, true), "Sin Gemini: los textos salen de la plantilla fija");
  assert.equal(insigniaSinGemini(false, false), "Sin Gemini: los textos salen de la plantilla fija");
  assert.equal(insigniaSinGemini(true, false), "Gemini apagado · costo cero");
  assert.equal(insigniaSinGemini(true, true), null);
  assert.equal(insigniaSinGemini(true, null), null);
});

// ── botón «Video» de Admin › Comercios (faseVideoNegocio) ──

test("faseVideoNegocio: un video armándose o listo manda sobre pedir otro", () => {
  const base = { consent: true, usable_photos: 6, ok: true, reason: null };
  const pieza = (status: "queued" | "rendering" | "ready_for_review" | "approved" | "published" | "failed") =>
    ({ ...base, last_piece: { id: "p1", status, scheduled_for: "2026-11-21" } });
  assert.equal(faseVideoNegocio(pieza("queued")).fase, "armando");
  assert.equal(faseVideoNegocio(pieza("rendering")).fase, "armando");
  assert.equal(faseVideoNegocio(pieza("ready_for_review")).fase, "listo");
  assert.equal(faseVideoNegocio(pieza("approved")).fase, "listo");
  assert.equal(faseVideoNegocio(pieza("published")).fase, "listo");
  // Un fallado con todo en regla deja pedir de nuevo.
  assert.equal(faseVideoNegocio(pieza("failed")).fase, "puede");
});

test("faseVideoNegocio: un video viejo no tapa lo que falta hoy", () => {
  const publicado = { id: "p1", status: "published" as const, scheduled_for: "2026-05-01" };
  const sinAut = faseVideoNegocio({ consent: false, usable_photos: 6, ok: false, reason: "El comercio no tiene autorización vigente para aparecer en las redes", last_piece: publicado });
  assert.equal(sinAut.fase, "falta_autorizacion");
  assert.match(sinAut.texto, /^Ya tiene un video publicado\. Para armar otro, falta la autorización/);
  const fallado = { id: "p2", status: "failed" as const, scheduled_for: "2026-11-01" };
  assert.equal(faseVideoNegocio({ consent: true, usable_photos: 2, ok: false, reason: "Tiene 2 fotos que sirven: subí al menos 4 en Banco de contenido", last_piece: fallado }).fase, "faltan_fotos");
  assert.equal(faseVideoNegocio({ consent: true, usable_photos: 6, ok: false, reason: "El comercio no está activo", last_piece: fallado }).texto,
    "El último video no se pudo armar. Para armar otro, el comercio no está activo");
});

test("faseVideoNegocio: sin video previo dice si se puede o qué falta", () => {
  assert.equal(faseVideoNegocio({ consent: true, usable_photos: 5, ok: true, reason: null, last_piece: null }).fase, "puede");
  const sinAut = faseVideoNegocio({ consent: false, usable_photos: 6, ok: false, reason: "El comercio no tiene autorización vigente para aparecer en las redes" });
  assert.equal(sinAut.fase, "falta_autorizacion");
  assert.match(sinAut.texto, /^Falta la autorización/);
  const fotos = faseVideoNegocio({ consent: true, usable_photos: 1, ok: false, reason: "Tiene 1 fotos que sirven: subí al menos 4 en Banco de contenido" });
  assert.equal(fotos.fase, "faltan_fotos");
  assert.match(fotos.texto, /^Tiene 1 foto que sirve, faltan 3\./);
  assert.match(faseVideoNegocio({ consent: true, usable_photos: 3, ok: false, reason: "x fotos" }).texto, /falta 1\b/);
  const baja = faseVideoNegocio({ consent: true, usable_photos: 6, ok: false, reason: "El comercio no está activo" });
  assert.deepEqual(baja, { fase: "no_se_puede", texto: "El comercio no está activo" });
});
