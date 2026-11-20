import Link from "next/link";
import type { TarjetaProducto } from "@/lib/home-productos-pure";
import { PistaCarrusel } from "./pista-carrusel";

/**
 * «Lo que se consigue en {ciudad}» (docs/home-ciudades.md §5): fotos de lo que hay en los locales, cada una
 * con el nombre del comercio y un enlace a su ficha, a la sección «Qué podés encontrar acá». Sin tarjetas,
 * no se dibuja nada. Es del servidor: las tarjetas ya vienen armadas (de la tabla `productos` o de los textos
 * de cada comercio).
 */
export function CarruselProductos({ tarjetas, ciudad }: { tarjetas: TarjetaProducto[]; ciudad: string }) {
  if (tarjetas.length === 0) return null;
  return (
    <section className="uk-container uk-home-sec uk-hc-sec" aria-labelledby="home-productos">
      <div className="uk-section-head">
        <h2 id="home-productos">Lo que se consigue en {ciudad} <small>Lo que se ve en la foto de cada local</small></h2>
      </div>
      <PistaCarrusel etiqueta={`Lo que se consigue en ${ciudad}`}>
        {tarjetas.map((t) => (
          <div role="listitem" key={t.id} className="uk-hc-item">
            <Link href={t.href} className="uk-hc-prod">
              {/* Miniaturas de 200 px: perezosas, no frenan la carga de la portada. */}
              <img src={t.foto} alt="" loading="lazy" decoding="async" />
              <span className="uk-hc-prod-txt">
                <b>{t.titulo}</b>
                {t.precio && <em>{t.precio}</em>}
                <small>{t.comercio}</small>
              </span>
            </Link>
          </div>
        ))}
      </PistaCarrusel>
    </section>
  );
}
