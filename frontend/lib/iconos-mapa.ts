/**
 * Los íconos como texto HTML, para los pines del mapa.
 *
 * Leaflet no recibe componentes: un pin es un string de HTML (`divIcon`). Por
 * eso ahí no se puede poner `<Ic n="ropa" />`, y por eso el mapa fue lo último
 * del sitio que siguió dibujando emojis.
 *
 * Los dibujos son los mismos de `components/ic.tsx` —salen de la misma tabla
 * generada—, así que el pin de ferretería y el ícono de ferretería de la ficha
 * son el mismo dibujo. Lo único distinto es el peso: ACÁ VA RELLENO, NO
 * DUOTONO. Es la excepción al duotono del manual y es por tamaño: un pin mide
 * entre 10 y 20 px, y a 10 px el duotono —trazo fino más relleno al 20%— se
 * deshace en una manchita. El relleno macizo se lee como silueta, que es
 * exactamente lo que hacía el emoji y lo que un mapa necesita.
 */
import { RELLENO, POR_CLAVE } from "@/lib/iconos-dibujos";

/** El `<svg>` de una clave, al 100% de la caja que lo contenga: el tamaño y el
 *  color los pone el CSS del pin (`.ukpin-emo` y compañía). */
function svg(clave: string): string {
  const i = POR_CLAVE[clave] ?? POR_CLAVE.otros;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" fill="currentColor" viewBox="0 0 256 256">${RELLENO[i]}</svg>`;
}

/** El dibujo de un rubro, con respaldo genérico: hay slugs en la base que el
 *  catálogo todavía no conoce, y antes que un pin vacío va un paquete. */
export function rubroSvg(slug: string | null | undefined): string {
  return svg(slug ?? "otros");
}

/** Los dos que no son rubros: la etiqueta de una galería y el punto suelto. */
export const SVG_COMERCIOS = svg("comercios");
export const SVG_UBICACION = svg("ubicacion");
