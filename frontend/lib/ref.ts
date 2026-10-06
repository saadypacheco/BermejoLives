// El `?ref=` con el que llegó una persona (volante, mesa, QR de la ficha).
//
// Se guarda con la fecha y VENCE A LOS 30 DÍAS: una persona que escaneó un
// volante en septiembre y en noviembre abre el sitio por su cuenta no vino por
// el volante. El backend aplica la misma regla en /lead y /visita; acá se corta
// antes para no mandar un origen que ya no vale.
//
// Formato guardado en la clave `uruku_ref`: JSON `{"v": "volante-x", "t": 1759...}`.
// El formato viejo era el texto pelado, sin fecha: se lo trata como de HOY (ver
// `leerRef`) y se lo reescribe con fecha.

const KEY = "uruku_ref";
export const REF_VENCE_MS = 30 * 24 * 60 * 60 * 1000;

type RefGuardado = { v: string; t: number };

function esRefGuardado(x: unknown): x is RefGuardado {
  if (typeof x !== "object" || x === null) return false;
  const o = x as Record<string, unknown>;
  return typeof o.v === "string" && typeof o.t === "number";
}

/** El ref vigente, o null si no hay o ya venció (en ese caso lo borra). */
export function leerRef(): string | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;

    let parsed: unknown = null;
    try { parsed = JSON.parse(raw); } catch { /* formato viejo: texto pelado */ }

    if (esRefGuardado(parsed)) {
      if (!parsed.v || Date.now() - parsed.t > REF_VENCE_MS) {
        localStorage.removeItem(KEY);
        return null;
      }
      return parsed.v;
    }

    // Formato viejo, sin fecha: no se sabe cuándo llegó. Se toma como de HOY y
    // se reescribe con fecha, así vale 30 días más desde ahora y no para
    // siempre. (Descartarlo perdería la atribución de quien llegó hace pocos
    // días, que es casi todos: el ref por volante es reciente.)
    guardarRef(raw);
    return raw;
  } catch {
    return null;   // localStorage no disponible
  }
}

/** Guarda el ref con la fecha de hoy. */
export function guardarRef(ref: string): void {
  try {
    const v = ref.slice(0, 64);
    localStorage.setItem(KEY, JSON.stringify({ v, t: Date.now() } satisfies RefGuardado));
  } catch { /* localStorage no disponible — ignorar */ }
}

/** Alias con el nombre que ya usa el resto del código. */
export const refGuardado = leerRef;
