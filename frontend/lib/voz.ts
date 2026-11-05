/**
 * Búsqueda por voz con la Web Speech API del navegador: costo cero, sin
 * servicios externos ni dependencias. Acá vive la lógica PURA (sin React ni
 * `window` pegado a nada): elegir el idioma, limpiar lo que se reconoció y
 * traducir los errores del navegador a una frase que se entienda. El botón
 * está en `components/microfono-busqueda.tsx` y sólo la usa.
 */

/** Lo mínimo que usamos del reconocedor. TypeScript no trae estos tipos en
 *  `lib.dom`, y declararlos acá evita un `any` y una dependencia de tipos. */
export interface ReconocedorVoz {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onspeechstart: (() => void) | null;
  onresult: ((e: EventoResultadoVoz) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export type ConstructorReconocedor = new () => ReconocedorVoz;

/** Forma de `SpeechRecognitionEvent` que leemos: una lista de resultados, cada
 *  uno con alternativas ordenadas de más a menos probable. */
export interface EventoResultadoVoz {
  resultIndex?: number;
  results: ArrayLike<{
    isFinal: boolean;
    length: number;
    [i: number]: { transcript: string };
  }>;
}

/** El constructor del reconocedor, o `null` si este navegador no lo trae
 *  (Firefox, algunos WebView). Chrome y Safari lo exponen con prefijo. */
export function constructorVoz(w: {
  SpeechRecognition?: ConstructorReconocedor;
  webkitSpeechRecognition?: ConstructorReconocedor;
} | null | undefined): ConstructorReconocedor | null {
  if (!w) return null;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

/** El idioma a pedir: español de Bolivia y, si el navegador no lo reconoce,
 *  español a secas. */
export const IDIOMA_VOZ = "es-BO";
export const IDIOMA_VOZ_RESPALDO = "es";

export function idiomaVoz(respaldo: boolean): string {
  return respaldo ? IDIOMA_VOZ_RESPALDO : IDIOMA_VOZ;
}

/** Cuánto silencio se aguanta antes de cortar solo. */
export const SILENCIO_MAX_MS = 8000;

/** Tope de largo de lo que se pone en la caja: una frase dictada no necesita
 *  más y evita pegar un párrafo entero en la búsqueda. */
export const LARGO_MAX_VOZ = 100;

/**
 * Limpia lo que devolvió el reconocedor para usarlo como búsqueda: sin
 * espacios de más y sin la puntuación que algunos navegadores agregan al
 * dictar («Zapatillas.», «¿Dónde hay farmacia?»). Vacío si no quedó nada.
 */
export function normalizarTextoVoz(crudo: string | null | undefined): string {
  let t = (crudo ?? "").replace(/\s+/g, " ").trim();
  t = t.replace(/^[\s.,;:¿?¡!"'«»]+/, "").replace(/[\s.,;:¿?¡!"'«»]+$/, "");
  if (t.length > LARGO_MAX_VOZ) {
    t = t.slice(0, LARGO_MAX_VOZ);
    const corte = t.lastIndexOf(" ");
    if (corte > LARGO_MAX_VOZ / 2) t = t.slice(0, corte);
    t = t.trim();
  }
  return t;
}

/** Junta el texto de un evento de resultado y lo normaliza. `soloFinal`: ignora
 *  lo provisional (el reconocedor lo va corrigiendo hasta cerrarlo). */
export function textoDeEvento(e: EventoResultadoVoz, soloFinal = true): string {
  const partes: string[] = [];
  for (let i = 0; i < e.results.length; i++) {
    const r = e.results[i];
    if (soloFinal && !r.isFinal) continue;
    if (r.length > 0) partes.push(r[0].transcript);
  }
  return normalizarTextoVoz(partes.join(" "));
}

export type TipoErrorVoz = "permiso" | "sin_conexion" | "sin_microfono" | "no_entendi";

export interface ErrorVoz {
  tipo: TipoErrorVoz;
  mensaje: string;
}

export const MENSAJES_VOZ: Record<TipoErrorVoz, string> = {
  permiso: "Para buscar con la voz, permití el micrófono en tu navegador",
  sin_conexion: "No hay conexión. Revisá tu internet y probá de nuevo",
  sin_microfono: "No encontramos un micrófono. Revisá que esté conectado",
  no_entendi: "No te entendí, probá de nuevo",
};

/**
 * Traduce el código de error del navegador (`SpeechRecognitionErrorEvent.error`)
 * a un mensaje para la persona. `null` cuando no hay nada que mostrar: `aborted`
 * es que ella misma tocó para cortar. `language-not-supported` tampoco llega
 * acá: el componente reintenta con el idioma de respaldo antes (ver
 * `debeReintentarConRespaldo`).
 */
export function errorDeVoz(codigo: string | null | undefined): ErrorVoz | null {
  switch (codigo) {
    case "aborted":
      return null;
    case "not-allowed":
    case "service-not-allowed":
      return { tipo: "permiso", mensaje: MENSAJES_VOZ.permiso };
    case "network":
      return { tipo: "sin_conexion", mensaje: MENSAJES_VOZ.sin_conexion };
    case "audio-capture":
      return { tipo: "sin_microfono", mensaje: MENSAJES_VOZ.sin_microfono };
    default:
      // `no-speech`, `bad-grammar`, y cualquier código que no conozcamos.
      return { tipo: "no_entendi", mensaje: MENSAJES_VOZ.no_entendi };
  }
}

/** Si el error es que el navegador no sabe «es-BO», conviene reintentar con
 *  «es» en vez de avisarle algo a la persona. Sólo en el primer intento. */
export function debeReintentarConRespaldo(codigo: string | null | undefined, yaEsRespaldo: boolean): boolean {
  return codigo === "language-not-supported" && !yaEsRespaldo;
}
