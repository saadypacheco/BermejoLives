// Recuperar la cuenta del comercio: la solicitud en curso (código + token).
//
// POST /auth/comercio/recuperar devuelve el `token` UNA sola vez, a quien pidió el
// código. Sin ese token el backend no deja consultar el estado ni confirmar: el
// código de 6 números solo ya no abre nada. Por eso hay que guardarlo, y por eso se
// guarda en sessionStorage —sólo esta pestaña, se pierde al cerrarla— y NO en
// localStorage: es una credencial de un solo uso que vale 15 minutos.
//
// Sirve además para el 409 «ya hay una confirmación en curso»: si la persona
// recarga la página o vuelve a tocar «Continuar», se retoma la solicitud guardada
// en vez de decirle que espere.

export type RecuperacionEnCurso = {
  whatsapp: string;
  comercioId?: string;
  codigo: string;
  wa_link: string;
  token: string;
  /** Cuándo se pidió (ms). */
  en: number;
};

const CLAVE = "uk-recuperar-comercio";
/** El código vence a los 15 minutos (backend); se descuenta un minuto de margen. */
export const VIGENCIA_RECUPERACION_MS = 14 * 60 * 1000;

const soloDigitos = (s: string) => s.replace(/\D+/g, "");

/** ¿Esta solicitud guardada sirve para este número (y negocio, si lo eligió) y no venció? */
export function recuperacionVigente(
  guardada: RecuperacionEnCurso | null | undefined, whatsapp: string, ahora: number, comercioId?: string,
): guardada is RecuperacionEnCurso {
  if (!guardada || !guardada.token || !guardada.codigo) return false;
  if (ahora - guardada.en >= VIGENCIA_RECUPERACION_MS || ahora < guardada.en) return false;
  if (soloDigitos(guardada.whatsapp) !== soloDigitos(whatsapp)) return false;
  // Si ya había un negocio elegido y ahora se pide otro, no es la misma solicitud.
  return !guardada.comercioId || !comercioId || guardada.comercioId === comercioId;
}

export function guardarRecuperacion(r: RecuperacionEnCurso): void {
  try { sessionStorage.setItem(CLAVE, JSON.stringify(r)); } catch { /* modo privado: queda sólo en memoria */ }
}

export function leerRecuperacion(): RecuperacionEnCurso | null {
  try {
    const raw = sessionStorage.getItem(CLAVE);
    return raw ? (JSON.parse(raw) as RecuperacionEnCurso) : null;
  } catch { return null; }
}

export function olvidarRecuperacion(): void {
  try { sessionStorage.removeItem(CLAVE); } catch { /* nada que borrar */ }
}
