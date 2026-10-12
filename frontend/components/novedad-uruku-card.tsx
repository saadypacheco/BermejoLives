import Link from "next/link";
import { Ic } from "@/components/ic";
import { fechaNovedad, type NovedadUruku } from "@/lib/data";

/**
 * La tarjeta de una novedad de URUKU (migración 0150), la misma en el inicio y
 * en /novedades: portada —o el póster del video— de fondo, la etiqueta URUKU,
 * un play si tiene video, el título y la fecha. Reusa el molde de `.uk-offer`
 * (la tarjeta de oferta) para que las dos sean hermanas en la grilla.
 *
 * El estado no va sólo en el color: la etiqueta dice «URUKU» y el video tiene
 * su ícono, así que se lee igual sin distinguir colores.
 */
export function NovedadUrukuCard({ n }: { n: NovedadUruku }) {
  const imagen = n.portada_thumb_url || n.portada_url || n.video_poster_url;
  return (
    <Link
      href={`/novedades/uruku/${n.id}`}
      className={`uk-offer uk-offer-uruku${imagen ? "" : " sin-foto"}`}
      style={imagen ? { backgroundImage: `url(${JSON.stringify(imagen)})` } : undefined}
    >
      <span className="uk-offer-tag">URUKU</span>
      {/* Sin imagen, el ícono ocupa su lugar (como el rubro en una oferta sin foto). */}
      {!imagen && <span className="uk-offer-emoji"><Ic n={n.video_url ? "video_play" : "novedades"} s={64} peso="fill" /></span>}
      {n.video_url && imagen && (
        <span className="uk-offer-play" aria-label="Tiene video"><Ic n="video_play" s={52} peso="fill" /></span>
      )}
      <div className="uk-offer-body">
        <h3>{n.titulo}</h3>
        <small>{fechaNovedad(n.fecha)}{n.video_url ? " · Con video" : ""}</small>
      </div>
    </Link>
  );
}
