/**
 * SEO y datos estructurados: las reglas en UN solo lugar.
 *
 * Spec: docs/visibilidad-buscadores-ia.md (§3.1 indexación, §3.4 robots, §3.6
 * JSON-LD, §3.10 marca). Lo importan la ficha, las rutas /{ciudad} y
 * /{ciudad}/{rubro}, robots.ts, sitemap.ts y la home. Ninguna de esas páginas
 * decide por su cuenta qué se indexa ni arma su propio JSON-LD.
 *
 * PUREZA: este módulo no hace red ni lee cookies, y sus imports de lib/ son
 * relativos (no `@/`): así los tests unitarios lo cargan con Node sin Next
 * (`npm test`).
 *
 * ─── API ───────────────────────────────────────────────────────────────────
 *
 * Indexación (§3.1)
 *   isBusinessThin(c)            ficha «vacía»: rubro otros/sin rubro y sin dato propio, o «… a clasificar»
 *   isBusinessIndexable(c)       activo, no suspendido y no vacía
 *   robotsFor(indexable)         { index, follow:true } para `metadata.robots`
 *   categoryPageState(pages, citySlug, categorySlug)  "missing" (404) | "noindex" | "index"
 *   cityHasIndexablePage(pages, citySlug)             ¿hay algún par indexable en la ciudad?
 *   indexablePagesOfCity(pages, citySlug)             los pares indexables de una ciudad
 *
 * Direcciones
 *   absoluteUrl(path)   cityPath(slug)   categoryPath(city, cat)   businessPath(slug)
 *
 * Rubro → tipo de schema.org (§3.6)
 *   RUBRO_SCHEMA_TYPE, SCHEMA_TYPE_WHITELIST, schemaTypeForRubro(slug)
 *
 * Robots (§3.4, decisión del dueño del 2/11: se permite todo salvo lo abusivo)
 *   ALLOWED_CRAWLERS, BLOCKED_AI_CRAWLERS, BLOCKED_SCRAPERS, PRIVATE_PATHS
 *
 * JSON-LD (§3.6). Todos devuelven objetos planos; se envuelven con
 * `jsonLdGraph([...])` y se dibujan con <JsonLd data={...} /> (components/json-ld.tsx).
 *   jsonLdGraph(nodes)            { "@context", "@graph" }
 *   organizationNodes(opts)       [Organization, WebSite]  (home)
 *   localBusinessNode(input)      LocalBusiness (o el subtipo del rubro)  (ficha)
 *   breadcrumbNode(items)         BreadcrumbList
 *   itemListNode(items, max=100)  ItemList sin numberOfItems
 *   collectionPageNode(opts)      CollectionPage con su ItemList  (/{ciudad})
 *   faqPageNode(preguntas)        FAQPage
 *   aboutPageNode(opts?)          AboutPage  (/que-es-uruku)
 *   openingHoursSpecification(h)  OpeningHoursSpecification[] o undefined
 *   sameAsFromRedes(redes)        URLs de las redes de la marca
 *   serializeJsonLd(data)         JSON seguro para ir dentro de <script>
 *
 * Reglas del JSON-LD: sólo datos reales y visibles; nunca aggregateRating,
 * review, rating, priceRange ni horario estimado; nunca un número de comercios.
 */
import { enlaceRed } from "./catalogo";
import { parseOpeningHours, type HorarioParseado } from "./horario";
import {
  BRAND_ALTERNATE_NAMES, BRAND_NAME, CONTACT, ENTITY_PROFILES, ONE_LINER, SITE_URL, SLOGAN,
} from "./marca";

/* ─── Reglas de indexación (§3.1) ─────────────────────────────────────────── */

/** Un par ciudad+rubro con comercios, tal como lo devuelve la RPC
 *  `city_category_pages()` (migración 0169). A propósito NO trae el conteo: el
 *  número de comercios no sale al público. `indexable` = el par llega al umbral
 *  (5 comercios) que decide la base. Se lee con `getCityCategoryPages()` (data.ts). */
export type CityCategoryPage = {
  city_slug: string;
  city_name: string;
  /** `ciudades.departamento`. */
  region: string;
  category_slug: string;
  category_name: string;
  indexable: boolean;
  /** El `updated_at` más reciente de los comercios del par (ISO). */
  last_modified: string | null;
};

/** Los datos de un comercio que deciden si su ficha vale la pena indexar. */
export type BusinessSeoFields = {
  nombre: string;
  /** Slug del rubro principal; `null`/ausente = sin rubro. */
  rubro_slug?: string | null;
  subcategoria?: string | null;
  descripcion?: string | null;
  prod_obs_human?: string | null;
  prod_det_ia?: string | null;
  activo?: boolean;
  suspendido?: boolean | null;
};

function blank(s: string | null | undefined): boolean {
  return s == null || s.trim() === "";
}

/**
 * Ficha «vacía» (§3.1): rubro `otros` (o ninguno) y sin subcategoría, descripción
 * ni productos; o un nombre «… a clasificar». Son las que Google leería como
 * páginas casi iguales («Otros (a clasificar) en Santa Cruz»).
 *
 *   thin = (rubro ∈ {null, otros} ∧ todo lo demás en blanco) ∨ nombre ~ /a clasificar/i
 *
 * Se vuelve indexable sola cuando alguien la clasifica o le carga datos.
 */
export function isBusinessThin(c: BusinessSeoFields): boolean {
  const sinRubro = c.rubro_slug == null || c.rubro_slug === "otros";
  const sinDatos = blank(c.subcategoria) && blank(c.descripcion) && blank(c.prod_obs_human) && blank(c.prod_det_ia);
  return (sinRubro && sinDatos) || /a clasificar/i.test(c.nombre);
}

/** ¿La ficha va al índice? Activa, no suspendida y no vacía. `activo` ausente
 *  cuenta como NO: sin el dato, ante la duda no se indexa. */
export function isBusinessIndexable(c: BusinessSeoFields): boolean {
  return c.activo === true && !c.suspendido && !isBusinessThin(c);
}

/** El valor de `metadata.robots`: las páginas pobres se rastrean pero no se
 *  indexan (`noindex, follow`: los enlaces que llevan siguen contando). */
export function robotsFor(indexable: boolean): { index: boolean; follow: boolean } {
  return { index: indexable, follow: true };
}

/** El estado de la página de un par ciudad+rubro según `city_category_pages()`:
 *  `missing` → 404 (no existe, ciudad inactiva, rubro `otros` o inactivo),
 *  `noindex` → 200 con `noindex, follow` (menos de 5 comercios), `index` → 200. */
export function categoryPageState(
  pages: readonly CityCategoryPage[], citySlug: string, categorySlug: string,
): "missing" | "noindex" | "index" {
  const p = pages.find((x) => x.city_slug === citySlug && x.category_slug === categorySlug);
  if (!p) return "missing";
  return p.indexable ? "index" : "noindex";
}

/** Los pares indexables de una ciudad (los que van al sitemap y a los enlaces). */
export function indexablePagesOfCity(pages: readonly CityCategoryPage[], citySlug: string): CityCategoryPage[] {
  return pages.filter((p) => p.city_slug === citySlug && p.indexable);
}

/** ¿La ciudad tiene algún par indexable? Si no, su página va `noindex, follow`. */
export function cityHasIndexablePage(pages: readonly CityCategoryPage[], citySlug: string): boolean {
  return pages.some((p) => p.city_slug === citySlug && p.indexable);
}

/* ─── Direcciones absolutas ───────────────────────────────────────────────── */

/** `/algo` → `https://uruku.bo/algo` (acepta con o sin barra inicial). */
export function absoluteUrl(path = "/"): string {
  return `${SITE_URL}${path.startsWith("/") ? path : `/${path}`}`;
}
export const cityPath = (citySlug: string): string => `/${citySlug}`;
export const categoryPath = (citySlug: string, categorySlug: string): string => `/${citySlug}/${categorySlug}`;
export const businessPath = (slug: string): string => `/comercios/${slug}`;

/* ─── Rubro → tipo de schema.org (§3.6) ───────────────────────────────────── */

/** Tipo de schema.org de la ficha según el rubro principal. Lo que no está acá
 *  (y `otros`) es `LocalBusiness`; «lavadero» y «salones» son ambiguos a propósito. */
export const RUBRO_SCHEMA_TYPE: Readonly<Record<string, string>> = {
  ropa: "ClothingStore", lenceria: "ClothingStore", "ropa-americana": "ClothingStore",
  calzado: "ShoeStore", "calzado-usado": "ShoeStore",
  joyeria: "JewelryStore",
  celulares: "MobilePhoneStore",
  computacion: "ComputerStore",
  electronica: "ElectronicsStore", electrodomesticos: "ElectronicsStore",
  bazar: "HomeGoodsStore", hogar: "HomeGoodsStore", blanqueria: "HomeGoodsStore",
  muebles: "FurnitureStore",
  ferreteria: "HardwareStore",
  "repuestos-autos": "AutoPartsStore",
  neumaticos: "TireShop",
  motos: "MotorcycleDealer",
  bicicletas: "BikeStore",
  alimentos: "GroceryStore",
  kiosco: "ConvenienceStore",
  mascotas: "PetStore",
  jugueteria: "ToyStore",
  deportes: "SportingGoodsStore",
  floreria: "Florist",
  bolsos: "Store", marroquineria: "Store", bebidas: "Store", bebes: "Store", regaleria: "Store",
  usados: "Store", agro: "Store", coca: "Store", limpieza: "Store", telas: "Store", carniceria: "Store",
  farmacia: "Pharmacy",
  optica: "Optician",
  peluqueria: "HairSalon",
  belleza: "HealthAndBeautyBusiness",
  gimnasios: "ExerciseGym",
  restaurantes: "Restaurant",
  "comida-rapida": "FastFoodRestaurant",
  cafeteria: "CafeOrCoffeeShop",
  panaderia: "Bakery",
  hospedaje: "LodgingBusiness",
  nocturna: "NightClub",
  "taller-mecanico": "AutoRepair", "gomeria-servicio": "AutoRepair",
  "estacion-servicio": "GasStation",
  cambio: "FinancialService",
  cajeros: "AutomatedTeller",
  cerrajeria: "Locksmith",
  carpinteria: "HomeAndConstructionBusiness", herreria: "HomeAndConstructionBusiness",
  emergencias: "EmergencyService",
  banos: "PublicToilet",
  estacionamiento: "ParkingFacility",
  lavadero: "LocalBusiness", salones: "LocalBusiness", envios: "LocalBusiness", taxis: "LocalBusiness",
  wifi: "LocalBusiness", alquiler: "LocalBusiness", "servicio-tecnico": "LocalBusiness",
  funeraria: "LocalBusiness", otros: "LocalBusiness",
};

/** Los tipos de schema.org que se pueden emitir para una ficha. Escrita a mano
 *  y aparte del mapa: si alguien tipea mal un tipo (`Pharmasy`), el test lo atrapa. */
export const SCHEMA_TYPE_WHITELIST: readonly string[] = [
  "LocalBusiness", "Store", "ClothingStore", "ShoeStore", "JewelryStore", "MobilePhoneStore", "ComputerStore",
  "ElectronicsStore", "HomeGoodsStore", "FurnitureStore", "HardwareStore", "AutoPartsStore", "TireShop",
  "MotorcycleDealer", "BikeStore", "GroceryStore", "ConvenienceStore", "PetStore", "ToyStore",
  "SportingGoodsStore", "Florist", "Pharmacy", "Optician", "HairSalon", "HealthAndBeautyBusiness",
  "ExerciseGym", "Restaurant", "FastFoodRestaurant", "CafeOrCoffeeShop", "Bakery", "LodgingBusiness",
  "NightClub", "AutoRepair", "GasStation", "FinancialService", "AutomatedTeller", "Locksmith",
  "HomeAndConstructionBusiness", "EmergencyService", "PublicToilet", "ParkingFacility",
];

/** El tipo de la ficha para un rubro; sin mapeo (o sin rubro) → `LocalBusiness`. */
export function schemaTypeForRubro(rubroSlug: string | null | undefined): string {
  return (rubroSlug && RUBRO_SCHEMA_TYPE[rubroSlug]) || "LocalBusiness";
}

/* ─── Robots (§3.4) ───────────────────────────────────────────────────────── */

/** Buscadores, asistentes de IA y robots de entrenamiento permitidos (decisión
 *  D-2 de la spec: «cualquier IA»). Un robot que coincide con un grupo con
 *  nombre IGNORA el grupo `*`, así que robots.ts repite `PRIVATE_PATHS` en cada grupo. */
export const ALLOWED_CRAWLERS: readonly string[] = [
  "OAI-SearchBot", "GPTBot", "ChatGPT-User", "Googlebot", "Google-Extended", "Bingbot",
  "ClaudeBot", "Claude-SearchBot", "Claude-User", "PerplexityBot", "Perplexity-User",
  "Applebot", "Applebot-Extended", "meta-externalagent", "meta-externalfetcher",
  "Amazonbot", "DuckAssistBot", "CCBot", "MistralAI-User",
];

/** Robots de IA que se bloquean por abusivos (decisión del dueño, 2/11): rastreo
 *  agresivo y sin valor en Bolivia ni Argentina. */
export const BLOCKED_AI_CRAWLERS: readonly string[] = ["Bytespider"];

/** Scrapers y herramientas de SEO que la spec bloquea (§3.4, grupo 2). Va APARTE
 *  de `BLOCKED_AI_CRAWLERS` porque el dueño sólo nombró a Bytespider: quien arme
 *  robots.ts decide si los incluye. */
export const BLOCKED_SCRAPERS: readonly string[] = ["Diffbot", "omgili", "SemrushBot-SWA"];

/** Lo que ningún robot debe rastrear. */
export const PRIVATE_PATHS: readonly string[] = [
  "/admin", "/contenido", "/publicar", "/campo", "/mi-comercio", "/volante/",
];

/* ─── JSON-LD ─────────────────────────────────────────────────────────────── */

export type JsonLdNode = { [clave: string]: unknown };

/**
 * Serializa JSON-LD para ir DENTRO de un `<script>`. Escapa `<`, `>`, `&` y los
 * separadores de línea U+2028/U+2029 como `\uXXXX` (siguen siendo JSON válido):
 * los nombres los cargan agentes y la IA, y un comercio llamado `</script><b>`
 * cerraría la etiqueta e inyectaría HTML. OBLIGATORIO para todo JSON-LD.
 */
export function serializeJsonLd(data: unknown): string {
  return JSON.stringify(data)
    .replace(/</g, "\\u003c")
    .replace(/>/g, "\\u003e")
    .replace(/&/g, "\\u0026")
    .replace(new RegExp("\u2028", "g"), "\\u2028")
    .replace(new RegExp("\u2029", "g"), "\\u2029");
}

/** Junta nodos en un solo documento `@graph` (un solo `<script>` por página). */
export function jsonLdGraph(nodes: readonly (JsonLdNode | null | undefined)[]): JsonLdNode {
  return { "@context": "https://schema.org", "@graph": nodes.filter((n): n is JsonLdNode => Boolean(n)) };
}

export type MigaItem = { name: string; /** Ruta (`/bermejo`); sin ella, es la página actual. */ path?: string };

/** Migas. La última (la página actual) va sin `item`, como pide Google. */
export function breadcrumbNode(items: readonly MigaItem[]): JsonLdNode {
  return {
    "@type": "BreadcrumbList",
    itemListElement: items.map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name,
      ...(it.path ? { item: absoluteUrl(it.path) } : {}),
    })),
  };
}

export type ListaItem = { name: string; path: string };

/** `ItemList` de enlaces. Sin `numberOfItems`: ningún número de comercios sale al público. */
export function itemListNode(items: readonly ListaItem[], max = 100): JsonLdNode {
  return {
    "@type": "ItemList",
    itemListElement: items.slice(0, max).map((it, i) => ({
      "@type": "ListItem", position: i + 1, url: absoluteUrl(it.path), name: it.name,
    })),
  };
}

/** `CollectionPage` con la lista de páginas que agrupa (la página de una ciudad). */
export function collectionPageNode(o: { name: string; path: string; description?: string; items: readonly ListaItem[] }): JsonLdNode {
  return {
    "@type": "CollectionPage",
    "@id": `${absoluteUrl(o.path)}#page`,
    name: o.name,
    url: absoluteUrl(o.path),
    inLanguage: "es",
    ...(o.description ? { description: o.description } : {}),
    mainEntity: itemListNode(o.items),
  };
}

/** `FAQPage`: debe llevar EXACTAMENTE las preguntas visibles en la página. Textos planos. */
export function faqPageNode(preguntas: readonly { pregunta: string; respuesta: string }[]): JsonLdNode {
  return {
    "@type": "FAQPage",
    mainEntity: preguntas.map((p) => ({
      "@type": "Question",
      name: p.pregunta,
      acceptedAnswer: { "@type": "Answer", text: p.respuesta },
    })),
  };
}

/** `AboutPage` de /que-es-uruku; apunta al mismo nodo `Organization` de la home. */
export function aboutPageNode(o: { path?: string; name?: string } = {}): JsonLdNode {
  const path = o.path ?? "/que-es-uruku";
  return {
    "@type": "AboutPage",
    "@id": `${absoluteUrl(path)}#page`,
    url: absoluteUrl(path),
    name: o.name ?? `Qué es ${BRAND_NAME}`,
    inLanguage: "es",
    about: { "@id": ORGANIZATION_ID },
    isPartOf: { "@id": WEBSITE_ID },
  };
}

const ORGANIZATION_ID = `${SITE_URL}/#organization`;
const WEBSITE_ID = `${SITE_URL}/#website`;

/** Lo que `getRedes()` devuelve (estructural, para no depender de data.ts). */
export type RedPublica = { clave: string; url: string | null; etiqueta?: string | null };

/**
 * Las URLs de las redes de la MARCA para `sameAs`: `getRedes()` normalizado (los
 * handles `@uruku.bo` pasan a URL con `enlaceRed`) más `ENTITY_PROFILES`. Una red
 * cuyo perfil diga «no disponible» queda afuera (hoy Instagram); lo que no es
 * una red pública conocida (WhatsApp, etc.) tampoco entra. Sin repetidos.
 */
export function sameAsFromRedes(redes: readonly RedPublica[]): string[] {
  const conocidas = ["instagram", "tiktok", "facebook", "youtube"] as const;
  const out: string[] = [];
  for (const r of redes) {
    const clave = conocidas.find((k) => k === r.clave.toLowerCase());
    if (!clave || !r.url) continue;
    if (/no disponible/i.test(`${r.etiqueta ?? ""} ${r.url}`)) continue;
    const url = enlaceRed(clave, r.url);
    if (url && url.startsWith("https://")) out.push(url);
  }
  out.push(...ENTITY_PROFILES);
  return [...new Set(out)];
}

/** Una ciudad atendida, para `Organization.areaServed`. */
export type CiudadServida = { nombre: string; departamento: string; pais?: string | null };

function paisIso(pais: string | null | undefined): string {
  return pais && /argentina/i.test(pais) ? "AR" : "BO";
}

/**
 * Los nodos de la home: `Organization` + `WebSite` (§3.6). `ciudades`: sólo las
 * que tienen al menos un par indexable (no una ciudad vacía). `sameAs`: salida de
 * `sameAsFromRedes()`.
 */
export function organizationNodes(o: { ciudades?: readonly CiudadServida[]; sameAs?: readonly string[] } = {}): JsonLdNode[] {
  const sameAs = o.sameAs ?? [];
  return [
    {
      "@type": "Organization",
      "@id": ORGANIZATION_ID,
      name: BRAND_NAME,
      alternateName: [...BRAND_ALTERNATE_NAMES],
      url: `${SITE_URL}/`,
      logo: { "@type": "ImageObject", url: `${SITE_URL}/logouruku.png` },
      description: ONE_LINER,
      slogan: SLOGAN,
      email: CONTACT.email,
      contactPoint: {
        "@type": "ContactPoint", telephone: CONTACT.telefono, contactType: "customer support", availableLanguage: "es",
      },
      ...((o.ciudades?.length ?? 0) > 0 ? {
        areaServed: o.ciudades!.map((c) => ({
          "@type": "City",
          name: c.nombre,
          containedInPlace: { "@type": "AdministrativeArea", name: `${c.departamento}, ${/argentina/i.test(c.pais ?? "") ? "Argentina" : "Bolivia"}` },
        })),
      } : {}),
      ...(sameAs.length > 0 ? { sameAs: [...sameAs] } : {}),
    },
    {
      "@type": "WebSite",
      "@id": WEBSITE_ID,
      url: `${SITE_URL}/`,
      name: BRAND_NAME,
      inLanguage: "es",
      publisher: { "@id": ORGANIZATION_ID },
      potentialAction: {
        "@type": "SearchAction",
        target: { "@type": "EntryPoint", urlTemplate: `${SITE_URL}/buscar?q={search_term_string}` },
        "query-input": "required name=search_term_string",
      },
    },
  ];
}

const DIA_SCHEMA = [
  "", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
].map((d) => (d ? `https://schema.org/${d}` : ""));

function hhmm(min: number): string {
  const m = min >= 24 * 60 ? 0 : min;   // 24:00 se escribe 00:00
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
}

/**
 * `openingHoursSpecification` desde el horario parseado, o `undefined` si no se
 * debe declarar: sólo cuando el parser entendió TODO el texto (`completo`).
 * Los días con las mismas franjas se agrupan en un solo `dayOfWeek`. El
 * llamador además exige `horario_estimado === false` (ver `localBusinessNode`).
 */
export function openingHoursSpecification(h: HorarioParseado | null): JsonLdNode[] | undefined {
  if (!h || !h.completo || h.dias.length === 0) return undefined;
  const grupos = new Map<string, { dias: number[]; franjas: HorarioParseado["dias"][number]["franjas"] }>();
  for (const d of h.dias) {
    const clave = d.franjas.map((f) => `${f.desde}-${f.hasta}`).join("|");
    const g = grupos.get(clave) ?? { dias: [], franjas: d.franjas };
    g.dias.push(d.dia);
    grupos.set(clave, g);
  }
  const out: JsonLdNode[] = [];
  for (const g of grupos.values()) {
    for (const f of g.franjas) {
      out.push({
        "@type": "OpeningHoursSpecification",
        dayOfWeek: g.dias.map((d) => DIA_SCHEMA[d]),
        opens: hhmm(f.desde),
        closes: hhmm(f.hasta),
      });
    }
  }
  return out;
}

/** Los campos del comercio que usa `localBusinessNode`. */
export type LocalBusinessFields = {
  slug: string;
  nombre: string;
  descripcion?: string | null;
  calle?: string | null;
  direccion?: string | null;
  lat?: number | null;
  lng?: number | null;
  whatsapp?: string | null;
  telefono?: string | null;
  horario?: string | null;
  horario_estimado?: boolean;
  monedas_aceptadas?: string[] | null;
  tiktok_url?: string | null;
  facebook_url?: string | null;
  instagram_url?: string | null;
  sitio_web?: string | null;
  portada_url?: string | null;
  logo_url?: string | null;
};

export type LocalBusinessInput = {
  comercio: LocalBusinessFields;
  ciudad: { nombre: string; departamento: string; pais?: string | null };
  /** Rubro principal; define el `@type`. */
  rubroSlug?: string | null;
  /** Lo que vende (los de «Qué podés encontrar acá»); va a `keywords`. */
  productos?: readonly string[];
  /** Descripción ya armada para la página (la misma que la meta). Por defecto, `comercio.descripcion`. */
  descripcion?: string | null;
};

function absolutaOUndef(u: string | null | undefined): string | undefined {
  const t = (u ?? "").trim();
  if (!t) return undefined;
  if (/^https?:\/\//i.test(t)) return t;
  return t.startsWith("/") ? absoluteUrl(t) : undefined;
}

/**
 * El nodo `LocalBusiness` (o el subtipo del rubro) de una ficha (§3.6). Sólo
 * emite lo que hay: teléfono, horario, redes, monedas y coordenadas son
 * condicionales. NUNCA emite rating, reseñas, `priceRange` ni el horario
 * estimado (`horario_estimado !== false` → sin horario). El nodo se junta con
 * `breadcrumbNode` en un `jsonLdGraph`.
 */
export function localBusinessNode(i: LocalBusinessInput): JsonLdNode {
  const c = i.comercio;
  const url = absoluteUrl(businessPath(c.slug));
  const imagenes = [absolutaOUndef(c.portada_url), absolutaOUndef(c.logo_url)].filter((x): x is string => Boolean(x));
  const descripcion = (i.descripcion ?? c.descripcion ?? "").trim();
  const calle = (c.calle ?? c.direccion ?? "").trim();
  const digitos = (c.whatsapp ?? "").replace(/\D/g, "");
  const telefono = digitos ? `+${digitos}` : (c.telefono ?? "").trim();
  const sameAs = [
    enlaceRed("tiktok", c.tiktok_url), enlaceRed("instagram", c.instagram_url),
    enlaceRed("facebook", c.facebook_url), enlaceRed("web", c.sitio_web),
  ].filter((x): x is string => x != null && x.startsWith("https://"));
  const horario = c.horario_estimado === false ? openingHoursSpecification(parseOpeningHours(c.horario)) : undefined;
  const claves = (i.productos ?? []).map((p) => p.trim()).filter(Boolean);
  const tieneGeo = typeof c.lat === "number" && typeof c.lng === "number";

  return {
    "@type": schemaTypeForRubro(i.rubroSlug),
    "@id": `${url}#business`,
    name: c.nombre,
    url,
    ...(imagenes.length > 0 ? { image: imagenes } : {}),
    ...(descripcion ? { description: descripcion } : {}),
    ...(claves.length > 0 ? { keywords: claves.join(", ") } : {}),
    address: {
      "@type": "PostalAddress",
      ...(calle ? { streetAddress: calle } : {}),
      addressLocality: i.ciudad.nombre,
      addressRegion: i.ciudad.departamento,
      addressCountry: paisIso(i.ciudad.pais),
    },
    ...(tieneGeo ? { geo: { "@type": "GeoCoordinates", latitude: c.lat, longitude: c.lng } } : {}),
    ...(telefono ? { telephone: telefono } : {}),
    ...(horario ? { openingHoursSpecification: horario } : {}),
    ...(sameAs.length > 0 ? { sameAs: [...new Set(sameAs)] } : {}),
    ...((c.monedas_aceptadas?.length ?? 0) > 0 ? { paymentAccepted: c.monedas_aceptadas!.join(", ") } : {}),
  };
}
