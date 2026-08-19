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
import { versionLabel } from "@/lib/version";

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

      {/* Header: fila 1 = logo + ciudad + Ingresar + tema · fila 2 = redes + clima +
          cotización · fila 3 = buscador */}
      <header className="uk-header">
        <div className="uk-container uk-headwrap">
          <div className="uk-head-top">
            <Link href="/" className="uk-brand"><img className="uk-brand-full" src="/logouruku-wordmark.png" alt="URUKU" /></Link>
            <div className="uk-head-actions">
              <CitySelector actual={ciudad} ciudades={ciudades} />
              <IngresarMenu />
              <ThemeToggle iconOnly />
            </div>
          </div>

          <div className="uk-head-strip">
            <SocialLinks redes={redes} cls="uk-social-links" />
            <div className="uk-topinfo">
              {clima?.temp_c != null && (
                <span className="uk-top-item">{clima.icono || "☀"} {Math.round(clima.temp_c)}°</span>
              )}
              {cot2.map((c) => (
                <span key={c.clave} className="uk-top-item"><b>{money(c.valor)}</b> {c.unidad} · {c.etiqueta}</span>
              ))}
            </div>
          </div>

          <form className="uk-search" action="/buscar" method="get">
            <Ic d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3" />
            <input name="q" placeholder="¿Qué estás buscando?" aria-label="Buscar" />
            <button type="submit">Buscar</button>
          </form>
        </div>

        {showCatnav && <CatNav active={activeCat} />}
      </header>

      <main className={`${fill ? "uk-fill-main" : ""}${mainClass ? " " + mainClass : ""}`.trim() || undefined}>{children}</main>

      {showFoot && (
        <footer className="uk-footer">
          <div className="uk-container">
            <div className="uk-foot-cols">
              <div className="uk-foot-col">
                <h4>Descubrí</h4>
                <Link href="/" className="uk-foot-link"><Ic d="M3 11l9-8 9 8M5 10v10h14V10" /><span>Inicio</span><i>›</i></Link>
                <Link href="/mapa" className="uk-foot-link"><Ic d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3zM9 3v15M15 6v15" /><span>Mapa</span><i>›</i></Link>
                <Link href="/mapa?of=1" className="uk-foot-link"><Ic d="M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" /><span>Ofertas</span><i>›</i></Link>
                <Link href="/buscar" className="uk-foot-link"><Ic d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3" /><span>Buscar</span><i>›</i></Link>
                <Link href="/guardados" className="uk-foot-link"><Ic d="M6 3h12v18l-6-4-6 4V3z" /><span>Guardados</span><i>›</i></Link>
              </div>
              <div className="uk-foot-col">
                <h4>Para comercios</h4>
                <Link href="/autoregistro" className="uk-foot-link"><Ic d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0" /><span>Publicar comercio</span><i>›</i></Link>
                <Link href="/mi-comercio" className="uk-foot-link"><Ic d="M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" /><span>Mi negocio</span><i>›</i></Link>
                <Link href="/autoregistro" className="uk-foot-link"><Ic d="M2 20h20M3 17l2-9 5 4 2-6 2 6 5-4 2 9" /><span>Planes y beneficios</span><i>›</i></Link>
              </div>
              <div className="uk-foot-col">
                <h4>Información</h4>
                <a href="#" className="uk-foot-link"><Ic d="M12 17h.01M9.1 9a3 3 0 1 1 4 2.8c-.7.4-1.1 1-1.1 1.7M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" /><span>Preguntas frecuentes</span><i>›</i></a>
                <a href="#" className="uk-foot-link"><Ic d="M14 3v4a1 1 0 0 0 1 1h4M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" /><span>Términos y condiciones</span><i>›</i></a>
                <a href="#" className="uk-foot-link"><Ic d="M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z" /><span>Política de privacidad</span><i>›</i></a>
              </div>
            </div>

            <div className="uk-foot-cta">
              <span className="uk-foot-cta-ic"><Ic d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0" /></span>
              <div className="uk-foot-cta-txt">
                <b>¿Tenés un comercio?</b>
                <p>Sumate a URUKU y hacé crecer tu negocio con más visibilidad y nuevos clientes.</p>
              </div>
              <Link href="/autoregistro" className="uk-foot-cta-btn">Publicar mi negocio <span>›</span></Link>
            </div>

            <div className="uk-foot-bottom">
              <Link href="/" className="uk-foot-logo"><img src="/logouruku-wordmark.png" alt="URUKU" /></Link>
              <SocialLinks redes={redes} cls="uk-footer-socials" />
              <span className="uk-foot-copy">© 2026 URUKU. Todos los derechos reservados.</span>
              <span className="uk-version" title="Build en línea">{versionLabel()}</span>
            </div>
          </div>
        </footer>
      )}

      {!fill && <div style={{ height: 20 }} />}
      <BottomNav active={activeNav ?? ""} />
    </div>
  );
}
