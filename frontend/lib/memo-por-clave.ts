// Memoria en proceso por clave, con vencimiento, para lecturas que se hacen en cada visita (home de las ciudades,
// clima por ciudad). Sin React ni red: se prueba con `npm test` inyectando el reloj y la lectura.
//
// Reglas:
// - Pedidos simultáneos de la misma clave comparten UNA sola lectura (se guarda la promesa en curso).
// - Una lectura que falla (lanza) nunca se recuerda.
// - Un valor «incompleto» (`esCacheable` devuelve false: lectura vacía, catálogo que no llegó…) se devuelve igual
//   pero NO se recuerda `ttlIncompletoMs` (0 = no se recuerda): casi seguro fue un fallo y la próxima visita reintenta.
// - Las entradas vencidas se tiran al consultar, y hay un tope de claves: la memoria no crece sin límite.

export type OpcionesMemo<T> = {
  ttlMs: number;
  esCacheable?: (valor: T) => boolean;
  ttlIncompletoMs?: number;
  /** Tope de claves guardadas (por defecto 64); al llegar, se tira la más vieja. */
  maxClaves?: number;
  reloj?: () => number;
};

export function crearMemoPorClave<T>(o: OpcionesMemo<T>): (clave: string, leer: () => Promise<T>) => Promise<T> {
  const reloj = o.reloj ?? Date.now;
  const max = o.maxClaves ?? 64;
  const guardado = new Map<string, { valor: T; hasta: number }>();
  const enCurso = new Map<string, Promise<T>>();

  const limpiarVencidas = (ahora: number) => {
    for (const [k, v] of guardado) if (ahora >= v.hasta) guardado.delete(k);
  };

  return (clave, leer) => {
    const ahora = reloj();
    const hit = guardado.get(clave);
    if (hit && ahora < hit.hasta) return Promise.resolve(hit.valor);
    limpiarVencidas(ahora);
    const pendiente = enCurso.get(clave);
    if (pendiente) return pendiente;
    const p = leer()
      .then((valor) => {
        const ttl = (o.esCacheable ?? (() => true))(valor) ? o.ttlMs : (o.ttlIncompletoMs ?? 0);
        if (ttl > 0) {
          guardado.delete(clave);
          // Tope: se tira la entrada más vieja (el Map conserva el orden de inserción).
          while (guardado.size >= max) {
            const primera = guardado.keys().next().value;
            if (primera === undefined) break;
            guardado.delete(primera);
          }
          guardado.set(clave, { valor, hasta: reloj() + ttl });
        }
        return valor;
      })
      .finally(() => { enCurso.delete(clave); });
    enCurso.set(clave, p);
    return p;
  };
}
