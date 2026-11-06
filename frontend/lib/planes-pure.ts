// Las líneas de /planes que salen de los números del plan (no de las viñetas), para que
// lo que se cambie en Admin › Planes se vea en la página sin tocar código.

/** Las fotos del local que entran en cualquier plan pago (backend: fotos_galeria.FOTOS_DEL_LOCAL). */
export const FOTOS_DEL_LOCAL = 10;

/** La línea de fotos de la galería. `fotos_max` es el total; la portada va aparte. */
export function lineaFotos(fotosMax: number | null | undefined): string | null {
  if (fotosMax == null) return null;
  const n = Math.max(0, Math.floor(Number(fotosMax) || 0));
  if (n === 0) return "Sólo foto de portada";
  if (n <= FOTOS_DEL_LOCAL) return `${n} ${n === 1 ? "foto" : "fotos"} de tu local`;
  return `${FOTOS_DEL_LOCAL} fotos de tu local + ${n - FOTOS_DEL_LOCAL} fotos que podés cambiar todos los días`;
}

/** La línea de publicaciones. El gratis publica sólo sus primeros meses. */
export function lineaCuota(p: {
  publicaciones_mes: number | null; publica_meses: number | null; esGratis: boolean;
}): string {
  if (p.publicaciones_mes == null) return "Publicaciones sin límite";
  const base = `Hasta ${p.publicaciones_mes} publicaciones por mes`;
  if (p.esGratis && p.publica_meses) {
    return `${base} durante los primeros ${p.publica_meses} ${p.publica_meses === 1 ? "mes" : "meses"}`;
  }
  return base;
}
