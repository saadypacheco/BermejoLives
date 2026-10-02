import { ImageResponse } from "next/og";
import { mensajePrincipal, bajadaOg, COLOR, MARCA, CIUDAD_POR_DEFECTO } from "@/lib/marca";

/**
 * La imagen que se ve al compartir uruku.bo por WhatsApp, Facebook o Instagram.
 *
 * POR QUÉ SE DIBUJA Y NO ES UN PNG
 * ================================
 * El kit de marca trae un `og-image.png` con «Todo Bermejo en un solo lugar» y
 * «antes de cruzar» ESCRITOS ADENTRO de la imagen. Con una sola ciudad eso
 * alcanza; con cinco, compartir el enlace de Santa Cruz mostraría Bermejo —
 * y el que lo recibe cree que URUKU es de otro lado y no entra.
 *
 * Acá se arma en el servidor, así que cambiar el titular es una línea de
 * código y no abrir un editor de imágenes.
 *
 * PERO NO PUEDE SABER LA CIUDAD, y conviene tenerlo claro
 * ------------------------------------------------------
 * En URUKU la ciudad vive en una COOKIE, no en la dirección: uruku.bo es la
 * misma URL para todas. Y la vista previa no la pide una persona: la pide el
 * robot de WhatsApp o de Facebook, que no manda cookies. Así que acá nunca se
 * sabe a quién se le está mostrando.
 *
 * Hoy eso no miente: los 1.250 comercios cargados son de Bermejo y el
 * lanzamiento es de Bermejo. El día que Santa Cruz tenga catálogo, la vista
 * previa va a seguir diciendo Bermejo — y la solución NO es esta pantalla,
 * es que cada ciudad tenga su propia dirección (uruku.bo/santa-cruz). Ese es
 * el trabajo que hay que hacer entonces; dejarlo escrito acá es para que no
 * se descubra el día que alguien comparta un enlace y se vea mal.
 *
 * Se dibuja con estilos planos a propósito: esto NO corre en un navegador —
 * lo renderiza Satori en el servidor, que entiende un subconjunto de CSS y no
 * lee ninguna hoja de estilos del sitio. Por eso los colores vienen de
 * `lib/marca`, en código, y no de las variables `--uk-*`.
 */

// EDGE Y NO NODEJS. Con el runtime de node, `@vercel/og` resuelve una ruta de
// archivo con `fileURLToPath` y revienta al compilar EN WINDOWS («Invalid
// URL»). El build de edge no pasa por ahí. Si alguna vez hay que volver a
// node, el síntoma es ése y no es culpa de esta pantalla.
export const runtime = "edge";
export const alt = "Uruku · Todo en un solo lugar";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function Image() {
  const nombre = CIUDAD_POR_DEFECTO;
  const frontera = true;

  const titular = mensajePrincipal(nombre);
  // «Todo Santa Cruz en un solo lugar» → la ciudad va en verde, como en el
  // kit. Se parte en tres para poder pintar sólo el medio.
  const [antes, resto] = ["Todo ", titular.slice(5)];
  const corte = resto.lastIndexOf(" en un solo lugar");
  const ciudadTxt = corte > 0 ? resto.slice(0, corte) : resto;
  const despues = corte > 0 ? resto.slice(corte) : "";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", flexDirection: "column",
          justifyContent: "center", padding: "0 80px",
          background: `linear-gradient(160deg, ${COLOR.cielo} 0%, ${COLOR.fondo} 55%, ${COLOR.fondo} 100%)`,
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", fontSize: 40, fontWeight: 800, color: COLOR.verdeHondo, letterSpacing: "-0.01em" }}>
          {MARCA.toUpperCase()}
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", marginTop: 28, fontSize: 82, fontWeight: 800, lineHeight: 1.05, letterSpacing: "-0.03em", color: COLOR.texto }}>
          <span>{antes}</span>
          <span style={{ color: COLOR.verde }}>{ciudadTxt}</span>
          <span>{despues}</span>
        </div>
        <div style={{ display: "flex", marginTop: 26, fontSize: 34, color: COLOR.texto2 }}>
          {bajadaOg(frontera)}
        </div>
        <div style={{ display: "flex", gap: 16, marginTop: 36 }}>
          {["Comercios", "Ofertas", frontera ? "Cambio" : "Mapa"].map((t) => (
            <div key={t} style={{
              display: "flex", padding: "12px 26px", borderRadius: 999,
              background: "#FFFFFF", color: COLOR.verdeTexto, fontSize: 26, fontWeight: 600,
              border: `1px solid ${COLOR.cielo}`,
            }}>{t}</div>
          ))}
        </div>
      </div>
    ),
    size,
  );
}
