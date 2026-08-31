/** Qué vende el local, ordenado por lo que la persona buscó.
 *
 * La tarjeta mostraba un rubro amplio ("Calzado") y el comprador tenía que
 * confiar en que adentro estaba lo que buscó. Los productos sí lo dicen, pero
 * hay comercios con treinta términos cargados: mostrados en el orden en que se
 * cargaron, la palabra buscada queda fuera del corte la mitad de las veces y el
 * resultado parece equivocado estando bien.
 */

export type Termino = { texto: string; coincide: boolean };

/** Sin tildes y en minúsculas, que es como compara Postgres en el buscador. */
function normalizar(s: string): string {
  return s.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
}

/** Prefijo y no igualdad: se busca "zapatilla" y el comercio tiene cargado
 *  "zapatillas". Es el mismo desajuste que ya rompió el conteo de los chips. */
function coincideCon(termino: string, palabras: string[]): boolean {
  if (palabras.length === 0) return false;
  const suyas = normalizar(termino).split(/[^a-z0-9]+/).filter(Boolean);
  return palabras.some((p) => suyas.some((s) => s.startsWith(p) || p.startsWith(s)));
}

/**
 * @param campos  prod_obs_human, prod_det_ia, subcategoría — en ese orden de
 *                confianza: lo que anotó una persona va antes que lo que dedujo
 *                el modelo.
 * @param q       lo que se buscó. Vacío = no se resalta nada y no se reordena.
 * @param tope    cuántos términos entran; el resto se resume en "+N".
 */
export function productosDe(campos: (string | null | undefined)[], q: string, tope = 8): { terminos: Termino[]; resto: number } {
  const vistos = new Set<string>();
  const crudos: string[] = [];
  for (const campo of campos) {
    for (const parte of (campo ?? "").split(/[,;·|\n]+/)) {
      const t = parte.trim().replace(/\.$/, "");
      // Una palabra suelta de dos letras no describe nada y ensucia el renglón.
      if (t.length < 3) continue;
      const clave = normalizar(t);
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      crudos.push(t);
    }
  }

  const palabras = normalizar(q).split(/[^a-z0-9]+/).filter((p) => p.length > 2);
  const marcados = crudos.map((texto) => ({ texto, coincide: coincideCon(texto, palabras) }));

  // Estable a propósito: dentro de cada grupo se respeta el orden de carga, así
  // que el primer término sigue siendo el que alguien eligió poner primero.
  const ordenados = [...marcados.filter((t) => t.coincide), ...marcados.filter((t) => !t.coincide)];
  return { terminos: ordenados.slice(0, tope), resto: Math.max(0, ordenados.length - tope) };
}
