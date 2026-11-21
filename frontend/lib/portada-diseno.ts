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

/**
 * La versión con estilo URUKU de una foto de galería (docs/fotos-estilo-uruku.md §3): si ya se aprobó
 * (`diseno_url`), la grilla muestra su miniatura y la ampliada la grande. Sin miniatura de diseño la grilla
 * usa la grande (nunca la miniatura de la foto real: sería otra imagen). Lo demás del sitio sigue con `url`.
 */
function conDiseno(f: GaleriaFoto): GaleriaFoto {
  const d = texto(f.diseno_url);
  if (!d) return f;
  return { ...f, url: d, thumb_url: texto(f.diseno_thumb_url) };
}

export function fotosDeFicha(
  c: { portada_url?: string | null; portada_thumb_url?: string | null; portada_pos?: number | null; portada_diseno_url?: string | null },
  galeria: GaleriaFoto[],
): FotosDeFicha {
  const original = texto(c.portada_url);
  const diseno = texto(c.portada_diseno_url);
  // Se busca la portada original por su `url` REAL, antes de cambiar `url` por la del diseño.
  const existente = original ? galeria.find((f) => f.url === original) : undefined;
  const hayDisenoEnGaleria = galeria.some((f) => texto(f.diseno_url));
  const lista = hayDisenoEnGaleria ? galeria.map(conDiseno) : galeria;   // sin diseños: la misma lista, sin tocarla

  if (!diseno) return { portada: original, posicion: c.portada_pos ?? null, fotos: lista };
  if (!original) return { portada: diseno, posicion: null, fotos: lista };

  const primera: GaleriaFoto = existente
    ? lista[galeria.indexOf(existente)]
    : { id: ID_PORTADA_ORIGINAL, url: original, thumb_url: texto(c.portada_thumb_url) };
  return {
    portada: diseno,
    posicion: null,
    fotos: [primera, ...lista.filter((_, i) => galeria[i] !== existente)],
  };
}
