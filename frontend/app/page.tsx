import type { Metadata } from "next";
import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { UnirmeComunidad } from "@/components/unirme-comunidad";
import { FECHA_LANZAMIENTO, faltaParaLanzamiento } from "@/lib/lanzamiento";
import { getClima, getCotizaciones, getFeed, getFronteraEstado, getVideosPromo } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";
import { precioFmt } from "@/lib/types";
import { formatoMonto, tasasDe } from "@/lib/cambio";

export const dynamic = "force-dynamic";

/**
 * El home: "Todo Bermejo en un solo lugar".
 *
 * Cambió el 16/9: antes hablaba del sitio ("descubrí Bermejo como nunca
 * antes") y le vendía al comerciante desde el hero. Ahora le sirve al que
 * llega: qué necesita (baños, cajeros, farmacias, cambio), cómo está la
 * frontera hoy, qué tiene que saber antes de comprar, y las ofertas. Cada
 * cosa aparece UNA vez —el cambio vive en /cambio, con calculadora y casas
 * de cambio juntas, y desde acá se llega por un solo lugar—. El comerciante
 * tiene su banner al pie, que es donde lo busca el que ya tiene un negocio.
 */

// Los servicios del mapa. Todos son RUBROS —baños, cajeros, estacionamientos
// y wifi son rubros no comerciales (0083, 0113)— así que cada acceso trae
// exactamente lo cargado bajo ese rubro, no lo que el texto libre encuentre
// ("estacionamiento" devolvía estaciones de servicio). El cambio va a /cambio.
const SERVICIOS = [
  { i: "🚻", t: "Baños cercanos", d: "Ubicaciones", href: "/buscar?rubro=banos&vista=mapa" },
  { i: "💊", t: "Farmacias", d: "Turnos y direcciones", href: "/buscar?rubro=farmacia&vista=mapa" },
  { i: "🏧", t: "Cajeros y bancos", d: "Dónde sacar plata", href: "/buscar?rubro=cajeros&vista=mapa" },
  { i: "🅿️", t: "Estacionamiento", d: "Dónde dejar el auto", href: "/buscar?rubro=estacionamiento&vista=mapa" },
  { i: "💱", t: "Casas de cambio", d: "Cotización, calculadora y mapa", href: "/cambio" },
  { i: "📶", t: "WiFi y chips", d: "Internet y telefonía", href: "/buscar?rubro=wifi&vista=mapa" },
  { i: "🚕", t: "Taxis y transporte", d: "Cómo moverte", href: "/buscar?rubro=taxis&vista=mapa" },
  { i: "🚓", t: "Policía y emergencias", d: "Dónde están, y los teléfonos", href: "/buscar?rubro=emergencias&vista=mapa" },
];

// Sin frontera: el cambio es un rubro más (casas de cambio en el mapa), no
// la página de pesos argentinos.
const SERVICIOS_SIN_GUIA = SERVICIOS.map((s) =>
  s.href === "/cambio" ? { ...s, d: "Dólares y otras monedas", href: "/buscar?rubro=cambio&vista=mapa" } : s);

// La fila de accesos debajo del buscador: los mismos destinos, en una palabra.
const CHIPS = [
  { i: "🚻", t: "Baños", href: SERVICIOS[0].href }, { i: "💊", t: "Farmacias", href: SERVICIOS[1].href },
  { i: "🏧", t: "Cajeros", href: SERVICIOS[2].href }, { i: "🅿️", t: "Estacionamiento", href: SERVICIOS[3].href },
  { i: "💱", t: "Casas de cambio", href: "/cambio" }, { i: "🚕", t: "Taxis", href: SERVICIOS[6].href },
  { i: "📶", t: "WiFi", href: SERVICIOS[5].href },
  { i: "🚓", t: "Policía", href: SERVICIOS[7].href },
  { i: "🚌", t: "Transporte", href: "/guia#transporte" }, { i: "🌉", t: "Frontera", href: "/guia#frontera" },
];
const CHIPS_SIN_GUIA = CHIPS
  .filter((c) => !c.href.startsWith("/guia"))
  .map((c) => (c.href === "/cambio" ? { ...c, t: "Cambio", href: "/buscar?rubro=cambio&vista=mapa" } : c));

const GUIAS = [
  { i: "🛃", t: "Aduana", d: "Franquicia, qué podés pasar y qué no.", href: "/guia#aduana" },
  { i: "🪪", t: "Documentación", d: "DNI, pasaporte y viaje con menores.", href: "/guia#documentos" },
  { i: "🌉", t: "Frontera", d: "Estado del paso, horarios, río y clima.", href: "/guia#frontera" },
  { i: "🛍️", t: "Comprar", d: "Horarios, por docena, pagos y envíos.", href: "/guia#comercios" },
];

const HERRAMIENTAS = [
  { i: "🚌", t: "Cómo llegar", href: "/guia#transporte" },
  { i: "🏔️", t: "Cómo salir de la ciudad", href: "/guia#transporte" },
  { i: "🕒", t: "Qué está abierto ahora", href: "/guia#comercios" },
  { i: "📍", t: "Qué hay cerca tuyo", href: "/buscar?cerca=1" },
];
const HERRAMIENTAS_SIN_GUIA = [
  { i: "📍", t: "Qué hay cerca tuyo", href: "/buscar?cerca=1" },
  { i: "🗺️", t: "Todo en el mapa", href: "/buscar?vista=mapa" },
  { i: "🏷️", t: "Las ofertas de hoy", href: "/buscar?of=1" },
];

const INFO = [
  { i: "💳", t: "Medios de pago", d: "Pesos, bolivianos, dólares, QR", href: "/guia#comercios" },
  { i: "🛡️", t: "Seguridad y consejos", d: "Para la primera vez", href: "/guia#seguridad" },
  { i: "📞", t: "Teléfonos útiles", d: "110 · 119 · 168 y dónde queda la policía", href: "/guia#seguridad" },
  { i: "📱", t: "Comprar chip o eSIM", d: "Entel y Tigo", href: "/guia#conectividad" },
  { i: "▶️", t: "Videos guía", d: "Recorridos y tips", href: "/guia#ofertas" },
  { i: "⭐", t: "Top de ofertas", d: "Lo más buscado", href: "/buscar?of=1" },
];

const ESTADO: Record<string, Record<string, [string, string]>> = {
  puente: { normal: ["habilitada", "ok"], demoras: ["con demoras", "ojo"], cerrado: ["cerrada", "mal"] },
  chalanas: { operando: ["operando", "ok"], limitadas: ["con restricciones", "ojo"], suspendidas: ["suspendidas", "mal"] },
  rio: { normal: ["normal", "ok"], crecido: ["crecido", "ojo"] },
};

function hace(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(min) || min < 0) return null;
  if (min < 60) return `hace ${Math.max(1, min)} min`;
  if (min < 48 * 60) return `hace ${Math.floor(min / 60)} h`;
  return `hace ${Math.floor(min / 1440)} días`;
}

export async function generateMetadata(): Promise<Metadata> {
  const { ciudad } = await ciudadActual();
  const nombre = ciudad?.nombre ?? "Bermejo";
  // Cada frontera tiene su guía y su estado del paso (0124).
  const conGuia = ciudad ? (ciudad.guia_activa ?? ciudad.slug === "bermejo") : true;
  return {
    title: `URUKU — Todo ${nombre} en un solo lugar`,
    description: conGuia
      ? "Comercios, ofertas, cambio, servicios y la guía para tu visita a Bermejo: qué se vende, dónde, cómo llegar y el WhatsApp de cada local."
      : `Comercios, ofertas y servicios de ${nombre}: qué se vende, dónde, cómo llegar y el WhatsApp de cada local.`,
  };
}

export default async function InicioPage() {
  const { ciudad } = await ciudadActual();
  // Lo de la frontera —el paso, las chalanas, la guía del que cruza, la
  // comunidad, los videos— está cargado para Bermejo. En otra ciudad no se
  // muestra: un "Frontera: habilitada" en Santa Cruz es un dato inventado.
  // (Otra frontera, Yacuiba o Villazón, tendrá lo suyo cuando se cargue.)
  const conGuia = (ciudad?.slug ?? "bermejo") === "bermejo";
  // El peso argentino, en cualquier ciudad de frontera.
  const esFrontera = ciudad?.es_frontera ?? true;
  const [feed, videos, frontera, clima, cotizaciones] = await Promise.all([
    getFeed(12, ciudad?.slug), conGuia ? getVideosPromo(6) : Promise.resolve([]),
    conGuia ? getFronteraEstado(ciudad?.id) : Promise.resolve(null), conGuia ? getClima() : Promise.resolve(null), getCotizaciones(),
  ]);
  const nombre = ciudad?.nombre ?? "Bermejo";
  // La foto del hero es de la ciudad; sin foto propia, la de Bermejo sólo en
  // Bermejo. Otra ciudad sin foto va con el fondo liso, no con el río de otra.
  const heroImg = ciudad?.hero_url || (conGuia ? "/bermejo-ciudad4.png" : "");
  const ofertas = feed.filter((f) => f.tipo === "oferta");
  const cards = (ofertas.length ? ofertas : feed.filter((f) => f.tipo !== "video")).slice(0, 4);
  const t = tasasDe(cotizaciones);
  const fechas = [frontera?.actualizado_en, t.actualizado_en].filter(Boolean) as string[];
  const ultima = fechas.length ? fechas.sort()[fechas.length - 1] : null;

  return (
    <UrukuShell activeCat="Todos" activeNav="Inicio">
      {/* ===== Los accesos rápidos, debajo del buscador ===== */}
      <nav className="uk-container uk-home-chips" aria-label="Servicios">
        {(conGuia ? CHIPS : CHIPS_SIN_GUIA).map((c) => <Link key={c.t} href={c.href}><span aria-hidden>{c.i}</span>{c.t}</Link>)}
      </nav>

      {/* ===== Hero: qué es esto, y cómo está Bermejo hoy ===== */}
      <section className="uk-hero uk-home-hero" style={heroImg ? { backgroundImage: `url('${heroImg}')` } : undefined}>
        <div className="uk-container uk-home-hero-grid">
          <div>
            <h1>Todo <span>{nombre}</span><br />en un solo lugar</h1>
            <p>{conGuia ? "Comercios, ofertas, cambio, servicios y datos útiles para tu visita." : `Comercios, ofertas y servicios de ${nombre}, en el mapa y con el WhatsApp de cada local.`}</p>
            <div className="uk-hero-actions">
              <Link href="/buscar?of=1" className="uk-btn uk-btn-primary">🏷️ Ver ofertas del día</Link>
              <Link href={conGuia ? "/guia" : "/buscar?vista=mapa"} className="uk-btn uk-btn-ghost uk-home-btn-claro">{conGuia ? "🧭 Explorar servicios" : "🗺️ Ver el mapa"}</Link>
            </div>
            <div className="uk-home-props">
              <div><b>Comercios locales</b><span>Locales con productos y ofertas</span></div>
              <div><b>Información confiable</b><span>Cargada por gente de {nombre}</span></div>
              <div><b>{conGuia ? "Tu visita más fácil" : "Directo al WhatsApp"}</b><span>{conGuia ? "Todo lo que necesitás, en un solo lugar" : "Le escribís al local y sabés cómo llegar"}</span></div>
            </div>
          </div>

          {(conGuia || t.usd_bob != null) && (
          <aside className="uk-home-hoy">
            <div className="uk-home-hoy-cab">
              <h3>Hoy en {nombre}</h3>
              {ultima && <small>Actualizado {hace(ultima)}</small>}
            </div>
            <ul>
              {frontera && (["puente", "chalanas"] as const).filter((k) => frontera[k] !== "no_aplica").map((k) => {
                const [txt, nivel] = ESTADO[k][frontera[k]] ?? [frontera[k], "ojo"];
                const horario = k === "chalanas" && frontera.chalanas !== "suspendidas" && frontera.chalanas_horario ? ` · ${frontera.chalanas_horario}` : "";
                return <li key={k}><span>{k === "puente" ? "🌉" : "⛵"}</span>{k === "puente" ? "Frontera" : "Chalanas"}: <b className={nivel}>{txt}</b>{horario}</li>;
              })}
              {frontera?.rio === "crecido" && <li><span>🌊</span>Río: <b className="ojo">crecido</b></li>}
              {clima?.temp_c != null && <li><span>{clima.icono || "☀"}</span>Clima: <b>{Math.round(clima.temp_c)}°</b>{clima.descripcion ? ` · ${clima.descripcion}` : ""}</li>}
              {t.usd_bob != null && <li><span>🇺🇸</span>1 USD = <b>{formatoMonto(t.usd_bob, "BOB")} Bs</b></li>}
              {esFrontera && t.ars_bob != null && (ciudad?.moneda_vecina ?? "ARS") === "ARS" && (
                <li><span>🇦🇷</span>1.000 ARS = <b>{formatoMonto(t.ars_bob * 1000, "BOB")} Bs</b></li>
              )}
              {frontera?.nota && <li className="uk-home-hoy-nota">{frontera.nota}</li>}
            </ul>
            {conGuia
              ? <Link href="/cambio" className="uk-home-hoy-link">📍 Casas de cambio y calculadora <span>›</span></Link>
              : <Link href="/buscar?rubro=cambio&vista=mapa" className="uk-home-hoy-link">📍 Casas de cambio en el mapa <span>›</span></Link>}
          </aside>
          )}
        </div>
      </section>

      {/* ===== La comunidad (sólo cuando hay enlace cargado; es la de los que cruzan a Bermejo) ===== */}
      {conGuia && <UnirmeComunidad variante="banner" />}

      {/* ===== Servicios útiles ===== */}
      <section className="uk-container uk-home-sec">
        <div className="uk-section-head">
          <h2>Servicios útiles <small>Encontrá rápido lo que necesitás en {nombre}.</small></h2>
          <Link href="/guia#mapa">Ver todos →</Link>
        </div>
        <div className="uk-home-grid uk-home-grid-4">
          {(conGuia ? SERVICIOS : SERVICIOS_SIN_GUIA).map((s) => (
            <Link key={s.t} href={s.href} className="uk-home-card">
              <span className="uk-home-ic">{s.i}</span>
              <b>{s.t}</b><small>{s.d}</small>
            </Link>
          ))}
        </div>
      </section>

      {/* ===== Antes de comprar + Herramientas ===== */}
      <section className={`uk-container uk-home-sec${conGuia ? " uk-home-dos" : ""}`}>
        {conGuia && (
        <div>
          <div className="uk-section-head">
            <h2>Antes de comprar <small>Lo que hay que saber para tu visita.</small></h2>
            <Link href="/guia">Ver la guía →</Link>
          </div>
          <div className="uk-home-grid uk-home-grid-2">
            {GUIAS.map((g) => (
              <Link key={g.t} href={g.href} className="uk-home-card">
                <span className="uk-home-ic">{g.i}</span>
                <b>{g.t}</b><small>{g.d}</small>
                <em>Ver guía →</em>
              </Link>
            ))}
          </div>
        </div>
        )}
        <div>
          <div className="uk-section-head">
            <h2>Herramientas útiles <small>{conGuia ? "Planeá tu visita." : `Para moverte por ${nombre}.`}</small></h2>
          </div>
          <div className={`uk-home-grid ${conGuia ? "uk-home-grid-2" : "uk-home-grid-4"}`}>
            {(conGuia ? HERRAMIENTAS : HERRAMIENTAS_SIN_GUIA).map((h) => (
              <Link key={h.t} href={h.href} className="uk-home-card uk-home-card-c">
                <span className="uk-home-ic">{h.i}</span>
                <b>{h.t}</b>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ===== El lanzamiento de las ofertas (hasta el lunes 28) ===== */}
      {cards.length === 0 && faltaParaLanzamiento() && (
        <section className="uk-container uk-home-sec">
          <div className="uk-lanzamiento">
            <span className="uk-lanzamiento-tag">Nuevo en URUKU</span>
            <h2>Las ofertas de {nombre} empiezan {FECHA_LANZAMIENTO}</h2>
            <p>
              Desde ese día vas a ver todos los días lo que publican los comercios: precios, lo que llegó, la
              liquidación de la semana. Directo del local a tu celular.
            </p>
            <div className="uk-lanzamiento-acciones">
              <Link href="/buscar?vista=mapa" className="uk-btn uk-btn-primary">Mientras tanto, mirá los comercios</Link>
              <Link href="/planes" className="uk-btn-ghost">¿Tenés un negocio? Publicá tus ofertas</Link>
            </div>
          </div>
        </section>
      )}

      {/* ===== Ofertas destacadas ===== */}
      {cards.length > 0 && (
        <section className="uk-container uk-home-sec">
          <div className="uk-section-head">
            <h2>Ofertas destacadas <small>De comercios de {nombre}.</small></h2>
            <Link href="/buscar?of=1">Ver más ofertas →</Link>
          </div>
          <div className="uk-offers">
            {cards.map((o) => (
              <Link key={o.id} href={`/comercios/${o.comercio_slug}`} className="uk-offer"
                style={o.imagen_url ? { backgroundImage: `url('${o.imagen_url}')` } : undefined}>
                <span className="uk-offer-tag">{o.zona_nombre || o.comercio_nombre}</span>
                {o.descuento_pct != null && <span className="uk-offer-disc">-{o.descuento_pct}%</span>}
                <div className="uk-offer-body">
                  <h3>{o.titulo}</h3>
                  <small>{o.comercio_nombre}</small>
                  {o.precio != null && <strong>{precioFmt(o.precio, o.moneda)}</strong>}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ===== Información para tu visita (lo de la guía: sólo en la frontera) ===== */}
      {conGuia && (
      <section className="uk-container uk-home-sec">
        <div className="uk-section-head">
          <h2>Información para tu visita <small>Consejos y recursos.</small></h2>
        </div>
        <div className="uk-home-grid uk-home-grid-3">
          {INFO.map((x) => (
            <Link key={x.t} href={x.href} className="uk-home-card uk-home-card-fila">
              <span className="uk-home-ic">{x.i}</span>
              <div><b>{x.t}</b><small>{x.d}</small></div>
            </Link>
          ))}
        </div>
      </section>
      )}

      {/* ===== Videos ===== */}
      {videos.length > 0 && (
        <section className="uk-container uk-home-sec">
          <div className="uk-section-head"><h2>🎬 Recorrimos {nombre}</h2></div>
          <div className="uk-rail">
            {videos.map((v) => (
              <div key={v.id} className="uk-vid">
                <video src={v.url} controls preload="metadata" playsInline />
                {v.titulo && <span>{v.titulo}</span>}
              </div>
            ))}
          </div>
        </section>
      )}
    </UrukuShell>
  );
}
