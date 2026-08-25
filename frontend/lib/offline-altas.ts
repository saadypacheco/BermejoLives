// Cola OFFLINE de altas de comercio. En zonas sin internet el alta se guarda en el
// celular (IndexedDB) y se sube sola cuando vuelve la señal. El GPS se captura offline
// (viene de los satélites, no de internet), así que el alta queda completa; solo se
// difiere la SUBIDA. Reutiliza altaComercioCampo (mismo endpoint + token del agente).
import { altaComercioCampo } from "@/lib/campo";

const DB = "uruku-offline";
const STORE = "altas";

export type AltaPendiente = {
  id: string;
  campos: Record<string, string>;   // nombre, whatsapp, lat, lng, modalidad, etc.
  rubro_slugs: string[];
  foto: Blob | null;
  fotoName: string;
  creado: number;
};

function abrir(): Promise<IDBDatabase> {
  return new Promise((res, rej) => {
    // v2: comparte la base con offline-media.ts (store "media"). Ambos módulos
    // abren con la MISMA versión y crean los stores que falten, para que abrir
    // con una versión menor no tire VersionError.
    const req = indexedDB.open(DB, 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" });
      if (!db.objectStoreNames.contains("media")) db.createObjectStore("media", { keyPath: "id" });
    };
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}

function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  return abrir().then((db) => new Promise<T>((res, rej) => {
    const r = fn(db.transaction(STORE, mode).objectStore(STORE));
    r.onsuccess = () => res(r.result as T);
    r.onerror = () => rej(r.error);
  }));
}

function uid(): string {
  return `${Date.now()}-${Math.round(performance.now())}-${Math.random().toString(36).slice(2, 8)}`;
}

export async function encolarAlta(campos: Record<string, string>, rubro_slugs: string[], foto: File | null): Promise<void> {
  // Sin coordenadas el backend rechaza el alta con 400 para SIEMPRE: el GPS es
  // el único campo obligatorio, y no se puede completar después desde el
  // celular porque hay que estar parado en el local. Encolar un alta así es
  // guardar basura que reintenta eternamente y le hace creer al agente que su
  // trabajo está a salvo. Mejor fallar acá, mientras todavía está en el local.
  if (coordenada(campos.lat) === null || coordenada(campos.lng) === null) {
    throw new Error("Sin ubicación no se puede guardar: volvé a tocar \"Usar mi ubicación actual\".");
  }
  const rec: AltaPendiente = {
    id: uid(), campos, rubro_slugs, foto: foto ?? null, fotoName: foto?.name ?? "foto.jpg", creado: Date.now(),
  };
  await run("readwrite", (s) => s.put(rec));
}

/** Descarta una pendiente que no se va a poder subir nunca (ej: sin GPS). */
export async function descartarPendiente(id: string): Promise<void> {
  await borrar(id);
}

/** Las que nunca van a entrar: sin coordenadas el backend las rechaza siempre. */
export function esIrrecuperable(rec: AltaPendiente): boolean {
  // Misma lectura que usa armarFd. Antes cada uno interpretaba la coordenada a
  // su manera, así que la cola podía marcar un alta como recuperable y el envío
  // mandarla sin ubicación — o al revés. Un solo criterio, en un solo lugar.
  return coordenada(rec.campos.lat) === null || coordenada(rec.campos.lng) === null;
}

export async function listarPendientes(): Promise<AltaPendiente[]> {
  const all = await run<AltaPendiente[]>("readonly", (s) => s.getAll());
  return (all ?? []).sort((a, b) => a.creado - b.creado);
}

export async function contarPendientes(): Promise<number> {
  return run<number>("readonly", (s) => s.count());
}

async function borrar(id: string): Promise<void> {
  await run("readwrite", (s) => s.delete(id));
}

/** Una coordenada utilizable, o null. Tolera lo que puede haber quedado
 *  guardado: número, texto, coma decimal, espacios.
 *
 *  El 0 se descarta a propósito: no es una ubicación de Bermejo sino el valor
 *  que queda cuando el GPS no llegó a fijar. Un alta en 0,0 cae en el Atlántico
 *  y en el mapa se ve como un pin perdido en el océano, no como un error. */
export function coordenada(v: unknown): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(String(v).trim().replace(",", "."));
  return Number.isFinite(n) && n !== 0 ? n : null;
}

function armarFd(rec: AltaPendiente): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(rec.campos)) {
    // Un valor nulo o vacío se enviaba igual, como el texto "null" o "": el
    // backend lo recibe como un dato presente e inválido y responde 422, no
    // como un campo que no vino. Para los opcionales la diferencia es
    // justamente ésa — y para lat/lng convertía un alta buena en un rechazo.
    if (k === "lat" || k === "lng") continue;      // van aparte, normalizadas
    if (v === null || v === undefined) continue;
    const s = String(v);
    if (s === "" || s === "null" || s === "undefined") continue;
    fd.append(k, s);
  }

  // Las coordenadas se re-arman desde el registro en formato canónico, en vez
  // de reenviar el texto que quedó guardado.
  //
  // El backend responde "Falta la ubicación" (400) tanto si `lat` no viene como
  // si viene VACÍO — para él son lo mismo. Y responde 422 si viene con coma
  // decimal o con la palabra "null". O sea: tres formas distintas de tener la
  // coordenada guardada y que el alta rebote igual, mientras el detalle de la
  // cola la muestra ahí, escrita. Es el peor lugar para ser frágil: el agente
  // ya caminó hasta el local y no puede volver.
  const lat = coordenada(rec.campos.lat);
  const lng = coordenada(rec.campos.lng);
  if (lat !== null) fd.append("lat", String(lat));
  if (lng !== null) fd.append("lng", String(lng));

  rec.rubro_slugs.forEach((r) => fd.append("rubro_slugs", r));
  if (rec.foto) fd.append("foto", rec.foto, rec.fotoName);
  return fd;
}

/** Lo que se mandó, para poder leerlo cuando el servidor dice que faltaba algo.
 *
 * El detalle de la cola ya muestra las coordenadas guardadas. Si el servidor
 * igual responde "Falta la ubicación", el problema está entre el registro y el
 * pedido — y sin ver qué salió de acá, eso es imposible de ubicar desde el
 * celular de un agente parado en la calle.
 */
function loQueSeMando(fd: FormData): string {
  const partes: string[] = [];
  for (const clave of ["lat", "lng", "ciudad_slug", "modalidad"]) {
    const v = fd.get(clave);
    partes.push(`${clave}=${v === null ? "(no vino)" : String(v)}`);
  }
  return partes.join(" ");
}

export type ResultadoSync = {
  subidas: number;
  fallas: number;
  sinSenal: boolean;
  /** Motivos de las que fallaron, sin repetir. Sin esto el botón "Sincronizar"
   * falla en silencio: el contador no baja y no hay forma de saber por qué. */
  errores: string[];
};

/** Sube todas las pendientes (una por una). Las que suben se borran de la cola; las
 * que fallan quedan para reintentar. */
export async function sincronizarPendientes(onCambio?: () => void): Promise<ResultadoSync> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return { subidas: 0, fallas: 0, sinSenal: true, errores: [] };
  }
  const pend = await listarPendientes();
  let subidas = 0, fallas = 0;
  const errores: string[] = [];
  for (const rec of pend) {
    const fd = armarFd(rec);
    try {
      await altaComercioCampo(fd);
      await borrar(rec.id);
      subidas += 1;
      onCambio?.();
    } catch (ex) {
      fallas += 1;   // queda en la cola; se reintenta la próxima vez que haya señal
      const base = ex instanceof Error ? ex.message : String(ex);
      const status = (ex as Error & { status?: number })?.status;
      // Con el motivo solo no se puede actuar: "Falta la ubicación" mientras el
      // detalle muestra las coordenadas deja al agente sin nada que hacer. Se
      // adjunta lo que efectivamente salió en el pedido, que es donde está la
      // diferencia — y el nombre, para saber CUÁL de las seis es.
      const nombre = rec.campos.nombre || "(sin nombre)";
      const motivo = status === 400 || status === 422
        ? `${nombre}: ${base} — se mandó ${loQueSeMando(fd)}`
        : `${nombre}: ${base}`;
      if (!errores.includes(motivo)) errores.push(motivo);
    }
  }
  return { subidas, fallas, sinSenal: false, errores };
}
