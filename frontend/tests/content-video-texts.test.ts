// Tests de los textos del video (plantillas v2, docs/contenido-redes-tecnico.md §16.6, §16.9 y §16.10).
// Cubren las funciones puras de `lib/content-pure.ts`: el validador que replica al del backend,
// el origen de los textos y cuándo una pieza v2 no se puede aprobar.
// Se corren con `npm test` (tsc → node --test).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  aprobableEnLote, chipsEditables, esPiezaV2, motivoNoAprobable, origenTextosVideo,
  validateVideoTexts, validateVideoTextsPorCampo, type VideoTextsEditable,
} from "../lib/content-pure";

const RAIZ = process.cwd();   // `npm test` corre en frontend/

const BUENOS: VideoTextsEditable = {
  kick: "NUEVA TEMPORADA", title1: "Camperas que", title2: "ya llegaron",
  subtitle: "Eco cuero, doble faz y más modelos", search_term: "camperas",
};

test("validateVideoTexts: los textos del ejemplo de la spec salen en verde", () => {
  assert.deepEqual(validateVideoTexts(BUENOS, ["Eco cuero con cinturón", null, ""], "comercio_del_dia"), []);
});

test("validateVideoTexts: kick, subtítulo y frases son opcionales; títulos y búsqueda no", () => {
  const sin: VideoTextsEditable = { kick: null, title1: "", title2: " ", subtitle: null, search_term: "" };
  const o = validateVideoTexts(sin, [], "comercio_del_dia");
  assert.equal(o.length, 3);
  assert.ok(o.every((x) => x.endsWith("es obligatorio")), o.join(" | "));
});

test("validateVideoTexts: largos por campo (kick 22, título 18, subtítulo 42, búsqueda 16, frase 30)", () => {
  const largo = (n: number) => "a".repeat(n);
  assert.deepEqual(validateVideoTexts({ ...BUENOS, kick: largo(22) }, [], "ofertas"), []);
  assert.equal(validateVideoTexts({ ...BUENOS, kick: largo(23) }, [], "ofertas").length, 1);
  assert.equal(validateVideoTexts({ ...BUENOS, title1: largo(19) }, [], "ofertas").length, 1);
  assert.equal(validateVideoTexts({ ...BUENOS, subtitle: largo(43) }, [], "ofertas").length, 1);
  assert.equal(validateVideoTexts({ ...BUENOS, search_term: largo(17) }, [], "ofertas").length, 1);
  assert.equal(validateVideoTexts(BUENOS, [`ab ${largo(28)}`], "comercio_del_dia").length, 1);
  assert.deepEqual(validateVideoTexts(BUENOS, [`ab ${largo(27)}`], "comercio_del_dia"), []);
});

test("validateVideoTexts: palabras (título 1 a 4, búsqueda 1 o 2, frase 2 a 5)", () => {
  assert.equal(validateVideoTexts({ ...BUENOS, title1: "a b c d" }, [], "ofertas").length, 0);
  assert.equal(validateVideoTexts({ ...BUENOS, title1: "a b c d e" }, [], "ofertas").length, 1);
  assert.equal(validateVideoTexts({ ...BUENOS, search_term: "a b c" }, [], "ofertas").length, 1);
  assert.equal(validateVideoTexts(BUENOS, ["sola"], "comercio_del_dia").length, 1);
  assert.equal(validateVideoTexts(BUENOS, ["una dos tres cuatro cinco seis"], "comercio_del_dia").length, 1);
});

test("validateVideoTexts: sin dígitos, sin Bs, $ ni US$", () => {
  const con = (subtitle: string) => validateVideoTexts({ ...BUENOS, subtitle }, [], "ofertas");
  assert.ok(con("Desde 50 pesos").some((x) => /números/.test(x)));
  assert.ok(con("Todo en Bs").some((x) => /plata/.test(x)));
  assert.ok(con("Mucho $").some((x) => /plata/.test(x)));
  assert.ok(con("Precio en US$").some((x) => /plata/.test(x)));
  // «Bs» cuenta como palabra entera: «Absoluta» no.
  assert.deepEqual(con("Absoluta calidad"), []);
});

test("validateVideoTexts: sin emoji, links, @, dominios, códigos ni claves", () => {
  const con = (subtitle: string) => validateVideoTexts({ ...BUENOS, subtitle }, [], "ofertas");
  assert.ok(con("Venga hoy \u{1F600}").some((x) => /emoji/.test(x)));
  assert.ok(con("Mire uruku.bo").some((x) => /links/.test(x)));
  assert.ok(con("Sígalo en @uruku").some((x) => /links/.test(x)));
  assert.ok(con("Sitio https://x.test").some((x) => /links/.test(x)));
  assert.ok(con("Código URUKU-ABCD").some((x) => /códigos/.test(x)));
  assert.ok(con("Escriba CONFIRMAR-ABC").some((x) => /códigos/.test(x)));
  assert.ok(con("Su clave PEDRO-XYZWQ").some((x) => /códigos/.test(x)));
  assert.deepEqual(con("Ropa. Nueva temporada"), []);
});

test("validateVideoTexts: lo que no se promete", () => {
  const con = (subtitle: string) => validateVideoTexts({ ...BUENOS, subtitle }, [], "ofertas");
  for (const f of ["El mejor local", "Envíos a todo el país", "Con garantía", "Más barato", "Próximamente"]) {
    assert.ok(con(f).some((x) => /promete/.test(x)), f);
  }
});

test("validateVideoTexts: «cuero» sólo como «eco cuero»", () => {
  const con = (subtitle: string) => validateVideoTexts({ ...BUENOS, subtitle }, [], "ofertas");
  assert.deepEqual(con("Eco cuero con cinturón"), []);
  assert.deepEqual(con("ECO  CUERO"), []);
  assert.ok(con("Camperas de cuero").some((x) => /eco cuero/.test(x)));
  assert.ok(con("Cuero legítimo").some((x) => /eco cuero/.test(x)));
  assert.ok(con("Eco cuero y cuero").some((x) => /eco cuero/.test(x)));
});

test("validateVideoTexts: rechaza voseo y tuteo, acepta el trato de usted", () => {
  const con = (subtitle: string) => validateVideoTexts({ ...BUENOS, subtitle }, [], "ofertas");
  for (const f of ["Buscá su campera", "Mirá lo nuevo", "Vení hoy", "Si querés, escribile", "Tú eliges", "Puedes pasar", "Encuentra tu talle", "Para ti"]) {
    assert.ok(con(f).some((x) => /voseo/.test(x)), f);
  }
  for (const f of ["Consulte precio directo con el local", "Búsquelo en Uruku", "Venga a conocerlo", "Busca el local", "Encuentra Bolivia"]) {
    assert.deepEqual(con(f), [], f);
  }
});

test("validateVideoTexts: en ofertas la frase de cada foto no se valida (es el nombre del comercio)", () => {
  assert.deepEqual(validateVideoTexts(BUENOS, ["Calzados Luz 2"], "ofertas"), []);
  assert.ok(validateVideoTexts(BUENOS, ["Calzados Luz 2"], "comercio_del_dia").length > 0);
});

test("validateVideoTextsPorCampo: separa las objeciones por campo y por foto", () => {
  const r = validateVideoTextsPorCampo({ ...BUENOS, title2: "ya llegó 2" }, ["ok total", "dos 3"], "comercio_del_dia");
  assert.deepEqual(Object.keys(r.campos), ["title2"]);
  assert.equal(r.chips.length, 2);
  assert.deepEqual(r.chips[0], []);
  assert.equal(r.chips[1].length, 1);
});

test("origenTextosVideo: Gemini, a mano, texto fijo", () => {
  assert.equal(origenTextosVideo("gemini:gemini-2.5-flash"), "Propuesto por Gemini");
  assert.equal(origenTextosVideo("human"), "Escrito a mano");
  assert.equal(origenTextosVideo("template"), "Texto fijo");
  assert.equal(origenTextosVideo(null), "");
  assert.equal(origenTextosVideo("gemini"), "");
});

test("esPiezaV2 y chipsEditables", () => {
  assert.equal(esPiezaV2({ template_version: 2 }), true);
  assert.equal(esPiezaV2({ template_version: 1, video_texts: {} }), false);
  assert.equal(esPiezaV2({}), false);
  assert.equal(esPiezaV2({ video_texts: { title1: "x" } }), true);
  assert.equal(chipsEditables("comercio_del_dia"), true);
  assert.equal(chipsEditables("ofertas"), false);
});

test("motivoNoAprobable y aprobableEnLote: objeciones de los textos y fotos marcadas sin confirmar (§16.9)", () => {
  assert.equal(motivoNoAprobable({}), null);                                   // pieza v1
  assert.match(motivoNoAprobable({ video_texts_checks: ["Título: es obligatorio"] }) ?? "", /textos del video/);
  const marcada = [{ photo_flags: ["price_or_code_visible"] }, { photo_flags: [] }];
  assert.match(motivoNoAprobable({ sources: marcada, photo_flags_ok: false }) ?? "", /fotos marcadas/);
  assert.equal(motivoNoAprobable({ sources: marcada, photo_flags_ok: true }), null);
  assert.equal(motivoNoAprobable({ sources: [{ photo_flags: [] }], photo_flags_ok: false }), null);

  const base = { status: "ready_for_review", caption_checks: [], caption_edited: false };
  assert.equal(aprobableEnLote(base), true);
  assert.equal(aprobableEnLote({ ...base, video_texts_checks: ["x"] }), false);
  assert.equal(aprobableEnLote({ ...base, sources: marcada, photo_flags_ok: false }), false);
  assert.equal(aprobableEnLote({ ...base, sources: marcada, photo_flags_ok: true }), true);
});

test("el cliente expone los dos endpoints nuevos y el estado no_renderer", () => {
  const t = readFileSync(resolve(RAIZ, "lib/content.ts"), "utf8");
  assert.ok(t.includes('"no_renderer"'));
  assert.ok(t.includes("/video-texts`") && t.includes("/video-texts/propose`"));
  assert.ok(/video-texts`, \{ method: "PATCH", body \}/.test(t));
  assert.ok(/video-texts\/propose`, \{ method: "POST" \}/.test(t));
});
