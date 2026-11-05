// «¿Te contestó?»: los contactos por WhatsApp que el comprador hizo desde
// este navegador, para preguntarle un rato después si le contestaron.
//
// Se guardan acá (localStorage) con el id del lead que devolvió /lead y el
// `token` de ese contacto: sin él el backend rechaza el voto (403), así nadie
// puede votar por un contacto que no hizo. La pregunta la hace
// <PreguntaContesto/>: cuando la persona vuelve a la pestaña o abre otra
// página, tres minutos o más después del clic. Una pregunta por vez, y cada
// contacto se pregunta una sola vez.
export type ContactoPendiente = {
  id: string;
  comercioId: string;
  nombre: string;
  en: number;
  /** Lo que devolvió POST /lead junto al id. Sin esto no se puede votar. */
  token: string;
  /** La sesión de la pestaña con la que se hizo el contacto (la misma de /visita). */
  sesion?: string;
  pospuesto?: number;
};

const CLAVE = "uk-contactos-pendientes";
const ESPERA_MS = 3 * 60 * 1000;         // no antes de 3 minutos: el backend contesta 425 antes de 2
const VENCE_MS = 3 * 24 * 60 * 60 * 1000; // después de 3 días ya no vale la pena preguntar (el backend corta a los 7)

export function leerPendientes(): ContactoPendiente[] {
  try {
    const raw = localStorage.getItem(CLAVE);
    const lista = raw ? (JSON.parse(raw) as ContactoPendiente[]) : [];
    // Los anotados antes de que existiera el token (sin `token`) no se pueden
    // votar —el backend los rechazaría con 403—, así que no se preguntan.
    return lista.filter((c) => c && c.id && c.token && Date.now() - c.en < VENCE_MS);
  } catch { return []; }
}

function guardar(lista: ContactoPendiente[]) {
  try { localStorage.setItem(CLAVE, JSON.stringify(lista.slice(-20))); } catch { /* modo privado */ }
}

export function anotarContacto(id: string, comercioId: string, nombre: string, token: string, sesion?: string) {
  const lista = leerPendientes().filter((c) => c.id !== id);
  lista.push({ id, comercioId, nombre, en: Date.now(), token, ...(sesion ? { sesion } : {}) });
  guardar(lista);
}

/** El contacto que toca preguntar ahora, si hay uno. */
export function proximoParaPreguntar(): ContactoPendiente | null {
  const ahora = Date.now();
  return leerPendientes().find((c) => ahora - c.en >= ESPERA_MS && (!c.pospuesto || ahora >= c.pospuesto)) ?? null;
}

export function quitarContacto(id: string) {
  guardar(leerPendientes().filter((c) => c.id !== id));
}

export function posponerContacto(id: string, minutos = 30) {
  guardar(leerPendientes().map((c) => (c.id === id ? { ...c, pospuesto: Date.now() + minutos * 60 * 1000 } : c)));
}

// ---- Contrato con el backend (lógica pura, con tests) ----

/** Lo que responde POST /lead: `{ok, id, token}`. Devuelve null si no trae id y token. */
export function leadDeRespuesta(j: unknown): { id: string; token: string } | null {
  if (!j || typeof j !== "object") return null;
  const { id, token } = j as { id?: unknown; token?: unknown };
  return typeof id === "string" && id && typeof token === "string" && token ? { id, token } : null;
}

/** Cuerpo de POST /lead/{id}/respondio: `{respondio, token, sesion?}`. */
export function cuerpoRespondio(respondio: boolean, token: string, sesion?: string): { respondio: boolean; token: string; sesion?: string } {
  return { respondio, token, ...(sesion ? { sesion } : {}) };
}

/** Qué hacer con la respuesta de POST /lead/{id}/respondio.
 *  - `registrado`: {ok:true}.
 *  - `ya`: {ok:true, ya:true}, ya había votado.
 *  - `silencio`: 425 (contacto de menos de 2 min) y 429 (tope): no se le dice nada a la persona.
 *  - `descartar`: 403 (token inválido) y 410 (más de 7 días): este contacto ya no sirve, se borra.
 *  - `error`: cualquier otra cosa; tampoco se le dice nada (es una métrica, no una venta). */
export type ResultadoRespondio = "registrado" | "ya" | "silencio" | "descartar" | "error";

export function resultadoRespondio(status: number, cuerpo?: unknown): ResultadoRespondio {
  if (status === 425 || status === 429) return "silencio";
  if (status === 403 || status === 410) return "descartar";
  if (status >= 200 && status < 300) {
    const ya = cuerpo && typeof cuerpo === "object" && (cuerpo as { ya?: unknown }).ya === true;
    return ya ? "ya" : "registrado";
  }
  return "error";
}
