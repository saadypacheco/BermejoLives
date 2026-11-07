// Memoria en proceso con vencimiento, para rutas que se arman al pedido (sitemap, llms.txt).
//
// Por qué existe: esas rutas no pueden armarse en el build (el build no llega a la base) y, como
// rutas sin parámetros, Next no tiene forma de dejarlas «ISR a pedido». Entonces son dinámicas y
// recuerdan el último resultado BUENO unos minutos: una consulta a la base por ventana, no una por
// robot. Un resultado fallido nunca se recuerda; si falla la regeneración se sigue sirviendo el
// último bueno (y se reintenta al rato), y si no hay ninguno el error sube (500, que el robot
// reintenta) en vez de publicar una versión recortada.

const REINTENTO_TRAS_FALLA_MS = 60_000;

export function conMemoriaTtl<T>(
  ttlMs: number,
  producir: () => Promise<T>,
  reloj: () => number = Date.now,
): () => Promise<T> {
  let guardado: { valor: T; hasta: number } | null = null;
  let enCurso: Promise<T> | null = null;

  // Un solo cálculo a la vez: pedidos simultáneos comparten la misma lectura.
  const regenerar = (): Promise<T> => {
    if (!enCurso) {
      enCurso = producir()
        .then((valor) => {
          guardado = { valor, hasta: reloj() + ttlMs };
          return valor;
        })
        .finally(() => {
          enCurso = null;
        });
    }
    return enCurso;
  };

  return async () => {
    if (guardado && reloj() < guardado.hasta) return guardado.valor;
    if (guardado) {
      // Vencido pero hay uno bueno: se sirve ya y se regenera en segundo plano. Así una base lenta
      // (PostgREST acepta pero no contesta) no deja colgados a los pedidos.
      const anterior = guardado;
      regenerar().catch(() => {
        if (guardado === anterior) anterior.hasta = reloj() + REINTENTO_TRAS_FALLA_MS;
      });
      return anterior.valor;
    }
    return regenerar();
  };
}
