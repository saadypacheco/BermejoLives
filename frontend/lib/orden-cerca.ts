// El orden de «Cerca de mí» (spec docs/cerca-abiertos-estrella.md, decisiones 1-3).
//
// En franjas, de más a menos importante:
//   1. Abiertos antes que cerrados. «Abierto» incluye al que NO tiene horario
//      cargado (o uno que no se pudo interpretar): hasta que se cargue, se
//      supone abierto para ordenar. El sello «Abierto ahora» ese no lo muestra
//      (lo decide HorarioBadge), porque mandar a alguien a una puerta cerrada
//      le cuesta la confianza a URUKU.
//   2. Dentro de cada grupo, franjas de distancia: hasta 300 m, hasta 1 km y
//      más lejos. Sin ubicación, al final de todo el grupo.
//   3. Dentro de cada franja, primero los de estrella (el plan más caro arriba)
//      y después por distancia, el más cercano primero.
import { abiertoAhora, ahoraEnBolivia } from "@/lib/horario";

export const FRANJA_CERCA_M = 300;
export const FRANJA_MEDIA_M = 1000;

type ParaOrdenar = { horario: string | null; estrella?: boolean; plan_orden?: number };

/** 0 = hasta 300 m, 1 = hasta 1 km, 2 = más lejos, 3 = sin ubicación. */
function franja(d: number | null): number {
  if (d == null) return 3;
  if (d <= FRANJA_CERCA_M) return 0;
  if (d <= FRANJA_MEDIA_M) return 1;
  return 2;
}

/** Devuelve una lista nueva ordenada. `distancia` va por parámetro para que el
 *  buscador use la suya (la que ya tiene la ubicación de la persona). */
export function ordenarCerca<T extends ParaOrdenar>(
  lista: readonly T[],
  distancia: (r: T) => number | null,
  ahora: Date = ahoraEnBolivia(),
): T[] {
  // Se calcula una vez por comercio, no dentro del comparador: el parser de
  // horarios no es gratis y son hasta cuatro mil filas.
  const filas = lista.map((r) => {
    const d = distancia(r);
    return {
      r, d,
      cerrado: abiertoAhora(r.horario, ahora).estado === "cerrado" ? 1 : 0,
      f: franja(d),
      estrella: r.estrella === true,
      orden: r.estrella === true ? (r.plan_orden ?? 0) : 0,
    };
  });
  filas.sort((a, b) =>
    a.cerrado - b.cerrado
    || a.f - b.f
    || Number(b.estrella) - Number(a.estrella)
    || b.orden - a.orden
    || (a.d ?? 1e12) - (b.d ?? 1e12));
  return filas.map((x) => x.r);
}
