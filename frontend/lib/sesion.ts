// La «sesión» de la pestaña: un número al azar que vive en sessionStorage y se
// pierde al cerrarla. No identifica a nadie ni sigue a nadie entre visitas.
//
// La usan DOS cosas y tiene que ser LA MISMA: /visita (components/contador-visitas)
// y /lead (lib/campo), porque el backend ata el voto de «¿te contestó?» a la
// sesión del contacto original. Por eso vive acá y no en un componente.

export const CLAVE_SESION = "uk-sesion";

/** El backend acepta letras, números y guion, hasta 40 (POST /lead y /visita). */
export const SESION_MAX = 40;
const SESION_RE = /^[A-Za-z0-9-]*$/;

export function sesionValida(s: unknown): s is string {
  return typeof s === "string" && s.length > 0 && s.length <= SESION_MAX && SESION_RE.test(s);
}

export function nuevaSesion(): string {
  // `randomUUID` no está en navegadores viejos ni fuera de HTTPS (y el agente de
  // campo abre el sitio por IP más de una vez). Un UUID mide 36: entra en el tope.
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

export function sesionDeLaPestania(): { id: string; primera: boolean } {
  try {
    const guardada = sessionStorage.getItem(CLAVE_SESION);
    if (guardada && sesionValida(guardada)) return { id: guardada, primera: false };
    const id = nuevaSesion();
    sessionStorage.setItem(CLAVE_SESION, id);
    return { id, primera: true };
  } catch {
    // Modo privado o almacenamiento bloqueado: se cuenta la página igual, con
    // una sesión de un solo uso. Mejor contar de más que perder la visita.
    return { id: `x${Math.random().toString(36).slice(2, 12)}`, primera: true };
  }
}
