import Link from "next/link";
import { Ic, IcRubro } from "@/components/ic";
import { TarjetaDax } from "@/components/tarjeta-dax";
import { buscarComercios, getFotosDeComercios } from "@/lib/data";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";
import { sinEmoji } from "@/lib/rubros";
import { etiquetaHasta, listaNombres, nombreCorto, type TurnoFarmacia } from "@/lib/turnos-farmacia";
import type { ResultadoBusqueda } from "@/lib/types";

/**
 * Lo que pasa en el carrusel de Novedades además de las novedades: servicios
 * (farmacia de turno, baños cerca, el servicio de URUKU) y PUBLICIDAD de los
 * comercios con plan pago al día o de cortesía (la estrella): su portada y
 * hasta dos fotos de su galería. Lo usan la portada y /novedades.
 *
 * Los destacados salen en orden al azar en cada visita para que roten parejo.
 * Nunca se dice cuántos son ni se muestran precios de planes.
 */
export type Promo = {
  destacados: ResultadoBusqueda[];
  productos: { comercio: ResultadoBusqueda; foto: string }[];
};

export async function getPromo(ciudadSlug: string | undefined): Promise<Promo> {
  // Sin texto, la búsqueda trae primero a los que tienen plan (estrella).
  const comercios = await buscarComercios({ ciudad: ciudadSlug }, 120, 0);
  const pagos = comercios
    .filter((c) => c.estrella === true)
    .map((c) => ({ c, k: Math.random() }))
    .sort((a, b) => a.k - b.k)
    .slice(0, 12)
    .map(({ c }) => c);
  const fotos = await getFotosDeComercios(pagos.map((c) => c.id), 2);
  const porId = new Map(pagos.map((c) => [c.id, c]));
  return {
    destacados: pagos.filter((c) => c.portada_thumb_url || c.portada_url),
    productos: fotos
      .map((f) => ({ comercio: porId.get(f.comercio_id)!, foto: f.thumb_url || f.url }))
      .filter((p) => p.comercio && p.foto),
  };
}

/** Devuelve la LISTA de tarjetas (no un fragmento): el carrusel arma un lugar
 *  por cada hijo, y un componente contaría como uno solo. Se usa como
 *  `{tarjetasPromo({ ... })}` adentro de `<CarruselNovedades>`. */
export function tarjetasPromo({ promo, turnos, conGuia }: {
  promo: Promo;
  turnos: TurnoFarmacia[] | null;
  /** Bermejo: baños y el servicio de URUKU (son de acá). */
  conGuia: boolean;
}): React.ReactElement[] {
  const deTurno = (turnos ?? []).filter((t) => t.comercios?.nombre);
  // Portada de un local y, al lado, sus productos: se intercalan para que la
  // publicidad no sean doce frentes de local seguidos.
  const productosDe = new Map<string, { comercio: ResultadoBusqueda; foto: string }[]>();
  for (const p of promo.productos) productosDe.set(p.comercio.id, [...(productosDe.get(p.comercio.id) ?? []), p]);
  const ids = new Set([...promo.destacados.map((c) => c.id), ...promo.productos.map((p) => p.comercio.id)]);
  const orden = [...ids];

  const lista: React.ReactElement[] = [];
  if (deTurno.length > 0) lista.push(
        <Link key="s-turno" href="/farmacias-de-turno" className="uk-offer sin-foto uk-offer-servicio">
          <span className="uk-offer-tag">De turno hoy</span>
          <span className="uk-offer-emoji"><Ic n="turno_farmacia" s={64} peso="fill" /></span>
          <div className="uk-offer-body">
            <h3>{listaNombres(deTurno.map((t) => nombreCorto(t.comercios!.nombre)))}</h3>
            <small>Farmacia de turno · {etiquetaHasta(deTurno[0].fin)}</small>
          </div>
        </Link>,
  );
  if (conGuia) lista.push(
        <Link key="s-banos" href="/buscar?rubro=banos&cerca=1" className="uk-offer sin-foto uk-offer-servicio">
          <span className="uk-offer-tag">Servicio</span>
          <span className="uk-offer-emoji"><IcRubro slug="banos" s={64} peso="fill" /></span>
          <div className="uk-offer-body">
            <h3>Baños cerca de vos</h3>
            <small>Los más cercanos, en el mapa</small>
          </div>
        </Link>,
  );
  // SERVICIO DE URUKU (la empresa, no un comercio): retira o hace las compras y
  // las guarda en la guardería URUKU, con garantía de custodia. Sin precios.
  if (conGuia) lista.push(
        <a key="s-uruku" href={waUruku("Hola URUKU, quiero que retiren o hagan mis compras en Bermejo y me las guarden en la guardería")}
           target="_blank" rel="noopener" className="uk-offer sin-foto uk-offer-servicio uk-offer-uruku">
          <span className="uk-offer-tag">Servicio URUKU</span>
          <span className="uk-offer-emoji"><Ic n="encargo" s={64} peso="fill" /></span>
          <div className="uk-offer-body">
            <h3>Retiramos o hacemos tus compras</h3>
            <small>Te las guardamos en la guardería URUKU · custodia garantizada · WhatsApp {WA_URUKU_TEXTO}</small>
          </div>
        </a>,
  );
  // CÓMO HACER: encontrar algo (abre a Dax) y, para el que tiene un local,
  // cómo aparecer acá. Van antes de la publicidad.
  lista.push(<TarjetaDax key="s-dax" />);
  lista.push(
        <Link key="s-tu-comercio" href="/autoregistro" className="uk-offer sin-foto uk-offer-servicio">
          <span className="uk-offer-tag">¿Tenés un comercio?</span>
          <span className="uk-offer-emoji"><Ic n="comercios" s={64} peso="fill" /></span>
          <div className="uk-offer-body">
            <h3>Aparecé en URUKU</h3>
            <small>Tu ficha con fotos, WhatsApp y ubicación · los destacados salen acá</small>
          </div>
        </Link>,
  );
  lista.push(...orden.flatMap((id) => {
        const c = promo.destacados.find((d) => d.id === id) ?? productosDe.get(id)?.[0]?.comercio;
        if (!c) return [];
        const tarjetas: React.ReactElement[] = [];
        const portada = promo.destacados.some((d) => d.id === id) ? (c.portada_thumb_url || c.portada_url) : null;
        if (portada) {
          tarjetas.push(
            <Link key={`d-${c.id}`} href={`/comercios/${c.slug}`} className="uk-offer uk-offer-destacado"
                  style={{ backgroundImage: `url(${JSON.stringify(portada)})`,
                           ...(c.portada_pos != null ? { backgroundPosition: `center ${c.portada_pos}%` } : {}) }}>
              <span className="uk-offer-tag">Destacado</span>
              <div className="uk-offer-body">
                <h3>{c.nombre}</h3>
                {c.rubro_nombre && <small>{sinEmoji(c.rubro_nombre)}</small>}
              </div>
            </Link>,
          );
        }
        for (const [n, p] of (productosDe.get(id) ?? []).entries()) {
          tarjetas.push(
            <Link key={`p-${c.id}-${n}`} href={`/comercios/${c.slug}#fotos`} className="uk-offer uk-offer-destacado"
                  style={{ backgroundImage: `url(${JSON.stringify(p.foto)})` }}>
              <span className="uk-offer-tag">Destacado</span>
              <div className="uk-offer-body">
                <h3>{c.nombre}</h3>
                <small>Mirá lo que tiene · fotos del local</small>
              </div>
            </Link>,
          );
        }
        return tarjetas;
      }));
  return lista;
}
