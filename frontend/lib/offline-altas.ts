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
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
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
  const rec: AltaPendiente = {
    id: uid(), campos, rubro_slugs, foto: foto ?? null, fotoName: foto?.name ?? "foto.jpg", creado: Date.now(),
  };
  await run("readwrite", (s) => s.put(rec));
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

function armarFd(rec: AltaPendiente): FormData {
  const fd = new FormData();
  for (const [k, v] of Object.entries(rec.campos)) fd.append(k, v);
  rec.rubro_slugs.forEach((r) => fd.append("rubro_slugs", r));
  if (rec.foto) fd.append("foto", rec.foto, rec.fotoName);
  return fd;
}

/** Sube todas las pendientes (una por una). Las que suben se borran de la cola; las
 * que fallan quedan para reintentar. Devuelve el conteo. */
export async function sincronizarPendientes(onCambio?: () => void): Promise<{ subidas: number; fallas: number }> {
  if (typeof navigator !== "undefined" && !navigator.onLine) return { subidas: 0, fallas: 0 };
  const pend = await listarPendientes();
  let subidas = 0, fallas = 0;
  for (const rec of pend) {
    try {
      await altaComercioCampo(armarFd(rec));
      await borrar(rec.id);
      subidas += 1;
      onCambio?.();
    } catch {
      fallas += 1;   // queda en la cola; se reintenta la próxima vez que haya señal
    }
  }
  return { subidas, fallas };
}
