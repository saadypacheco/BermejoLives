// Las líneas de fotos de /planes salen de `fotos_max` (no de las viñetas), para que
// lo que se cambie en Admin › Planes se vea en la página sin tocar código.

/** Las fotos del local que entran en cualquier plan pago (backend: fotos_galeria.FOTOS_DEL_LOCAL). */
export const FOTOS_DEL_LOCAL = 10;

/** Las líneas de fotos de la galería. `fotos_max` es el total; la portada va aparte.
 *  Con más de 10: las que puede subir por día y las que se ven siempre en su página. */
export function lineaFotos(fotosMax: number | null | undefined): string[] {
  if (fotosMax == null) return [];
  const n = Math.max(0, Math.floor(Number(fotosMax) || 0));
  if (n === 0) return ["Sólo foto de portada"];
  if (n <= FOTOS_DEL_LOCAL) return [`${n} ${n === 1 ? "foto" : "fotos"} de tu local`];
  const cambian = n - FOTOS_DEL_LOCAL;
  return [
    `Publicás hasta ${cambian} fotos por día`,
    `En tu página se ven siempre ${n} fotos: las ${FOTOS_DEL_LOCAL} de tu local + ${cambian} que cambiás cuando quieras`,
  ];
}
