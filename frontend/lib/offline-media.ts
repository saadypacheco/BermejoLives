// Cola OFFLINE de MEDIA (fotos extra + video) de un comercio YA creado. Es la 2ª
// pasada del agente: sobre un local que ya existe le suma material (video, más
// fotos). Si no hay señal, el archivo queda en el celu (IndexedDB) y se sube solo
// cuando vuelve. Distinta de offline-altas.ts: aquella difiere el ALTA (crear el
// comercio); esta difiere el MATERIAL de uno existente (necesita su comercio_id).
import { subirFotoCampo, subirVideoCampo } from "@/lib/campo";

const DB = "uruku-offline";
const STORE = "media";

export type MediaPendiente = {
  id: string;
  comercioId: string;
  kind: "foto" | "video";
  blob: Blob;
  name: string;
  dur: number | null;   // solo video
  creado: number;
};

// Reusa la MISMA base que offline-altas (uruku-offline). Como la base ya existía
// con version 1 y un solo store, subimos a version 2 y creamos "media" si falta.
function abrir(): Promise<IDBDatabase> {
  return new Promise((res, rej) => {
    const req = indexedDB.open(DB, 2);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains("altas")) db.createObjectStore("altas", { keyPath: "id" });
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: "id" });
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

export async function encolarMedia(
  comercioId: string, kind: "foto" | "video", file: File | Blob, dur: number | null = null,
): Promise<void> {
  const rec: MediaPendiente = {
    id: uid(), comercioId, kind, blob: file,
    name: (file as File).name ?? (kind === "video" ? "video.mp4" : "foto.jpg"),
    dur, creado: Date.now(),
  };
  await run("readwrite", (s) => s.put(rec));
}

async function todas(): Promise<MediaPendiente[]> {
  const all = await run<MediaPendiente[]>("readonly", (s) => s.getAll());
  return (all ?? []).sort((a, b) => a.creado - b.creado);
}

/** Pendientes de un comercio (para mostrarlas como "sin subir todavía"). */
export async function listarMedia(comercioId: string): Promise<MediaPendiente[]> {
  return (await todas()).filter((m) => m.comercioId === comercioId);
}

export async function contarMedia(comercioId?: string): Promise<number> {
  const all = await todas();
  return comercioId ? all.filter((m) => m.comercioId === comercioId).length : all.length;
}

async function borrar(id: string): Promise<void> {
  await run("readwrite", (s) => s.delete(id));
}

/** Sube todo el material pendiente (opcionalmente de un solo comercio). Lo que
 * sube se borra de la cola; lo que falla queda para el próximo intento. */
export async function sincronizarMedia(
  comercioId?: string, onCambio?: () => void,
): Promise<{ subidas: number; fallas: number }> {
  if (typeof navigator !== "undefined" && !navigator.onLine) return { subidas: 0, fallas: 0 };
  const pend = (await todas()).filter((m) => !comercioId || m.comercioId === comercioId);
  let subidas = 0, fallas = 0;
  for (const m of pend) {
    try {
      const file = new File([m.blob], m.name, { type: m.blob.type });
      if (m.kind === "video") await subirVideoCampo(m.comercioId, file, m.dur);
      else await subirFotoCampo(m.comercioId, file);
      await borrar(m.id);
      subidas += 1;
      onCambio?.();
    } catch {
      fallas += 1;   // queda en la cola; se reintenta cuando haya señal
    }
  }
  return { subidas, fallas };
}
