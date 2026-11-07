// «Entrar como este comercio», correcciones de la revisión de seguridad: pestañas viejas, clave de remontado,
// quién entró como admin, lectura de «Últimas entradas del equipo» y que el código use todo eso.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  MENSAJE_PESTANA_VIEJA, claveDeSesion, emailPorAdmin, fechaHoraBolivia, leerEntradasDelEquipo, pestanaVieja,
} from "../lib/entrar-como";

const raiz = (ruta: string) => readFileSync(resolve(process.cwd(), ruta.replace(/^frontend[/]/, "")), "utf8");

test("pestanaVieja: sólo cuando la sesión guardada es de OTRO comercio que el de la vista", () => {
  assert.equal(pestanaVieja("A", { id: "B" }), true);
  assert.equal(pestanaVieja("A", { id: "A" }), false);
  assert.equal(pestanaVieja("A", { id: "A", porAdmin: "x@y.z", expiraEn: "2026-11-07T10:00:00Z" }), false, "renovar la entrada al mismo comercio no es vieja");
  assert.equal(pestanaVieja(null, { id: "B" }), false, "sin vista de comercio no se controla");
  assert.equal(pestanaVieja(undefined, { id: "B" }), false);
  assert.equal(pestanaVieja("A", null), false, "sin sesión no hay token que mandar");
  assert.equal(pestanaVieja("A", {}), false);
});

test("el mensaje de pestaña vieja es el acordado", () => {
  assert.equal(MENSAJE_PESTANA_VIEJA, "Esta pestaña quedó vieja: se abrió otro comercio en otra pestaña. Recargá.");
});

test("claveDeSesion: cambia con el comercio y con el vencimiento de la entrada", () => {
  assert.equal(claveDeSesion({ id: "A" }), "A:");
  assert.equal(claveDeSesion({ id: "A", expiraEn: "2026-11-07T10:00:00Z" }), "A:2026-11-07T10:00:00Z");
  assert.notEqual(claveDeSesion({ id: "A" }), claveDeSesion({ id: "B" }));
  assert.notEqual(claveDeSesion({ id: "A" }), claveDeSesion({ id: "A", expiraEn: "2026-11-07T10:00:00Z" }));
  assert.equal(claveDeSesion(null), "");
});

test("emailPorAdmin sigue a la sesión actual y cae al perfil", () => {
  assert.equal(emailPorAdmin({ id: "A", porAdmin: "adm@u.bo" }, null), "adm@u.bo");
  assert.equal(emailPorAdmin({ id: "A" }, null), null, "sesión del dueño");
  assert.equal(emailPorAdmin({ id: "A" }, "adm@u.bo"), "adm@u.bo", "el perfil también delata la entrada");
  assert.equal(emailPorAdmin({ id: "A", porAdmin: "uno@u.bo" }, "otro@u.bo"), "uno@u.bo", "manda la sesión");
  assert.equal(emailPorAdmin(null, ""), null);
});

test("leerEntradasDelEquipo: lee items, descarta basura y conserva el orden", () => {
  const filas = leerEntradasDelEquipo({
    items: [
      { admin: "a@u.bo", motivo: " ayudar con fotos ", at: "2026-11-07T18:05:00Z", expira_en: "2026-11-07T18:35:00Z" },
      { admin: "b@u.bo", motivo: null, at: "2026-11-06T12:00:00Z", expira_en: "2026-11-06T12:30:00Z" },
      { admin: "", at: "2026-11-06T12:00:00Z" },
      { admin: "c@u.bo", at: "no es fecha" },
      "basura",
    ],
  });
  assert.deepEqual(filas.map((f) => f.admin), ["a@u.bo", "b@u.bo"]);
  assert.equal(filas[0].motivo, "ayudar con fotos");
  assert.equal(filas[1].motivo, null);
  assert.deepEqual(leerEntradasDelEquipo(null), []);
  assert.deepEqual(leerEntradasDelEquipo({ items: "x" }), []);
});

test("fechaHoraBolivia: UTC-4, con cambio de día", () => {
  assert.equal(fechaHoraBolivia("2026-11-07T18:05:00Z"), "07/11/2026 14:05");
  assert.equal(fechaHoraBolivia("2026-11-07T02:30:00Z"), "06/11/2026 22:30");
  assert.equal(fechaHoraBolivia("2027-01-01T03:59:00Z"), "31/12/2026 23:59");
  assert.equal(fechaHoraBolivia("nada"), "");
});

test("Mi comercio: el admin nunca ve «pagar una foto extra» ni «Destacar»", () => {
  const p = raiz("frontend/app/mi-comercio/page.tsx");
  assert.ok(p.includes("<GaleriaUploader puedePagarExtra={!porAdmin}"), "galería: puedePagarExtra={!porAdmin}");
  assert.ok(!/<GaleriaUploader puedePagarExtra\s/.test(p), "ninguna galería con puedePagarExtra fijo");
  const prod = p.slice(p.indexOf("function ProductosTab"), p.indexOf("function ProductosTab") + 4000);
  assert.ok(/porAdmin\s*\r?\n?\s*\?/.test(prod) && prod.includes("Destacar $1.000"), "destacar escondido para el admin");
});

test("Mi comercio: el panel se remonta por sesión y porAdmin se recalcula", () => {
  const p = raiz("frontend/app/mi-comercio/page.tsx");
  assert.ok(p.includes("<Panel key={claveDeSesion(sess)}"));
  assert.ok(p.includes("emailPorAdmin(sess, porAdminPerfil)"));
  assert.ok(!/useState<string \| null>\(sess\.porAdmin/.test(p), "porAdmin ya no se fija una sola vez");
  assert.ok(p.includes("fijarComercioEsperado(sess.id)"));
  assert.ok(!p.includes("clearComercio()"), "la página no borra la sesión a mano: pasa por cerrarSesionComercio");
});

test("cliente del comercio: todo pedido toma el token con la guarda de pestaña vieja", () => {
  const c = raiz("frontend/lib/comercio.ts");
  assert.ok(c.includes("export function tokenVigente"));
  assert.ok(c.includes("throw new PestanaVieja()"));
  // Fuera de la propia guarda, nadie manda un token leído con getCToken().
  const sinDefinicion = c.replace(/export function getCToken[\s\S]*?\r?\n}\r?\n/, "");
  assert.ok(!sinDefinicion.includes("getCToken()"), "comercio.ts: usar tokenVigente()");
  assert.ok(!raiz("frontend/lib/content.ts").includes("getCToken()"), "content.ts: usar tokenVigente()");
});

test("Salir: llama a POST /comercio/entrada/salir con el token de la entrada y no pisa la sesión de otra pestaña", () => {
  const c = raiz("frontend/lib/comercio.ts");
  const f = c.slice(c.indexOf("export async function cerrarSesionComercio"));
  assert.ok(f.includes("/comercio/entrada/salir") && f.includes('method: "POST"'));
  assert.ok(f.indexOf("pestanaVieja(") < f.indexOf("clearComercio()"), "primero mira si la pestaña quedó vieja");
  assert.ok(f.includes("catch"), "los errores del aviso se ignoran");
  const p = raiz("frontend/app/mi-comercio/page.tsx");
  assert.ok(p.includes("cerrarSesionComercio(leida?.id ?? null, true)"), "al abrir con la entrada vencida también avisa");
  assert.ok(p.includes("cerrarSesion(true, true)"), "al vencer también avisa");
});

test("Admin: «Generar clave nueva» y «Últimas entradas» sólo con el permiso equipo", () => {
  const a = raiz("frontend/app/admin/page.tsx");
  assert.ok(/puedeEntrar && <GenerarClaveComercio/.test(a));
  assert.ok(!/puedeCuenta && <GenerarClaveComercio/.test(a));
  assert.ok(/puedeEntrar && <EntradasDelEquipo/.test(a));
  assert.ok(raiz("frontend/lib/api.ts").includes("/entradas`"));
});

test("«Cambié de número» sigue escondido para el admin", () => {
  const p = raiz("frontend/app/mi-comercio/page.tsx");
  const i = p.indexOf('href="/recuperar-negocio"');
  assert.ok(i > 0);
  const antes = p.slice(Math.max(0, i - 400), i);
  assert.ok(/porAdmin\s*\r?\n?\s*\?/.test(antes), "rama porAdmin ? aviso : enlace");
});
