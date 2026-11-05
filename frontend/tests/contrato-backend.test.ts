// Cambios de contrato con el backend (5/11): «¿te contestó?» con token y sesión,
// recuperar cuenta con token, archivos privados del admin, bajas «sin verificar» y
// el aviso del alta oculta. Todo lógica pura: sin red ni navegador.
import test from "node:test";
import assert from "node:assert/strict";
import { cuerpoRespondio, leadDeRespuesta, resultadoRespondio } from "../lib/contestaron";
import { SESION_MAX, sesionValida, nuevaSesion } from "../lib/sesion";
import { recuperacionVigente, VIGENCIA_RECUPERACION_MS, type RecuperacionEnCurso } from "../lib/recuperacion";
import { rutaPrivada } from "../lib/archivo-privado";
import { botonReactivar, confirmarReactivar, esSinVerificar, etiquetaBaja, resumenBajas } from "../lib/baja-comercio";
import { avisoDeAlta } from "../lib/alta-comercio";

// ---- «¿Te contestó?» ----

test("leadDeRespuesta: necesita id y token; sin uno de los dos no se puede votar", () => {
  assert.deepEqual(leadDeRespuesta({ ok: true, id: "L1", token: "abc" }), { id: "L1", token: "abc" });
  assert.equal(leadDeRespuesta({ ok: true, id: "L1" }), null);
  assert.equal(leadDeRespuesta({ ok: true, token: "abc" }), null);
  assert.equal(leadDeRespuesta({ id: "", token: "" }), null);
  assert.equal(leadDeRespuesta(null), null);
  assert.equal(leadDeRespuesta("x"), null);
});

test("cuerpoRespondio: {respondio, token} y la sesión sólo si hay", () => {
  assert.deepEqual(cuerpoRespondio(true, "tk"), { respondio: true, token: "tk" });
  assert.deepEqual(cuerpoRespondio(false, "tk", "s-1"), { respondio: false, token: "tk", sesion: "s-1" });
  assert.deepEqual(cuerpoRespondio(true, "tk", ""), { respondio: true, token: "tk" });
});

test("resultadoRespondio: 425 y 429 en silencio; 403 y 410 descartan; ya votado", () => {
  assert.equal(resultadoRespondio(200, { ok: true }), "registrado");
  assert.equal(resultadoRespondio(200, { ok: true, ya: true }), "ya");
  assert.equal(resultadoRespondio(425), "silencio");
  assert.equal(resultadoRespondio(429), "silencio");
  assert.equal(resultadoRespondio(403), "descartar");
  assert.equal(resultadoRespondio(410), "descartar");
  assert.equal(resultadoRespondio(500), "error");
  assert.equal(resultadoRespondio(200), "registrado");
});

test("sesionValida: la misma regla que el backend (letras, números y guion, hasta 40)", () => {
  assert.equal(sesionValida("a1b2-C3"), true);
  assert.equal(sesionValida(nuevaSesion()), true);          // UUID (36) o `s…` de respaldo
  assert.equal(sesionValida("x".repeat(SESION_MAX)), true);
  assert.equal(sesionValida("x".repeat(SESION_MAX + 1)), false);
  assert.equal(sesionValida(""), false);
  assert.equal(sesionValida("con espacio"), false);
  assert.equal(sesionValida("a_b"), false);
  assert.equal(sesionValida(null), false);
});

// ---- Recuperar cuenta ----

const base: RecuperacionEnCurso = { whatsapp: "+591 7000-0001", codigo: "123456", wa_link: "https://wa.me/x", token: "t".repeat(32), en: 1_000_000 };

test("recuperacionVigente: mismo número (aunque venga con otro formato) y sin vencer", () => {
  assert.equal(recuperacionVigente(base, "59170000001", base.en + 60_000), true);
  assert.equal(recuperacionVigente(base, "59170000002", base.en + 60_000), false);
});

test("recuperacionVigente: vence a los 14 minutos (el código dura 15) y no acepta relojes raros", () => {
  assert.equal(recuperacionVigente(base, "59170000001", base.en + VIGENCIA_RECUPERACION_MS - 1), true);
  assert.equal(recuperacionVigente(base, "59170000001", base.en + VIGENCIA_RECUPERACION_MS), false);
  assert.equal(recuperacionVigente(base, "59170000001", base.en - 1), false);
});

test("recuperacionVigente: sin token o sin código no sirve; otro negocio elegido tampoco", () => {
  assert.equal(recuperacionVigente(null, "59170000001", base.en), false);
  assert.equal(recuperacionVigente({ ...base, token: "" }, "59170000001", base.en), false);
  assert.equal(recuperacionVigente({ ...base, codigo: "" }, "59170000001", base.en), false);
  const conNegocio = { ...base, comercioId: "A" };
  assert.equal(recuperacionVigente(conNegocio, "59170000001", base.en, "A"), true);
  assert.equal(recuperacionVigente(conNegocio, "59170000001", base.en, "B"), false);
  assert.equal(recuperacionVigente(conNegocio, "59170000001", base.en), true);
});

// ---- Archivos privados del admin ----

test("rutaPrivada: sólo las dos rutas del backend, con ruta o con la URL del propio backend", () => {
  const api = "https://api.uruku.bo";
  assert.equal(rutaPrivada("/admin/pagos/abc-123/comprobante", api), "/admin/pagos/abc-123/comprobante");
  assert.equal(rutaPrivada("/admin/solicitudes-cambio-numero/9f/foto", api), "/admin/solicitudes-cambio-numero/9f/foto");
  assert.equal(rutaPrivada("https://api.uruku.bo/admin/pagos/abc/comprobante", api), "/admin/pagos/abc/comprobante");
  assert.equal(rutaPrivada("https://api.uruku.bo/admin/pagos/abc/comprobante", "https://api.uruku.bo/"), "/admin/pagos/abc/comprobante");
});

test("rutaPrivada: nunca otro origen, otra ruta ni un dato vacío (el Bearer no sale del backend)", () => {
  const api = "https://api.uruku.bo";
  assert.equal(rutaPrivada("https://malo.example/admin/pagos/abc/comprobante", api), null);
  assert.equal(rutaPrivada("//malo.example/admin/pagos/abc/comprobante", api), null);
  assert.equal(rutaPrivada("/admin/pagos/abc/otra-cosa", api), null);
  assert.equal(rutaPrivada("/admin/pagos/a/b/comprobante", api), null);
  assert.equal(rutaPrivada("/admin/pagos/abc/comprobante?x=1", api), null);
  assert.equal(rutaPrivada("https://x.supabase.co/storage/comprobante.jpg", api), null);
  assert.equal(rutaPrivada("", api), null);
  assert.equal(rutaPrivada(null, api), null);
  assert.equal(rutaPrivada(undefined, api), null);
});

// ---- Dados de baja ----

test("«sin_verificar» se ve como «Sin verificar» y el botón es «Aprobar»", () => {
  assert.equal(esSinVerificar("sin_verificar"), true);
  assert.deepEqual(etiquetaBaja("sin_verificar"), { texto: "Sin verificar", icono: "reloj" });
  assert.equal(botonReactivar("sin_verificar").texto, "Aprobar");
  assert.equal(botonReactivar("sin_verificar").enCurso, "Aprobando…");
  assert.match(confirmarReactivar("sin_verificar", "Rústico"), /Aprobar "Rústico"/);
});

test("el resto de las bajas sigue igual: admin, sin motivo y «Reactivar»", () => {
  assert.equal(esSinVerificar("admin"), false);
  assert.equal(esSinVerificar(null), false);
  assert.equal(etiquetaBaja("admin").texto, "Dado de baja por el admin");
  assert.equal(etiquetaBaja(null).texto, "Sin motivo registrado");
  assert.equal(etiquetaBaja(undefined).texto, "Sin motivo registrado");
  assert.equal(botonReactivar("admin").texto, "Reactivar");
  assert.equal(botonReactivar(null).texto, "Reactivar");
  assert.match(confirmarReactivar("admin", ""), /Reactivar "este negocio"/);
});

test("resumenBajas: singular, plural y cuántos están sin verificar", () => {
  assert.match(resumenBajas(1, 0), /^1 negocio dado de baja\./);
  assert.match(resumenBajas(3, 0), /^3 negocios dados de baja\./);
  assert.match(resumenBajas(3, 2), /3 negocios dados de baja \(2 sin verificar\)/);
});

// ---- Alta oculta ----

test("avisoDeAlta: sólo si el backend marcó oculto_hasta_confirmar", () => {
  assert.equal(avisoDeAlta({ oculto_hasta_confirmar: true, aviso: "Tu negocio sale al confirmar." }), "Tu negocio sale al confirmar.");
  assert.match(avisoDeAlta({ oculto_hasta_confirmar: true }) ?? "", /todavía no se ve/);
  assert.equal(avisoDeAlta({ oculto_hasta_confirmar: false, aviso: "x" }), null);
  assert.equal(avisoDeAlta({ aviso: "x" }), null);
  assert.equal(avisoDeAlta(null), null);
});
