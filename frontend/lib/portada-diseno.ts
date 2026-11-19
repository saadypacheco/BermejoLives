import type { GaleriaFoto } from "./data-pure";

/**
 * Qué foto va arriba en la ficha pública y qué fotos quedan en «Fotos del local»
 * (docs/portada-diseno.md, «En la ficha pública»).
 *
 * Con `portada_diseno_url`: esa imagen es la principal —ya viene encuadrada, así
 * que sin `portada_pos`— y la foto original pasa a ser la PRIMERA de la galería,
 * para que no se pierda. Si la original ya estaba en la galería se la mueve al
 * frente (no se repite). Sin diseño todo queda como antes.
 */
export type FotosDeFicha = {
  /** La foto grande de arriba; `null` = sin portada (arriba va la primera de `fotos`). */
  portada: string | null;
  /** El encuadre vertical sólo aplica a la foto original; el diseño ya viene recortado. */
  posicion: number | null;
  /** Las fotos de «Fotos del local». */
  fotos: GaleriaFoto[];
};

const ID_PORTADA_ORIGINAL = "portada-original";

function texto(v: string | null | undefined): string | null {
  const t = (v ?? "").trim();
  return t ? t : null;
}

export function fotosDeFicha(
  c: { portada_url?: string | null; portada_thumb_url?: string | null; portada_pos?: number | null; portada_diseno_url?: string | null },
  galeria: GaleriaFoto[],
): FotosDeFicha {
  const original = texto(c.portada_url);
  const diseno = texto(c.portada_diseno_url);
  if (!diseno) return { portada: original, posicion: c.portada_pos ?? null, fotos: galeria };
  if (!original) return { portada: diseno, posicion: null, fotos: galeria };

  const existente = galeria.find((f) => f.url === original);
  const primera: GaleriaFoto = existente
    ?? { id: ID_PORTADA_ORIGINAL, url: original, thumb_url: texto(c.portada_thumb_url) };
  return {
    portada: diseno,
    posicion: null,
    fotos: [primera, ...galeria.filter((f) => f !== existente)],
  };
}
