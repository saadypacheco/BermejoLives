import Link from "next/link";
import "@/app/uruku.css";
import { ThemeToggle, ThemeNoFlash } from "@/components/uruku-theme";
import { CitySelector } from "@/components/city-selector";
import { IngresarMenu } from "@/components/ingresar-menu";
import { BottomNav } from "@/components/bottom-nav";
import { Asistente } from "@/components/asistente";
import { CatNav } from "@/components/catnav";
import { Ic, SocialLinks, money } from "@/components/uruku-ui";
import { getClima, getCotizaciones, getRedes } from "@/lib/data";
import { ciudadActual } from "@/lib/ciudad-server";
import { versionLabel } from "@/lib/version";
import { URUKU_SVG } from "@/lib/adornos";

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
  showSearch = true,
  showFooter = true,
  mainClass,
  fill = false,
  rootClass,
  asistente,
}: {
  children: React.ReactNode;
  activeCat?: string;
  activeNav?: string;
  showCatnav?: boolean;
  /** El buscador del header. Se apaga en /buscar, que tiene el suyo propio y
   *  en vivo: dos cajas de texto en la misma pantalla, una que navega y otra
   *  que filtra mientras escribís, no se entienden. */
  showSearch?: boolean;
  showFooter?: boolean;
  mainClass?: string;
  fill?: boolean;   // llena la pantalla (ej. mapa): flex column, sin footer, main flex-1
  rootClass?: string;   // clase extra en el root (ej. "uk-map" para overrides del mapa)
  /** Uruku Ayuda. Por defecto el asistente de URUKU; en la ficha de un local
   *  con el plan que lo incluye, el de ese local; `false` lo esconde. */
  asistente?: { id: string; nombre: string } | false;
}) {
  const [{ ciudad, ciudades }, clima, cotizaciones, redes] = await Promise.all([
    ciudadActual(), getClima(), getCotizaciones(), getRedes(),
  ]);
  const nombre = ciudad?.nombre ?? "tu ciudad";
  // Dos preguntas distintas. `esFrontera` (columna de la ciudad): si el
  // peso argentino le importa. `conGuia`: si lo que hoy está cargado —la
  // guía del que cruza, el estado del paso, el clima, el conversor de
  // pesos, la comunidad— es de ESTA ciudad. Todo eso es de Bermejo; otra
  // frontera (Yacuiba, Villazón) tendrá lo suyo cuando se cargue. Sin ciudad
  // conocida: Bermejo, la primera.
  const esFrontera = ciudad?.es_frontera ?? true;
  // Cada frontera tiene su guía (0124): se muestra cuando está cargada.
  const conGuia = ciudad ? (ciudad.guia_activa ?? ciudad.slug === "bermejo") : true;
  // El dólar sirve en cualquier ciudad; el peso argentino, en la frontera.
  // El dólar en todas; la moneda del país vecino, en su frontera (peso en
  // Bermejo/Yacuiba/Villazón, real en Cobija, sol en Desaguadero).
  const claveVecina = { ARS: "ars_bob", BRL: "brl_bob", PEN: "pen_bob" }[ciudad?.moneda_vecina ?? "ARS"] ?? "ars_bob";
  const cot2 = cotizaciones.filter((c) => c.clave === "usd_bob" || (esFrontera && c.clave === claveVecina)).slice(0, 2);

  const showFoot = showFooter && !fill;

  return (
    <div id="ukroot" className={`uk${fill ? " uk-fill" : ""}${rootClass ? " " + rootClass : ""}`}>
      <ThemeNoFlash />

      {/* Header: fila 1 = logo + ciudad + Ingresar + tema · fila 2 = redes + clima +
          cotización · fila 3 = buscador */}
      <header className="uk-header">
        <div className="uk-container uk-headwrap">
          {/* Una sola fila en compu y tablet: logo · redes y cotización al
              centro · ciudad e Ingresar. Eran dos filas y la segunda estaba
              casi vacía, empujando el mapa medio centenar de píxeles hacia
              abajo por nada. En el celular la tira baja sola a su renglón (ver
              el `flex-wrap` y el `order` en el CSS), que es donde entra. */}
          <div className="uk-head-top">
            <Link href="/" className="uk-brand"><img className="uk-brand-full" src="/logouruku-wordmark.png" alt="URUKU" /></Link>

            <div className="uk-head-strip">
              <SocialLinks redes={redes} cls="uk-social-links" />
              <div className="uk-topinfo">
                {conGuia && clima?.temp_c != null && (
                  <span className="uk-top-item">{clima.icono || "☀"} {Math.round(clima.temp_c)}°</span>
                )}
                {/* La tira lleva al conversor: el que mira el dólar arriba
                    quiere saber cuánto son SUS pesos, y eso está en /cambio. */}
                {cot2.map((c) => (
                  <Link key={c.clave} href={conGuia ? "/cambio" : "/buscar?rubro=cambio&vista=mapa"} className="uk-top-item" title={conGuia ? "Calculadora y casas de cambio" : "Casas de cambio en el mapa"}>{c.detalle} = <b>{money(c.valor)}</b> {c.unidad}</Link>
                ))}
              </div>
            </div>

            {/* En la compu no hay barra de abajo: Mapa, Ofertas y Cambio van
                acá, entre la cotización y la ciudad. Se esconde en el celular,
                donde la barra de abajo ya los tiene. */}
            <nav className="uk-topnav" aria-label="Secciones">
              {(conGuia
                ? [["Guía", "/guia"], ["Mapa", "/buscar?vista=mapa"], ["Ofertas", "/ofertas"], ["Novedades", "/novedades"], ["Cambio", "/cambio"]]
                : [["Mapa", "/buscar?vista=mapa"], ["Ofertas", "/ofertas"], ["Novedades", "/novedades"], ["Guardados", "/guardados"]]
              ).map(([k, href]) => (
                <Link key={k} href={href} className={activeNav === k ? "active" : ""}>{k}</Link>
              ))}
            </nav>

            <div className="uk-head-actions">
              <CitySelector actual={ciudad} ciudades={ciudades} />
              <IngresarMenu />
              <ThemeToggle iconOnly />
            </div>
          </div>

          {showSearch && (
          <form className="uk-search" action="/buscar" method="get">
            <Ic d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3" />
            <input name="q" placeholder="¿Qué estás buscando?" aria-label="Buscar" />
            <button type="submit">Buscar</button>
          </form>
          )}
        </div>

        {showCatnav && <CatNav active={activeCat} />}
      </header>

      <main className={`${fill ? "uk-fill-main" : ""}${mainClass ? " " + mainClass : ""}`.trim() || undefined}>{children}</main>

      {showFoot && (
        <footer className="uk-footer">
          {/* La vaina del uruku de fondo, muy tenue. Decorativa: sin clic y
              oculta para lectores de pantalla. */}
          <div className="uk-uruku-marca" aria-hidden="true"
               dangerouslySetInnerHTML={{ __html: URUKU_SVG }} />
          <div className="uk-container">
            <div className="uk-foot-cols">
              <div className="uk-foot-col">
                <h4>Descubrí</h4>
                <Link href="/" className="uk-foot-link"><Ic d="M3 11l9-8 9 8M5 10v10h14V10" /><span>Inicio</span><i>›</i></Link>
                <Link href="/ofertas" className="uk-foot-link"><Ic d="M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" /><span>Ofertas</span><i>›</i></Link>
                <Link href="/novedades" className="uk-foot-link"><Ic d="M3 11v2a1 1 0 0 0 1 1h3l4 4V6L7 10H4a1 1 0 0 0-1 1zM16 8a5 5 0 0 1 0 8" /><span>Novedades</span><i>›</i></Link>
                <Link href="/buscar" className="uk-foot-link"><Ic d="M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3" /><span>Buscar</span><i>›</i></Link>
                <Link href="/guardados" className="uk-foot-link"><Ic d="M6 3h12v18l-6-4-6 4V3z" /><span>Guardados</span><i>›</i></Link>
                {conGuia && <Link href="/comunidad" className="uk-foot-link"><Ic d="M4 4h16v12H7l-3 3V4z" /><span>Comunidad</span><i>›</i></Link>}
              </div>
              <div className="uk-foot-col">
                <h4>Para comercios</h4>
                <Link href="/autoregistro" className="uk-foot-link"><Ic d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4zM3 6h18M16 10a4 4 0 0 1-8 0" /><span>Publicar comercio</span><i>›</i></Link>
                <Link href="/mi-comercio" className="uk-foot-link"><Ic d="M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" /><span>Mi negocio</span><i>›</i></Link>
                <Link href="/planes" className="uk-foot-link"><Ic d="M2 20h20M3 17l2-9 5 4 2-6 2 6 5-4 2 9" /><span>Planes y beneficios</span><i>›</i></Link>
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
      <BottomNav active={activeNav ?? ""} conGuia={conGuia} />
      {asistente !== false && (
        <Asistente comercio={asistente || undefined}
                   ciudad={ciudad ? { slug: ciudad.slug, nombre: ciudad.nombre, con_guia: conGuia } : undefined} />
      )}
    </div>
  );
}
