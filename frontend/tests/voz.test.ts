// Búsqueda por voz: lógica pura de lib/voz (idioma, normalización, errores).
import test from "node:test";
import assert from "node:assert/strict";
import {
  constructorVoz, debeReintentarConRespaldo, errorDeVoz, idiomaVoz, LARGO_MAX_VOZ,
  MENSAJES_VOZ, normalizarTextoVoz, SILENCIO_MAX_MS, textoDeEvento,
  type ConstructorReconocedor, type EventoResultadoVoz,
} from "../lib/voz";

const Falso = function () {} as unknown as ConstructorReconocedor;
const Otro = function () {} as unknown as ConstructorReconocedor;

test("constructorVoz: usa el estándar, cae en webkit y devuelve null si no hay", () => {
  assert.equal(constructorVoz({ SpeechRecognition: Falso, webkitSpeechRecognition: Otro }), Falso);
  assert.equal(constructorVoz({ webkitSpeechRecognition: Otro }), Otro);
  assert.equal(constructorVoz({}), null);
  assert.equal(constructorVoz(null), null);
  assert.equal(constructorVoz(undefined), null);
});

test("idiomaVoz: es-BO primero y es de respaldo", () => {
  assert.equal(idiomaVoz(false), "es-BO");
  assert.equal(idiomaVoz(true), "es");
});

test("normalizarTextoVoz: espacios y puntuación del dictado", () => {
  assert.equal(normalizarTextoVoz("  zapatillas   nike. "), "zapatillas nike");
  assert.equal(normalizarTextoVoz("¿Dónde hay farmacia?"), "Dónde hay farmacia");
  assert.equal(normalizarTextoVoz("\n celulares \t"), "celulares");
  assert.equal(normalizarTextoVoz("..."), "");
  assert.equal(normalizarTextoVoz(""), "");
  assert.equal(normalizarTextoVoz(null), "");
  assert.equal(normalizarTextoVoz(undefined), "");
});

test("normalizarTextoVoz: conserva tildes, ñ y puntos internos", () => {
  assert.equal(normalizarTextoVoz("pañales de 3.5 kg"), "pañales de 3.5 kg");
  assert.equal(normalizarTextoVoz("Cafetería Ñandú"), "Cafetería Ñandú");
});

test("normalizarTextoVoz: corta lo larguísimo en límite de palabra", () => {
  const largo = Array.from({ length: 60 }, () => "palabra").join(" ");
  const r = normalizarTextoVoz(largo);
  assert.ok(r.length <= LARGO_MAX_VOZ);
  assert.ok(!r.endsWith(" "));
  assert.ok(r.endsWith("palabra"), "no corta una palabra por la mitad");
});

function evento(rs: Array<{ f: boolean; t: string }>): EventoResultadoVoz {
  return { results: rs.map((r) => Object.assign([{ transcript: r.t }], { isFinal: r.f })) };
}

test("textoDeEvento: sólo lo final, normalizado", () => {
  assert.equal(textoDeEvento(evento([{ f: true, t: " zapatillas " }, { f: true, t: "nike." }])), "zapatillas nike");
  assert.equal(textoDeEvento(evento([{ f: false, t: "zapa" }])), "");
  assert.equal(textoDeEvento(evento([{ f: false, t: "zapa" }]), false), "zapa");
  assert.equal(textoDeEvento(evento([])), "");
});

test("errorDeVoz: permiso, conexión, micrófono y no entendido", () => {
  assert.deepEqual(errorDeVoz("not-allowed"), { tipo: "permiso", mensaje: MENSAJES_VOZ.permiso });
  assert.equal(errorDeVoz("service-not-allowed")?.tipo, "permiso");
  assert.equal(errorDeVoz("network")?.tipo, "sin_conexion");
  assert.equal(errorDeVoz("audio-capture")?.tipo, "sin_microfono");
  assert.equal(errorDeVoz("no-speech")?.mensaje, "No te entendí, probá de nuevo");
  assert.equal(errorDeVoz("algo-raro")?.tipo, "no_entendi");
  assert.equal(errorDeVoz(undefined)?.tipo, "no_entendi");
});

test("errorDeVoz: cortar a mano (aborted) no muestra error", () => {
  assert.equal(errorDeVoz("aborted"), null);
});

test("mensajes en voseo, sin tuteo", () => {
  assert.equal(MENSAJES_VOZ.permiso, "Para buscar con la voz, permití el micrófono en tu navegador");
  for (const m of Object.values(MENSAJES_VOZ)) assert.ok(!/\b(puedes|prueba|revisa|permite)\b/i.test(m), m);
});

test("debeReintentarConRespaldo: sólo language-not-supported y una vez", () => {
  assert.equal(debeReintentarConRespaldo("language-not-supported", false), true);
  assert.equal(debeReintentarConRespaldo("language-not-supported", true), false);
  assert.equal(debeReintentarConRespaldo("no-speech", false), false);
});

test("el silencio máximo son 8 segundos", () => {
  assert.equal(SILENCIO_MAX_MS, 8000);
});
