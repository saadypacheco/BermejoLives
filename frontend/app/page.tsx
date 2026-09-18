import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { UnirmeComunidad } from "@/components/unirme-comunidad";
import { AbrirAyuda } from "@/components/abrir-ayuda";
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

// La fila de accesos debajo del buscador: los mismos destinos, en una palabra.
const CHIPS = [
  { i: "🚻", t: "Baños", href: SERVICIOS[0].href }, { i: "💊", t: "Farmacias", href: SERVICIOS[1].href },
  { i: "🏧", t: "Cajeros", href: SERVICIOS[2].href }, { i: "🅿️", t: "Estacionamiento", href: SERVICIOS[3].href },
  { i: "💱", t: "Casas de cambio", href: "/cambio" }, { i: "🚕", t: "Taxis", href: SERVICIOS[6].href },
  { i: "📶", t: "WiFi", href: SERVICIOS[5].href },
  { i: "🚓", t: "Policía", href: SERVICIOS[7].href },
  { i: "🚌", t: "Transporte", href: "/guia#transporte" }, { i: "🌉", t: "Frontera", href: "/guia#frontera" },
];

const GUIAS = [
  { i: "🛃", t: "Aduana", d: "Franquicia, qué podés pasar y qué no.", href: "/guia#aduana" },
  { i: "🪪", t: "Documentación", d: "DNI, pasaporte y viaje con menores.", href: "/guia#documentos" },
  { i: "🌉", t: "Frontera", d: "Estado del paso, horarios, río y clima.", href: "/guia#frontera" },
  { i: "🛍️", t: "Comprar", d: "Horarios, por docena, pagos y envíos.", href: "/guia#comercios" },
];

const HERRAMIENTAS = [
  { i: "🚌", t: "Cómo llegar desde Orán o Salta", href: "/guia#transporte" },
  { i: "🏔️", t: "De Bermejo a Tarija", href: "/guia#transporte" },
  { i: "🕒", t: "Qué está abierto ahora", href: "/guia#comercios" },
  { i: "📍", t: "Qué hay cerca tuyo", href: "/buscar?cerca=1" },
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
  chalanas: { operando: ["operando", "ok"], suspendidas: ["suspendidas", "mal"] },
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

export default async function InicioPage() {
  const [{ ciudad }, feed, videos, frontera, clima, cotizaciones] = await Promise.all([
    ciudadActual(), getFeed(12), getVideosPromo(6), getFronteraEstado(), getClima(), getCotizaciones(),
  ]);
  const nombre = ciudad?.nombre ?? "Bermejo";
  const heroImg = ciudad?.hero_url || "/bermejo-ciudad4.png";
  const ofertas = feed.filter((f) => f.tipo === "oferta");
  const cards = (ofertas.length ? ofertas : feed.filter((f) => f.tipo !== "video")).slice(0, 4);
  const t = tasasDe(cotizaciones);
  const fechas = [frontera?.actualizado_en, t.actualizado_en].filter(Boolean) as string[];
  const ultima = fechas.length ? fechas.sort()[fechas.length - 1] : null;

  return (
    <UrukuShell activeCat="Todos" activeNav="Inicio">
      {/* ===== Los accesos rápidos, debajo del buscador ===== */}
      <nav className="uk-container uk-home-chips" aria-label="Servicios">
        {CHIPS.map((c) => <Link key={c.t} href={c.href}><span aria-hidden>{c.i}</span>{c.t}</Link>)}
      </nav>

      {/* ===== Hero: qué es esto, y cómo está Bermejo hoy ===== */}
      <section className="uk-hero uk-home-hero" style={{ backgroundImage: `url('${heroImg}')` }}>
        <div className="uk-container uk-home-hero-grid">
          <div>
            <h1>Todo <span>{nombre}</span><br />en un solo lugar</h1>
            <p>Comercios, ofertas, cambio, servicios y datos útiles para tu visita.</p>
            <div className="uk-hero-actions">
              <Link href="/buscar?of=1" className="uk-btn uk-btn-primary">🏷️ Ver ofertas del día</Link>
              <Link href="/guia" className="uk-btn uk-btn-ghost uk-home-btn-claro">🧭 Explorar servicios</Link>
            </div>
            <div className="uk-home-props">
              <div><b>Comercios locales</b><span>Cientos de locales con productos y ofertas</span></div>
              <div><b>Información confiable</b><span>Cargada por gente de {nombre}</span></div>
              <div><b>Tu visita más fácil</b><span>Todo lo que necesitás, en un solo lugar</span></div>
            </div>
          </div>

          <aside className="uk-home-hoy">
            <div className="uk-home-hoy-cab">
              <h3>Hoy en {nombre}</h3>
              {ultima && <small>Actualizado {hace(ultima)}</small>}
            </div>
            <ul>
              {frontera && (["puente", "chalanas"] as const).map((k) => {
                const [txt, nivel] = ESTADO[k][frontera[k]] ?? [frontera[k], "ojo"];
                return <li key={k}><span>{k === "puente" ? "🌉" : "⛵"}</span>{k === "puente" ? "Frontera" : "Chalanas"}: <b className={nivel}>{txt}</b></li>;
              })}
              {frontera?.rio === "crecido" && <li><span>🌊</span>Río: <b className="ojo">crecido</b></li>}
              {clima?.temp_c != null && <li><span>{clima.icono || "☀"}</span>Clima: <b>{Math.round(clima.temp_c)}°</b>{clima.descripcion ? ` · ${clima.descripcion}` : ""}</li>}
              {t.usd_bob != null && <li><span>🇺🇸</span>1 USD = <b>{formatoMonto(t.usd_bob, "BOB")} Bs</b></li>}
              {t.ars_bob != null && <li><span>🇦🇷</span>1.000 ARS = <b>{formatoMonto(t.ars_bob * 1000, "BOB")} Bs</b></li>}
              {frontera?.nota && <li className="uk-home-hoy-nota">{frontera.nota}</li>}
            </ul>
            <Link href="/cambio" className="uk-home-hoy-link">📍 Casas de cambio y calculadora <span>›</span></Link>
          </aside>
        </div>
      </section>

      {/* ===== La comunidad (sólo cuando hay enlace cargado) ===== */}
      <UnirmeComunidad variante="banner" />

      {/* ===== Servicios útiles ===== */}
      <section className="uk-container uk-home-sec">
        <div className="uk-section-head">
          <h2>Servicios útiles <small>Encontrá rápido lo que necesitás en {nombre}.</small></h2>
          <Link href="/guia#mapa">Ver todos →</Link>
        </div>
        <div className="uk-home-grid uk-home-grid-4">
          {SERVICIOS.map((s) => (
            <Link key={s.t} href={s.href} className="uk-home-card">
              <span className="uk-home-ic">{s.i}</span>
              <b>{s.t}</b><small>{s.d}</small>
            </Link>
          ))}
        </div>
      </section>

      {/* ===== Antes de comprar + Herramientas ===== */}
      <section className="uk-container uk-home-sec uk-home-dos">
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
        <div>
          <div className="uk-section-head">
            <h2>Herramientas útiles <small>Planeá tu visita.</small></h2>
          </div>
          <div className="uk-home-grid uk-home-grid-2">
            {HERRAMIENTAS.map((h) => (
              <Link key={h.t} href={h.href} className="uk-home-card uk-home-card-c">
                <span className="uk-home-ic">{h.i}</span>
                <b>{h.t}</b>
              </Link>
            ))}
            <AbrirAyuda className="uk-home-card uk-home-card-c uk-home-card-ayuda">
              <span className="uk-home-ic">💬</span>
              <b>Preguntale a URUKU</b>
              <small>Lo que no esté acá</small>
            </AbrirAyuda>
          </div>
        </div>
      </section>

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

      {/* ===== Información para tu visita ===== */}
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
