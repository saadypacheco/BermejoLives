import Link from "next/link";
import { BottomNav } from "@/components/bottom-nav";
import { getFeed, getCotizaciones, getClima, getVideosPromo, getRedes } from "@/lib/data";
import { precioFmt } from "@/lib/types";

export const dynamic = "force-dynamic";

const CATS = [
  { label: "Restaurantes", emoji: "🍴", q: "restaurante" },
  { label: "Supermercados", emoji: "🛒", q: "supermercado" },
  { label: "Ropa", emoji: "👕", q: "ropa" },
  { label: "Salud", emoji: "➕", q: "farmacia" },
  { label: "Ferreterías", emoji: "🔧", q: "ferreteria" },
  { label: "Servicios", emoji: "🧰", q: "servicio" },
];

const money = (v: number | null | undefined) =>
  v && v > 0 ? v.toLocaleString("es-AR", { maximumFractionDigits: 2 }) : "s/d";

const RED_ICON: Record<string, string> = {
  tiktok: "🎵", instagram: "📷", facebook: "📘", youtube: "▶️", whatsapp_canal: "💬",
};

export default async function InicioPage() {
  const [feed, cotizaciones, clima, videos, redes] = await Promise.all([
    getFeed(10), getCotizaciones(), getClima(), getVideosPromo(8), getRedes(),
  ]);
  const ofertas = feed.filter((f) => f.tipo !== "video");
  const canalWa = redes.find((r) => r.clave === "whatsapp_canal")?.url;
  const seguinos = redes.filter((r) => r.url && r.clave !== "whatsapp_canal");

  return (
    <div className="ini">
      {/* HERO con foto de Bermejo */}
      <header className="ini-hero">
        <div className="ini-hero-in">
          <div className="ini-brand">ENCON<i>TRALO</i> <span>BERMEJO</span></div>
          <h1>El mapa de comercios de Bermejo</h1>
          <p>Encontrá, reservá y elegí lo mejor de tu ciudad.</p>
          <form className="ini-search" action="/buscar" method="get">
            <span aria-hidden>🔍</span>
            <input name="q" placeholder="¿Qué estás buscando?" aria-label="Buscar" />
            <button type="submit">Buscar</button>
          </form>
          <Link href="/mapa" className="ini-cta">Explorá el mapa →</Link>
        </div>
      </header>

      {/* COTIZACIÓN + CLIMA (los ganchos diarios) */}
      <section className="ini-sec">
        <div className="ini-widgets">
          {cotizaciones.map((c) => (
            <div key={c.clave} className="ini-w">
              <span className="ini-w-lbl">{c.etiqueta}</span>
              <span className="ini-w-val">{money(c.valor)} <small>{c.unidad}</small></span>
              {c.detalle && <span className="ini-w-sub">{c.detalle}</span>}
            </div>
          ))}
          <div className="ini-w ini-w-clima">
            <span className="ini-w-lbl">Clima · Bermejo</span>
            <span className="ini-w-val">{clima?.icono ?? "🌡️"} {clima?.temp_c != null ? `${Math.round(clima.temp_c)}°` : "—"}</span>
            {clima?.descripcion && <span className="ini-w-sub">{clima.descripcion}</span>}
          </div>
        </div>
      </section>

      {/* CATEGORÍAS */}
      <section className="ini-sec">
        <div className="ini-cats">
          {CATS.map((c) => (
            <Link key={c.label} href={`/buscar?q=${c.q}`} className="ini-cat">
              <span className="ini-cat-ic">{c.emoji}</span><span>{c.label}</span>
            </Link>
          ))}
          <Link href="/buscar" className="ini-cat"><span className="ini-cat-ic">•••</span><span>Ver más</span></Link>
        </div>
      </section>

      {/* OFERTAS DEL DÍA */}
      {ofertas.length > 0 && (
        <section className="ini-sec">
          <div className="ini-head"><h2>🔥 Ofertas del día</h2><Link href="/mapa?of=1">Ver todas</Link></div>
          <div className="ini-rail">
            {ofertas.slice(0, 8).map((o) => (
              <Link key={o.id} href={`/comercios/${o.comercio_slug}`} className="ini-off">
                <div className="ini-off-img">
                  {o.descuento_pct != null && <span className="off-badge">-{o.descuento_pct}%</span>}
                  {o.imagen_url && <img src={o.imagen_url} alt="" loading="lazy" decoding="async" />}
                </div>
                <div className="ini-off-b">
                  <b>{o.titulo}</b><small>{o.comercio_nombre}</small>
                  {o.precio != null && <div className="ini-off-price">{precioFmt(o.precio, o.moneda)}</div>}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* RECORRIMOS BERMEJO (videos promocionales de zonas) */}
      {videos.length > 0 && (
        <section className="ini-sec">
          <div className="ini-head"><h2>🎬 Recorrimos Bermejo</h2></div>
          <div className="ini-rail">
            {videos.map((v) => (
              <div key={v.id} className="ini-vid">
                <video src={v.url} controls preload="metadata" playsInline />
                {v.titulo && <span className="ini-vid-b">{v.titulo}</span>}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* SEGUINOS (redes que cargó el admin) */}
      {seguinos.length > 0 && (
        <section className="ini-sec">
          <div className="ini-head"><h2>Seguinos</h2></div>
          <div className="ini-redes">
            {seguinos.map((r) => (
              <a key={r.clave} href={r.url as string} target="_blank" rel="noopener" className="ini-red">
                <span className="ini-red-ic">{RED_ICON[r.clave] ?? "🔗"}</span>{r.etiqueta}
              </a>
            ))}
          </div>
        </section>
      )}

      {/* CANAL + PUBLICÁ */}
      <section className="ini-sec">
        {canalWa && (
        <div className="ini-canal">
          <div><h3>📢 Canal de novedades</h3><p>Ofertas diarias, nuevos comercios y eventos de Bermejo.</p></div>
          <a className="btn btn-wa" href={canalWa} target="_blank" rel="noopener">Unirme al canal</a>
        </div>
        )}
        <Link href="/autoregistro" className="ini-negocio">
          <div><b>¿Tenés un comercio?</b><span>Publicalo gratis y aparecé en el mapa.</span></div>
          <span className="ini-negocio-cta">Publicá tu negocio ↗</span>
        </Link>
      </section>

      <div style={{ height: 20 }} />
      <BottomNav active="Inicio" />
    </div>
  );
}
