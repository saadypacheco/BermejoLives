import Link from "next/link";
import { Nav } from "@/components/nav";
import { BoliviaMap } from "@/components/bolivia-map";
import { Counter } from "@/components/counter";
import { LiveFeed } from "@/components/live-feed";
import { getFeed, getComercios, getZonas, getCiudades } from "@/lib/data";
import { WhatsApp, Pin, Store, Arrow, Send } from "@/components/icons";

// Feed en vivo: siempre fresco en cada request (no cachear el SSR del home).
export const dynamic = "force-dynamic";

export default async function Home() {
  const [feed, comercios, zonas, ciudades] = await Promise.all([getFeed(6), getComercios(), getZonas(), getCiudades()]);

  return (
    <>
      <Nav active="inicio" />

      {/* HERO */}
      <section className="hero">
        <div className="wrap">
          <div className="hero-text">
            <span className="eyebrow"><span className="dot-live" /> Bermejo · Bolivia · Frontera viva</span>
            <h1 className="hero-title">
              Todo lo que se<br />vende en Bermejo,<br /><span className="green">en tiempo real</span>
            </h1>
            <p className="hero-sub">
              Explora ofertas, videos, comercios y promociones publicadas directamente desde WhatsApp.
            </p>
            <div className="hero-cta">
              <Link href="#mapa" className="btn btn-primary">Explorar Bermejo <Pin /></Link>
              <Link href="/publicar" className="btn btn-ghost"><Store /> Publicar mi negocio</Link>
            </div>
            <div className="hero-social">
              <div className="avatars">
                {[11, 32, 15, 45, 8].map((n) => (
                  <img key={n} src={`https://i.pravatar.cc/80?img=${n}`} alt="" />
                ))}
              </div>
              <div><b><Counter to={12450} prefix="+" /></b><small>usuarios este mes</small></div>
            </div>
          </div>
          <BoliviaMap ciudades={ciudades} />
        </div>
      </section>

      {/* STATS */}
      <div className="wrap">
        <div className="stats glass">
          <div className="stat">
            <span className="ic g"><Store style={{ width: 22, height: 22 }} /></span>
            <div><b><Counter to={1250} /></b><span>Comercios</span></div>
          </div>
          <div className="stat">
            <span className="ic o"><WhatsApp style={{ width: 22, height: 22 }} /></span>
            <div><b><Counter to={2450} /></b><span>Ofertas activas</span></div>
          </div>
          <div className="stat">
            <span className="ic p"><Send style={{ width: 20, height: 20 }} /></span>
            <div><b><Counter to={350} /></b><span>Videos hoy</span></div>
          </div>
          <div className="stat">
            <span className="ic pk"><Send style={{ width: 20, height: 20 }} /></span>
            <div><b><Counter to={780} /></b><span>Publicaciones hoy</span></div>
          </div>
          <div className="stat">
            <span className="live-badge"><span className="dot-live" /> EN VIVO</span>
            <span className="ic b"><Store style={{ width: 20, height: 20 }} /></span>
            <div><b><Counter to={1235} /></b><span>Usuarios conectados</span></div>
          </div>
        </div>
      </div>

      {/* FEED EN VIVO + COMERCIOS */}
      <section className="section" id="ofertas">
        <div className="wrap">
          <div className="section-head">
            <div>
              <span className="eyebrow"><span className="dot-live" /> Feed en tiempo real</span>
              <h2>Lo que se publica ahora en Bermejo</h2>
              <p>Publicaciones aprobadas por moderadores, llegando directo desde WhatsApp.</p>
            </div>
          </div>
          <div className="grid-2col">
            <LiveFeed initial={feed} />
            <div>
              <div className="section-head"><div><h2 style={{ fontSize: 20 }}>Negocios destacados</h2></div></div>
              <div className="feed">
                {comercios.slice(0, 4).map((c) => (
                  <article className="post" key={c.id}>
                    <div className="phead">
                      <img src={c.logo_url ?? ""} alt="" />
                      <div style={{ flex: 1 }}>
                        <b><Link href={`/comercios/${c.slug}`}>{c.nombre}</Link></b>
                        <small>{c.direccion}</small>
                      </div>
                      <span className="pill" style={{ color: "var(--amber)" }}>★ {c.rating}</span>
                    </div>
                    <div className="pbody" style={{ paddingTop: 0 }}>
                      <div className="pactions">
                        <a className="btn btn-wa btn-sm" href={`https://wa.me/${c.whatsapp}`} target="_blank" rel="noopener">
                          <WhatsApp style={{ width: 16, height: 16 }} /> Contactar
                        </a>
                        <Link className="btn btn-ghost btn-sm" href={`/comercios/${c.slug}`}>Ver perfil</Link>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ZONAS */}
      <section className="section" id="zonas" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="explore">
            <div>
              <span className="eyebrow">Mapa comercial conceptual</span>
              <h2>Explora Bermejo</h2>
              <p>Descubre galerías, mercados y todas las zonas comerciales.</p>
              <div className="zone-chips">
                {zonas.map((z) => (
                  <div className="zchip" key={z.id}>
                    <div className="zi" style={{ background: `${z.color}22`, color: z.color ?? "var(--neon)" }}>
                      <Store style={{ width: 21, height: 21 }} />
                    </div>
                    <b>{z.nombre.replace("Zona ", "")}</b>
                    <small>ver</small>
                  </div>
                ))}
              </div>
              <Link href="#mapa" className="btn btn-ghost">Ver mapa completo <Arrow /></Link>
            </div>
            <div className="explore-map">
              <img src="/bermejociudad.jpg" alt="Bermejo, Bolivia" />
            </div>
          </div>
        </div>
      </section>

      {/* NEGOCIOS DESTACADOS GRID */}
      <section className="section" id="negocios" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="section-head">
            <div><h2>Negocios destacados</h2><p>Los comercios con más actividad esta semana.</p></div>
          </div>
          <div className="biz-grid">
            {comercios.map((c) => (
              <Link className="bizcard" href={`/comercios/${c.slug}`} key={c.id}>
                <div className="cover">
                  <img src={c.portada_url ?? ""} alt={c.nombre} />
                  <img className="logo" src={c.logo_url ?? ""} alt="" />
                </div>
                <div className="body">
                  <h4>{c.nombre}</h4>
                  <div className="zone">{c.direccion}</div>
                  <div className="row">
                    <span className="pill">★ {c.rating}</span>
                    <span className="wa-mini" style={{ background: "var(--wa)" }}>
                      <WhatsApp style={{ width: 17, height: 17, color: "#04240f" }} />
                    </span>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section" style={{ paddingTop: 0 }}>
        <div className="wrap">
          <div className="cta">
            <div>
              <h2>¿Tenés un comercio en Bermejo?</h2>
              <p>Publicá tus ofertas, videos y novedades mandando un mensaje por WhatsApp. Nosotros las mostramos al instante.</p>
            </div>
            <a className="btn btn-primary" href="https://wa.me/59170000000?text=Quiero%20publicar%20en%20Bermejo%20Live%20Market" target="_blank" rel="noopener">
              <WhatsApp style={{ width: 18, height: 18 }} /> Publicar por WhatsApp
            </a>
          </div>
        </div>
      </section>

      <footer className="footer">
        <div className="wrap">
          <div className="copy">
            <span>© 2026 Bermejo Live Market. Todos los derechos reservados.</span>
            <span>Hecho con <span className="heart">♥</span> en Bermejo, Bolivia</span>
          </div>
        </div>
      </footer>
    </>
  );
}
