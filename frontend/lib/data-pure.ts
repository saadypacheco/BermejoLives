// Tipos y funciones PURAS de lib/data.ts: sin supabase, sin red, sin `server-only`.
// Los componentes cliente importan de acá (o de lib/data-client.ts para leer
// datos); lib/data.ts, que habla con la base, sólo corre en el servidor.
// lib/data.ts re-exporta todo esto, así que el código de servidor no cambia.

/**
 * Qué filtros tienen datos detrás. Un filtro que no filtra es peor que uno que
 * no está: la persona lo toca, no cambia nada, y deja de confiar en los demás.
 *
 * Medido el 27/8 sobre 680 comercios: **ninguno tenía horario cargado**, así
 * que "Abierto ahora" —construido, visible y en la lista de hechos— no podía
 * dar un resultado correcto nunca. No fallaba: no hacía nada, que es la forma
 * de romperse más difícil de ver.
 *
 * Son consultas de conteo puro (`head: true`), sin traer filas. Van una vez al
 * cargar la pantalla y cuestan prácticamente nada.
 */
export type FiltrosDisponibles = { horario: boolean; zona: boolean; ofertas: boolean };

/** Cuánto hay de cada cosa que el home promete.
 *
 * POR QUÉ EXISTE
 * ==============
 * El home decía "Comercios verificados", "Locales destacados" y "Promos
 * exclusivas" desde el primer día. Con cero verificados y cero destacados, eso
 * no es una promesa: es una lista de lo que falta, firmada por nosotros. Y en
 * la etapa de captación un comerciante que entra, lee "promos exclusivas" y no
 * ve ninguna, aprende que la plataforma está vacía — que es exactamente lo que
 * no queremos que aprenda.
 *
 * Así que cada bloque aparece cuando hay volumen detrás. Los umbrales están más
 * abajo, en un solo lugar, y son altos a propósito: mostrar tres ofertas es
 * peor que no mostrar la sección.
 */
export type Volumenes = {
  ofertas: number;
  verificados: number;
  destacados: number;
  promos: number;
  lugares: number;
};

/** Desde cuánto vale la pena prometer cada cosa. Un solo lugar para cambiarlos.
 *
 *  No son redondeos: son el punto donde la sección deja de contar lo que falta
 *  y empieza a contar lo que hay. */
export const UMBRALES: Volumenes = {
  ofertas: 100,
  verificados: 300,
  destacados: 50,
  promos: 50,
  lugares: 8,
};

/** Secciones apagadas a mano mientras el catálogo crece.
 *
 *  No son umbrales: son una decisión. Un umbral dice "cuando haya tanto, esto
 *  vale la pena"; esto dice "hoy no queremos mostrarlo, aunque el número dé".
 *  Mezclarlas escondería la decisión adentro de un número y nadie sabría, en
 *  dos meses, si la sección no aparece porque falta dato o porque se apagó.
 *
 *  Se vuelve a encender poniendo `false`. */
export const APAGADAS = {
  /** Con pocos mercados cargados la sección cuenta lo que falta. */
  mercados: true,
  /** "Lo mejor de hoy": con una oferta activa, el panel dice "1" y eso mide
   *  el vacío en vez de mostrar la ciudad. */
  loMejorDeHoy: true,
  /** Los filtros del buscador: los chips de refinamiento y los desplegables de
   *  Categoría, Zona, Precio y Tipo.
   *
   *  Un filtro sirve cuando hay demasiado y hace falta cortar. Con lo que hay
   *  hoy, afinar "ropa" a "ropa femenina 25" no ayuda a nadie a decidir: sólo
   *  muestra qué poco hay de cada cosa. Mientras tanto la pantalla es el
   *  buscador, el total y la lista — y ese total es el termómetro. */
  filtrosBuscador: true,
};

// Contenido de la home Inicio (migración 0032): cotizaciones, clima, videos promo.
export type Cotizacion = { clave: string; etiqueta: string; detalle: string | null; valor: number | null; unidad: string | null; actualizado_en?: string | null };
export type Clima = { temp_c: number | null; descripcion: string | null; icono: string | null };
export type VideoPromo = { id: string; titulo: string | null; url: string };

export type Red = { clave: string; etiqueta: string; url: string | null };

export type NovedadFoto = { url: string; thumb_url: string | null };
export type NovedadUruku = {
  id: string;
  ciudad_id: string | null;       // null = «todas las ciudades»
  titulo: string;
  texto: string | null;
  fecha: string;                  // YYYY-MM-DD
  portada_url: string | null;
  portada_thumb_url: string | null;
  fotos: NovedadFoto[];
  video_url: string | null;
  video_poster_url: string | null;
  enlace_url: string | null;
  destacada: boolean;
  activo: boolean;
};

/** «12 oct 2026» a partir de un `YYYY-MM-DD`, sin pasar por la zona horaria
 *  (un `new Date("2026-10-12")` en La Paz caía en el 11). */
export function fechaNovedad(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return "";
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${Number(m[3])} ${meses[Number(m[2]) - 1] ?? ""} ${m[1]}`;
}

export type GaleriaFoto = { id: string; url: string; thumb_url: string | null };
export type GaleriaVideo = { id: string; url: string; duracion_seg: number | null };

export type FronteraEstado = {
  // "no_aplica": esta frontera no tiene chalanas o no tiene río (0124).
  puente: "normal" | "demoras" | "cerrado";
  chalanas: "operando" | "limitadas" | "suspendidas" | "no_aplica";
  rio: "normal" | "crecido" | "no_aplica";
  chalanas_horario?: string | null;
  nota: string | null; actualizado_en: string | null;
};
