import Link from "next/link";
import "@/app/styles/turismo.css";
import { Ic } from "@/components/ic";
import { CarruselNovedades } from "@/components/carrusel-novedades";
import { HREF_PARA_VISITAR, RUBRO_PARA_VISITAR } from "@/lib/para-visitar";
import { businessPath, categoryPath } from "@/lib/seo";
import {
  bajadaVisita, iconoDeLugar, rutaTurismo, type AccesoVisita, type LocalTurismo,
} from "@/lib/turismo-ciudad-pure";

/**
 * «Visitá {ciudad}»: la banda de turismo de la home de una ciudad con lugares para visitar
 * (docs/turismo-home-y-repetidos.md §3). Es A PROPÓSITO otra cosa que las grillas de tarjetas del resto de
 * la home: banda a todo el ancho con fondo propio (el verde de marca, más profundo de noche), título
 * grande, un carrusel de lugares con foto y accesos grandes en tarjetas claras.
 *
 * Sin números (ni «22 guías» ni «49 hoteles»), sin emojis (íconos de components/ic.tsx) y sin fotos ni textos
 * de la página de turismo: sólo la foto propia de URUKU del lugar, si la tiene. Estilos en
 * app/styles/turismo.css. Es un componente de servidor: el único JS que lleva es el del carrusel.
 */

/** Las montañas del fondo: una cresta de dos capas (decoración; las pinta el CSS con `currentColor`). */
function Cordillera() {
  return (
    <svg className="uk-visita-cordillera" viewBox="0 0 1200 120" preserveAspectRatio="none" aria-hidden focusable="false">
      <path className="atras" d="M0 120V70l90-34 70 26 110-52 100 58 80-30 120 48 90-42 110 40 90-56 120 62 70-26 110 40V120z" />
      <path className="frente" d="M0 120V96l120-30 90 22 100-40 110 44 120-34 90 30 130-46 110 40 90-26 140 36V120z" />
    </svg>
  );
}

export function VisitaCiudad({ ciudad, lugares, accesos }: {
  ciudad: { slug: string; nombre: string };
  /** Ya en el orden del carrusel (`lugaresParaCarrusel`). Vacío = la banda sale sin carrusel. */
  lugares: readonly LocalTurismo[];
  accesos: readonly AccesoVisita[];
}) {
  return (
    <section className="uk-visita" aria-labelledby="visita-h">
      <span className="uk-visita-sol" aria-hidden="true" />
      <div className="uk-container uk-visita-in">
        <p className="uk-visita-eyebrow"><Ic n="turismo" s={16} /> Para el que nos visita</p>
        <h2 id="visita-h" className="uk-visita-h">Visitá <span>{ciudad.nombre}</span></h2>
        <p className="uk-visita-bajada">{bajadaVisita(ciudad.nombre)}</p>
        <div className="uk-visita-cta">
          <Link href={rutaTurismo(ciudad.slug)} className="uk-visita-btn"><Ic n="ruta" s={20} /> Armá tu visita</Link>
          <Link href={HREF_PARA_VISITAR} className="uk-visita-btn ghost"><Ic n="mapa" s={20} /> Ver en el mapa</Link>
        </div>

        {lugares.length > 0 && (
          <div className="uk-visita-lugares">
            <div className="uk-visita-cab">
              <h3>Lugares para visitar</h3>
              <Link href={categoryPath(ciudad.slug, RUBRO_PARA_VISITAR)}>Ver todos <Ic n="seguir" s={16} /></Link>
            </div>
            <CarruselNovedades>
              {lugares.map((l) => {
                const tipo = (l.subcategoria ?? "").trim() || "Para visitar";
                return (
                  <Link key={l.id} href={businessPath(l.slug)} className={`uk-visita-lugar${l.foto ? "" : " sin-foto"}`}>
                    {l.foto
                      // eslint-disable-next-line @next/next/no-img-element
                      ? <img src={l.foto} alt="" loading="lazy" decoding="async" />
                      : <Ic n={iconoDeLugar(l.subcategoria)} s={96} className="uk-visita-lugar-ic" />}
                    <span className="uk-visita-tipo"><Ic n={iconoDeLugar(l.subcategoria)} s={16} /> {tipo}</span>
                    <span className="uk-visita-lugar-pie">
                      <span className="uk-visita-lugar-nombre">{l.nombre}</span>
                      <span className="uk-visita-ir" aria-hidden="true"><Ic n="seguir" s={18} /></span>
                    </span>
                  </Link>
                );
              })}
            </CarruselNovedades>
          </div>
        )}

        {accesos.length > 0 && (
          <nav aria-label={`Para tu visita a ${ciudad.nombre}`} className="uk-visita-accesos-wrap">
            <ul className="uk-visita-accesos">
              {accesos.map((a) => (
                <li key={a.clave}>
                  <Link href={a.href} className="uk-visita-acceso">
                    <span className="uk-visita-acceso-ic"><Ic n={a.i} s={30} /></span>
                    <b>{a.t}</b>
                    <small>{a.d}</small>
                    <Ic n="seguir" s={18} className="uk-visita-acceso-flecha" />
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </div>
      <Cordillera />
    </section>
  );
}
