import Link from "next/link";
import "@/app/uruku.css";
import { ThemeToggle, ThemeNoFlash } from "@/components/uruku-theme";
import { CitySelector } from "@/components/city-selector";
import { IngresarMenu } from "@/components/ingresar-menu";
import { BottomNav } from "@/components/bottom-nav";
import { CatNav } from "@/components/catnav";
import { Ic, SocialLinks, money } from "@/components/uruku-ui";
import { getClima, getCotizaciones, getRedes } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";

/**
 * Marco compartido del diseño URUKU: barra social + header (buscador, ciudad,
 * clima, cotización) + nav de categorías + footer + tema claro/oscuro.
 * Cada página envuelve su contenido en <UrukuShell>…</UrukuShell>.
 */
export async function UrukuShell({
  children,
  activeCat = "Todos",
  activeNav,
  showCatnav = true,
  showFooter = true,
  mainClass,
  fill = false,
  rootClass,
}: {
  children: React.ReactNode;
  activeCat?: string;
  activeNav?: string;
  showCatnav?: boolean;
  showFooter?: boolean;
  mainClass?: string;
  fill?: boolean;   // llena la pantalla (ej. mapa): flex column, sin footer, main flex-1
  rootClass?: string;   // clase extra en el root (ej. "uk-map" para overrides del mapa)
}) {
  const [{ ciudad, ciudades }, clima, cotizaciones, redes] = await Promise.all([
    ciudadActual(), getClima(), getCotizaciones(), getRedes(),
  ]);
  const nombre = ciudad?.nombre ?? "tu ciudad";
  const cot2 = cotizaciones.slice(0, 2);

  const showFoot = showFooter && !fill;

  return (
    <div id="ukroot" className={`uk${fill ? " uk-fill" : ""}${rootClass ? " " + rootClass : ""}`}>
      <ThemeNoFlash />

      {/* Barra social */}
      <div className="uk-social-bar">
        <div className="uk-container uk-social-inner">
          <div className="uk-social-copy">
            <strong>URUKU EN REDES</strong>
            <span aria-hidden>›</span>
            <span className="uk-hide-sm">Ofertas, novedades y tips todos los días</span>
          </div>
          <div className="uk-social-right">
            <SocialLinks redes={redes} cls="uk-social-links" />
            <ThemeToggle />
          </div>
        </div>
      </div>

      {/* Header */}
      <header className="uk-header">
        <div className="uk-container uk-header-main">
          <Link href="/" className="uk-brand">
            <div className="uk-brand-word"><img className="uk-brand-logo" src="/logouruku.png" alt="URUKU" /><span>URUKU</span></div>
            <small>Descubrí. <span className="uk-red">Ahorrá.</span> Disfrutá {nombre}.</small>
          </Link>

          <form className="uk-search" action="/buscar" method="get">
            <Ic d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3" />
            <input name="q" placeholder="¿Qué estás buscando?" aria-label="Buscar" />
            <button type="submit">Buscar</button>
          </form>

          <div className="uk-tools">
            <CitySelector actual={ciudad} ciudades={ciudades} />
            {clima?.temp_c != null && (
              <div className="uk-weather">
                <span className="uk-sun">{clima.icono || "☀"}</span>
                <div className="uk-weather-t">
                  <strong>{Math.round(clima.temp_c)}°C</strong>
                  {clima.descripcion && <small>{clima.descripcion}</small>}
                </div>
              </div>
            )}
            {cot2.map((c) => (
              <div key={c.clave} className="uk-quote-mini">
                <small>{c.etiqueta}</small>
                <strong>{money(c.valor)} {c.unidad}</strong>
              </div>
            ))}
            <IngresarMenu />
          </div>
        </div>

        {showCatnav && <CatNav active={activeCat} />}
      </header>

      <main className={`${fill ? "uk-fill-main" : ""}${mainClass ? " " + mainClass : ""}`.trim() || undefined}>{children}</main>

      {showFoot && (
        <footer className="uk-footer">
          <div className="uk-container uk-footer-grid">
            <div>
              <div className="uk-brand uk-footer-brand">
                <div className="uk-brand-word"><img className="uk-brand-logo" src="/logouruku.png" alt="URUKU" /><span>URUKU</span></div>
                <small>Descubrí. <span className="uk-red">Ahorrá.</span> Disfrutá {nombre}.</small>
              </div>
              <p>La plataforma local que conecta a compradores y comercios en {nombre} y en muchas ciudades más.</p>
              <SocialLinks redes={redes} cls="uk-footer-socials" />
            </div>
            <div>
              <h4>Navegación</h4>
              <Link href="/">Inicio</Link>
              <Link href="/mapa">Mapa</Link>
              <Link href="/mapa?of=1">Ofertas</Link>
              <Link href="/buscar">Buscar</Link>
              <Link href="/autoregistro">Publicá tu negocio</Link>
            </div>
            <div>
              <h4>Para comercios</h4>
              <Link href="/autoregistro">Publicar comercio</Link>
              <Link href="/mi-comercio">Mi negocio</Link>
              <Link href="/autoregistro">Planes y beneficios</Link>
            </div>
            <div>
              <h4>Información</h4>
              <a href="#">Preguntas frecuentes</a>
              <a href="#">Términos y condiciones</a>
              <a href="#">Política de privacidad</a>
            </div>
          </div>
          <div className="uk-container uk-footer-bottom">
            <span>© 2026 Uruku. Todos los derechos reservados.</span>
            <span>Hecho con ♥ para nuestra comunidad.</span>
          </div>
        </footer>
      )}

      {!fill && <div style={{ height: 20 }} />}
      <BottomNav active={activeNav ?? ""} />
    </div>
  );
}
