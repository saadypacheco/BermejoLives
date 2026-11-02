// Cola OFFLINE de las fotos del Banco de contenido (docs/contenido-redes-tecnico.md §9.2).
//
// Quien saca fotos adelante de un local casi nunca tiene señal. Lo que no sube
// queda en el teléfono (IndexedDB) y se reintenta al volver `online` y al abrir
// la pantalla. Reintentar es SEGURO: el backend contesta `duplicate=true` ante
// una foto que ya tiene (por `source_sha256`), así que una subida que llegó pero
// cuya respuesta se perdió no se duplica.
//
// Base propia (`uruku-content`, versión 1) y no la de `offline-media.ts`
// (`uruku-offline` v2): subirle la versión a aquella obligaría a migrar el alta
// de campo, que no tiene nada que ver con esto.
import { claveCola } from "@/lib/content-pure";
import type { ContentAssetUploadResponse } from "@/lib/content";

const DB = "uruku-content";
const STORE = "uploads";

/** Qué token hace falta para subirla: el del panel o el del agente. */
export type AmbitoCola = "admin" | "campo";

export type SubidaPendiente = {
  /** `comercioId:sha256` del archivo ORIGINAL (§9.2). */
  key: string;
  ambito: AmbitoCola;
  comercioId: string;
  /** La foto YA comprimida (2048 px): es la que se sube. */
  blob: Blob;
  name: string;
  source_sha256: string;
  taken_at_ms: number | null;
  show_in_ficha: boolean;
  has_people: boolean;
  people_ok: boolean | null;
  creado: number;
  /** El último motivo por el que no subió (para mostrarlo), si lo hubo. */
  ultimoError?: string;
};

function abrir(): Promise<IDBDatabase> {
  return new Promise((res, rej) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "key" });
    };
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}

function run<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest): Promise<T> {
  return abrir().then((db) => new Promise<T>((res, rej) => {
    const tx = db.transaction(STORE, mode);
    const r = fn(tx.objectStore(STORE));
    r.onsuccess = () => res(r.result as T);
    r.onerror = () => rej(r.error);
    // Cerrar la conexión al terminar: abrir una por llamada sin cerrarla deja
    // conexiones colgadas en un celular que sube cincuenta fotos.
    tx.oncomplete = () => db.close();
    tx.onabort = () => db.close();
  }));
}

/** ¿Este navegador tiene IndexedDB? (modo privado de algunos Safari: no.) */
export function colaDisponible(): boolean {
  return typeof indexedDB !== "undefined";
}

export async function encolarSubida(item: Omit<SubidaPendiente, "key" | "creado">): Promise<void> {
  // Sin huella (la pantalla se abrió por http y no hay `crypto.subtle`) la clave sale
  // de lo que tiene el archivo: dos fotos sin huella nunca pisan la misma entrada.
  const huella = item.source_sha256 || `f${item.blob.size}-${Date.now()}-${item.name}`;
  const rec: SubidaPendiente = { ...item, key: claveCola(item.comercioId, huella), creado: Date.now() };
  await run("readwrite", (s) => s.put(rec));   // `put`: encolar dos veces la misma foto = una entrada
}

async function todas(): Promise<SubidaPendiente[]> {
  const all = await run<SubidaPendiente[]>("readonly", (s) => s.getAll());
  return (all ?? []).sort((a, b) => a.creado - b.creado);
}

/** Las pendientes de un ámbito (y, si se pide, de un comercio). */
export async function listarSubidas(ambito: AmbitoCola, comercioId?: string): Promise<SubidaPendiente[]> {
  return (await todas()).filter((m) => m.ambito === ambito && (!comercioId || m.comercioId === comercioId));
}

export async function contarSubidas(ambito: AmbitoCola, comercioId?: string): Promise<number> {
  return (await listarSubidas(ambito, comercioId)).length;
}

export async function quitarSubida(key: string): Promise<void> {
  await run("readwrite", (s) => s.delete(key));
}

async function marcarError(item: SubidaPendiente, motivo: string): Promise<void> {
  await run("readwrite", (s) => s.put({ ...item, ultimoError: motivo }));
}

export type ResultadoSync = {
  subidas: number;
  /** Las que contestó el servidor como ya existentes. */
  duplicadas: number;
  /** Las que siguen en la cola (sin señal o con un error). */
  quedan: number;
  /** El último error del servidor que NO es de falta de señal, si hubo. */
  error?: string;
  /** Hubo que frenar toda la tanda (disco lleno, sesión vencida…). */
  frenada?: boolean;
};

/**
 * Sube lo pendiente de un ámbito, de a una. Lo que sube se borra de la cola; lo
 * que falla queda para el próximo intento. `subir` la pasa quien llama (así esta
 * cola no sabe de tokens ni de endpoints). `esRed` decide si el fallo fue de
 * señal (se corta la tanda: las demás fallarían igual) o del servidor (se sigue
 * con la siguiente, salvo que `frena` diga que no tiene sentido seguir).
 */
export async function sincronizarSubidas(opts: {
  ambito: AmbitoCola;
  comercioId?: string;
  subir: (item: SubidaPendiente) => Promise<ContentAssetUploadResponse>;
  esRed: (ex: unknown) => boolean;
  frena: (ex: unknown) => boolean;
  mensaje: (ex: unknown) => string;
  onSubida?: (item: SubidaPendiente, r: ContentAssetUploadResponse) => void;
}): Promise<ResultadoSync> {
  if (typeof navigator !== "undefined" && !navigator.onLine) {
    return { subidas: 0, duplicadas: 0, quedan: await contarSubidas(opts.ambito, opts.comercioId) };
  }
  const pend = await listarSubidas(opts.ambito, opts.comercioId);
  let subidas = 0, duplicadas = 0;
  let error: string | undefined;
  let frenada = false;
  for (const item of pend) {
    try {
      const r = await opts.subir(item);
      await quitarSubida(item.key);
      subidas += 1;
      if (r.duplicate) duplicadas += 1;
      opts.onSubida?.(item, r);
    } catch (ex) {
      if (opts.esRed(ex)) break;                 // sin señal: se reintenta después
      const motivo = opts.mensaje(ex);
      error = motivo;
      await marcarError(item, motivo).catch(() => {});
      if (opts.frena(ex)) { frenada = true; break; }
    }
  }
  return { subidas, duplicadas, quedan: await contarSubidas(opts.ambito, opts.comercioId), error, frenada };
}
