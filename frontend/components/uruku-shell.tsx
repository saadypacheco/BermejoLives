import Link from "next/link";
import "@/app/uruku.css";
import { ThemeToggle, ThemeNoFlash, POR_DEFECTO } from "@/components/uruku-theme";
import { CitySelector } from "@/components/city-selector";
import { IngresarMenu } from "@/components/ingresar-menu";
import { BottomNav } from "@/components/bottom-nav";
import { Asistente } from "@/components/asistente";
import { Suspense } from "react";
import { CatNav } from "@/components/catnav";
import { SocialLinks, money } from "@/components/uruku-ui";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";
import { Ic, climaIcono } from "@/components/ic";
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
    <div id="ukroot" data-theme={POR_DEFECTO} className={`uk${fill ? " uk-fill" : ""}${rootClass ? " " + rootClass : ""}`}>
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
            {/* En SVG: el PNG se veía borroso en pantallas de alta densidad y tenía
                un velo blanco que en modo oscuro se notaba como un recuadro. */}
            <Link href="/" className="uk-brand"><img className="uk-brand-full" src="/uruku-horizontal.svg" alt="Uruku" /></Link>

            <div className="uk-head-strip">
              <SocialLinks redes={redes} cls="uk-social-links" />
              <div className="uk-topinfo">
                {conGuia && clima?.temp_c != null && (
                  <span className="uk-top-item"><Ic n={climaIcono(clima.descripcion)} s={15} /> {Math.round(clima.temp_c)}°</span>
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
            <Ic n="buscar" />
            <input name="q" placeholder="¿Qué estás buscando?" aria-label="Buscar" />
            <button type="submit">Buscar</button>
          </form>
          )}
        </div>

        {/* En Suspense porque CatNav lee el rubro de la URL
            (useSearchParams): sin el límite, TODA la página se renderiza del
            lado del cliente y se pierde el HTML del servidor. */}
        {showCatnav && <Suspense fallback={null}><CatNav active={activeCat} /></Suspense>}
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
                <Link href="/" className="uk-foot-link"><Ic n="inicio" /><span>Inicio</span><i>›</i></Link>
                <Link href="/ofertas" className="uk-foot-link"><Ic n="ofertas" /><span>Ofertas</span><i>›</i></Link>
                <Link href="/novedades" className="uk-foot-link"><Ic n="novedades" /><span>Novedades</span><i>›</i></Link>
                <Link href="/buscar" className="uk-foot-link"><Ic n="buscar" /><span>Buscar</span><i>›</i></Link>
                <Link href="/guardados" className="uk-foot-link"><Ic n="guardado" /><span>Guardados</span><i>›</i></Link>
                {conGuia && <Link href="/comunidad" className="uk-foot-link"><Ic n="comunidad" /><span>Comunidad</span><i>›</i></Link>}
              </div>
              <div className="uk-foot-col">
                <h4>Para comercios</h4>
                <Link href="/autoregistro" className="uk-foot-link"><Ic n="comercios" /><span>Publicar comercio</span><i>›</i></Link>
                <Link href="/mi-comercio" className="uk-foot-link"><Ic n="usuario" /><span>Mi negocio</span><i>›</i></Link>
                <a href={waUruku("Hola, quiero hacer una consulta a URUKU")} target="_blank" rel="noopener" className="uk-foot-link"><Ic n="whatsapp" /><span>WhatsApp {WA_URUKU_TEXTO}</span><i>›</i></a>
                {/* El enlace a /planes salió del sitio el 2/10: los precios se deciden
          por ciudad y mostrar los de Bermejo en Santa Cruz es prometer algo
          que todavía no está decidido. La pantalla sigue existiendo para uso
          interno; lo que se sacó es la puerta pública. */}
              </div>
              <div className="uk-foot-col">
                <h4>Información</h4>
                <a href="#" className="uk-foot-link"><Ic n="ayuda" /><span>Preguntas frecuentes</span><i>›</i></a>
                <a href="#" className="uk-foot-link"><Ic n="documento" /><span>Términos y condiciones</span><i>›</i></a>
                <a href="#" className="uk-foot-link"><Ic n="seguridad" /><span>Política de privacidad</span><i>›</i></a>
              </div>
            </div>

            <div className="uk-foot-cta">
              <span className="uk-foot-cta-ic"><Ic n="comercios" /></span>
              <div className="uk-foot-cta-txt">
                <b>¿Tenés un comercio?</b>
                <p>Sumate a URUKU y hacé crecer tu negocio con más visibilidad y nuevos clientes.</p>
              </div>
              <Link href="/autoregistro" className="uk-foot-cta-btn">Publicar mi negocio <span>›</span></Link>
            </div>

            <div className="uk-foot-bottom">
              <Link href="/" className="uk-foot-logo"><img src="/uruku-horizontal.svg" alt="Uruku" /></Link>
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
