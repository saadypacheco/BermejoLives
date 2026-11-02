// Tests de «Videos de URUKU» en la home (docs/contenido-redes-tecnico.md §15.2): armado de
// direcciones, duración ISO 8601, nodo JSON-LD `VideoObject`, lectura defensiva de la API,
// y que los archivos nuevos no tengan emojis ni secretos.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  duracionCorta, duracionIso, esLinkWeb, normalizarVideos, videoObjectNode, videoObjectNodes, videoUrl,
  type PublicVideo,
} from "../lib/videos-pure";
import { SKIP_REASON_LABEL, urlApi } from "../lib/content-pure";
import { serializeJsonLd } from "../lib/seo";

const RAIZ = process.cwd();   // `npm test` corre en frontend/
const API = "https://api.uruku.test";

const VIDEO: PublicVideo = {
  id: "v1", title: "Ferretería Ejemplo",
  comercio: { nombre: "Ferretería Ejemplo", slug: "ferreteria-ejemplo" },
  city_slug: "bermejo", published_at: "2026-11-01T15:30:00Z", duration_s: 45,
  cover_url: "/public/videos/v1/cover", video_url: "/public/videos/v1/video",
  network_links: { tiktok: "https://www.tiktok.com/@uruku/video/1" },
};

/* ─── Direcciones ────────────────────────────────────────────────────────── */

test("videoUrl antepone la base de la API a las rutas relativas, sin barras de más", () => {
  assert.equal(videoUrl("/public/videos/v1/cover", API), `${API}/public/videos/v1/cover`);
  assert.equal(videoUrl("/public/videos/v1/cover", `${API}/`), `${API}/public/videos/v1/cover`);
  assert.equal(videoUrl("public/videos/v1/video", API), `${API}/public/videos/v1/video`);
});

test("videoUrl deja como están las direcciones que ya vienen completas", () => {
  assert.equal(videoUrl("https://cdn.uruku.test/x.mp4", API), "https://cdn.uruku.test/x.mp4");
  assert.equal(videoUrl("/a/b", API), urlApi("/a/b", API));
});

/* ─── Duración ───────────────────────────────────────────────────────────── */

test("duracionIso arma ISO 8601 (PT…H…M…S)", () => {
  assert.equal(duracionIso(45), "PT45S");
  assert.equal(duracionIso(60), "PT1M");
  assert.equal(duracionIso(90), "PT1M30S");
  assert.equal(duracionIso(3600), "PT1H");
  assert.equal(duracionIso(3725), "PT1H2M5S");
  assert.equal(duracionIso(30.6), "PT31S");
});

test("duracionIso no declara lo que no sirve", () => {
  for (const v of [null, undefined, 0, -5, Number.NaN, Number.POSITIVE_INFINITY, 0.2]) {
    assert.equal(duracionIso(v as number | null | undefined), undefined, String(v));
  }
});

test("duracionCorta: m:ss para la etiqueta de la portada", () => {
  assert.equal(duracionCorta(75), "1:15");
  assert.equal(duracionCorta(9), "0:09");
  assert.equal(duracionCorta(null), null);
  assert.equal(duracionCorta(0), null);
});

/* ─── JSON-LD ────────────────────────────────────────────────────────────── */

test("videoObjectNode: name, description, thumbnailUrl y contentUrl absolutos, uploadDate y duration ISO", () => {
  const n = videoObjectNode(VIDEO, { ciudad: "Bermejo", base: API });
  assert.ok(n);
  assert.equal(n["@type"], "VideoObject");
  assert.equal(n.name, "Ferretería Ejemplo");
  assert.match(String(n.description), /Ferretería Ejemplo/);
  assert.match(String(n.description), /Bermejo/);
  assert.deepEqual(n.thumbnailUrl, [`${API}/public/videos/v1/cover`]);
  assert.equal(n.contentUrl, `${API}/public/videos/v1/video`);
  assert.equal(n.uploadDate, "2026-11-01T15:30:00.000Z");
  assert.equal(n.duration, "PT45S");
  for (const u of [...(n.thumbnailUrl as string[]), n.contentUrl as string]) assert.match(u, /^https?:\/\//);
});

test("videoObjectNode: un compilado (sin comercio) usa el título; sin duración no inventa una", () => {
  const n = videoObjectNode({ ...VIDEO, title: "Ofertas de la semana", comercio: null, duration_s: null }, { base: API });
  assert.ok(n);
  assert.match(String(n.description), /Ofertas de la semana/);
  assert.equal("duration" in n, false);
});

test("videoObjectNode: sin fecha de publicación válida no se declara el nodo", () => {
  assert.equal(videoObjectNode({ ...VIDEO, published_at: "" }, { base: API }), null);
  assert.equal(videoObjectNode({ ...VIDEO, published_at: "ayer" }, { base: API }), null);
  assert.equal(videoObjectNodes([VIDEO, { ...VIDEO, id: "v2", published_at: "" }], { base: API }).length, 1);
});

test("un título con </script> sale escapado en el JSON-LD", () => {
  const n = videoObjectNode({ ...VIDEO, title: "</script><b>x" }, { base: API });
  const s = serializeJsonLd({ "@graph": [n] });
  assert.ok(!s.includes("</script>"));
});

/* ─── Lectura defensiva de la API ────────────────────────────────────────── */

test("normalizarVideos: lo que no es una lista da []", () => {
  for (const v of [null, undefined, {}, { items: null }, { items: "x" }, 5, "x"]) assert.deepEqual(normalizarVideos(v), []);
});

test("normalizarVideos: descarta los items sin id, título, portada o video y deja los buenos", () => {
  const r = normalizarVideos({ items: [
    VIDEO,
    { ...VIDEO, id: "" }, { ...VIDEO, id: "v3", title: "" }, { ...VIDEO, id: "v4", cover_url: "" }, { ...VIDEO, id: "v5", video_url: null },
    null, 7,
  ] });
  assert.deepEqual(r.map((v) => v.id), ["v1"]);
});

test("normalizarVideos: sólo deja links de red http(s); javascript: y basura se descartan", () => {
  const [v] = normalizarVideos({ items: [{ ...VIDEO, network_links: {
    tiktok: "javascript:alert(1)", instagram: "https://www.instagram.com/reel/abc/", facebook: "no es un link", youtube: "", otra: "https://x.test",
  } }] });
  assert.deepEqual(v.network_links, { instagram: "https://www.instagram.com/reel/abc/" });
  assert.equal(esLinkWeb("data:text/html,x"), false);
  assert.equal(esLinkWeb("https://vm.tiktok.com/ZM1/"), true);
});

test("normalizarVideos: comercio incompleto pasa a null y la duración rara a null", () => {
  const [v] = normalizarVideos({ items: [{ ...VIDEO, comercio: { nombre: "Sin slug" }, duration_s: "10" }] });
  assert.equal(v.comercio, null);
  assert.equal(v.duration_s, null);
});

/* ─── Etiquetas de los arreglos del 2/11 ─────────────────────────────────── */

test("SKIP_REASON_LABEL suma comercio_inactivo y asset_removed", () => {
  assert.equal(SKIP_REASON_LABEL.comercio_inactivo, "El comercio está de baja");
  assert.equal(SKIP_REASON_LABEL.asset_removed, "Se quitó una foto");
});

/* ─── Archivos nuevos ────────────────────────────────────────────────────── */

const NUEVOS = [
  "components/videos-uruku.tsx", "components/video-uruku-card.tsx", "components/subscribers/entrega-a-mano.tsx",
  "lib/videos-pure.ts", "lib/videos-public.ts",
].map((f) => resolve(RAIZ, f));

const EMOJI = /[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}\u{200D}]/u;

test("ningún archivo nuevo de los videos tiene un emoji", () => {
  for (const f of NUEVOS) {
    const m = EMOJI.exec(readFileSync(f, "utf8"));
    assert.equal(m, null, `${f} tiene un emoji o pictograma: ${m?.[0]}`);
  }
});

test("ningún archivo nuevo de los videos toca secretos ni usa any", () => {
  for (const f of NUEVOS) {
    const t = readFileSync(f, "utf8");
    assert.ok(!/SERVICE_ROLE/i.test(t), `${f} menciona SERVICE_ROLE`);
    assert.ok(!/:\s*any\b|<any>|as any\b/.test(t.replace(/\/\/.*$/gm, "")), `${f} usa any`);
  }
});

test("la tarea piece_delivery no ofrece WhatsApp (ni el link wa.me ni el botón)", () => {
  const f = readFileSync(resolve(RAIZ, "components/subscribers/entrega-a-mano.tsx"), "utf8");
  assert.ok(!/wa\.me|EnvioWhatsapp|linkWhatsappTarea/.test(f));
  const dia = readFileSync(resolve(RAIZ, "components/content/content-day-package.tsx"), "utf8");
  assert.ok(!/EnvioWhatsapp/.test(dia), "el Paquete del día no tiene que mandar por WhatsApp");
});
