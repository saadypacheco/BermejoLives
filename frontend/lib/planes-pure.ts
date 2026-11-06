// Las líneas de /planes que salen de los números del plan (no de las viñetas), para que
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

/** La línea de publicaciones. El gratis no la muestra (decisión del dueño, 6/11/2026):
 *  la cuota de sus primeros meses sigue rigiendo, pero no se anuncia. */
export function lineaCuota(p: {
  publicaciones_mes: number | null; esGratis: boolean;
}): string | null {
  if (p.esGratis) return null;
  if (p.publicaciones_mes == null) return "Publicaciones sin límite";
  return `Hasta ${p.publicaciones_mes} publicaciones por mes`;
}
