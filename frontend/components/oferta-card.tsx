import Link from "next/link";
import { IcRubro } from "@/components/ic";
import { PrecioArs } from "@/components/precio-ars";
import { precioFmt, type FeedItem } from "@/lib/types";

/**
 * La tarjeta de una oferta de la portada: foto (o el ícono del rubro si no hay),
 * etiqueta arriba, `-%` si tiene descuento, y abajo el título, el comercio y el
 * precio con su «≈ $ ARS» en frontera. La usan «Ofertas destacadas» y «Vencen hoy»;
 * lo único que cambia entre las dos es la etiqueta (`tag`).
 */
export function OfertaCard({ o, tag }: { o: FeedItem; tag?: string }) {
  return (
    <Link href={`/comercios/${o.comercio_slug}`}
      className={`uk-offer${o.imagen_url ? "" : " sin-foto"}${tag ? " uk-offer-urgente" : ""}`}
      style={o.imagen_url ? { backgroundImage: `url('${o.imagen_url}')` } : undefined}>
      <span className="uk-offer-tag">{tag ?? (o.zona_nombre || o.comercio_nombre)}</span>
      {/* Sin foto, el ícono del rubro ocupa su lugar. */}
      {!o.imagen_url && <span className="uk-offer-emoji"><IcRubro slug={o.rubro_slug} s={64} peso="fill" /></span>}
      {o.descuento_pct != null && <span className="uk-offer-disc">-{o.descuento_pct}%</span>}
      <div className="uk-offer-body">
        <h3>{o.titulo}</h3>
        <small>{o.comercio_nombre}</small>
        {o.precio != null && <strong>{precioFmt(o.precio, o.moneda)}</strong>}
        <PrecioArs precio={o.precio} moneda={o.moneda} />
      </div>
    </Link>
  );
}
