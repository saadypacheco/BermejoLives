/**
 * La última capa de calles que vio el agente, guardada en el celular para verla
 * sin señal (mismo criterio que lib/campo-cache.ts).
 *
 * Qué se guarda: el trazado, el estado, la cobertura y la fecha del último
 * paso. NO se guarda quién marcó ni quién cargó (`marca.actor`, `ultimo.quien`):
 * son nombres de personas y en un celular compartido no tienen por qué quedar a
 * la vista. Al salir de la sesión se borra todo (`olvidarCapaCalles`, que llama
 * `olvidarLista`).
 *
 * El acceso al almacenamiento va en try/catch: en modo privado o con el sitio
 * bloqueado tira, y si la capa pesa más que la cuota (miles de tramos) tampoco
 * entra. En ambos casos sigue funcionando en memoria.
 */
import { normalizarCapa, type CapaCalles } from "@/lib/calles";

const CLAVE = "uruku_campo_calles_v1";
const CLAVE_VER = "uruku_campo_calles_ver";

export type CapaGuardada = CapaCalles & { guardada: string };

let enMemoria: CapaGuardada | null = null;

/** Sin nombres de personas. */
function sinPersonas(c: CapaCalles): CapaCalles {
  return {
    resumen: c.resumen,
    tramos: c.tramos.map((t) => ({
      ...t,
      marca: t.marca ? { ...t.marca, actor: null } : null,
      ultimo: t.ultimo ? { fecha: t.ultimo.fecha, quien: null } : null,
    })),
  };
}

export function recordarCapa(c: CapaCalles): CapaGuardada {
  const limpia = { ...sinPersonas(c), guardada: new Date().toISOString() };
  enMemoria = limpia;
  try { localStorage.setItem(CLAVE, JSON.stringify(limpia)); } catch { /* sin cupo o sin almacenamiento: queda en memoria */ }
  return limpia;
}

/** Lo último guardado (memoria o celular), o null. */
export function capaGuardada(): CapaGuardada | null {
  if (enMemoria) return enMemoria;
  try {
    const raw = localStorage.getItem(CLAVE);
    if (!raw) return null;
    const j = JSON.parse(raw) as { guardada?: unknown };
    const capa = normalizarCapa(j);
    if (capa.tramos.length === 0) return null;
    enMemoria = { ...capa, guardada: typeof j.guardada === "string" ? j.guardada : "" };
    return enMemoria;
  } catch { return null; }
}

/** El interruptor «Calles»: una comodidad por celular, no un dato. */
export function leerVerCalles(): boolean {
  try { return localStorage.getItem(CLAVE_VER) === "1"; } catch { return false; }
}
export function guardarVerCalles(v: boolean): void {
  try { localStorage.setItem(CLAVE_VER, v ? "1" : "0"); } catch { /* nada que guardar */ }
}

/** Al salir: la capa es de la ciudad de ESTE agente. */
export function olvidarCapaCalles(): void {
  enMemoria = null;
  try { localStorage.removeItem(CLAVE); localStorage.removeItem(CLAVE_VER); } catch { /* nada que borrar */ }
}
