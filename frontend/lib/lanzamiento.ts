// El lanzamiento de las ofertas: lunes 28 de septiembre de 2026.
//
// Hasta ese día, la pantalla de Ofertas no dice «no hay nada»: dice cuándo
// empieza. Es la diferencia entre un sitio vacío y uno que está por estrenar
// algo — y le da al comerciante una fecha concreta para tener su oferta lista.
//
// Pasada la fecha, el aviso desaparece solo y vuelve el texto de siempre. No
// hay que acordarse de sacarlo: un cartel de «próximamente» que queda puesto
// tres semanas después es peor que no haberlo puesto.
export const LANZAMIENTO_OFERTAS = new Date("2026-09-28T00:00:00-04:00");

export function faltaParaLanzamiento(ahora: Date = new Date()): boolean {
  return ahora < LANZAMIENTO_OFERTAS;
}

/** «el lunes 28 de septiembre», para escribirlo en una frase. */
export const FECHA_LANZAMIENTO = "el lunes 28 de septiembre";
