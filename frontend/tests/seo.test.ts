// Tests de la tarea F0 (docs/visibilidad-buscadores-ia.md §4): reglas de
// indexación, mapa rubro→schema, JSON-LD con escape, parser de horario.
// Se corren con `npm test` (tsc → node --test); no hay dependencias de test.
import test from "node:test";
import assert from "node:assert/strict";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import {
  ALLOWED_CRAWLERS, BLOCKED_AI_CRAWLERS, JSONLD_INCLUDE_TELEPHONE, PRIVATE_PATHS, RUBRO_SCHEMA_TYPE, SCHEMA_TYPE_WHITELIST,
  aboutPageNode, breadcrumbNode, esSlugPublico, urlDeImagenPropia, categoryPageState, cityHasIndexablePage, collectionPageNode,
  isBusinessIndexable, isBusinessThin, itemListNode, jsonLdGraph, localBusinessNode,
  openingHoursSpecification, organizationNodes, sameAsFromRedes, schemaTypeForRubro, serializeJsonLd,
  type BusinessSeoFields, type CityCategoryPage,
} from "../lib/seo";
import { JsonLd } from "../components/json-ld";
import { abiertoAhora, parseOpeningHours } from "../lib/horario";
import { enlaceRed } from "../lib/catalogo";
import { DESCRIPTOR, ONE_LINER, RESPONSIBLE, SLOGAN } from "../lib/marca";

/* ─── isBusinessThin: los 4 casos de §3.1 ────────────────────────────────── */

const base: BusinessSeoFields = { nombre: "Galería Cortez", rubro_slug: "otros", activo: true, suspendido: false };

test("isBusinessThin: rubro otros y sin ningún dato propio → vacía", () => {
  assert.equal(isBusinessThin(base), true);
  assert.equal(isBusinessThin({ ...base, rubro_slug: null, descripcion: "  ", subcategoria: "" }), true, "sin rubro y datos en blanco");
});

test("isBusinessThin: rubro otros pero con algún dato propio → no es vacía", () => {
  assert.equal(isBusinessThin({ ...base, subcategoria: "blanquería" }), false);
  assert.equal(isBusinessThin({ ...base, descripcion: "Frazadas y almohadas" }), false);
  assert.equal(isBusinessThin({ ...base, prod_obs_human: "frazada, almohada" }), false);
  assert.equal(isBusinessThin({ ...base, prod_det_ia: "toalla" }), false);
});

test("isBusinessThin: rubro real, aunque no tenga otros datos → no es vacía", () => {
  assert.equal(isBusinessThin({ ...base, rubro_slug: "farmacia" }), false);
});

test("isBusinessThin: nombre «a clasificar» → vacía aunque tenga rubro y datos", () => {
  assert.equal(isBusinessThin({ ...base, nombre: "Otros (A Clasificar)", rubro_slug: "ropa", descripcion: "Ropa" }), true);
});

test("isBusinessIndexable: activa, no suspendida y no vacía", () => {
  const buena = { ...base, rubro_slug: "ropa" };
  assert.equal(isBusinessIndexable(buena), true);
  assert.equal(isBusinessIndexable({ ...buena, activo: false }), false);
  assert.equal(isBusinessIndexable({ ...buena, suspendido: true }), false);
  assert.equal(isBusinessIndexable({ ...base }), false, "vacía");
  assert.equal(isBusinessIndexable({ nombre: "X", rubro_slug: "ropa" }), false, "sin el dato activo, no se indexa");
});

test("categoryPageState / cityHasIndexablePage según los pares de la RPC", () => {
  const par = (city: string, cat: string, indexable: boolean): CityCategoryPage => ({
    city_slug: city, city_name: city, region: "Tarija", category_slug: cat, category_name: cat, indexable, last_modified: null,
  });
  const pages = [par("bermejo", "ropa", true), par("bermejo", "farmacia", false), par("cochabamba", "ropa", false)];
  assert.equal(categoryPageState(pages, "bermejo", "ropa"), "index");
  assert.equal(categoryPageState(pages, "bermejo", "farmacia"), "noindex");
  assert.equal(categoryPageState(pages, "bermejo", "otros"), "missing");
  assert.equal(categoryPageState(pages, "yacuiba", "ropa"), "missing");
  assert.equal(cityHasIndexablePage(pages, "bermejo"), true);
  assert.equal(cityHasIndexablePage(pages, "cochabamba"), false);
});

/* ─── Rubro → schema.org ─────────────────────────────────────────────────── */

test("todo @type del mapa de rubros está en la lista blanca de schema.org", () => {
  for (const [rubro, tipo] of Object.entries(RUBRO_SCHEMA_TYPE)) {
    assert.ok(SCHEMA_TYPE_WHITELIST.includes(tipo), `${rubro} → ${tipo} no está en la lista blanca`);
  }
  assert.equal(schemaTypeForRubro("farmacia"), "Pharmacy");
  assert.equal(schemaTypeForRubro("blanqueria"), "HomeGoodsStore");
  assert.equal(schemaTypeForRubro("otros"), "LocalBusiness");
  assert.equal(schemaTypeForRubro("rubro-que-no-existe"), "LocalBusiness");
  assert.equal(schemaTypeForRubro(null), "LocalBusiness");
});

/* ─── Robots ─────────────────────────────────────────────────────────────── */

test("robots: Bytespider bloqueado; los de IA que quiere el dueño, permitidos", () => {
  assert.deepEqual([...BLOCKED_AI_CRAWLERS], ["Bytespider"]);
  assert.ok(!ALLOWED_CRAWLERS.includes("Bytespider"));
  for (const bot of ["GPTBot", "ClaudeBot", "Google-Extended", "meta-externalagent", "CCBot", "PerplexityBot"]) {
    assert.ok(ALLOWED_CRAWLERS.includes(bot), bot);
  }
});

test("robots: las pantallas privadas de la cuenta no se rastrean", () => {
  for (const p of ["/guia-venta", "/perfil", "/guardados", "/reservas", "/recuperar-negocio"]) assert.ok(PRIVATE_PATHS.includes(p), p);
});

test("esSlugPublico: sólo [a-z0-9-] de 2 a 40; el resto no toca la base", () => {
  for (const ok of ["bermejo", "la-paz", "ropa-americana", "a1"]) assert.equal(esSlugPublico(ok), true, ok);
  for (const no of [".env", "a", "Bermejo", "wp-login.php", "a/b", "x".repeat(41), "", "ropa_x"]) assert.equal(esSlugPublico(no), false, no);
});

test("urlDeImagenPropia: sólo hosts propios y https", () => {
  assert.equal(urlDeImagenPropia("https://uruku.bo/logo.png"), "https://uruku.bo/logo.png");
  assert.equal(urlDeImagenPropia("https://api.uruku.bo/fotos/x.jpg"), "https://api.uruku.bo/fotos/x.jpg");
  assert.equal(urlDeImagenPropia("/fotos/x.jpg"), "https://uruku.bo/fotos/x.jpg");
  for (const no of ["https://evil.example/x.jpg", "http://uruku.bo/x.jpg", "https://uruku.bo.evil.example/x.jpg", "https://evil.example/uruku.bo/x.jpg", "javascript:alert(1)", ""]) {
    assert.equal(urlDeImagenPropia(no), undefined, no);
  }
});

test("localBusinessNode: image sólo de hosts propios; la dirección sigue el orden visible (direccion || calle)", () => {
  const nodo = localBusinessNode({
    comercio: {
      slug: "a", nombre: "A", portada_url: "https://api.uruku.bo/fotos/a.jpg", logo_url: "https://cdn.otro.example/logo.png",
      direccion: "", calle: "Calle Sucre",
    },
    ciudad: { nombre: "Bermejo", departamento: "Tarija" },
  });
  assert.deepEqual(nodo.image, ["https://api.uruku.bo/fotos/a.jpg"]);
  assert.equal((nodo.address as { streetAddress?: string }).streetAddress, "Calle Sucre", "dirección vacía no tapa a la calle");
  const ambas = localBusinessNode({
    comercio: { slug: "a", nombre: "A", direccion: "Av. Petrolera 12", calle: "Petrolera" },
    ciudad: { nombre: "Bermejo", departamento: "Tarija" },
  });
  assert.equal((ambas.address as { streetAddress?: string }).streetAddress, "Av. Petrolera 12");
  assert.ok(!("image" in ambas));
});

/* ─── JSON-LD y escape ───────────────────────────────────────────────────── */

test("serializeJsonLd: un nombre «</script><b>» no puede cerrar la etiqueta", () => {
  const data = { "@type": "LocalBusiness", name: "</script><b>Hola</b> & \u2028 \u2029 fin" };
  const s = serializeJsonLd(data);
  for (const peligroso of ["<", ">", "&", "\u2028", "\u2029"]) assert.ok(!s.includes(peligroso), `quedó sin escapar: ${JSON.stringify(peligroso)}`);
  assert.deepEqual(JSON.parse(s), data, "sigue siendo JSON válido y equivalente");
});

test("<JsonLd>: el HTML tiene UN solo </script> y el nombre sale escapado", () => {
  const html = renderToStaticMarkup(createElement(JsonLd, { data: jsonLdGraph([{ "@type": "LocalBusiness", name: "</script><b>x" }]) }));
  assert.equal(html.split("</script>").length - 1, 1);
  assert.ok(html.startsWith('<script type="application/ld+json">'));
  assert.ok(!html.includes("<b>"));
  assert.ok(html.includes("\\u003c/script\\u003e\\u003cb\\u003ex"));
});

test("localBusinessNode: datos reales, sin rating ni horario estimado, con el @type del rubro", () => {
  const nodo = localBusinessNode({
    comercio: {
      slug: "galeria-cortez", nombre: "Galería cortez", calle: "Avenida Petrolera", lat: -22.7361, lng: -64.3433,
      whatsapp: "59167671888", horario: "Lun-Sáb 8:00-12:00 y 14:30-20:00", horario_estimado: true,
      portada_url: "https://api.uruku.bo/fotos/x.jpg", instagram_url: "@galeria", monedas_aceptadas: ["BOB", "ARS"],
    },
    ciudad: { nombre: "Bermejo", departamento: "Tarija" },
    rubroSlug: "blanqueria",
    productos: ["frazada", "almohada"],
  });
  assert.equal(nodo["@type"], "HomeGoodsStore");
  assert.equal(nodo["@id"], "https://uruku.bo/comercios/galeria-cortez#business");
  assert.equal(JSONLD_INCLUDE_TELEPHONE, false, "el teléfono va apagado por defecto (decide el dueño)");
  assert.ok(!("telephone" in nodo), "sin telephone mientras el interruptor esté apagado");
  assert.equal(nodo.keywords, "frazada, almohada");
  assert.equal(nodo.paymentAccepted, "BOB, ARS");
  assert.deepEqual(nodo.sameAs, ["https://instagram.com/galeria"]);
  assert.equal(nodo.openingHoursSpecification, undefined, "horario estimado: no se declara");
  for (const prohibido of ["aggregateRating", "review", "rating", "priceRange"]) assert.ok(!(prohibido in nodo), prohibido);
  const confirmado = localBusinessNode({
    comercio: { slug: "a", nombre: "A", horario: "Lun-Sáb 8:00-12:00 y 14:30-20:00", horario_estimado: false },
    ciudad: { nombre: "Bermejo", departamento: "Tarija" },
  });
  assert.ok(Array.isArray(confirmado.openingHoursSpecification));
  assert.equal(confirmado["@type"], "LocalBusiness");
});

test("ItemList / CollectionPage no llevan numberOfItems; migas sin item en la última", () => {
  const items = Array.from({ length: 150 }, (_, i) => ({ name: `R${i}`, path: `/bermejo/r${i}` }));
  const lista = itemListNode(items);
  assert.equal((lista.itemListElement as unknown[]).length, 100);
  assert.ok(!("numberOfItems" in lista));
  assert.ok(!JSON.stringify(collectionPageNode({ name: "Bermejo", path: "/bermejo", items })).includes("numberOfItems"));
  const migas = breadcrumbNode([{ name: "URUKU", path: "/" }, { name: "Bermejo", path: "/bermejo" }, { name: "Galería" }]);
  const els = migas.itemListElement as { item?: string; position: number }[];
  assert.equal(els[0].item, "https://uruku.bo/");
  assert.equal(els[2].item, undefined);
  assert.equal(els[2].position, 3);
});

test("organizationNodes: la marca del dueño y sameAs de las redes (YouTube incluido)", () => {
  const sameAs = sameAsFromRedes([
    { clave: "facebook", url: "https://www.facebook.com/uruku.bo/" },
    { clave: "tiktok", url: "@uruku.bo" },
    { clave: "youtube", url: "@uruku" },
    { clave: "instagram", url: "@uruku.bo", etiqueta: "Instagram (no disponible)" },
    { clave: "whatsapp", url: "https://wa.me/59167671888" },
  ]);
  assert.deepEqual(sameAs, [
    "https://www.facebook.com/uruku.bo/", "https://www.tiktok.com/@uruku.bo", "https://www.youtube.com/@uruku",
  ]);
  const [org, web] = organizationNodes({ sameAs, ciudades: [{ nombre: "Bermejo", departamento: "Tarija" }] });
  assert.equal(org.name, "URUKU");
  assert.deepEqual(org.alternateName, ["Uruku", "uruku.bo"]);
  assert.equal(org.description, ONE_LINER);
  assert.equal(org.slogan, SLOGAN);
  assert.equal(web["@type"], "WebSite");
  assert.equal(aboutPageNode()["@type"], "AboutPage");
  assert.equal(SLOGAN, "Llevá tu ciudad con vos.");
  assert.equal(DESCRIPTOR, "Guía de comercios y servicios de Bolivia");
  assert.equal(RESPONSIBLE, "Equipo URUKU");
});

test("enlaceRed: YouTube arma la URL del canal y rechaza esquemas peligrosos", () => {
  assert.equal(enlaceRed("youtube", "@uruku"), "https://www.youtube.com/@uruku");
  assert.equal(enlaceRed("youtube", "https://youtube.com/@uruku"), "https://youtube.com/@uruku");
  assert.equal(enlaceRed("youtube", "javascript:alert(1)"), null);
  assert.equal(enlaceRed("tiktok", "@x"), "https://www.tiktok.com/@x");
});

/* ─── parseOpeningHours / abiertoAhora ───────────────────────────────────── */

test("parseOpeningHours: «Lun-Sáb 8:00-12:00 y 14:30-20:00» → 6 días × 2 rangos", () => {
  const h = parseOpeningHours("Lun-Sáb 8:00-12:00 y 14:30-20:00");
  assert.ok(h);
  assert.equal(h.completo, true);
  assert.deepEqual(h.dias.map((d) => d.dia), [1, 2, 3, 4, 5, 6]);
  for (const d of h.dias) {
    assert.deepEqual(d.franjas, [{ desde: 480, hasta: 720 }, { desde: 870, hasta: 1200 }]);
  }
  const spec = openingHoursSpecification(h);
  assert.ok(spec);
  assert.equal(spec.length, 2, "dos franjas, con los 6 días agrupados");
  assert.equal((spec[0].dayOfWeek as string[]).length, 6);
  assert.equal(spec[0].opens, "08:00");
  assert.equal(spec[1].closes, "20:00");
});

test("parseOpeningHours: texto que no se entiende del todo → completo=false; vacío → null", () => {
  assert.equal(parseOpeningHours("Lun-Vie 9-18 · Dom cerrado")?.completo, false);
  assert.equal(parseOpeningHours("Lun-Vie 9-18 previa cita")?.completo, false);
  assert.equal(parseOpeningHours("Lun a Vie 9 a 13 y de 15 a 19")?.completo, true);
  assert.equal(openingHoursSpecification(parseOpeningHours("Lun-Vie 9-18 previa cita")), undefined);
  assert.equal(parseOpeningHours(""), null);
  assert.equal(parseOpeningHours(null), null);
  assert.equal(parseOpeningHours("consultar"), null);
});

// 2/11/2026 es lunes. `now` se inyecta: los getters locales son los «de Bolivia».
const lun = (h: number, m = 0) => new Date(2026, 10, 2, h, m);
const dom = (h: number, m = 0) => new Date(2026, 10, 8, h, m);
const sab3am = new Date(2026, 10, 7, 3, 0);

test("abiertoAhora: comportamiento previo intacto", () => {
  const H = "Lun-Sáb 8:00-12:00 y 14:30-20:00";
  assert.deepEqual(abiertoAhora(H, lun(10)), { estado: "abierto", cierraEn: 120 });
  assert.deepEqual(abiertoAhora(H, lun(13)), { estado: "cerrado", abreEn: 90, abreHoy: true });
  const domingo = abiertoAhora(H, dom(10));
  assert.equal(domingo.estado, "cerrado");
  assert.equal(domingo.abreHoy, false);
  // La tarde hereda los días de la mañana: el domingo a las 15 no está abierto.
  assert.equal(abiertoAhora("Lun a Sáb 8-12 · 14:30-20", dom(15)).estado, "cerrado");
  // Cruza la medianoche: el viernes 22–4 sigue abierto el sábado a las 3.
  assert.equal(abiertoAhora("Vie 22-4", sab3am).estado, "abierto");
  assert.equal(abiertoAhora("", lun(10)).estado, "desconocido");
  assert.equal(abiertoAhora(null, lun(10)).estado, "desconocido");
  assert.equal(abiertoAhora("consultar", lun(10)).estado, "desconocido");
  assert.equal(abiertoAhora("Mar-Sab 9:30-13 16-20 + Dom 9:30-13", dom(11)).estado, "abierto");
});
