/**
 * La forma del recuadro de la foto grande de la ficha (components/ficha-galeria.tsx).
 *
 * Una horizontal se ve entera (hasta 2:1, más apaisada se recorta a los costados).
 * Una vertical o cuadrada va en 4:3, el MISMO recorte que la tarjeta de los
 * resultados, con el encuadre elegido en el panel. Antes iba en un cuadrado, que
 * en una foto alta de celular dejaba ver mucho más abajo que la tarjeta: el
 * cartel quedaba arriba y el resto era piso (La Cueva, 20/11).
 */
export const PROP_MIN = 4 / 3;
export const PROP_MAX = 2;

export function proporcionFicha(ancho: number, alto: number): number {
  if (!(ancho > 0) || !(alto > 0)) return PROP_MIN;
  return Math.min(PROP_MAX, Math.max(PROP_MIN, ancho / alto));
}
