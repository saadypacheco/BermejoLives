// QA de aceptación: fotos con estilo URUKU, lado frontend (docs/fotos-estilo-uruku.md §3, §7 y §9).
// Independiente de tests/fotos-estilo.test.ts: parte de los criterios y ataca bordes y entradas raras del servidor.
import test from "node:test";
import assert from "node:assert/strict";
import {
  aplicarResultado, avisoPropuesta, estadoFoto, etiquetaConIA, leerCoverDesign, leerEstado, leerGalleryItem,
  nombreDescarga, problemaArchivoExterno, puedeIA, resumenIA, textoCosto, AVISO_REVISION, MAX_BYTES_EXTERNA,
  type GalleryItem, type GeminiState, type PhotoStyleState,
} from "../lib/fotos-estilo-pure";
import { fotosDeFicha } from "../lib/portada-diseno";
import type { GaleriaFoto } from "../lib/data-pure";

const ia = (o: Partial<GeminiState> = {}): GeminiState => ({
  available: true, reason: null, cost_usd: 0.0336, used_today: 0, daily_cap: 20, merchant_uses: 0, merchant_cost_usd: 0, ...o,
});

// ═══════════════════════════════════════════════════════════════ fotosDeFicha (ficha pública, §3)

const g = (id: string, extra: Partial<GaleriaFoto> = {}): GaleriaFoto =>
  ({ id, url: `/real/${id}.jpg`, thumb_url: `/real/${id}-t.jpg`, ...extra });
const conDis = (id: string): GaleriaFoto => g(id, { diseno_url: `/dis/${id}.jpg`, diseno_thumb_url: `/dis/${id}-t.jpg` });
const portada = { portada_url: "/real/orig.jpg", portada_thumb_url: "/real/orig-t.jpg", portada_pos: 25 };

test("fotosDeFicha: sin ningún diseño devuelve la MISMA lista de siempre (no se copia ni se toca)", () => {
  const lista = [g("a"), g("b")];
  assert.equal(fotosDeFicha({ ...portada }, lista).fotos, lista);
  assert.equal(fotosDeFicha({ ...portada, portada_diseno_url: "" }, lista).fotos, lista);
});

test("fotosDeFicha: una foto con diseño muestra la miniatura y la grande de diseño, no las reales", () => {
  const r = fotosDeFicha({ ...portada }, [conDis("a"), g("b")]);
  assert.deepEqual(r.fotos.map((f) => [f.id, f.url, f.thumb_url]), [
    ["a", "/dis/a.jpg", "/dis/a-t.jpg"],
    ["b", "/real/b.jpg", "/real/b-t.jpg"],
  ]);
});

test("fotosDeFicha: diseño sin miniatura de diseño -> thumb null (nunca la miniatura de la foto real, sería otra imagen)", () => {
  const r = fotosDeFicha({ ...portada }, [g("a", { diseno_url: "/dis/a.jpg", diseno_thumb_url: null })]);
  assert.equal(r.fotos[0].url, "/dis/a.jpg");
  assert.equal(r.fotos[0].thumb_url, null);
  const r2 = fotosDeFicha({ ...portada }, [g("a", { diseno_url: "/dis/a.jpg" })]);   // columna ausente
  assert.equal(r2.fotos[0].thumb_url, null);
});

test("fotosDeFicha: diseno_url vacío, en blanco o null cuenta como sin diseño", () => {
  for (const v of ["", "   ", null, undefined]) {
    const r = fotosDeFicha({ ...portada }, [g("a", { diseno_url: v, diseno_thumb_url: "/dis/x-t.jpg" })]);
    assert.equal(r.fotos[0].url, "/real/a.jpg", `diseno_url=${JSON.stringify(v)}`);
    assert.equal(r.fotos[0].thumb_url, "/real/a-t.jpg");
  }
});

test("fotosDeFicha: con portada de diseño la original va primera y NO se duplica aunque ya esté en la galería", () => {
  const original = g("o", { url: "/real/orig.jpg", thumb_url: "/real/orig-t.jpg" });
  const r = fotosDeFicha({ ...portada, portada_diseno_url: "/dis/portada.jpg" }, [g("a"), original, g("b")]);
  assert.equal(r.portada, "/dis/portada.jpg");
  assert.equal(r.posicion, null);
  assert.deepEqual(r.fotos.map((f) => f.id), ["o", "a", "b"], "la original primera y una sola vez");
  assert.equal(r.fotos.filter((f) => f.url === "/real/orig.jpg").length, 1);
});

test("fotosDeFicha: la portada original en la galería CON diseño de galería: aparece una sola vez, primera, con su diseño", () => {
  const original = g("o", { url: "/real/orig.jpg", thumb_url: "/real/orig-t.jpg", diseno_url: "/dis/o.jpg", diseno_thumb_url: "/dis/o-t.jpg" });
  const r = fotosDeFicha({ ...portada, portada_diseno_url: "/dis/portada.jpg" }, [g("a"), original]);
  assert.deepEqual(r.fotos.map((f) => f.id), ["o", "a"], "no se pierde ni se duplica la fila de la original (se buscó por su url real)");
  assert.equal(r.fotos[0].url, "/dis/o.jpg");
});

test("fotosDeFicha: la original que NO está en la galería se agrega primera con su miniatura real", () => {
  const r = fotosDeFicha({ ...portada, portada_diseno_url: "/dis/portada.jpg" }, [conDis("a")]);
  assert.equal(r.fotos.length, 2);
  assert.equal(r.fotos[0].url, "/real/orig.jpg");
  assert.equal(r.fotos[0].thumb_url, "/real/orig-t.jpg");
  assert.equal(r.fotos[1].url, "/dis/a.jpg");
});

test("fotosDeFicha: sin portada original pero con diseño -> el diseño arriba y la galería (con sus diseños) abajo", () => {
  const r = fotosDeFicha({ portada_url: null, portada_diseno_url: "/dis/portada.jpg" }, [conDis("a"), g("b")]);
  assert.equal(r.portada, "/dis/portada.jpg");
  assert.deepEqual(r.fotos.map((f) => f.url), ["/dis/a.jpg", "/real/b.jpg"]);
});

test("fotosDeFicha: no muta la lista ni las filas que recibe", () => {
  const filas = [conDis("a"), g("b")];
  const copia = JSON.parse(JSON.stringify(filas));
  fotosDeFicha({ ...portada, portada_diseno_url: "/dis/portada.jpg" }, filas);
  fotosDeFicha({ ...portada }, filas);
  assert.deepEqual(filas, copia);
});

test("fotosDeFicha: galería vacía, y el id de la portada original sintética no choca con uno real", () => {
  assert.deepEqual(fotosDeFicha({ ...portada }, []).fotos, []);
  const r = fotosDeFicha({ ...portada, portada_diseno_url: "/dis/portada.jpg" }, []);
  assert.equal(r.fotos.length, 1);
  assert.ok(r.fotos[0].id, "tiene id (la ficha lo usa de key)");
});

test("fotosDeFicha: la propuesta (privada) no existe para la ficha: sólo se lee diseno_url", () => {
  const fila = { ...g("a"), diseno_propuesta_url: "/dis/PROPUESTA.jpg" } as GaleriaFoto & { diseno_propuesta_url: string };
  const r = fotosDeFicha({ ...portada, portada_diseno_url: "/dis/portada.jpg" }, [fila]);
  assert.ok(!JSON.stringify(r).includes("PROPUESTA") || r.fotos.some((f) => (f as unknown as Record<string, unknown>).diseno_propuesta_url),
    "si la propuesta viaja en la fila, la ficha no la usa como imagen");
  assert.ok(!r.fotos.some((f) => f.url.includes("PROPUESTA") || f.thumb_url?.includes("PROPUESTA")));
});

// ═══════════════════════════════════════════════════════════════ puedeIA: cada motivo (§7)

test("puedeIA: disponible y con cupo -> puede, sin motivo", () => {
  assert.deepEqual(puedeIA(ia({ used_today: 19 })), { puede: true, motivo: null });
});

test("puedeIA: no disponible -> el motivo del servidor, tal cual, en español", () => {
  const motivo = "El interruptor «Fotos con IA (Gemini)» está apagado";
  assert.deepEqual(puedeIA(ia({ available: false, reason: motivo })), { puede: false, motivo });
  for (const reason of ["Falta la clave de Gemini", "Falta el modelo de imagen", "Falta el costo por imagen"]) {
    const r = puedeIA(ia({ available: false, reason }));
    assert.equal(r.puede, false);
    assert.equal(r.motivo, reason);
  }
});

test("puedeIA: no disponible SIN motivo del servidor -> igual da un motivo para mostrar (nunca null)", () => {
  const r = puedeIA(ia({ available: false, reason: null }));
  assert.equal(r.puede, false);
  assert.ok(r.motivo && r.motivo.length > 10);
});

test("puedeIA: tope del día alcanzado o superado -> no puede, y el motivo nombra el tope", () => {
  for (const usados of [20, 21, 500]) {
    const r = puedeIA(ia({ used_today: usados, daily_cap: 20 }));
    assert.equal(r.puede, false, `usados=${usados}`);
    assert.match(r.motivo ?? "", /tope de 20/);
  }
  assert.equal(puedeIA(ia({ used_today: 1, daily_cap: 1 })).puede, false);
  assert.equal(puedeIA(ia({ used_today: 0, daily_cap: 1 })).puede, true);
});

test("puedeIA: no disponible gana sobre el tope (el motivo es el de disponibilidad)", () => {
  const r = puedeIA(ia({ available: false, reason: "apagado", used_today: 99, daily_cap: 20 }));
  assert.equal(r.motivo, "apagado");
});

test("puedeIA: un tope diario de 0 bloquea la IA (el backend contesta 429 «tope de 0 fotos»)", () => {
  // GEMINI_FOTOS_TOPE_DIARIO=0 en el backend => `usados_hoy >= 0` siempre => 429. Si el front ofrece el botón igual, la persona
  // confirma el gasto y recibe un error: la ventana tendría que mostrarlo apagado.
  const r = puedeIA(ia({ used_today: 0, daily_cap: 0 }));
  assert.equal(r.puede, false);
});

test("puedeIA: el motivo no puede arrastrar la clave ni el estado crudo", () => {
  const r = puedeIA(ia({ available: false, reason: "Falta la clave" }));
  assert.ok(!/AIza|api[_-]?key=/i.test(r.motivo ?? ""));
});

// ═══════════════════════════════════════════════════════════════ textoCosto

test("textoCosto: el ejemplo de la spec y sus vecinos", () => {
  assert.equal(textoCosto(0.0336), "≈ US$ 0,034");
  assert.equal(textoCosto(0.034), "≈ US$ 0,034");
  assert.equal(textoCosto(0.0672), "≈ US$ 0,067");
  assert.equal(textoCosto(0.07), "≈ US$ 0,07");
  assert.equal(textoCosto(0.134), "≈ US$ 0,134");
  assert.equal(textoCosto(2), "≈ US$ 2,00");
  assert.equal(textoCosto(12.3456), "≈ US$ 12,346");
});

test("textoCosto: usa coma decimal, nunca punto, y no deja NaN/Infinity/negativos en pantalla", () => {
  for (const v of [0.0336, 0.07, 1, 100.5, 0]) assert.ok(!textoCosto(v).includes("."), String(v));
  for (const v of [Number.NaN, Infinity, -Infinity, -0.5, -0]) {
    assert.equal(textoCosto(v), "≈ US$ 0,00", String(v));
  }
});

test("textoCosto: lo que no es número (null/undefined/string del servidor) no rompe", () => {
  for (const v of [null, undefined, "0.03", {}, []]) {
    assert.doesNotThrow(() => textoCosto(v as unknown as number));
    assert.ok(!/NaN|undefined|null|\[object/.test(textoCosto(v as unknown as number)));
  }
});

test("textoCosto: costos de fracción de centavo se redondean a tres decimales sin pasarse", () => {
  assert.equal(textoCosto(0.0004), "≈ US$ 0,00");
  assert.equal(textoCosto(0.0005), "≈ US$ 0,001");
  assert.equal(textoCosto(0.0999), "≈ US$ 0,10");
});

test("etiquetaConIA y resumenIA usan el costo; sin costo no inventan uno", () => {
  assert.equal(etiquetaConIA(ia(), false), "Con IA ≈ US$ 0,034");
  assert.equal(etiquetaConIA(ia(), true), "Confirmar ≈ US$ 0,034");
  assert.equal(etiquetaConIA(ia({ cost_usd: 0 }), false), "Con IA");
  assert.equal(etiquetaConIA(ia({ cost_usd: 0 }), true), "Confirmar");
  assert.equal(resumenIA(ia({ used_today: 3, merchant_uses: 2, merchant_cost_usd: 0.0672 })),
    "≈ US$ 0,034 por foto · hoy 3 de 20 · este negocio: 2 (≈ US$ 0,067)");
  assert.equal(resumenIA(ia({ cost_usd: 0, daily_cap: 0 })), "este negocio: 0");
});

// ═══════════════════════════════════════════════════════════════ leer el JSON del servidor con tolerancia

test("leerEstado: basura, null y tipos equivocados no tiran la ventana", () => {
  for (const raw of [null, undefined, 42, "x", [], {}, { gallery: "no", gemini: null, cover: [] }]) {
    const e = leerEstado(raw);
    assert.deepEqual(e.gallery, []);
    assert.equal(e.gemini.available, false, "sin dato no se ofrece la IA");
    assert.equal(e.cover.proposal_url, null);
    assert.equal(e.comercio.nombre, "");
  }
});

test("leerEstado: una foto sin foto_id se descarta; los métodos desconocidos son null", () => {
  const e = leerEstado({
    gallery: [{ foto_id: "", photo_url: "/a" }, { foto_id: "f1", photo_url: "/b", proposal_method: "dalle" },
      { foto_id: "f2", photo_url: "/c", proposal_url: "/p", proposal_method: "gemini" }, null, 7],
    gemini: { available: "true" },
  });
  assert.deepEqual(e.gallery.map((f) => f.foto_id), ["f1", "f2"]);
  assert.equal(e.gallery[0].proposal_method, null);
  assert.equal(e.gallery[1].proposal_method, "gemini");
  assert.equal(e.gemini.available, false, "sólo `true` de verdad prende la IA (un string no)");
});

test("leerEstado: los strings en blanco son null y los números raros son 0", () => {
  const e = leerEstado({ cover: { photo_url: "   ", design_url: "" }, gemini: { cost_usd: "0.03", used_today: NaN, daily_cap: null } });
  assert.equal(e.cover.photo_url, null);
  assert.equal(e.cover.design_url, null);
  assert.equal(e.gemini.cost_usd, 0);
  assert.equal(e.gemini.used_today, 0);
  assert.equal(e.gemini.daily_cap, null, "un tope que no viene no es un 0");
  assert.equal(leerEstado({ gemini: { daily_cap: 0 } }).gemini.daily_cap, 0, "y un 0 explícito se conserva");
});

test("leerCoverDesign / leerGalleryItem: tolerantes y sin inventar propuesta", () => {
  assert.deepEqual(leerCoverDesign(null), { portada_diseno_url: null, portada_diseno_propuesta_url: null, proposal_method: null });
  assert.equal(leerCoverDesign({ proposal_method: "free", portada_diseno_propuesta_url: "/p" }).proposal_method, "free");
  assert.equal(leerGalleryItem({}).proposal_url, null);
  assert.equal(leerGalleryItem({ foto_id: 5 }).foto_id, "", "un id que no es string no se convierte en uno válido");
});

// ═══════════════════════════════════════════════════════════════ aplicarResultado: la propuesta no publica

const estado = (): PhotoStyleState => leerEstado({
  comercio: { id: "c", nombre: "N", slug: "n" },
  cover: { photo_url: "/o.jpg", design_url: "/dv.jpg", proposal_url: null },
  gallery: [{ foto_id: "f1", photo_url: "/1.jpg" }, { foto_id: "f2", photo_url: "/2.jpg", design_url: "/d2.jpg" }],
  gemini: { available: true, cost_usd: 0.0336, daily_cap: 20 },
});

test("aplicarResultado: una propuesta nueva de galería no toca el diseño vigente ni las otras filas", () => {
  const item: GalleryItem = { foto_id: "f2", photo_url: "/2.jpg", thumb_url: null, design_url: "/d2.jpg", design_thumb_url: null, proposal_url: "/p2.jpg", proposal_method: "free" };
  const e = aplicarResultado(estado(), { tipo: "foto", id: "f2" }, { tipo: "foto", data: item });
  assert.equal(e.gallery[1].proposal_url, "/p2.jpg");
  assert.equal(e.gallery[1].design_url, "/d2.jpg");
  assert.deepEqual(e.gallery[0], estado().gallery[0]);
  assert.deepEqual(e.cover, estado().cover);
});

test("aplicarResultado: el resultado de otra clase de objetivo no se aplica, y no muta el estado de entrada", () => {
  const antes = estado();
  const copia = JSON.parse(JSON.stringify(antes));
  const r = aplicarResultado(antes, { tipo: "cover" }, { tipo: "foto", data: leerGalleryItem({ foto_id: "f1" }) });
  assert.equal(r, antes);
  aplicarResultado(antes, { tipo: "foto", id: "f1" }, { tipo: "foto", data: leerGalleryItem({ foto_id: "f1", proposal_url: "/x" }) });
  assert.deepEqual(antes, copia);
});

test("aplicarResultado: portada con propuesta nueva mantiene el diseño vigente que devolvió el servidor", () => {
  const e = aplicarResultado(estado(), { tipo: "cover" }, {
    tipo: "cover", data: { portada_diseno_url: "/dv.jpg", portada_diseno_propuesta_url: "/pn.jpg", proposal_method: "external" },
  });
  assert.deepEqual([e.cover.design_url, e.cover.proposal_url, e.cover.proposal_method], ["/dv.jpg", "/pn.jpg", "external"]);
  assert.equal(e.cover.photo_url, "/o.jpg", "la original no cambia");
});

test("aplicarResultado: un id que no está en la galería no inventa filas", () => {
  const e = aplicarResultado(estado(), { tipo: "foto", id: "nada" }, { tipo: "foto", data: leerGalleryItem({ foto_id: "nada" }) });
  assert.equal(e.gallery.length, 2);
});

// ═══════════════════════════════════════════════════════════════ estado, aviso, archivo externo, descarga

test("estadoFoto/avisoPropuesta: la IA y lo hecho afuera piden revisar; la plantilla gratis no", () => {
  assert.equal(avisoPropuesta("free"), null);
  assert.equal(avisoPropuesta(null), null);
  assert.equal(avisoPropuesta(undefined), null);
  for (const m of ["gemini", "external"] as const) assert.ok(avisoPropuesta(m)!.endsWith(AVISO_REVISION));
  assert.equal(estadoFoto({ proposal_url: "/p", design_url: "/d" }).clave, "propuesta");
});

test("problemaArchivoExterno: tipos y bordes de 15 MB", () => {
  assert.equal(problemaArchivoExterno({ type: "image/png", size: 1 }), null);
  assert.equal(problemaArchivoExterno({ type: "image/jpeg", size: MAX_BYTES_EXTERNA }), null, "justo 15 MB sirve");
  assert.match(problemaArchivoExterno({ type: "image/webp", size: MAX_BYTES_EXTERNA + 1 }) ?? "", /15 MB/);
  assert.match(problemaArchivoExterno({ type: "image/png", size: 0 }) ?? "", /vac/);
  for (const type of ["image/gif", "image/svg+xml", "application/pdf", "text/html", "", "image/PNG", "image/heic"]) {
    assert.ok(problemaArchivoExterno({ type, size: 100 }), `tipo ${JSON.stringify(type)} debería rechazarse`);
  }
});

test("nombreDescarga: sólo caracteres seguros, sin path traversal ni vacío", () => {
  assert.equal(nombreDescarga("ferreteria-el-sur", { tipo: "cover" }), "ferreteria-el-sur-portada.jpg");
  assert.equal(nombreDescarga("ferreteria-el-sur", { tipo: "foto", id: "f1" }, 3), "ferreteria-el-sur-foto-3.jpg");
  assert.equal(nombreDescarga("ferreteria-el-sur", { tipo: "foto", id: "f1" }), "ferreteria-el-sur-foto-1.jpg");
  for (const feo of ["../../etc/passwd", "a/b\\c", "Ñandú & Co.", "", "   ", "..", "<script>", "a\u0000b"]) {
    const n = nombreDescarga(feo, { tipo: "cover" });
    assert.match(n, /^[a-z0-9-]+-portada\.jpg$/, JSON.stringify(feo));
    assert.ok(!n.includes("..") && !n.includes("/") && !n.includes("\\"));
  }
});
