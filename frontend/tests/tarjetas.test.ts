// «Cargar tarjetas» (docs/carga-tarjetas.md): validación de archivos, texto del estado de la
// ubicación, parche del PATCH, regla de promover y que los archivos nuevos no traigan emojis.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  MAX_ARCHIVOS, MAX_BYTES, MSG_SIN_RUTAS, chipUbicacion, diffPatch, erroresDeRespuesta, esRutaAusente, esTarjeta,
  formDeItem, hayCambios, mensajeError, paramFuente, puedePromover, resumenCarga, textoUbicar, tienePunto,
  tipoPermitido, validarArchivos,
} from "../lib/tarjetas-pure";

const f = (name: string, size: number, type: string) => ({ name, size, type });

test("validarArchivos: acepta JPEG, PNG y WebP; rechaza el resto con motivo", () => {
  const r = validarArchivos([
    f("a.jpg", 1000, "image/jpeg"), f("b.png", 1000, "image/png"), f("c.webp", 1000, "image/webp"),
    f("d.gif", 1000, "image/gif"), f("e.pdf", 1000, "application/pdf"),
  ]);
  assert.deepEqual(r.validos.map((x) => x.name), ["a.jpg", "b.png", "c.webp"]);
  assert.deepEqual(r.errores.map((x) => x.archivo), ["d.gif", "e.pdf"]);
  assert.match(r.errores[0].motivo, /JPEG, PNG ni WebP/);
});

test("validarArchivos: tipo vacío se acepta por extensión (celulares que no lo informan)", () => {
  assert.equal(tipoPermitido(f("IMG_1.JPG", 10, "")), true);
  assert.equal(tipoPermitido(f("IMG_1.heic", 10, "")), false);
  assert.equal(tipoPermitido(f("sin-extension", 10, "")), false);
});

test("validarArchivos: 10 MB es el tope y vacío no sirve", () => {
  const r = validarArchivos([f("justo.jpg", MAX_BYTES, "image/jpeg"), f("grande.jpg", MAX_BYTES + 1, "image/jpeg"), f("vacio.jpg", 0, "image/jpeg")]);
  assert.deepEqual(r.validos.map((x) => x.name), ["justo.jpg"]);
  assert.equal(r.errores.length, 2);
  assert.match(r.errores[0].motivo, /máximo es 10 MB/);
  assert.match(r.errores[1].motivo, /vacío/);
});

test("validarArchivos: hasta 20 en total, contando las ya elegidas", () => {
  const veinticinco = Array.from({ length: 25 }, (_, i) => f(`t${i}.jpg`, 10, "image/jpeg"));
  const r = validarArchivos(veinticinco);
  assert.equal(r.validos.length, MAX_ARCHIVOS);
  assert.equal(r.errores.length, 5);
  assert.match(r.errores[0].motivo, /hasta 20/);
  const r2 = validarArchivos(veinticinco.slice(0, 3), 18);
  assert.equal(r2.validos.length, 2);
  assert.equal(r2.errores.length, 1);
});

test("resumenCarga: «N tarjetas leídas · M con problemas», con singular", () => {
  assert.equal(resumenCarga([1, 2, 3, 4], [1]).texto, "4 tarjetas leídas · 1 con problema");
  assert.equal(resumenCarga([1], [1, 2]).texto, "1 tarjeta leída · 2 con problemas");
  assert.equal(resumenCarga(undefined, null).texto, "0 tarjetas leídas · 0 con problemas");
});

test("erroresDeRespuesta: lee defensivo {archivo, motivo}", () => {
  assert.deepEqual(erroresDeRespuesta({ errores: [{ archivo: "x.jpg", motivo: "ilegible" }] }), [{ archivo: "x.jpg", motivo: "ilegible" }]);
  assert.deepEqual(erroresDeRespuesta({ errores: [{}] }), [{ archivo: "(sin nombre)", motivo: "No se pudo leer" }]);
  assert.deepEqual(erroresDeRespuesta({}), []);
  assert.deepEqual(erroresDeRespuesta(null), []);
});

test("404 y 405 dicen que el servidor es viejo; otros errores conservan su mensaje", () => {
  assert.equal(esRutaAusente(Object.assign(new Error("x"), { status: 404 })), true);
  assert.equal(esRutaAusente(Object.assign(new Error("x"), { status: 405 })), true);
  assert.equal(esRutaAusente(Object.assign(new Error("x"), { status: 500 })), false);
  assert.equal(mensajeError(Object.assign(new Error("Not Found"), { status: 404 }), "x"), MSG_SIN_RUTAS);
  assert.equal(MSG_SIN_RUTAS, "Esta versión del servidor todavía no tiene la carga de tarjetas");
  assert.equal(mensajeError(new Error("boom"), "x"), "boom");
  assert.equal(mensajeError("raro", "por defecto"), "por defecto");
});

test("chipUbicacion: el texto de cada estado, con ícono además del color", () => {
  assert.equal(chipUbicacion("aproximada").texto, "Ubicación aproximada: confirmá el punto");
  assert.equal(chipUbicacion("confirmada").texto, "Ubicación confirmada");
  assert.equal(chipUbicacion("no_encontrada").texto, "No se encontró la dirección: marcá el punto");
  assert.equal(chipUbicacion("confirmada").tono, "ok");
  assert.equal(chipUbicacion("no_encontrada").tono, "error");
  assert.match(chipUbicacion(null).texto, /marcá el punto/);
  assert.match(chipUbicacion("algo-nuevo").texto, /marcá el punto/);
});

test("textoUbicar: dice cuando no encontró y cuando sí (aproximada)", () => {
  assert.match(textoUbicar({ encontrado: false }), /No se encontró/);
  assert.match(textoUbicar({ encontrado: true, display_name: "Calle 1, Bermejo" }), /Calle 1, Bermejo.*aproximada/);
  assert.match(textoUbicar({ encontrado: true }), /aproximada/);
});

test("diffPatch: sólo lo que cambió, sin espacios de borde; vaciar un campo manda vacío", () => {
  const fila = { nombre: "Ferretería Sur", direccion: "Av. 1", telefono: null, whatsapp: "59170000000", website: null, email: null, rubro_slug: "ferreteria" };
  const form = formDeItem(fila);
  assert.equal(form.telefono, "");
  assert.deepEqual(diffPatch(fila, form), {});
  assert.equal(hayCambios(diffPatch(fila, form)), false);

  const editado = { ...form, nombre: "  Ferretería Sur SRL ", telefono: "4 6112233", whatsapp: "", rubro_slug: "ferreteria" };
  assert.deepEqual(diffPatch(fila, editado), { nombre: "Ferretería Sur SRL", telefono: "4 6112233", whatsapp: "" });
  assert.equal(hayCambios(diffPatch(fila, editado)), true);
  // Sólo espacios agregados a un campo vacío no es un cambio.
  assert.deepEqual(diffPatch(fila, { ...form, email: "   " }), {});
});

test("puedePromover: sin punto, sin nombre o con cambios sin guardar no se puede, y dice por qué", () => {
  const punto = { lat: -22.73, lng: -64.34 };
  assert.deepEqual(puedePromover(punto, { nombre: "X" }, false), { ok: true, motivo: "" });
  assert.match(puedePromover({ lat: null, lng: null }, { nombre: "X" }, false).motivo, /Falta el punto/);
  assert.match(puedePromover({ lat: -22, lng: null }, { nombre: "X" }, false).motivo, /Falta el punto/);
  assert.match(puedePromover(punto, { nombre: "  " }, false).motivo, /Falta el nombre/);
  assert.match(puedePromover(punto, { nombre: "X" }, true).motivo, /Guardá los cambios/);
  assert.equal(puedePromover(punto, { nombre: "X" }, true).ok, false);
});

test("tienePunto, esTarjeta y paramFuente", () => {
  assert.equal(tienePunto({ lat: 0, lng: 0 }), true);
  assert.equal(tienePunto({ lat: null, lng: 1 }), false);
  assert.equal(tienePunto({ lat: Number.NaN, lng: 1 }), false);
  assert.equal(esTarjeta({ fuente: "tarjeta" }), true);
  assert.equal(esTarjeta({ fuente: "osm" }), false);
  assert.equal(paramFuente("todas"), undefined);
  assert.equal(paramFuente("osm"), "osm");
  assert.equal(paramFuente("tarjeta"), "tarjeta");
});

test("archivos nuevos: sin emojis ni secretos, y la foto privada no lleva el token en la URL", () => {
  const emoji = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
  for (const rel of ["lib/tarjetas-pure.ts", "components/importados-tarjetas.tsx"]) {
    const src = readFileSync(resolve(process.cwd(), rel), "utf8");
    assert.equal(emoji.test(src), false, `${rel} tiene un emoji`);
    assert.equal(/SERVICE_ROLE/.test(src), false, `${rel} nombra la service role`);
  }
  const api = readFileSync(resolve(process.cwd(), "lib/api.ts"), "utf8");
  assert.equal(/importados\/\$\{[^}]+\}\/foto[^`]*[?&]token/.test(api), false);
});
