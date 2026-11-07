// «Entrar como este comercio»: lectura de la respuesta, vencimiento, texto del aviso, acciones bloqueadas y que una
// entrada de admin NUNCA cuente visitas ni contactos (lib/entrar-como.ts + lib/medicion.ts).
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  ACCIONES_BLOQUEADAS, MENSAJE_NO_DISPONIBLE, entradaVencida, esBloqueoAdmin, esEntradaAdmin, leerEntradaAdmin,
  minutosRestantes, motivoBloqueo, msRestantes, sesionAjena, suavizarBloqueo, textoAviso, textoRestante,
} from "../lib/entrar-como";
import { esEntradaDeAdmin, esEquipo, esMiComercio } from "../lib/medicion";

const respuesta = {
  access_token: "tok.en.x", comercio: { id: "c-1", nombre: "Boutique Sol", slug: "boutique-sol" },
  expira_en: "2026-11-07T15:30:00Z", por_admin: "saady@uruku.bo",
};

function almacen(inicial: Record<string, string> = {}) {
  const m = new Map(Object.entries(inicial));
  return { getItem: (k: string) => m.get(k) ?? null };
}

test("leerEntradaAdmin: lee la respuesta del contrato", () => {
  const e = leerEntradaAdmin(respuesta);
  assert.equal(e.accessToken, "tok.en.x");
  assert.deepEqual(e.comercio, { id: "c-1", nombre: "Boutique Sol", slug: "boutique-sol" });
  assert.equal(e.expiraEn, "2026-11-07T15:30:00Z");
  assert.equal(e.porAdmin, "saady@uruku.bo");
});

test("leerEntradaAdmin: sin token, sin comercio o con vencimiento ilegible no abre sesión", () => {
  assert.throws(() => leerEntradaAdmin(null));
  assert.throws(() => leerEntradaAdmin({ ...respuesta, access_token: "" }));
  assert.throws(() => leerEntradaAdmin({ ...respuesta, comercio: {} }));
  assert.throws(() => leerEntradaAdmin({ ...respuesta, expira_en: "mañana" }));
});

test("vencimiento: minutos restantes redondean para arriba y nunca bajan de 0", () => {
  const exp = "2026-11-07T15:30:00Z";
  const t = Date.parse(exp);
  assert.equal(minutosRestantes(exp, t - 30 * 60000), 30);
  assert.equal(minutosRestantes(exp, t - 20_000), 1);
  assert.equal(minutosRestantes(exp, t), 0);
  assert.equal(minutosRestantes(exp, t + 60000), 0);
  assert.equal(msRestantes("basura", t), 0);
  assert.equal(msRestantes(null, t), 0);
});

test("entradaVencida: sólo las sesiones de admin vencen; una común no", () => {
  const exp = "2026-11-07T15:30:00Z";
  const t = Date.parse(exp);
  const admin = { id: "c-1", porAdmin: "a@b.c", expiraEn: exp };
  assert.equal(entradaVencida(admin, t - 1), false);
  assert.equal(entradaVencida(admin, t), true);
  assert.equal(entradaVencida({ ...admin, expiraEn: undefined }, t - 1), true);
  assert.equal(entradaVencida({ id: "c-1" }, t + 9e9), false);
  assert.equal(entradaVencida(null, t), false);
  assert.equal(esEntradaAdmin(admin), true);
  assert.equal(esEntradaAdmin({ id: "c-1" }), false);
});

test("textos del aviso fijo", () => {
  assert.equal(
    textoAviso("Boutique Sol", "saady@uruku.bo"),
    "Estás dentro de «Boutique Sol» como admin (saady@uruku.bo). Lo que cambies queda registrado a tu nombre.",
  );
  assert.equal(textoRestante(12), "Quedan 12 min");
  assert.equal(textoRestante(1), "Queda 1 min o menos");
  assert.equal(textoRestante(0), "Queda 1 min o menos");
});

test("acciones bloqueadas: las cinco del contrato, con motivo y sin repetir", () => {
  assert.deepEqual(ACCIONES_BLOQUEADAS.map((a) => a.id), ["clave", "whatsapp", "baja", "pagos", "acceso"]);
  assert.equal(new Set(ACCIONES_BLOQUEADAS.map((a) => a.id)).size, ACCIONES_BLOQUEADAS.length);
  for (const a of ACCIONES_BLOQUEADAS) {
    assert.ok(a.nombre.length > 0 && a.motivo.length > 0);
    assert.match(motivoBloqueo(a.id), /no disponible entrando como admin/);
  }
});

test("403 «No disponible entrando como admin»: se reconoce y se completa; otros mensajes pasan igual", () => {
  assert.equal(esBloqueoAdmin(MENSAJE_NO_DISPONIBLE), true);
  assert.equal(esBloqueoAdmin("NO DISPONIBLE ENTRANDO COMO ADMIN."), true);
  assert.equal(esBloqueoAdmin("Credenciales incorrectas"), false);
  assert.equal(esBloqueoAdmin(undefined), false);
  assert.match(suavizarBloqueo(MENSAJE_NO_DISPONIBLE), /dueño del negocio/);
  assert.equal(suavizarBloqueo("Hiciste demasiados pedidos"), "Hiciste demasiados pedidos");
});

test("sesionAjena: avisa antes de pisar otra sesión de comerciante", () => {
  assert.equal(sesionAjena(null, "c-1"), null);
  assert.equal(sesionAjena({ id: "c-2", nombre: "Otro Local" }, "c-1"), "Otro Local");
  assert.equal(sesionAjena({ id: "c-2" }, "c-1"), "otro negocio");
  // misma entrada de admin al mismo comercio: se renueva sin aviso; la sesión real del dueño sí se avisa
  assert.equal(sesionAjena({ id: "c-1", nombre: "X", porAdmin: "a@b.c" }, "c-1"), null);
  assert.equal(sesionAjena({ id: "c-1", nombre: "X" }, "c-1"), "X");
});

test("medición: una sesión de comerciante abierta por un admin no cuenta visitas ni contactos", () => {
  const entrada = almacen({
    bermejo_comercio_token: "t",
    bermejo_comercio: JSON.stringify({ id: "c-1", nombre: "Sol", porAdmin: "a@b.c", expiraEn: "2026-11-07T15:30:00Z" }),
  });
  assert.equal(esEntradaDeAdmin(entrada), true);
  assert.equal(esEquipo(entrada), true, "es equipo: no se mide en NINGÚN comercio, ni en el suyo ni en otros");
  // un comerciante común sigue midiéndose en comercios ajenos y se excluye sólo en el suyo
  const dueno = almacen({ bermejo_comercio_token: "t", bermejo_comercio: JSON.stringify({ id: "c-1", nombre: "Sol" }) });
  assert.equal(esEntradaDeAdmin(dueno), false);
  assert.equal(esEquipo(dueno), false);
  assert.equal(esMiComercio(dueno, "c-1"), true);
  assert.equal(esMiComercio(dueno, "c-2"), false);
  // sin token no hay sesión, aunque haya quedado la ficha; JSON roto no revienta
  assert.equal(esEquipo(almacen({ bermejo_comercio: JSON.stringify({ porAdmin: "a@b.c" }) })), false);
  assert.equal(esEquipo(almacen({ bermejo_comercio_token: "t", bermejo_comercio: "{roto" })), false);
  assert.equal(esEquipo(null), false);
  // los tokens del equipo de siempre siguen valiendo
  assert.equal(esEquipo(almacen({ bermejo_admin_token: "x" })), true);
});

test("la sesión de entrada de admin no guarda claves en el navegador", () => {
  const fuente = readFileSync(resolve(process.cwd(), "lib/comercio.ts"), "utf8");
  const trozo = fuente.slice(fuente.indexOf("export function guardarEntradaAdmin"), fuente.indexOf("function guardarSesion("));
  assert.ok(trozo.includes("porAdmin: e.porAdmin") && trozo.includes("expiraEn: e.expiraEn"));
  assert.ok(!/clave|password|codigo/i.test(trozo.replace(/Sólo se guarda lo mínimo, sin ninguna clave\./, "")), "no debe tocar claves");
  assert.ok(!trozo.includes("bermejo_admin_token"), "no toca la sesión del admin");
});
