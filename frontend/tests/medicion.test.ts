// Medición: las piezas puras de lib/medicion.ts (sesión, primera página, referrer, rutas internas, equipo,
// catálogo de eventos, tamaño del cuerpo) y los textos de lib/origenes.ts.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  CATALOGO_EVENTOS, MAX_BODY_BYTES, RUTAS_INTERNAS, armarCuerpo, detectarDispositivo, esEquipo, esMiComercio,
  esRutaInterna, eventoDeEnlace, eventoValido, hostDeReferrer, leadRepetido, leerConfig, limpiarRuta,
  origenDeLaUrl, repiteRuta, tomarPrimera, vistaRepetida,
} from "../lib/medicion";
import { SESION_MAX, SESION_MIN, nuevaSesion, sesionValida } from "../lib/sesion";
import {
  agruparOrigenes, etiquetaOrigenComercio, etiquetaOrigenPanel, haceCuanto, porcentaje, resumirEventos, urlSegura,
} from "../lib/origenes";

/** Un almacén en memoria con la forma de `Storage`. */
function almacen(inicial: Record<string, string> = {}) {
  const m = new Map(Object.entries(inicial));
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => { m.set(k, v); } };
}

test("sesión: la misma regla que el backend (^[A-Za-z0-9-]{6,40}$)", () => {
  assert.equal(SESION_MIN, 6);
  assert.equal(SESION_MAX, 40);
  assert.equal(sesionValida(nuevaSesion()), true);
  assert.equal(sesionValida("abc123"), true);
  assert.equal(sesionValida("abc12"), false);               // 5: muy corta
  assert.equal(sesionValida("a".repeat(41)), false);
  assert.equal(sesionValida("a_b_c_d"), false);
});

test("rutas internas: la misma lista que RUTAS_INTERNAS del backend", () => {
  const py = readFileSync(resolve(process.cwd(), "..", "backend/app/services/site_metrics.py"), "utf8");
  const m = py.match(/^RUTAS_INTERNAS = \(([^)]*)\)/m);
  assert.ok(m, "no se encontró RUTAS_INTERNAS en el backend");
  const backend = [...m![1].matchAll(/"([^"]+)"/g)].map((x) => x[1]);
  assert.deepEqual([...RUTAS_INTERNAS], backend);
});

test("rutas internas: panel, campo y editor no se miden; el sitio público sí", () => {
  for (const r of ["/admin", "/admin/negocios", "/contenido", "/publicar", "/campo/x", "/mi-comercio", "/api/health", "/ADMIN"]) {
    assert.equal(esRutaInterna(r), true, r);
  }
  for (const r of ["/", "/buscar", "/comercios/rustico", "/mapa", "/ofertas", "/guia", "/novedades", "/apiario"]) {
    assert.equal(esRutaInterna(r), false, r);
  }
});

test("limpiarRuta: sin query ni hash, con «/» adelante y hasta 200 caracteres", () => {
  assert.equal(limpiarRuta("/buscar?q=zapatos&ref=volante"), "/buscar");
  assert.equal(limpiarRuta("/comercios/rustico#fotos"), "/comercios/rustico");
  assert.equal(limpiarRuta("buscar"), "/buscar");
  assert.equal(limpiarRuta("https://uruku.bo/ofertas?x=1"), "/ofertas");
  assert.equal(limpiarRuta(""), "/");
  assert.equal(limpiarRuta(`/${"a".repeat(500)}`).length, 200);
});

test("misma ruta dentro de 1 s es una sola página vista", () => {
  assert.equal(repiteRuta(null, "/", 1000), false);
  assert.equal(repiteRuta({ ruta: "/", t: 1000 }, "/", 1500), true);
  assert.equal(repiteRuta({ ruta: "/", t: 1000 }, "/", 2000), false);     // pasó el segundo
  assert.equal(repiteRuta({ ruta: "/", t: 1000 }, "/buscar", 1100), false);
});

test("primera página de la sesión: true una sola vez, aun sin almacenamiento", () => {
  const a = almacen();
  const estado = { v: false };
  assert.equal(tomarPrimera(a, estado), true);
  assert.equal(tomarPrimera(a, estado), false);
  // Recarga (memoria nueva) en la misma pestaña: el almacén recuerda que la sesión ya mandó una.
  assert.equal(tomarPrimera(a, { v: false }), false);
  // Sin almacén (modo privado): vale la marca en memoria.
  const e2 = { v: false };
  assert.equal(tomarPrimera(null, e2), true);
  assert.equal(tomarPrimera(null, e2), false);
  // Almacén que tira error: no rompe y cuenta como primera.
  const roto = { getItem: () => { throw new Error("bloqueado"); }, setItem: () => { throw new Error("bloqueado"); } };
  assert.equal(tomarPrimera(roto, { v: false }), true);
});

test("vista de ficha: una por pestaña cada 30 minutos", () => {
  const a = almacen();
  assert.equal(vistaRepetida(a, "c1", 1_000_000), false);
  assert.equal(vistaRepetida(a, "c1", 1_000_000 + 60_000), true);
  assert.equal(vistaRepetida(a, "c2", 1_000_000 + 60_000), false);          // otro comercio
  assert.equal(vistaRepetida(a, "c1", 1_000_000 + 31 * 60_000), false);     // pasó la media hora
  assert.equal(vistaRepetida(null, "c1", 1), false);
});

test("referrer: sólo el host, sin www, y nada si es del propio sitio", () => {
  assert.equal(hostDeReferrer("https://www.google.com.bo/search?q=zapatos", "uruku.bo"), "google.com.bo");
  assert.equal(hostDeReferrer("https://l.facebook.com/l.php?u=x", "uruku.bo"), "l.facebook.com");
  assert.equal(hostDeReferrer("android-app://com.whatsapp/", "uruku.bo"), "com.whatsapp");
  assert.equal(hostDeReferrer("https://uruku.bo/buscar", "uruku.bo"), null);
  assert.equal(hostDeReferrer("https://www.uruku.bo/", "uruku.bo"), null);
  assert.equal(hostDeReferrer("", "uruku.bo"), null);
  assert.equal(hostDeReferrer("no es una url", "uruku.bo"), null);
  assert.equal(hostDeReferrer(null, "uruku.bo"), null);
  // Nunca viaja la ruta ni la query de la otra página.
  assert.ok(!String(hostDeReferrer("https://mail.example.com/inbox/123?token=secreto", "uruku.bo")).includes("/"));
});

test("origen: ?ref= manda sobre utm_source", () => {
  assert.equal(origenDeLaUrl("?ref=volante-1"), "volante-1");
  assert.equal(origenDeLaUrl("?utm_source=chatgpt.com"), "chatgpt.com");
  assert.equal(origenDeLaUrl("?utm_source=instagram&ref=mesa-3"), "mesa-3");
  assert.equal(origenDeLaUrl("?q=zapatos"), null);
  assert.equal(origenDeLaUrl(""), null);
  assert.equal(origenDeLaUrl(`?ref=${"x".repeat(200)}`)?.length, 64);
});

test("dispositivo: celular, tablet o computadora", () => {
  const chromeAndroid = "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 Chrome/126.0 Mobile Safari/537.36";
  const tabletAndroid = "Mozilla/5.0 (Linux; Android 13; SM-X700) AppleWebKit/537.36 Chrome/126.0 Safari/537.36";
  const iphone = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148";
  const ipad = "Mozilla/5.0 (iPad; CPU OS 17_5 like Mac OS X) AppleWebKit/605.1.15";
  const mac = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15";
  const windows = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36";
  assert.equal(detectarDispositivo(chromeAndroid), "mobile");
  assert.equal(detectarDispositivo(tabletAndroid), "tablet");
  assert.equal(detectarDispositivo(iphone), "mobile");
  assert.equal(detectarDispositivo(ipad), "tablet");
  assert.equal(detectarDispositivo(mac, 5), "tablet");       // iPad que se hace pasar por Mac
  assert.equal(detectarDispositivo(mac, 0), "desktop");
  assert.equal(detectarDispositivo(windows), "desktop");
  assert.equal(detectarDispositivo(""), "desktop");
});

test("equipo: con un token de admin, agente o publicador no se mide", () => {
  assert.equal(esEquipo(almacen()), false);
  assert.equal(esEquipo(almacen({ bermejo_admin_token: "x" })), true);
  assert.equal(esEquipo(almacen({ bermejo_agente_token: "x" })), true);
  assert.equal(esEquipo(almacen({ bermejo_publicador_token: "x" })), true);
  assert.equal(esEquipo(almacen({ bermejo_comercio_token: "x" })), false);   // el comerciante no es equipo
  assert.equal(esEquipo(null), false);
});

test("comerciante logueado: no suma vistas ni contactos a SU comercio, sí a los otros", () => {
  const yo = almacen({ bermejo_comercio_token: "t", bermejo_comercio: JSON.stringify({ id: "c1", nombre: "Mío" }) });
  assert.equal(esMiComercio(yo, "c1"), true);
  assert.equal(esMiComercio(yo, "c2"), false);
  assert.equal(esMiComercio(almacen({ bermejo_comercio: JSON.stringify({ id: "c1" }) }), "c1"), false);   // sin token
  assert.equal(esMiComercio(almacen({ bermejo_comercio_token: "t", bermejo_comercio: "{no json" }), "c1"), false);
  assert.equal(esMiComercio(null, "c1"), false);
});

test("catálogo de eventos: cerrado, igual al del backend", () => {
  assert.deepEqual(Object.keys(CATALOGO_EVENTOS).sort(), ["pwa_install", "share", "uruku_whatsapp_click", "video_network_click", "video_play"]);
  assert.equal(eventoValido("share", "native"), true);
  assert.equal(eventoValido("share", "copy"), true);
  assert.equal(eventoValido("share", "otro"), false);
  assert.equal(eventoValido("share"), false);
  for (const d of ["shown", "accepted", "dismissed", "installed", "ios_hint"]) assert.equal(eventoValido("pwa_install", d), true, d);
  assert.equal(eventoValido("video_play", "0b6f6c5e-9d1a-4c1e-8d7a-3f2b1a9c0d4e"), true);
  assert.equal(eventoValido("video_play", "no-es-uuid"), false);
  assert.equal(eventoValido("video_network_click", "tiktok"), true);
  assert.equal(eventoValido("video_network_click", "twitter"), false);
  for (const d of ["canal", "comunidad", "contacto"]) assert.equal(eventoValido("uruku_whatsapp_click", d), true, d);
  assert.equal(eventoValido("inventado", "x"), false);
  assert.equal(eventoValido("constructor", "x"), false);          // no se cuela por el prototipo
});

test("enlaces de URUKU con data-uk-evento: sólo los válidos miden", () => {
  const el = (a: Record<string, string>) => ({ getAttribute: (n: string) => a[n] ?? null });
  assert.deepEqual(eventoDeEnlace(el({ "data-uk-evento": "uruku_whatsapp_click", "data-uk-detalle": "canal" })),
    { nombre: "uruku_whatsapp_click", detail: "canal" });
  assert.equal(eventoDeEnlace(el({ "data-uk-evento": "uruku_whatsapp_click", "data-uk-detalle": "otro" })), null);
  assert.equal(eventoDeEnlace(el({})), null);
  assert.equal(eventoDeEnlace(null), null);
});

test("cuerpo de /collect: JSON sin vacíos y siempre bajo el tope de 2 KB", () => {
  const normal = armarCuerpo({
    t: "pv", path: "/comercios/rustico", session: "abc-123-def", device: "mobile", standalone: false, first: true,
    ref: undefined, referrer: "", city: null,
  });
  assert.deepEqual(JSON.parse(normal), { t: "pv", path: "/comercios/rustico", session: "abc-123-def", device: "mobile", standalone: false, first: true });
  assert.ok(new TextEncoder().encode(normal).length < MAX_BODY_BYTES);

  // Aunque alguien mande campos enormes, el cuerpo entra y conserva lo esencial.
  const grande = armarCuerpo({
    t: "pv", path: "/" + "p".repeat(190), session: "abc-123-def", device: "desktop", standalone: true, first: false,
    ref: "r".repeat(3000), referrer: "h".repeat(3000), city: "c".repeat(3000),
  });
  assert.ok(new TextEncoder().encode(grande).length <= MAX_BODY_BYTES);
  const j = JSON.parse(grande);
  assert.equal(j.t, "pv");
  assert.equal(j.session, "abc-123-def");
  assert.ok(typeof j.path === "string" && j.path.startsWith("/p"));

  // El tope también cuenta bytes, no letras (los acentos pesan 2).
  const acentos = armarCuerpo({ t: "ev", path: "/", session: "abc-123-def", event: "share", detail: "é".repeat(2000) });
  assert.ok(new TextEncoder().encode(acentos).length <= MAX_BODY_BYTES);
  assert.equal(JSON.parse(acentos).event, "share");
});

test("/lead: «repetido» no se vuelve a anotar para el «¿te contestó?»", () => {
  assert.equal(leadRepetido({ ok: true, id: "L1", token: "t", repetido: true }), true);
  assert.equal(leadRepetido({ ok: true, id: "L1", token: "t" }), false);
  assert.equal(leadRepetido(null), false);
  assert.equal(leadRepetido("x"), false);
});

test("config pública: lo desconocido cae a «medir, sin Umami»", () => {
  assert.deepEqual(leerConfig({ internal: true, umami: null }), { internal: true, umami: null });
  assert.deepEqual(leerConfig(null), { internal: true, umami: null });
  assert.deepEqual(leerConfig("x"), { internal: true, umami: null });
  assert.equal(leerConfig({ internal: false, umami: null }).internal, false);
  assert.deepEqual(leerConfig({ internal: true, umami: { script_url: "https://s/script.js", website_id: "w" } }).umami,
    { script_url: "https://s/script.js", website_id: "w" });
  assert.equal(leerConfig({ internal: true, umami: { script_url: 1 } }).umami, null);
});

test("el módulo de medición no carga scripts de terceros", () => {
  const src = readFileSync(resolve(process.cwd(), "lib/medicion.ts"), "utf8");
  assert.ok(!/createElement\(["']script["']\)/.test(src));
  assert.ok(!/\.src\s*=/.test(src));
});

// ---- Textos (lib/origenes.ts) --------------------------------------------------------------------

test("origen para el comerciante: en castellano claro, con QR por su nombre", () => {
  assert.equal(etiquetaOrigenComercio({ kind: "qr", name: "volante" }), "QR del volante");
  assert.equal(etiquetaOrigenComercio({ kind: "qr", name: "mesa" }), "QR de la mesa");
  assert.equal(etiquetaOrigenComercio({ kind: "qr", name: "ficha" }), "QR de tu ficha");
  // un `?ref=` que no es de un QR nuestro (lo escribe cualquiera) no se muestra como QR
  assert.equal(etiquetaOrigenComercio({ kind: "qr", name: "raro" }), "Otros");
  assert.equal(etiquetaOrigenComercio({ kind: "qr", name: "tarjeta" }), "Otros");
  assert.equal(etiquetaOrigenComercio({ kind: "other", name: "qr_raro" }), "Otros");
  assert.equal(etiquetaOrigenComercio({ kind: "other", name: "otros" }), "Otros");
  assert.equal(etiquetaOrigenComercio({ kind: "search", name: "google" }), "Google");
  assert.equal(etiquetaOrigenComercio({ kind: "social", name: "facebook" }), "Facebook");
  assert.equal(etiquetaOrigenComercio({ kind: "whatsapp", name: "whatsapp" }), "WhatsApp");
  assert.equal(etiquetaOrigenComercio({ kind: "ai", name: "chatgpt" }), "ChatGPT (asistente de IA)");
  assert.match(etiquetaOrigenComercio({ kind: "direct", name: "" }), /^Directo/);
  assert.equal(etiquetaOrigenComercio({ kind: "other", name: "qr_volante" }), "QR del volante");
  assert.equal(etiquetaOrigenComercio({ kind: "other", name: "ejemplo.com" }), "ejemplo.com");
});

test("origen para el panel: agrupado por tipo, del más grande al más chico", () => {
  assert.equal(etiquetaOrigenPanel({ kind: "other", name: "qr_volante" }), "QR: volante");
  assert.equal(etiquetaOrigenPanel({ kind: "direct", name: "" }), "Directo");
  const g = agruparOrigenes([
    { kind: "search", name: "google", n: 10 },
    { kind: "social", name: "facebook", n: 30 },
    { kind: "social", name: "instagram", n: 5 },
    { kind: "direct", name: "", n: 0 },
    { kind: "other", name: "qr_mesa", n: 2 },
    { kind: "desconocido", name: "x", n: 1 },
  ]);
  assert.deepEqual(g.map((x) => [x.kind, x.n]), [["social", 35], ["search", 10], ["other", 3]]);
  assert.deepEqual(g[0].items, [{ nombre: "Facebook", n: 30 }, { nombre: "Instagram", n: 5 }]);
});

test("eventos del panel: compartir, instalar, videos y canal", () => {
  const r = resumirEventos([
    { event: "share", detail: "native", n: 4 }, { event: "share", detail: "copy", n: 2 },
    { event: "pwa_install", detail: "shown", n: 20 }, { event: "pwa_install", detail: "accepted", n: 5 },
    { event: "pwa_install", detail: "dismissed", n: 9 }, { event: "pwa_install", detail: "installed", n: 4 },
    { event: "pwa_install", detail: "ios_hint", n: 3 },
    { event: "video_play", detail: "id-1", n: 7 }, { event: "video_play", detail: "id-2", n: 1 },
    { event: "video_network_click", detail: "tiktok", n: 3 },
    { event: "uruku_whatsapp_click", detail: "canal", n: 6 }, { event: "uruku_whatsapp_click", detail: "comunidad", n: 2 },
  ]);
  assert.deepEqual(r.compartieron, { total: 6, nativo: 4, copiado: 2 });
  assert.deepEqual(r.instalacion, { mostrada: 20, aceptada: 5, rechazada: 9, instalada: 4, pistaIphone: 3 });
  assert.deepEqual(r.videos, { reproducidos: 8, distintos: 2, aRedes: [{ red: "TikTok", n: 3 }] });
  assert.deepEqual(r.canal, { canal: 6, comunidad: 2, contacto: 0 });
  assert.equal(r.hayAlgo, true);
  assert.equal(resumirEventos(undefined).hayAlgo, false);
  assert.equal(resumirEventos([]).hayAlgo, false);
});

test("«hace cuánto» y porcentajes", () => {
  const ahora = Date.parse("2026-11-06T12:00:00Z");
  assert.equal(haceCuanto(null).nivel, "sin_datos");
  assert.equal(haceCuanto("2026-11-06T11:55:00Z", ahora).texto, "Último dato recibido hace 5 min.");
  assert.equal(haceCuanto("2026-11-06T11:55:00Z", ahora).nivel, "ok");
  assert.equal(haceCuanto("2026-11-06T09:00:00Z", ahora).texto, "Último dato recibido hace 3 h.");
  assert.equal(haceCuanto("2026-11-06T04:00:00Z", ahora).nivel, "caida");
  assert.equal(haceCuanto("2026-11-04T12:00:00Z", ahora).texto, "Último dato recibido hace 2 días.");
  assert.equal(haceCuanto("basura", ahora).nivel, "sin_datos");
  assert.equal(porcentaje(1, 3), 33);
  assert.equal(porcentaje(1, 0), 0);
  assert.equal(urlSegura("https://stats.uruku.bo/"), "https://stats.uruku.bo/");
  assert.equal(urlSegura("javascript:alert(1)"), null);
  assert.equal(urlSegura("http://x.test"), null);
  assert.equal(urlSegura(null), null);
});

// ---- CSP (next.config.mjs) -------------------------------------------------------------------------

test("la CSP fija los scripts de unpkg a la ruta exacta que carga el sitio y deja Cloudflare Insights", () => {
  const raiz = process.cwd();
  const cfg = readFileSync(resolve(raiz, "next.config.mjs"), "utf8");
  const linea = cfg.split("\n").find((l) => l.includes('"script-src"')) ?? "";
  assert.ok(linea.includes("LEAFLET_JS") && linea.includes("MARKERCLUSTER_JS") && linea.includes("CF_BEACON"));
  assert.ok(!/\bUNPKG\b/.test(linea), "script-src no puede permitir todo unpkg.com");
  // Todo `.js` de unpkg que el sitio carga tiene que estar en la lista (si no, la CSP lo bloquearía al pasar a enforce).
  const usados = new Set<string>();
  for (const f of ["lib/mapa-visual.ts", "components/bolivia-map.tsx"]) {
    for (const m of readFileSync(resolve(raiz, f), "utf8").matchAll(/https:\/\/unpkg\.com\/[^"'`\s]+\.js/g)) usados.add(m[0]);
  }
  assert.ok(usados.size >= 2);
  for (const u of usados) assert.ok(cfg.includes(`"${u}"`), `falta ${u} en script-src`);
  assert.ok(cfg.includes('"https://static.cloudflareinsights.com"') && cfg.includes('"https://cloudflareinsights.com"'));
});
