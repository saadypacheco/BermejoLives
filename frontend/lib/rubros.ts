/**
 * Los nombres de rubro, sin el emoji que traen de la base.
 *
 * En la tabla `rubros` el nombre viene con un emoji adelante: «👟 Calzado»,
 * «🔧 Ferretería y construcción». Es de la primera versión del catálogo, y
 * cuando los íconos pasaron a Phosphor ese emoji quedó como lo único del sitio
 * que seguía dibujando el sistema operativo — y encima al lado de un ícono de
 * verdad, así que se veían dos dibujos del mismo rubro, uno en cada estilo.
 *
 * Se limpia al MOSTRAR y no en la base a propósito: el dato crudo lo escriben
 * el panel y las migraciones, y si mañana alguien carga un rubro nuevo con
 * emoji el sitio sigue mostrándolo bien. La misma función estaba copiada en
 * `catnav.tsx` y como un `replace(/^\S+\s/, "")` suelto en cuatro pantallas —
 * que además cortaba la primera palabra de los rubros que NO tenían emoji.
 */

/** «👟 Calzado» → «Calzado». Un nombre sin emoji vuelve igual. */
export function sinEmoji(nombre: string | null | undefined): string {
  const n = (nombre ?? "").trim();
  if (!n) return "";
  // Saca lo que haya adelante que no sea letra ni número: el emoji, el espacio
  // y la variante de color si la trae. Si al sacarlo no queda nada —un rubro
  // que se llame sólo con un símbolo— se devuelve el original antes que vacío.
  return n.replace(/^[^\p{L}\p{N}]+/u, "").trim() || n;
}
