import { Ic } from "@/components/ic";
import { EnlaceFiltrado } from "./enlace-filtrado";
import type { TileQueHacer } from "@/lib/home-ciudad-pure";

/**
 * «Qué podés hacer en {ciudad}» (docs/home-ciudades.md §6): un bloque oscuro con tarjetas de dos columnas
 * que llevan al mapa. Cada tarjeta sale sólo si la ciudad tiene datos de ese rubro, y su foto es la de un
 * comercio de ese rubro (nunca la de otro). Sin tarjetas, el bloque no aparece.
 */
export function QueHacer({ tiles, ciudad }: { tiles: TileQueHacer[]; ciudad: string }) {
  if (tiles.length === 0) return null;
  return (
    <section className="uk-container uk-home-sec uk-hc-sec" aria-labelledby="home-que-hacer">
      <div className="uk-hc-hacer">
        <div className="uk-hc-hacer-cab">
          <h2 id="home-que-hacer">Qué podés hacer en <em>{ciudad}</em></h2>
          <p>Todo te lleva al mapa</p>
        </div>
        <div className="uk-hc-tiles">
          {tiles.map((t) => (
            <EnlaceFiltrado key={t.id} href={t.href} className={`uk-hc-tile${t.foto ? " con-foto" : ""}`}>
              {t.foto && <img src={t.foto} alt="" loading="lazy" decoding="async" />}
              <span className="uk-hc-tile-ic"><Ic n={t.icono} s={22} /></span>
              <span className="uk-hc-tile-txt">
                <b>{t.titulo}</b>
                <small><Ic n="mapa" s={13} /> {t.detalle}</small>
              </span>
            </EnlaceFiltrado>
          ))}
        </div>
      </div>
    </section>
  );
}
