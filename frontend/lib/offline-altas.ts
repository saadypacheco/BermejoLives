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
  const lat = Number(campos.lat), lng = Number(campos.lng);
  if (!campos.lat || !campos.lng || !Number.isFinite(lat) || !Number.isFinite(lng)) {
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
  const lat = Number(rec.campos.lat), lng = Number(rec.campos.lng);
  return !rec.campos.lat || !rec.campos.lng || !Number.isFinite(lat) || !Number.isFinite(lng);
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
    try {
      await altaComercioCampo(armarFd(rec));
      await borrar(rec.id);
      subidas += 1;
      onCambio?.();
    } catch (ex) {
      fallas += 1;   // queda en la cola; se reintenta la próxima vez que haya señal
      const motivo = ex instanceof Error ? ex.message : String(ex);
      if (!errores.includes(motivo)) errores.push(motivo);
    }
  }
  return { subidas, fallas, sinSenal: false, errores };
}
