// El carrusel «Lo que se consigue en {ciudad}» y los productos frecuentes del botón «Productos»
// (docs/home-ciudades.md §5): lo puro, sin red, para poder probarlo con `npm test`.
//
// Dos orígenes: la tabla `productos` (cuando la ciudad tiene 4 o más con foto) o, hoy, los textos que el
// recorrido y la IA cargaron en cada comercio (`prod_obs_human` y `prod_det_ia`).
import { productosDeFicha } from "./ficha-seo";

/** Una tarjeta del carrusel de productos. */
export type TarjetaProducto = {
  id: string;
  /** A la ficha del comercio, a la sección de lo que se encuentra ahí. */
  href: string;
  foto: string;
  titulo: string;
  /** El precio, sólo si está cargado. */
  precio: string | null;
  comercio: string;
};

/** Una fila de `productos` (con su comercio) tal como llega de la base. */
export type FilaProducto = {
  id: string;
  nombre: string;
  precio: number | string | null;
  moneda: string | null;
  foto_url: string | null;
  comercio: { slug: string; nombre: string } | null;
};

/** Con menos productos cargados que esto, el carrusel se arma con los textos de los comercios. */
export const MIN_PRODUCTOS_CARGADOS = 4;
export const MAX_TARJETAS_PRODUCTO = 12;

const hrefFicha = (slug: string): string => `/comercios/${encodeURIComponent(slug)}#ficha-encontrar`;

const SIMBOLO: Record<string, string> = { BOB: "Bs", USD: "USD", ARS: "ARS" };

/** «Bs 120», «Bs 12,50», «USD 15». `null` si no hay precio cargado (o es 0 o negativo). */
export function precioDeProducto(precio: number | string | null | undefined, moneda: string | null | undefined): string | null {
  const n = typeof precio === "string" ? Number(precio) : precio;
  if (n == null || !Number.isFinite(n) || n <= 0) return null;
  const monto = Number.isInteger(n) ? String(n) : n.toFixed(2).replace(".", ",");
  return `${SIMBOLO[moneda ?? "BOB"] ?? moneda ?? "Bs"} ${monto}`;
}

/** Las tarjetas desde la tabla `productos`: sólo las que tienen foto y comercio. Ya vienen de las más nuevas
 *  a las más viejas. Menos de `MIN_PRODUCTOS_CARGADOS` útiles → `[]` (se usa el respaldo). */
export function tarjetasDeProductos(filas: readonly FilaProducto[], max = MAX_TARJETAS_PRODUCTO): TarjetaProducto[] {
  const utiles = filas.filter((f) => f.foto_url && f.comercio?.slug && f.nombre.trim());
  if (utiles.length < MIN_PRODUCTOS_CARGADOS) return [];
  return utiles.slice(0, max).map((f) => ({
    id: f.id, href: hrefFicha((f.comercio as { slug: string }).slug), foto: f.foto_url as string,
    titulo: f.nombre.trim(), precio: precioDeProducto(f.precio, f.moneda), comercio: (f.comercio as { nombre: string }).nombre,
  }));
}

/** Lo que hace falta de un comercio para armar su tarjeta desde sus textos. */
export type LocalConProductos = {
  id: string;
  slug: string;
  nombre: string;
  portada_thumb_url: string | null;
  prod_obs_human: string | null;
  prod_det_ia: string | null;
};

/** Los dos o tres primeros productos del local, con el mismo corte que la ficha (`productosDeFicha`). Primero lo que
 *  leyó la IA de la foto (`prod_det_ia`) y después lo que escribió el comerciante (`prod_obs_human`): ese texto es
 *  editable sin moderación y llega al home de la ciudad, así que no manda en la tarjeta. */
export function productosDelLocal(l: Pick<LocalConProductos, "prod_obs_human" | "prod_det_ia">, max = 3): string[] {
  return productosDeFicha(l.prod_det_ia, l.prod_obs_human, max);
}

/** Mezcla (Fisher-Yates con `azar`); no toca el original. */
function mezclar<T>(lista: readonly T[], azar: () => number): T[] {
  const a = [...lista];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(azar() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** El respaldo (hoy, en todas las ciudades): un local con foto y productos detectados es una tarjeta con la
 *  foto del local, sus primeros productos y su nombre. Hasta 12, mezclados. */
export function tarjetasDeLocales(
  locales: readonly LocalConProductos[], azar: () => number = Math.random, max = MAX_TARJETAS_PRODUCTO,
): TarjetaProducto[] {
  const con = locales
    .filter((l) => l.portada_thumb_url && l.slug)
    .map((l) => ({ l, prods: productosDelLocal(l) }))
    .filter((x) => x.prods.length > 0);
  return mezclar(con, azar).slice(0, max).map(({ l, prods }) => ({
    id: l.id, href: hrefFicha(l.slug), foto: l.portada_thumb_url as string, titulo: prods.join(", "), precio: null, comercio: l.nombre,
  }));
}

/** Sin mayúsculas ni tildes: la clave para no contar dos veces «Zapatillas» y «zapatillas». */
function clave(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
}

/** Los productos más repetidos entre los comercios de la ciudad, en minúscula y sin repetir, hasta `max`.
 *  Cada comercio cuenta una vez por producto. Empates: orden alfabético (para que no baile entre visitas).
 *  Seguridad: `prod_obs_human` lo edita el comerciante sin moderación, y estos términos llegan a los chips del home y
 *  a la búsqueda. Sólo se conserva un término si lo detectó la IA (`prod_det_ia`) o si lo declaran al menos DOS
 *  comercios distintos: un texto puesto por uno solo no llega a la portada. */
export function productosFrecuentes(locales: readonly Pick<LocalConProductos, "prod_obs_human" | "prod_det_ia">[], max = 12): string[] {
  const cuenta = new Map<string, { texto: string; n: number; deIa: boolean }>();
  for (const l of locales) {
    const vistosDelLocal = new Set<string>();
    // La IA primero: si un término está en las dos listas del local, cuenta como de la IA.
    const terminos = [
      ...productosDeFicha(l.prod_det_ia, null, 20).map((t) => ({ t, ia: true })),
      ...productosDeFicha(l.prod_obs_human, null, 20).map((t) => ({ t, ia: false })),
    ];
    for (const { t, ia } of terminos) {
      // Un producto es una o pocas palabras: una frase larga es una descripción, no algo para buscar.
      if (t.split(/\s+/).length > 4) continue;
      const k = clave(t);
      const previo = cuenta.get(k);
      if (vistosDelLocal.has(k)) {
        if (previo && ia) previo.deIa = true;
        continue;
      }
      vistosDelLocal.add(k);
      if (previo) { previo.n += 1; previo.deIa = previo.deIa || ia; }
      else cuenta.set(k, { texto: t.toLowerCase(), n: 1, deIa: ia });
    }
  }
  return [...cuenta.values()]
    .filter((x) => x.deIa || x.n >= 2)
    .sort((a, b) => b.n - a.n || a.texto.localeCompare(b.texto, "es"))
    .slice(0, max)
    .map((x) => x.texto);
}
