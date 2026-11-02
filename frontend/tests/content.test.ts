// Tests del Banco de contenido, el Contenido para redes y el Cuidado de suscriptores
// (docs/contenido-redes-tecnico.md §10.2). Cubren `lib/content-pure.ts` (funciones puras) y
// unas comprobaciones sobre los archivos nuevos: sin emojis, sin secretos y con la ruta
// pública `/pieza` protegida (middleware, robots y cabeceras).
// Se corren con `npm test` (tsc → node --test); no hay dependencias de test.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import {
  aprobableEnLote, camposSubida, claveCola, codigoDeError, contadorTexto, esErrorDeRed, etiquetaDe, fechaBo, fechaConDia,
  fechaCorta, fechaCortaBo, frenaLaTanda, hashtagsDisponibles, hexDe, horaBo, hoyBolivia, linkWhatsappTarea, lunesDe,
  mensajeDeSubida, minutosDesde, minutosRestantes, motivoLugarVacio, NETWORK_LABEL, normalizarHashtag, PIECE_STATUS_LABEL,
  piezaEnMovimiento, POST_STATUS_LABEL, redLabel, resumenDePlan, sumarDias, urlApi, urlApiOpt, validarLinkDeRed,
  type ContentNetwork,
} from "../lib/content-pure";
import { PRIVATE_PATHS } from "../lib/seo";

const RAIZ = process.cwd();   // `npm test` corre en frontend/

/* ─── validarLinkDeRed: los mismos hosts que §8.3 ────────────────────────── */

test("validarLinkDeRed: TikTok acepta tiktok.com, vm.tiktok.com y www.tiktok.com", () => {
  for (const u of ["https://www.tiktok.com/@uruku/video/123", "https://vm.tiktok.com/ZMabc/", "https://tiktok.com/@a/video/1"]) {
    assert.equal(validarLinkDeRed("tiktok", u).ok, true, u);
  }
});

test("validarLinkDeRed: Instagram acepta instagram.com y subdominios", () => {
  assert.equal(validarLinkDeRed("instagram", "https://www.instagram.com/reel/Cabc/").ok, true);
  assert.equal(validarLinkDeRed("instagram", "https://instagram.com/p/xyz").ok, true);
});

test("validarLinkDeRed: Facebook acepta facebook.com, m.facebook.com y fb.watch", () => {
  for (const u of ["https://www.facebook.com/uruku/videos/1", "https://m.facebook.com/watch/?v=1", "https://fb.watch/abc/"]) {
    assert.equal(validarLinkDeRed("facebook", u).ok, true, u);
  }
});

test("validarLinkDeRed: el canal de WhatsApp tiene que ser whatsapp.com/channel/…", () => {
  assert.equal(validarLinkDeRed("wa_channel", "https://whatsapp.com/channel/0029Vabc").ok, true);
  assert.equal(validarLinkDeRed("wa_channel", "https://www.whatsapp.com/channel/0029Vabc/123").ok, true);
  assert.equal(validarLinkDeRed("wa_channel", "https://whatsapp.com/").ok, false, "sin /channel/");
  assert.equal(validarLinkDeRed("wa_channel", "https://wa.me/59167671888").ok, false, "wa.me no es un canal");
});

test("validarLinkDeRed: el link de OTRA red se rechaza con el mensaje del backend", () => {
  const r = validarLinkDeRed("tiktok", "https://www.instagram.com/reel/Cabc/");
  assert.equal(r.ok, false);
  if (!r.ok) assert.equal(r.motivo, "Ese link no es de TikTok");
  const f = validarLinkDeRed("facebook", "https://www.tiktok.com/@a/video/1");
  if (!f.ok) assert.equal(f.motivo, "Ese link no es de Facebook");
});

test("validarLinkDeRed: no se deja engañar por hosts parecidos", () => {
  for (const u of [
    "https://tiktok.com.malo.com/x", "https://eviltiktok.com/x", "https://malo.com/?u=tiktok.com", "https://tiktok.com@malo.com/x",
  ]) {
    assert.equal(validarLinkDeRed("tiktok", u).ok, false, u);
  }
  assert.equal(validarLinkDeRed("instagram", "https://notinstagram.com/p/1").ok, false);
});

test("validarLinkDeRed: sólo https, y vacío o basura piden el link", () => {
  assert.equal(validarLinkDeRed("tiktok", "http://www.tiktok.com/@a/video/1").ok, false, "http no vale (el backend exige https)");
  assert.equal(validarLinkDeRed("tiktok", "javascript:alert(1)").ok, false);
  const vacio = validarLinkDeRed("instagram", "   ");
  assert.equal(vacio.ok, false);
  if (!vacio.ok) assert.equal(vacio.motivo, "Pegá el link o marcá que salió sin link");
  assert.equal(validarLinkDeRed("instagram", "no es un link").ok, false);
});

test("validarLinkDeRed: ignora espacios alrededor y devuelve la URL limpia", () => {
  const r = validarLinkDeRed("tiktok", "  https://vm.tiktok.com/ZMabc/  ");
  assert.equal(r.ok, true);
  if (r.ok) assert.equal(r.url, "https://vm.tiktok.com/ZMabc/");
});

/* ─── Etiquetas ──────────────────────────────────────────────────────────── */

test("etiquetas: cada red y cada estado tiene su texto, y lo desconocido se muestra tal cual", () => {
  const redes: ContentNetwork[] = ["tiktok", "instagram", "facebook", "wa_channel"];
  for (const n of redes) assert.ok(NETWORK_LABEL[n].length > 0, n);
  assert.equal(redLabel("tiktok"), "TikTok");
  assert.equal(redLabel("red_nueva"), "red_nueva");
  assert.equal(etiquetaDe(PIECE_STATUS_LABEL, "ready_for_review"), "Para revisar");
  assert.equal(etiquetaDe(PIECE_STATUS_LABEL, "estado_nuevo"), "estado_nuevo");
  assert.equal(etiquetaDe(PIECE_STATUS_LABEL, null), "");
  assert.equal(POST_STATUS_LABEL.claimed, "Publicándola");
});

/* ─── urlApi ─────────────────────────────────────────────────────────────── */

test("urlApi antepone la base sin duplicar ni perder barras", () => {
  assert.equal(urlApi("/content/files/asset/1/thumb?exp=1&sig=a", "https://api.uruku.bo"), "https://api.uruku.bo/content/files/asset/1/thumb?exp=1&sig=a");
  assert.equal(urlApi("content/files/x", "https://api.uruku.bo/"), "https://api.uruku.bo/content/files/x");
  assert.equal(urlApi("//content/x", "https://api.uruku.bo//"), "https://api.uruku.bo/content/x");
});

test("urlApi deja como están las URLs completas y urlApiOpt tolera null", () => {
  assert.equal(urlApi("https://otro.com/a.jpg", "https://api.uruku.bo"), "https://otro.com/a.jpg");
  assert.equal(urlApiOpt(null, "https://api.uruku.bo"), null);
  assert.equal(urlApiOpt(undefined, "https://api.uruku.bo"), null);
  assert.equal(urlApiOpt("/a", "https://api.uruku.bo"), "https://api.uruku.bo/a");
});

/* ─── wa.me de las tareas ────────────────────────────────────────────────── */

test("linkWhatsappTarea codifica el texto y usa sólo los dígitos del número", () => {
  const l = linkWhatsappTarea("+591 67-671888", "Hola Ana, ¿cómo va? Tu ficha: https://uruku.bo/comercios/a?ref=st-a");
  assert.ok(l);
  assert.ok((l as string).startsWith("https://wa.me/59167671888?text="));
  const texto = decodeURIComponent((l as string).split("?text=")[1]);
  assert.equal(texto, "Hola Ana, ¿cómo va? Tu ficha: https://uruku.bo/comercios/a?ref=st-a");
  assert.ok(!(l as string).includes(" "), "ningún espacio sin codificar");
  assert.ok(!(l as string).includes("¿"), "los caracteres no ASCII van codificados");
});

test("linkWhatsappTarea: sin WhatsApp válido o sin texto, no hay link", () => {
  assert.equal(linkWhatsappTarea(null, "Hola"), null);
  assert.equal(linkWhatsappTarea("", "Hola"), null);
  assert.equal(linkWhatsappTarea("1234", "Hola"), null, "menos de 8 dígitos");
  assert.equal(linkWhatsappTarea("59167671888", ""), null);
  assert.equal(linkWhatsappTarea("59167671888", "   "), null);
});

/* ─── Subida de fotos ────────────────────────────────────────────────────── */

test("camposSubida arma los campos de ContentAssetCreate y omite los vacíos", () => {
  const sha = "a".repeat(64);
  const c = camposSubida({ source_sha256: sha, taken_at_ms: Date.UTC(2026, 10, 2, 15, 0, 0), show_in_ficha: false, has_people: true, people_ok: true });
  assert.equal(c.source_sha256, sha);
  assert.equal(c.taken_at, "2026-11-02T15:00:00.000Z");
  assert.equal(c.show_in_ficha, "false");
  assert.equal(c.has_people, "true");
  assert.equal(c.people_ok, "true");
  const v = camposSubida({ source_sha256: null, taken_at_ms: null, show_in_ficha: true, has_people: false, people_ok: null });
  assert.deepEqual(Object.keys(v).sort(), ["has_people", "show_in_ficha"]);
});

test("claveCola: el mismo archivo para el mismo comercio es la misma entrada", () => {
  assert.equal(claveCola("c1", "abc"), claveCola("c1", "abc"));
  assert.notEqual(claveCola("c1", "abc"), claveCola("c2", "abc"));
});

test("hexDe pasa bytes a hexadecimal con ceros a la izquierda", () => {
  assert.equal(hexDe(new Uint8Array([0, 1, 15, 16, 255]).buffer), "00010f10ff");
});

test("esErrorDeRed: sin conexión sí; un error del servidor no", () => {
  assert.equal(esErrorDeRed(new Error("x"), false), true, "navigator.onLine = false");
  assert.equal(esErrorDeRed(new TypeError("Failed to fetch")), true);
  assert.equal(esErrorDeRed(new Error("Error de red al subir")), true);
  assert.equal(esErrorDeRed(Object.assign(new Error("La foto supera los 15 MB"), { status: 413 })), false);
  assert.equal(esErrorDeRed(Object.assign(new Error("Falló"), { status: 507 })), false);
});

test("mensajeDeSubida y frenaLaTanda: disco lleno, tamaño, personas y sesión", () => {
  assert.equal(mensajeDeSubida({ status: 507 }), "El banco de contenido llegó a su tope de espacio. Avisale al admin.");
  assert.equal(mensajeDeSubida({ status: 413 }), "La foto supera los 15 MB");
  assert.equal(mensajeDeSubida({ status: 409, datos: { codigo: "people_not_confirmed" } }), "Confirmá que las personas de la foto aceptaron aparecer");
  assert.equal(mensajeDeSubida({ status: 400, message: "El archivo no es una imagen válida" }), "El archivo no es una imagen válida");
  assert.equal(mensajeDeSubida({}), "No se pudo subir la foto");
  assert.equal(codigoDeError({ datos: { codigo: "x" } }), "x");
  assert.equal(codigoDeError(new Error("sin código")), null);
  assert.equal(frenaLaTanda({ status: 507 }), true);
  assert.equal(frenaLaTanda({ status: 401 }), true);
  assert.equal(frenaLaTanda({ status: 400 }), false, "una foto mala no frena las demás");
  assert.equal(frenaLaTanda({ status: 413 }), false);
});

/* ─── Textos y hashtags ──────────────────────────────────────────────────── */

test("contadorTexto avisa cuando se pasa", () => {
  assert.deepEqual(contadorTexto("hola", 300), { texto: "4/300", pasado: false });
  assert.equal(contadorTexto("x".repeat(301), 300).pasado, true);
  assert.equal(contadorTexto("x".repeat(300), 300).pasado, false);
});

test("hashtags: se normalizan y sólo se ofrecen los permitidos que faltan", () => {
  assert.equal(normalizarHashtag("  ##Bermejo "), "#Bermejo");
  assert.equal(normalizarHashtag("  "), "");
  assert.deepEqual(hashtagsDisponibles(["#URUKU", "#Bermejo", "#Tarija"], ["#uruku", "Bermejo"]), ["#Tarija"]);
});

/* ─── Fechas (Bolivia) ───────────────────────────────────────────────────── */

test("fechas: día, lunes y suma de días sin depender de la zona horaria del equipo", () => {
  assert.equal(fechaCorta("2026-11-04"), "04/11");
  assert.equal(fechaConDia("2026-11-04"), "mié 04/11");
  assert.equal(fechaConDia("2026-11-02"), "lun 02/11");
  assert.equal(lunesDe("2026-11-04"), "2026-11-02");
  assert.equal(lunesDe("2026-11-02"), "2026-11-02");
  assert.equal(lunesDe("2026-11-08"), "2026-11-02", "el domingo pertenece a la semana que empezó el lunes");
  assert.equal(sumarDias("2026-11-30", 1), "2026-12-01");
  assert.equal(sumarDias("2027-01-01", -1), "2026-12-31");
});

test("fechas: un instante se lleva a la hora de Bolivia (UTC-4)", () => {
  assert.equal(horaBo("2026-11-04T23:04:00Z"), "19:04");
  assert.equal(fechaBo("2027-01-03T02:00:00Z"), "02/01/2027", "a las 02:00 UTC todavía es el día anterior en Bolivia");
  assert.equal(fechaCortaBo("2026-10-12T15:00:00Z"), "12/10");
  assert.equal(fechaBo(null), "");
  assert.equal(horaBo("basura"), "");
  assert.equal(hoyBolivia(Date.UTC(2026, 10, 3, 2, 0, 0)), "2026-11-02");
});

test("minutosDesde y minutosRestantes no dan negativos", () => {
  const ahora = Date.parse("2026-11-04T20:00:00Z");
  assert.equal(minutosDesde("2026-11-04T19:57:30Z", ahora), 2);
  assert.equal(minutosDesde("2026-11-04T21:00:00Z", ahora), 0);
  assert.equal(minutosDesde(null, ahora), 0);
  assert.equal(minutosRestantes("2026-11-04T20:20:00Z", ahora), 20);
  assert.equal(minutosRestantes("2026-11-04T19:00:00Z", ahora), 0);
});

/* ─── Semana y piezas ────────────────────────────────────────────────────── */

test("resumenDePlan cuenta las piezas y explica los lugares vacíos", () => {
  assert.equal(resumenDePlan(4, []), "Se armaron 4 piezas.");
  assert.equal(resumenDePlan(1, []), "Se armó 1 pieza.");
  assert.equal(resumenDePlan(0, []), "No se armó ninguna pieza nueva.");
  assert.equal(
    resumenDePlan(4, [{ date: "2026-11-05", pillar: "ofertas", reason: "not_enough_offers" }]),
    "Se armaron 4 piezas. jue 05/11 quedó vacío: no hay 4 ofertas que sirvan.",
  );
  assert.equal(motivoLugarVacio("algo_nuevo"), "algo_nuevo");
});

test("aprobableEnLote: sólo lo que está en verde y nadie editó", () => {
  assert.equal(aprobableEnLote({ status: "ready_for_review", caption_checks: [], caption_edited: false }), true);
  assert.equal(aprobableEnLote({ status: "ready_for_review", caption_checks: ["Pasa de 300 caracteres"], caption_edited: false }), false);
  assert.equal(aprobableEnLote({ status: "ready_for_review", caption_checks: [], caption_edited: true }), false);
  assert.equal(aprobableEnLote({ status: "queued", caption_checks: [], caption_edited: false }), false);
  assert.equal(piezaEnMovimiento("queued"), true);
  assert.equal(piezaEnMovimiento("rendering"), true);
  assert.equal(piezaEnMovimiento("ready_for_review"), false);
});

/* ─── Los archivos nuevos ────────────────────────────────────────────────── */

function archivos(dir: string): string[] {
  const out: string[] = [];
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre);
    if (statSync(ruta).isDirectory()) out.push(...archivos(ruta));
    else if (/\.(ts|tsx|css)$/.test(nombre)) out.push(ruta);
  }
  return out;
}

const NUEVOS: string[] = [
  ...archivos(resolve(RAIZ, "components/content")),
  ...archivos(resolve(RAIZ, "components/subscribers")),
  ...archivos(resolve(RAIZ, "app/pieza")),
  resolve(RAIZ, "components/social-consent-toggle.tsx"),
  resolve(RAIZ, "app/styles/pieza.css"),
  resolve(RAIZ, "lib/content.ts"),
  resolve(RAIZ, "lib/content-pure.ts"),
  resolve(RAIZ, "lib/content-queue.ts"),
  resolve(RAIZ, "lib/subscribers.ts"),
  resolve(RAIZ, "lib/pieza.ts"),
];

// Emoji y pictogramas: los mismos rangos que el validador de textos del backend (§6.3).
const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/u;

test("hay archivos nuevos que revisar", () => {
  assert.ok(NUEVOS.length >= 20, `se encontraron ${NUEVOS.length}`);
});

test("ningún archivo nuevo tiene un emoji (los íconos salen de components/ic.tsx)", () => {
  for (const f of NUEVOS) {
    const m = EMOJI.exec(readFileSync(f, "utf8"));
    assert.equal(m, null, `${f} tiene un emoji o pictograma: ${m?.[0]}`);
  }
});

test("ningún archivo nuevo toca secretos ni lee comercios con select(*)", () => {
  for (const f of NUEVOS) {
    const t = readFileSync(f, "utf8");
    assert.ok(!/SERVICE_ROLE/i.test(t), `${f} menciona SERVICE_ROLE`);
    assert.ok(!/select\(\s*["'`]\*["'`]\s*\)/.test(t), `${f} hace select("*")`);
    assert.ok(!/\bany\b\s*[;,)>\]=]|:\s*any\b|<any>|as any\b/.test(t.replace(/\/\/.*$/gm, "").replace(/\/\*[\s\S]*?\*\//g, "")), `${f} usa any`);
  }
});

test("/pieza sigue funcionando en modo captura (middleware) y no se indexa (robots)", () => {
  const mw = readFileSync(resolve(RAIZ, "middleware.ts"), "utf8");
  const permitidas = /const PERMITIDAS = \[([^\]]*)\]/.exec(mw);
  assert.ok(permitidas, "no se encontró PERMITIDAS");
  assert.ok((permitidas as RegExpExecArray)[1].includes('"/pieza"'), "/pieza tiene que estar en PERMITIDAS");
  assert.ok(PRIVATE_PATHS.includes("/pieza/"), "/pieza/ tiene que estar en PRIVATE_PATHS");
});

test("next.config.mjs manda cabeceras private, no-store y noindex para /pieza/:path*", () => {
  const cfg = readFileSync(resolve(RAIZ, "next.config.mjs"), "utf8");
  const i = cfg.indexOf('source: "/pieza/:path*"');
  assert.ok(i >= 0, "falta la regla de /pieza/:path*");
  const bloque = cfg.slice(i, i + 400);
  assert.ok(bloque.includes("private, no-store"));
  assert.ok(bloque.includes("noindex, nofollow"));
});

test("la página /pieza/[token] es dinámica y noindex", () => {
  const p = readFileSync(resolve(RAIZ, "app/pieza/[token]/page.tsx"), "utf8");
  assert.ok(p.includes('export const dynamic = "force-dynamic"'));
  assert.ok(/robots:\s*\{\s*index:\s*false,\s*follow:\s*false/.test(p));
  const lib = readFileSync(resolve(RAIZ, "lib/pieza.ts"), "utf8");
  assert.ok(lib.includes('cache: "no-store"'));
});

test("el menú del panel tiene las tres secciones nuevas con su permiso", () => {
  const s = readFileSync(resolve(RAIZ, "components/admin/secciones.ts"), "utf8");
  assert.ok(/id: "banco"[^}]*permiso: "difusion"/.test(s), "banco / difusion");
  assert.ok(/id: "redes"[^}]*permiso: "difusion"/.test(s), "redes / difusion");
  assert.ok(/id: "suscriptores"[^}]*permiso: "pagos"/.test(s), "suscriptores / pagos");
});
