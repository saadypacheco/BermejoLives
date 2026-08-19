import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic } from "@/components/uruku-ui";
import { getFeed, getVideosPromo, getRedes, getLugaresPublicos } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";
import { precioFmt } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function InicioPage() {
  const [{ ciudad }, feed, videos, redes, lugares] = await Promise.all([
    ciudadActual(), getFeed(12), getVideosPromo(8), getRedes(), getLugaresPublicos(12),
  ]);
  const nombre = ciudad?.nombre ?? "tu ciudad";

  const ofertas = feed.filter((f) => f.tipo === "oferta");
  const novedades = feed.filter((f) => f.tipo === "novedad");
  const cards = (ofertas.length ? ofertas : feed.filter((f) => f.tipo !== "video")).slice(0, 8);
  const canalWa = redes.find((r) => r.clave === "whatsapp_canal")?.url;

  return (
    <UrukuShell activeCat="Todos" activeNav="Inicio">
      {/* ===== Hero ===== */}
      <section className="uk-hero" style={{ backgroundImage: "url('/bermejo-ciudad4.png')" }}>
        <div className="uk-container uk-hero-grid">
          <div>
            <h1>Descubrí <span>{nombre}</span><br />como nunca antes</h1>
            <p>Explorá comercios locales, ofertas increíbles y todo lo que necesitás cerca de vos.</p>
            <div className="uk-hero-actions">
              <Link href="/mapa" className="uk-btn uk-btn-primary">
                Explorá el mapa
                <Ic d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3zM9 3v15M15 6v15" />
              </Link>
              <Link href="/mapa?of=1" className="uk-btn uk-btn-secondary">
                <Ic d="M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" />
                Ofertas del día
              </Link>
            </div>
            <div className="uk-proof">
              <div className="uk-avatars"><span>SP</span><span>AM</span><span>LR</span><span>JF</span></div>
              <div>Miles de personas ya<br />descubren {nombre} con Uruku</div>
            </div>
          </div>

          <aside className="uk-quote-card uk-hero-cta">
            <h3>¿Tenés un comercio?</h3>
            <p>Sumate a Uruku y llegá a más personas en {nombre}.</p>
            <ul>
              <li>Aparecé en el mapa</li>
              <li>Fotos, videos y ofertas</li>
              <li>Más visibilidad, sin complicaciones</li>
            </ul>
            <Link href="/autoregistro" className="uk-panel-btn">Publicá tu negocio <span>→</span></Link>
          </aside>
        </div>
      </section>

      {/* ===== Trust strip ===== */}
      <section className="uk-container uk-trust">
        <article>
          <div className="uk-trust-ic green"><Ic d="M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" /></div>
          <div className="uk-trust-t"><strong>Ofertas todos los días</strong><span>Descuentos reales cerca tuyo.</span></div>
        </article>
        <article>
          <div className="uk-trust-ic blue"><Ic d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z" /></div>
          <div className="uk-trust-t"><strong>Comercios verificados</strong><span>Negocios confiables de tu ciudad.</span></div>
        </article>
        <article>
          <div className="uk-trust-ic orange"><Ic d="M12 3l2.9 5.9 6.6.9-4.8 4.6 1.1 6.5L12 17.8 6.2 21l1.1-6.5L2.5 10.3l6.6-.9z" /></div>
          <div className="uk-trust-t"><strong>Novedades locales</strong><span>Lo nuevo, primero acá.</span></div>
        </article>
        <article>
          <div className="uk-trust-ic violet"><Ic d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" /></div>
          <div className="uk-trust-t"><strong>Apoyemos lo local</strong><span>Juntos hacemos crecer {nombre}.</span></div>
        </article>
      </section>

      {/* ===== Ofertas destacadas ===== */}
      {cards.length > 0 && (
        <section className="uk-container uk-section">
          <div className="uk-section-head">
            <h2>Ofertas destacadas</h2>
            <Link href="/mapa?of=1">Ver todas →</Link>
          </div>
          <div className="uk-offers">
            {cards.slice(0, 4).map((o) => (
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

      {/* ===== Mercados y galerías (usa los lugares cargados) ===== */}
      {lugares.length > 0 && (
        <section className="uk-container uk-section">
          <div className="uk-section-head">
            <h2>🏬 Mercados y galerías de {nombre}</h2>
            <Link href="/mapa">Ver en el mapa →</Link>
          </div>
          <div className="uk-rail">
            {lugares.map((l) => (
              <Link key={l.id} href="/mapa" className="uk-lugar-card">
                <div className="uk-lugar-img" style={l.portada_thumb_url ? { backgroundImage: `url('${l.portada_thumb_url}')` } : undefined}>
                  {!l.portada_thumb_url && <span>🏬</span>}
                </div>
                <b>{l.nombre}</b>
                <small>{l.n_comercios} {l.n_comercios === 1 ? "local" : "locales"}</small>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* ===== Highlight grid ===== */}
      <section className="uk-container uk-highlight">
        <article className="uk-panel">
          <h3>Lo mejor de hoy en {nombre}</h3>
          {ofertas.length > 0 && <div className="uk-statrow"><span>🏷️ Ofertas activas</span><strong>{ofertas.length}</strong></div>}
          {novedades.length > 0 && <div className="uk-statrow"><span>✨ Novedades</span><strong>{novedades.length}</strong></div>}
          {videos.length > 0 && <div className="uk-statrow"><span>🎬 Recorridos</span><strong>{videos.length}</strong></div>}
          {ofertas.length === 0 && novedades.length === 0 && videos.length === 0 && (
            <p style={{ color: "var(--uk-ink-soft)", fontSize: 14, margin: "4px 0 0" }}>Explorá el mapa y descubrí los comercios de {nombre}.</p>
          )}
          <Link href="/mapa" className="uk-panel-btn">Explorá el mapa <span>→</span></Link>
        </article>

        <article className="uk-panel uk-discover" style={{ backgroundImage: "url('/Bermejo-plaza.png')" }}>
          <h3>Descubrí más.<br /><span>Ahorrá siempre.</span></h3>
          <p>Compará precios, encontrá promociones y elegí lo mejor para vos.</p>
          <div className="uk-discover-icons">
            <div><span><Ic d="M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z" /></span><small>Actualizado<br />todos los días</small></div>
            <div><span><Ic d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0zM12 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" /></span><small>Cerca tuyo,<br />siempre</small></div>
            <div><span><Ic d="M13 2 3 14h7l-1 8 10-12h-7z" /></span><small>Fácil, rápido<br />y útil</small></div>
            <div><span><Ic d="M12 21s-7-4.5-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 6C19 16.5 12 21 12 21z" /></span><small>100% local,<br />100% {nombre}</small></div>
          </div>
        </article>

      </section>

      {/* ===== Recorrimos ===== */}
      {videos.length > 0 && (
        <section className="uk-container uk-section">
          <h2>🎬 Recorrimos {nombre}</h2>
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

      {/* ===== Así de simple ===== */}
      <section className="uk-container uk-section" style={{ paddingTop: 0 }}>
        <h2>Así de simple</h2>
        <div className="uk-steps">
          <article>
            <span className="uk-step-ic"><Ic d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3" /><span className="uk-step-num">1</span></span>
            <div><strong>Buscá</strong><p>Encontrá lo que necesitás.</p></div>
            <span className="uk-arrow" aria-hidden>›</span>
          </article>
          <article>
            <span className="uk-step-ic"><Ic d="M3 3h2l2.4 12.3a1 1 0 0 0 1 .7h9.7a1 1 0 0 0 1-.8L22 7H6" /><span className="uk-step-num b">2</span></span>
            <div><strong>Explorá</strong><p>Compará opciones, mirá fotos y ofertas.</p></div>
            <span className="uk-arrow" aria-hidden>›</span>
          </article>
          <article>
            <span className="uk-step-ic"><Ic d="M12 21s-7-4.5-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 6C19 16.5 12 21 12 21z" /><span className="uk-step-num v">3</span></span>
            <div><strong>Guardá</strong><p>Guardá tus favoritos para volver.</p></div>
            <span className="uk-arrow" aria-hidden>›</span>
          </article>
          <article>
            <span className="uk-step-ic"><Ic d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0" /><span className="uk-step-num o">4</span></span>
            <div><strong>Disfrutá</strong><p>Ofertas exclusivas en tu ciudad.</p></div>
          </article>
        </div>
      </section>

      {/* ===== Canal de novedades ===== */}
      {canalWa && (
        <section className="uk-container uk-canal">
          <div>
            <h3>📢 Canal de novedades</h3>
            <p>Recibí ofertas, nuevos comercios y eventos de {nombre}.</p>
          </div>
          <a href={canalWa} target="_blank" rel="noopener">Unirme al canal</a>
        </section>
      )}
    </UrukuShell>
  );
}
