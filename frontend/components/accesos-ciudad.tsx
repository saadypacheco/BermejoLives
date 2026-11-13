import Link from "next/link";
import { Ic } from "@/components/ic";
import { listaAccesos } from "@/lib/accesos-ciudad";

/**
 * La fila de accesos que va debajo del buscador: baños, farmacias, cajeros,
 * cambio, taxis, wifi, policía.
 *
 * Vivía suelta en el home. Está acá porque la MISMA fila va en los
 * resultados: el que buscó «zapatillas», encontró y ahora necesita un baño o
 * un cajero tenía que volver al home para llegar a ellos, que es pedirle que
 * deshaga lo que acaba de hacer. En una pantalla de resultados esta fila es
 * más útil que en el home, no menos.
 *
 * Son todos RUBROS —baños, cajeros, estacionamientos y wifi son rubros no
 * comerciales (0083, 0113)—, así que cada acceso trae exactamente lo cargado
 * bajo ese rubro y no lo que el texto libre encuentre («estacionamiento»
 * devolvía estaciones de servicio).
 */

export function AccesosCiudad({ conGuia, ofertas, paraVisitar = false }: {
  conGuia: boolean;
  /** Sale sólo si la ciudad tiene lugares para visitar cargados: ver `hayParaVisitar` (lib/para-visitar.ts). */
  paraVisitar?: boolean;
  /** Suma «Ofertas» como primer acceso. Se usa en los RESULTADOS, donde si no
   *  no hay ninguna puerta a las ofertas: el home tiene el botón grande del
   *  hero y la pantalla de resultados no tenía nada. Si se pasa un rubro, va
   *  a las ofertas de ESE rubro, que es lo que la persona está mirando. */
  ofertas?: boolean | string;
}) {
  const lista = listaAccesos(conGuia, paraVisitar);
  const href = typeof ofertas === "string" && ofertas
    ? `/ofertas?rubro=${encodeURIComponent(ofertas)}`
    : "/ofertas";
  return (
    <nav className="uk-container uk-home-chips" aria-label="Servicios de la ciudad">
      {ofertas && (
        <Link href={href} className="uk-chip-ofertas"><Ic n="ofertas" s={18} />Ofertas</Link>
      )}
      {lista.map((c) => <Link key={c.t} href={c.href}><Ic n={c.i} s={18} />{c.t}</Link>)}
    </nav>
  );
}
