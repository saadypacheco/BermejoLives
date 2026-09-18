import Link from "next/link";
import { getRedes } from "@/lib/data";
import { redHref } from "@/components/uruku-ui";

/**
 * «Unite a la comunidad»: el botón hacia la Comunidad de WhatsApp de los
 * compradores. El enlace se carga en /contenido (Redes sociales ›
 * Comunidad de WhatsApp) y hasta que esté cargado el botón NO aparece —
 * un botón a una comunidad que no existe es una promesa rota en la primera
 * pantalla.
 *
 * Nadie es agregado: el que toca, entra. Es la única forma de comunidad
 * que WhatsApp no castiga (ver docs/que-falta.md, 17/9).
 */
export async function enlacesComunidad(): Promise<{ comunidad: string | null; canal: string | null }> {
  const redes = await getRedes();
  const de = (clave: string) => {
    const r = redes.find((x) => x.clave === clave);
    return r?.url ? redHref(clave, r.url) : null;
  };
  return { comunidad: de("comunidad"), canal: de("whatsapp_canal") };
}

export async function UnirmeComunidad({ variante = "banner" }: { variante?: "banner" | "boton" | "chico" }) {
  const { comunidad } = await enlacesComunidad();
  if (!comunidad) return null;
  if (variante === "boton") {
    return (
      <a className="uk-btn uk-btn-wa uk-comunidad-btn" href={comunidad} target="_blank" rel="noopener">
        💬 Unite a la comunidad
      </a>
    );
  }
  if (variante === "chico") {
    return (
      <p className="uk-comunidad-chico">
        💬 <a href={comunidad} target="_blank" rel="noopener"><b>Unite a la comunidad de compradores</b></a>: la cotización de la mañana,
        las ofertas del día y gente que ya compró en Bermejo. <Link href="/comunidad">Qué es →</Link>
      </p>
    );
  }
  return (
    <section className="uk-container">
      <div className="uk-comunidad-banner">
        <div className="uk-comunidad-texto">
          <b>💬 La comunidad de los que compran en Bermejo</b>
          <span>Cotización de la mañana, ofertas del día, cómo está el paso, y un grupo por ciudad para preguntar a los que ya vinieron. Entrás vos: nadie te agrega.</span>
        </div>
        <div className="uk-comunidad-acciones">
          <a className="uk-btn uk-btn-wa" href={comunidad} target="_blank" rel="noopener">Unite a la comunidad</a>
          <Link href="/comunidad" className="uk-btn-ghost">Cómo funciona</Link>
        </div>
      </div>
    </section>
  );
}
