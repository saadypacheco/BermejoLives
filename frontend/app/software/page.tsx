import Link from "next/link";
import { Nav } from "@/components/nav";
import { WhatsApp, Store, Pin, Search, Send, Play, Verified, TikTok, Arrow, Check } from "@/components/icons";

export const metadata = {
  title: "El software comercial de Bermejo — planes y funciones",
  description: "La plataforma que pone a tu comercio en el mapa de Bermejo: ofertas en vivo, WhatsApp directo, videos y más. Conocé los planes.",
};

const FEATURES = [
  { Icon: Pin, t: "En el mapa", d: "Tu comercio aparece en el mapa de Bermejo con foto, ubicación y cómo llegar." },
  { Icon: WhatsApp, t: "Contacto directo", d: "El comprador te escribe por WhatsApp con un toque — sin intermediarios ni comisiones." },
  { Icon: Send, t: "Ofertas en vivo", d: "Publicás tus ofertas y aparecen al instante en el feed que ve toda la ciudad." },
  { Icon: Search, t: "Buscador por rubro", d: "Te encuentran buscando lo que vendés: mayorista, minorista, rubro, zona y precio." },
  { Icon: Play, t: "Videos", d: "Mostrá tu local y tus productos con videos estilo TikTok." },
  { Icon: Verified, t: "Verificado", d: "Sello de confianza: tu comercio fue verificado en el lugar por nuestro equipo." },
];

const PLANES = [
  { nombre: "Presencia", precio: "Gratis", destacado: false, items: ["Aparecés en el mapa y el buscador", "Ficha con WhatsApp y cómo llegar", "Datos de contacto y redes"] },
  { nombre: "Activo", precio: "Bs 49", sub: "/mes", destacado: false, items: ["Todo lo de Presencia", "Publicás ofertas (con moderación)", "1 video por mes", "Aparecés en la publicidad regional", "Reporte mensual de visitas"] },
  { nombre: "Destacado", precio: "Bs 99", sub: "/mes", destacado: true, items: ["Todo lo de Activo", "Destacado en tu zona y rubro", "Más publicaciones y videos", "Hot-sale que late en el mapa", "Reporte semanal"] },
  { nombre: "Premium Frontera", precio: "Bs 199", sub: "/mes", destacado: false, items: ["Todo lo de Destacado", "Sello Verificado", "Publicación directa (sin espera)", "Bot de WhatsApp", "Cupo de publicidad paga incluido"] },
];

const ADDONS = [
  { Icon: TikTok, t: "Videos para redes", d: "Te grabamos, editamos y subimos videos." },
  { Icon: Store, t: "Tienda online", d: "Catálogo con carrito y pedido por WhatsApp (sin comisiones)." },
  { Icon: WhatsApp, t: "WhatsApp Business", d: "Te lo dejamos listo: catálogo, bienvenida, etiquetas." },
  { Icon: Send, t: "Campañas de pauta", d: "Avisos en redes y medios de Salta, Orán, Tucumán y más." },
];

export default function SoftwarePage() {
  return (
    <>
      <Nav />
      <section className="hero" style={{ paddingBottom: 20 }}>
        <div className="wrap" style={{ display: "block", textAlign: "center", maxWidth: 820, margin: "0 auto" }}>
          <span className="eyebrow" style={{ justifyContent: "center" }}><span className="dot-live" /> Para comercios de Bermejo</span>
          <h1 className="hero-title" style={{ fontSize: "clamp(40px,6vw,72px)" }}>
            Poné tu comercio<br /><span className="green">en el mapa</span>
          </h1>
          <p className="hero-sub" style={{ margin: "22px auto 30px" }}>
            La plataforma que muestra todo lo que se vende en Bermejo, en tiempo real. Más clientes, contacto directo por WhatsApp, sin comisiones por venta.
          </p>
          <div className="hero-cta" style={{ justifyContent: "center" }}>
            <a href="https://wa.me/59170000000?text=Quiero%20sumar%20mi%20comercio%20a%20Bermejo" target="_blank" rel="noopener" className="btn btn-primary">
              <WhatsApp style={{ width: 18, height: 18 }} /> Sumar mi comercio
            </a>
            <a href="#planes" className="btn btn-ghost">Ver planes <Arrow /></a>
          </div>
        </div>
      </section>

      {/* Qué hace */}
      <section className="section" style={{ paddingTop: 40 }}>
        <div className="wrap">
          <div className="section-head"><div><span className="eyebrow">Qué hace</span><h2>Todo lo que tu comercio necesita</h2></div></div>
          <div className="biz-grid" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
            {FEATURES.map((f) => (
              <div className="glass" key={f.t} style={{ padding: 22, borderRadius: "var(--radius)" }}>
                <span className="ic g" style={{ width: 44, height: 44, borderRadius: 12, display: "grid", placeItems: "center", background: "rgba(57,255,158,.12)", color: "var(--neon)" }}>
                  <f.Icon style={{ width: 22, height: 22 }} />
                </span>
                <h4 style={{ margin: "14px 0 6px", fontSize: 16 }}>{f.t}</h4>
                <p style={{ color: "var(--txt-2)", fontSize: 14, margin: 0 }}>{f.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Cómo funciona */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="explore" style={{ gridTemplateColumns: "1fr" }}>
            <div>
              <span className="eyebrow">Cómo funciona</span>
              <h2>Publicar es mandar un WhatsApp</h2>
              <div className="zone-chips" style={{ gridTemplateColumns: "repeat(3,1fr)", marginTop: 18 }}>
                <div className="zchip"><b>1. Te sumás</b><small>Cargás tu comercio (o lo reclamás)</small></div>
                <div className="zchip"><b>2. Publicás</b><small>Mandás tu oferta por WhatsApp o el panel</small></div>
                <div className="zchip"><b>3. Te encuentran</b><small>Aparecés en el mapa, el feed y el buscador</small></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Planes */}
      <section className="section" id="planes" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head"><div><span className="eyebrow">Planes</span><h2>Elegí cómo querés aparecer</h2><p>Pago mensual por QR. Sin comisiones por venta — la venta es tuya.</p></div></div>
          <div className="planes-grid">
            {PLANES.map((p) => (
              <div className={`plan-card glass ${p.destacado ? "dest" : ""}`} key={p.nombre}>
                {p.destacado && <span className="plan-badge">Más elegido</span>}
                <h3>{p.nombre}</h3>
                <div className="plan-precio">{p.precio}{p.sub && <small>{p.sub}</small>}</div>
                <ul>
                  {p.items.map((it) => (<li key={it}><Check style={{ width: 15, height: 15, color: "var(--neon)", flexShrink: 0 }} /> {it}</li>))}
                </ul>
                <a href="https://wa.me/59170000000?text=Quiero%20el%20plan%20" target="_blank" rel="noopener" className={`btn ${p.destacado ? "btn-primary" : "btn-ghost"} btn-sm`} style={{ width: "100%", marginTop: "auto" }}>Elegir</a>
              </div>
            ))}
          </div>
          <p style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 14, textAlign: "center" }}>* Precios de referencia, en bolivianos. El pago se realiza por QR a cuenta de Bolivia.</p>
        </div>
      </section>

      {/* Add-ons */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head"><div><span className="eyebrow">Servicios adicionales</span><h2>Lo que no sabés hacer, lo hacemos por vos</h2></div></div>
          <div className="biz-grid" style={{ gridTemplateColumns: "repeat(4,1fr)" }}>
            {ADDONS.map((a) => (
              <div className="glass" key={a.t} style={{ padding: 20, borderRadius: "var(--radius)" }}>
                <a.Icon style={{ width: 26, height: 26, color: "var(--blue-soft)" }} />
                <h4 style={{ margin: "12px 0 6px", fontSize: 15 }}>{a.t}</h4>
                <p style={{ color: "var(--txt-2)", fontSize: 13.5, margin: 0 }}>{a.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="cta">
            <div><h2>¿Sumamos tu comercio?</h2><p>Escribinos y en minutos estás en el mapa de Bermejo.</p></div>
            <a className="btn btn-primary" href="https://wa.me/59170000000?text=Quiero%20sumar%20mi%20comercio" target="_blank" rel="noopener">
              <WhatsApp style={{ width: 18, height: 18 }} /> Hablar por WhatsApp
            </a>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap">
          <div className="copy">
            <span>© 2026 Bermejo Live Market</span>
            <Link href="/bermejo" style={{ color: "var(--txt-3)" }}>Acceso equipo</Link>
          </div>
        </div>
      </footer>
    </>
  );
}
