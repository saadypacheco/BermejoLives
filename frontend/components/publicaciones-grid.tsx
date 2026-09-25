import Link from "next/link";
import { LeadLink } from "@/components/lead-link";
import { WhatsApp } from "@/components/icons";
import { contactoDeOferta, precioFmt, vencimientoFmt, type FeedItem } from "@/lib/types";

/**
 * Las publicaciones de TODOS los comercios, con su foto: lo que se ve al
 * tocar Ofertas o Novedades.
 *
 * Es la misma tarjeta de la ficha del comercio, con una diferencia: acá el
 * nombre del local es lo primero que hay que poder leer —el comprador está
 * mirando la ciudad entera, no un negocio— y lleva a su ficha.
 */
export function PublicacionesGrid({ items, vacio }: { items: FeedItem[]; vacio?: React.ReactNode }) {
  if (items.length === 0) return <>{vacio}</>;
  return (
    <div className="uk-product-grid">
      {items.map((p) => {
        const wa = contactoDeOferta(p);
        const ancla = p.tipo === "novedad" ? "#novedades" : "#ofertas";
        return (
          <article className="uk-product" key={p.id}>
            {p.imagen_url && (
              <Link href={`/comercios/${p.comercio_slug}${ancla}`} className="uk-product-img">
                <img src={p.imagen_url} alt={p.titulo ?? ""} loading="lazy" decoding="async" />
                {p.descuento_pct != null && <span className="uk-product-off">{p.descuento_pct}% OFF</span>}
              </Link>
            )}
            <Link href={`/comercios/${p.comercio_slug}`} className="uk-product-com">
              {p.comercio_logo && <img src={p.comercio_logo} alt="" width={22} height={22} loading="lazy" />}
              <b>{p.comercio_nombre}</b>
              {p.comercio_verificado && <span title="Negocio verificado">✓</span>}
            </Link>
            <h4>{p.titulo ?? (p.tipo === "novedad" ? "Novedad" : "Oferta")}</h4>
            {p.descripcion && <p className="uk-product-desc">{p.descripcion}</p>}
            {p.precio != null && <div className="price">{precioFmt(p.precio, p.moneda)}</div>}
            {p.contacto_es_uruku && <span className="uk-marca-uruku">URUKU</span>}
            <div className="foot">
              <span>{p.vence_el ? `Hasta el ${vencimientoFmt(p.vence_el)}` : (p.zona_nombre ?? "")}</span>
              {wa && (
                <LeadLink className="wa-mini" comercioId={p.comercio_id} href={wa.href} tipo="whatsapp">
                  <WhatsApp style={{ width: 17, height: 17, color: "#fff" }} />
                </LeadLink>
              )}
            </div>
          </article>
        );
      })}
    </div>
  );
}

/** Las dos solapas. Están en las dos páginas para que cambiar de una a otra
 *  sea un toque, sin volver al menú. */
export function SolapasPublicaciones({ activa }: { activa: "ofertas" | "novedades" }) {
  return (
    <div className="uk-seg uk-pub-solapas">
      <Link href="/ofertas" className={activa === "ofertas" ? "active" : ""}>🏷️ Ofertas</Link>
      <Link href="/novedades" className={activa === "novedades" ? "active" : ""}>📣 Novedades</Link>
    </div>
  );
}
