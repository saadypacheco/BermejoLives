import Link from "next/link";
import { Nav } from "@/components/nav";
import { HomeMap } from "@/components/home-map";
import { SearchHero } from "@/components/search-hero";
import { getFeed, getComerciosMapa, getZonas } from "@/lib/data";
import { RUBROS, precioFmt } from "@/lib/types";
import { Arrow } from "@/components/icons";

export const dynamic = "force-dynamic";

// 8 categorías del mockup → cada una mapea a un filtro de rubro real.
const CATS: { label: string; icon: string; rubro: string }[] = [
  { label: "Alimentos", icon: "🥗", rubro: "mercado" },
  { label: "Bebidas", icon: "🥤", rubro: "mercado" },
  { label: "Electrónica", icon: "📱", rubro: "tecnologia" },
  { label: "Hogar", icon: "🏠", rubro: "hogar" },
  { label: "Vehículos", icon: "🚗", rubro: "gomeria" },
  { label: "Salud y belleza", icon: "💊", rubro: "farmacia" },
  { label: "Construcción", icon: "🚧", rubro: "otros" },
  { label: "Servicios", icon: "🔧", rubro: "servicios" },
];

export default async function Home() {
  const [feed, comercios, zonas] = await Promise.all([getFeed(12), getComerciosMapa(), getZonas()]);
  const premium = feed.slice(0, 8);
  const destacados = comercios.filter((c) => c.destacado);
  const auspi = (destacados.length >= 3 ? destacados : comercios).slice(0, 10);
  const rubroNombre = (slug: string | null) => RUBROS.find((r) => r.slug === slug)?.nombre ?? "Comercio";

  return (
    <>
      <Nav active="inicio" />

      {/* HERO — el buscador es el protagonista */}
      <section className="hero-centro">
        <div className="wrap">
          <h1 className="hc-title">¿Qué estás buscando?</h1>
          <p className="hc-sub">Negocios y servicios en el mapa de <span className="green">Bermejo</span>. Productos, en la tienda <b style={{ color: "var(--txt)" }}>Reservalo</b>.</p>
          <SearchHero rubros={RUBROS} zonas={zonas} />
        </div>
      </section>

      {/* MAPA full-width */}
      <section className="wrap" style={{ marginTop: 16 }}>
        <HomeMap comercios={comercios} />
      </section>

      {/* OFERTAS PREMIUM */}
      <section className="section" style={{ paddingTop: 26 }} id="ofertas">
        <div className="wrap">
          <div className="section-head">
            <div><h2 style={{ fontSize: 22 }}>👑 Ofertas premium</h2><p>Las mejores ofertas destacadas</p></div>
            <Link href="/buscar" className="btn btn-ghost btn-sm">Ver todas las ofertas <Arrow /></Link>
          </div>
          {premium.length === 0 ? (
            <p style={{ color: "var(--txt-3)" }}>Pronto: las ofertas destacadas de los comercios.</p>
          ) : (
            <div className="rail">
              {premium.map((p) => (
                <Link href={`/comercios/${p.comercio_slug}`} key={p.id} className="premium-card">
                  <div className="media">
                    <span className="premium-tag">PREMIUM</span>
                    {p.imagen_url && <img src={p.imagen_url} alt={p.titulo ?? ""} />}
                  </div>
                  <div className="pb">
                    <b style={{ display: "block" }}>{p.titulo ?? "Oferta"}</b>
                    <small style={{ color: "var(--txt-3)", display: "block", marginBottom: 4 }}>{p.comercio_nombre}</small>
                    {p.precio != null && <div style={{ color: "var(--neon)", fontWeight: 800 }}>{precioFmt(p.precio, p.moneda)}</div>}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* AUSPICIANTES */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head">
            <div><h2 style={{ fontSize: 20 }}>Auspiciantes destacados</h2><p>Empresas que apoyan el comercio local</p></div>
            <Link href="/buscar" className="btn btn-ghost btn-sm">Ver todos <Arrow /></Link>
          </div>
          <div className="rail auspi-rail">
            {auspi.map((c) => (
              <Link href={`/comercios/${c.slug}`} key={c.id} className="auspi-card" title={c.nombre}>
                <div className="auspi-logo-box">
                  {c.logo_url ? <img src={c.logo_url} alt={c.nombre} /> : <span className="auspi-initial">{c.nombre.charAt(0)}</span>}
                </div>
                <b>{c.nombre}</b>
                <small>{rubroNombre(c.rubro_slug)}</small>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CATEGORÍAS */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head">
            <div><h2 style={{ fontSize: 20 }}>Explorá por categorías</h2></div>
            <Link href="/buscar" className="btn btn-ghost btn-sm">Ver todas las categorías <Arrow /></Link>
          </div>
          <div className="cat-grid">
            {CATS.map((c) => (
              <Link href={`/buscar?rubro=${c.rubro}`} key={c.label} className="cat-item">
                <span className="emoji">{c.icon}</span>
                <b style={{ fontSize: 13, textAlign: "center" }}>{c.label}</b>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <footer className="footer" style={{ marginTop: 30 }}>
        <div className="wrap">
          <div className="copy">
            <span>© 2026 Encontralo. Todos los derechos reservados.</span>
            <span>Hecho con <span className="heart">♥</span> en la frontera</span>
          </div>
        </div>
      </footer>
    </>
  );
}
