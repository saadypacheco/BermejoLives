// Fotos con estilo URUKU (docs/fotos-estilo-uruku.md): la lógica pura de la ventana «Fotos» de Admin › Comercios.
import test from "node:test";
import assert from "node:assert/strict";
import {
  aplicarResultado, avisoPropuesta, estadoFoto, etiquetaConIA, leerCoverDesign, leerEstado, leerGalleryItem,
  nombreDescarga, problemaArchivoExterno, puedeIA, resumenIA, textoCosto, AVISO_REVISION, MAX_BYTES_EXTERNA,
  type GeminiState, type PhotoStyleState,
} from "../lib/fotos-estilo-pure";

const ia = (o: Partial<GeminiState> = {}): GeminiState => ({
  available: true, reason: null, cost_usd: 0.0336, used_today: 3, daily_cap: 20, merchant_uses: 2, merchant_cost_usd: 0.0672, ...o,
});

test("textoCosto: tres decimales con coma, sin el cero de sobra", () => {
  assert.equal(textoCosto(0.0336), "≈ US$ 0,034");
  assert.equal(textoCosto(0.07), "≈ US$ 0,07");
  assert.equal(textoCosto(0.0672), "≈ US$ 0,067");
  assert.equal(textoCosto(0.1), "≈ US$ 0,10");
  assert.equal(textoCosto(1), "≈ US$ 1,00");
  assert.equal(textoCosto(0), "≈ US$ 0,00");
});

test("textoCosto: un valor que no es número o es negativo no rompe ni muestra NaN", () => {
  assert.equal(textoCosto(Number.NaN), "≈ US$ 0,00");
  assert.equal(textoCosto(-1), "≈ US$ 0,00");
});

test("estadoFoto: la propuesta pendiente manda; después el diseño; si no, la original", () => {
  assert.deepEqual(estadoFoto({ design_url: null, proposal_url: null }), { clave: "original", texto: "Original" });
  assert.deepEqual(estadoFoto({ design_url: "/d.jpg", proposal_url: null }), { clave: "con_diseno", texto: "Con diseño" });
  assert.deepEqual(estadoFoto({ design_url: null, proposal_url: "/p.jpg" }), { clave: "propuesta", texto: "Propuesta lista" });
  assert.equal(estadoFoto({ design_url: "/d.jpg", proposal_url: "/p.jpg" }).clave, "propuesta", "hay algo para decidir");
  assert.equal(estadoFoto({}).clave, "original");
});

test("avisoPropuesta: gemini y external piden revisar; free y sin método no avisan", () => {
  assert.match(avisoPropuesta("gemini") ?? "", /IA/);
  assert.match(avisoPropuesta("external") ?? "", /afuera/);
  for (const m of ["gemini", "external"] as const) assert.ok(avisoPropuesta(m)?.includes(AVISO_REVISION), m);
  assert.match(AVISO_REVISION, /texto, precios/);
  assert.equal(avisoPropuesta("free"), null);
  assert.equal(avisoPropuesta(null), null);
  assert.equal(avisoPropuesta(undefined), null);
});

test("puedeIA: disponible y con cupo se puede", () => {
  assert.deepEqual(puedeIA(ia()), { puede: true, motivo: null });
});

test("puedeIA: no disponible dice el motivo del servidor (interruptor apagado, sin modelo, sin costo)", () => {
  const r = puedeIA(ia({ available: false, reason: "el interruptor está apagado" }));
  assert.equal(r.puede, false);
  assert.equal(r.motivo, "el interruptor está apagado");
});

test("puedeIA: no disponible sin motivo igual muestra uno", () => {
  const r = puedeIA(ia({ available: false, reason: null }));
  assert.equal(r.puede, false);
  assert.ok(r.motivo && r.motivo.length > 10);
});

test("puedeIA: con el tope del día alcanzado no se puede y el motivo dice el tope", () => {
  const r = puedeIA(ia({ used_today: 20, daily_cap: 20 }));
  assert.equal(r.puede, false);
  assert.match(r.motivo ?? "", /tope de 20/);
  assert.equal(puedeIA(ia({ used_today: 25, daily_cap: 20 })).puede, false);
  assert.equal(puedeIA(ia({ used_today: 19, daily_cap: 20 })).puede, true);
  assert.equal(puedeIA(ia({ used_today: 99, daily_cap: null })).puede, true, "sin tope informado no se inventa uno");
  assert.equal(puedeIA(ia({ used_today: 0, daily_cap: 0 })).puede, false, "un 0 explícito SÍ bloquea la IA");
  assert.match(puedeIA(ia({ daily_cap: 0 })).motivo ?? "", /tope diario.*en 0/);
});

test("resumenIA: costo por foto, uso de hoy y gasto de este negocio", () => {
  assert.equal(resumenIA(ia()), "≈ US$ 0,034 por foto · hoy 3 de 20 · este negocio: 2 (≈ US$ 0,067)");
  assert.equal(resumenIA(ia({ merchant_uses: 0, merchant_cost_usd: 0 })), "≈ US$ 0,034 por foto · hoy 3 de 20 · este negocio: 0");
  assert.equal(resumenIA(ia({ cost_usd: 0, daily_cap: 0 })), "este negocio: 2 (≈ US$ 0,067)");
});

test("etiquetaConIA: «Con IA ≈ US$ …» y, al confirmar, «Confirmar ≈ US$ …»", () => {
  assert.equal(etiquetaConIA(ia(), false), "Con IA ≈ US$ 0,034");
  assert.equal(etiquetaConIA(ia(), true), "Confirmar ≈ US$ 0,034");
  assert.equal(etiquetaConIA(ia({ cost_usd: 0 }), false), "Con IA");
});

test("problemaArchivoExterno: JPG, PNG o WEBP de hasta 15 MB", () => {
  assert.equal(problemaArchivoExterno({ type: "image/jpeg", size: 1000 }), null);
  assert.equal(problemaArchivoExterno({ type: "image/png", size: MAX_BYTES_EXTERNA }), null);
  assert.equal(problemaArchivoExterno({ type: "image/webp", size: 1 }), null);
  assert.match(problemaArchivoExterno({ type: "image/gif", size: 1000 }) ?? "", /JPG, PNG o WEBP/);
  assert.match(problemaArchivoExterno({ type: "application/pdf", size: 1000 }) ?? "", /JPG, PNG o WEBP/);
  assert.match(problemaArchivoExterno({ type: "image/jpeg", size: MAX_BYTES_EXTERNA + 1 }) ?? "", /15 MB/);
  assert.match(problemaArchivoExterno({ type: "image/jpeg", size: 0 }) ?? "", /vacío/);
});

test("nombreDescarga: slug seguro y distinto para la portada y cada foto", () => {
  assert.equal(nombreDescarga("ferreteria-el-sur", { tipo: "cover" }), "ferreteria-el-sur-portada.jpg");
  assert.equal(nombreDescarga("ferreteria-el-sur", { tipo: "foto", id: "x" }, 3), "ferreteria-el-sur-foto-3.jpg");
  assert.equal(nombreDescarga("", { tipo: "cover" }), "negocio-portada.jpg");
  assert.equal(nombreDescarga("../Raro Nombre!", { tipo: "cover" }), "raro-nombre-portada.jpg");
});

test("leerCoverDesign: el JSON del contrato; lo que falta queda en null y un método raro se descarta", () => {
  assert.deepEqual(
    leerCoverDesign({ portada_diseno_url: "/d.jpg", portada_diseno_propuesta_url: "/p.jpg", proposal_method: "gemini" }),
    { portada_diseno_url: "/d.jpg", portada_diseno_propuesta_url: "/p.jpg", proposal_method: "gemini" });
  assert.deepEqual(leerCoverDesign({}), { portada_diseno_url: null, portada_diseno_propuesta_url: null, proposal_method: null });
  assert.deepEqual(leerCoverDesign(null), { portada_diseno_url: null, portada_diseno_propuesta_url: null, proposal_method: null });
  assert.equal(leerCoverDesign({ proposal_method: "dalle" }).proposal_method, null);
  assert.equal(leerCoverDesign({ portada_diseno_url: "  " }).portada_diseno_url, null);
});

test("leerGalleryItem: los nombres del contrato", () => {
  assert.deepEqual(
    leerGalleryItem({ foto_id: "f1", photo_url: "/f.jpg", thumb_url: "/t.jpg", design_url: "/d.jpg", design_thumb_url: "/dt.jpg",
                      proposal_url: null, proposal_method: "external" }),
    { foto_id: "f1", photo_url: "/f.jpg", thumb_url: "/t.jpg", design_url: "/d.jpg", design_thumb_url: "/dt.jpg",
      proposal_url: null, proposal_method: "external" });
});

const crudo = {
  comercio: { id: "c1", nombre: "Ferretería El Sur", slug: "ferreteria-el-sur" },
  cover: { photo_url: "/p.jpg", design_url: null, proposal_url: null, proposal_method: null },
  gallery: [
    { foto_id: "f1", photo_url: "/f1.jpg", thumb_url: "/f1-t.jpg", design_url: null, design_thumb_url: null, proposal_url: null, proposal_method: null },
    { foto_id: "f2", photo_url: "/f2.jpg", thumb_url: null, design_url: "/d2.jpg", design_thumb_url: "/d2-t.jpg", proposal_url: null, proposal_method: null },
    { photo_url: "/sin-id.jpg" },
  ],
  gemini: { available: false, reason: "Fotos con IA no disponible: interruptor apagado", cost_usd: 0, used_today: 0, daily_cap: 20, merchant_uses: 0, merchant_cost_usd: 0 },
  instructions: { version: "fotos-estilo-v1", cover: "Edit the attached photo… COVER", gallery: "Edit the attached photo… GALLERY" },
};

test("leerEstado: el JSON de §6 completo (sin IA: igual se puede leer todo lo demás)", () => {
  const e = leerEstado(crudo);
  assert.equal(e.comercio.slug, "ferreteria-el-sur");
  assert.equal(e.cover.photo_url, "/p.jpg");
  assert.deepEqual(e.gallery.map((f) => f.foto_id), ["f1", "f2"], "una fila sin id no se puede operar y se ignora");
  assert.equal(e.gemini.available, false);
  assert.equal(e.gemini.reason, "Fotos con IA no disponible: interruptor apagado");
  assert.match(e.instructions.cover, /COVER/);
  assert.equal(puedeIA(e.gemini).puede, false);
});

test("leerEstado: una respuesta vacía o rota no tira la ventana (IA apagada, sin fotos)", () => {
  for (const raw of [null, undefined, {}, "x", []]) {
    const e = leerEstado(raw);
    assert.deepEqual(e.gallery, []);
    assert.equal(e.cover.photo_url, null);
    assert.equal(e.gemini.available, false);
    assert.equal(e.instructions.cover, "");
  }
});

test("aplicarResultado: la portada toma lo que contestó el servidor y no toca la galería", () => {
  const e: PhotoStyleState = leerEstado(crudo);
  const r = aplicarResultado(e, { tipo: "cover" }, {
    tipo: "cover", data: { portada_diseno_url: null, portada_diseno_propuesta_url: "/prop.jpg", proposal_method: "gemini" },
  });
  assert.equal(r.cover.proposal_url, "/prop.jpg");
  assert.equal(r.cover.proposal_method, "gemini");
  assert.equal(r.cover.photo_url, "/p.jpg", "la foto original no cambia");
  assert.equal(r.gallery, e.gallery);
  assert.equal(e.cover.proposal_url, null, "no muta el estado anterior");
});

test("aplicarResultado: la foto de galería reemplaza sólo su fila", () => {
  const e = leerEstado(crudo);
  const nueva = leerGalleryItem({ foto_id: "f1", photo_url: "/f1.jpg", thumb_url: "/f1-t.jpg", design_url: null,
                                  proposal_url: "/prop-f1.jpg", proposal_method: "free" });
  const r = aplicarResultado(e, { tipo: "foto", id: "f1" }, { tipo: "foto", data: nueva });
  assert.equal(r.gallery[0].proposal_url, "/prop-f1.jpg");
  assert.equal(r.gallery[1], e.gallery[1]);
  assert.equal(r.cover, e.cover);
});

test("aplicarResultado: si el servidor no repite el id, se usa el de la foto que se tocó", () => {
  const e = leerEstado(crudo);
  const r = aplicarResultado(e, { tipo: "foto", id: "f2" }, { tipo: "foto", data: leerGalleryItem({ photo_url: "/f2.jpg", design_url: null }) });
  assert.equal(r.gallery[1].foto_id, "f2");
  assert.equal(r.gallery[1].design_url, null);
});

test("aplicarResultado: un resultado de otro tipo no cambia nada", () => {
  const e = leerEstado(crudo);
  assert.equal(aplicarResultado(e, { tipo: "cover" }, { tipo: "foto", data: leerGalleryItem({}) }), e);
});
