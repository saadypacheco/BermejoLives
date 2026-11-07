// La «sesión» de la pestaña: un número al azar que vive en sessionStorage y se
// pierde al cerrarla. No identifica a nadie ni sigue a nadie entre visitas.
//
// La usan DOS cosas y tiene que ser LA MISMA: /collect (páginas vistas y eventos)
// y /lead (contactos), porque el backend ata el voto de «¿te contestó?» a la
// sesión del contacto original. Por eso vive acá y no en un componente.
// Quien la pide es `lib/medicion.ts`, el único punto de entrada de la medición.

export const CLAVE_SESION = "uk-sesion";

/** El backend acepta letras, números y guion, de 6 a 40 (`^[A-Za-z0-9-]{6,40}$`: POST /collect y /lead). */
export const SESION_MIN = 6;
export const SESION_MAX = 40;
const SESION_RE = /^[A-Za-z0-9-]*$/;

export function sesionValida(s: unknown): s is string {
  return typeof s === "string" && s.length >= SESION_MIN && s.length <= SESION_MAX && SESION_RE.test(s);
}

export function nuevaSesion(): string {
  // `randomUUID` no está en navegadores viejos ni fuera de HTTPS (y el agente de
  // campo abre el sitio por IP más de una vez). Un UUID mide 36: entra en el tope.
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `s${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

// Si el almacenamiento está bloqueado, la sesión de respaldo se recuerda acá: sin esto cada llamada
// inventaba una distinta y una misma pestaña se contaba como diez personas.
let respaldo: string | null = null;

export function sesionDeLaPestania(): { id: string; primera: boolean } {
  try {
    const guardada = sessionStorage.getItem(CLAVE_SESION);
    if (guardada && sesionValida(guardada)) return { id: guardada, primera: false };
    const id = nuevaSesion();
    sessionStorage.setItem(CLAVE_SESION, id);
    return { id, primera: true };
  } catch {
    // Modo privado o almacenamiento bloqueado: se cuenta la página igual, con
    // una sesión que dura lo que dura esta carga. Mejor contar de más que perder la visita.
    if (respaldo) return { id: respaldo, primera: false };
    respaldo = `x${Math.random().toString(36).slice(2).padEnd(10, "0").slice(0, 10)}`;
    return { id: respaldo, primera: true };
  }
}
