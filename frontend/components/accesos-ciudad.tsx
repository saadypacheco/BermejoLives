import Link from "next/link";
import { Ic, type NombreIcono } from "@/components/ic";

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

type Acceso = { i: NombreIcono; t: string; href: string };

const SERVICIOS: Acceso[] = [
  { i: "banos", t: "Baños", href: "/buscar?rubro=banos&vista=mapa" },
  { i: "farmacia", t: "Farmacias", href: "/buscar?rubro=farmacia&vista=mapa" },
  { i: "cajeros", t: "Cajeros", href: "/buscar?rubro=cajeros&vista=mapa" },
  { i: "estacionamiento", t: "Estacionamiento", href: "/buscar?rubro=estacionamiento&vista=mapa" },
  { i: "cambio", t: "Casas de cambio", href: "/cambio" },
  { i: "taxis", t: "Taxis", href: "/buscar?rubro=taxis&vista=mapa" },
  { i: "wifi", t: "WiFi", href: "/buscar?rubro=wifi&vista=mapa" },
  { i: "policia", t: "Policía", href: "/buscar?rubro=emergencias&vista=mapa" },
  { i: "transporte", t: "Transporte", href: "/guia#transporte" },
  { i: "frontera", t: "Frontera", href: "/guia#frontera" },
];

/** Sin guía (ciudad que no es de frontera): se van los dos accesos a la guía
 *  del paso, y el cambio deja de ser una página para ser un rubro del mapa. */
const SIN_GUIA: Acceso[] = SERVICIOS
  .filter((c) => !c.href.startsWith("/guia"))
  .map((c) => (c.href === "/cambio" ? { ...c, t: "Cambio", href: "/buscar?rubro=cambio&vista=mapa" } : c));

export function AccesosCiudad({ conGuia, ofertas }: {
  conGuia: boolean;
  /** Suma «Ofertas» como primer acceso. Se usa en los RESULTADOS, donde si no
   *  no hay ninguna puerta a las ofertas: el home tiene el botón grande del
   *  hero y la pantalla de resultados no tenía nada. Si se pasa un rubro, va
   *  a las ofertas de ESE rubro, que es lo que la persona está mirando. */
  ofertas?: boolean | string;
}) {
  const lista = conGuia ? SERVICIOS : SIN_GUIA;
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
