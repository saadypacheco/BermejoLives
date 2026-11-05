/**
 * Redirección segura tras el ingreso: sólo se vuelve a una ruta DEL MISMO sitio.
 *
 * El navegador trata `//dominio` y `/\dominio` como una dirección de otro sitio, y
 * descarta tabulaciones y saltos de línea al interpretar una URL, así que `/\t/dominio`
 * también termina afuera. Se acepta únicamente `/ruta` sin esas formas.
 * Devuelve la ruta o `null` si no es segura.
 */
export function rutaInternaSegura(next: string | null | undefined): string | null {
  if (!next || next[0] !== "/") return null;
  if (next[1] === "/" || next[1] === "\\") return null;
  // Barras invertidas y caracteres de control en cualquier lugar: no hay ruta legítima con ellos.
  if (/[\\\u0000-\u001f\u007f]/.test(next)) return null;
  return next;
}
