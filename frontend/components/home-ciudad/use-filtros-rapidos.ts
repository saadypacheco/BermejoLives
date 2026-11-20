"use client";

import { useCallback, useSyncExternalStore } from "react";
import {
  CLAVE_FILTROS_RAPIDOS, SIN_FILTROS, leerFiltros, serializarFiltros, type FiltrosRapidos,
} from "@/lib/filtros-rapidos";

/**
 * El estado de «Abiertos» y «Más cerca» (docs/home-ciudades.md §3): vive en `sessionStorage` y lo comparten
 * todos los componentes de la página (encabezado, botones de intención, carrusel, buscador).
 *
 * `useSyncExternalStore` y no un `useState` por componente: los interruptores del encabezado y el carrusel
 * del home están en ramas distintas del árbol y tienen que moverse juntos. El servidor siempre ve todo
 * apagado, así que el HTML no cambia con la sesión y la hidratación no se desacopla.
 */

const oyentes = new Set<() => void>();
let ultimoCrudo: string | null = null;
let ultimo: FiltrosRapidos = SIN_FILTROS;
// Si el navegador no deja usar `sessionStorage` (modo privado), el estado vive acá, en memoria.
let enMemoria: FiltrosRapidos | null = null;

function leerCrudo(): string | null {
  try { return sessionStorage.getItem(CLAVE_FILTROS_RAPIDOS); } catch { return null; }
}

function instantanea(): FiltrosRapidos {
  if (enMemoria) return enMemoria;
  const crudo = leerCrudo();
  // La misma referencia mientras el texto no cambie: si no, React cree que cambió en cada lectura y se cicla.
  if (crudo !== ultimoCrudo) { ultimoCrudo = crudo; ultimo = leerFiltros(crudo); }
  return ultimo;
}

function suscribir(avisar: () => void): () => void {
  oyentes.add(avisar);
  // `storage` avisa de los cambios hechos desde otra pestaña de la misma sesión.
  window.addEventListener("storage", avisar);
  return () => { oyentes.delete(avisar); window.removeEventListener("storage", avisar); };
}

/** Guarda el estado nuevo y avisa a todos los que lo usan. */
export function guardarFiltrosRapidos(f: FiltrosRapidos): void {
  try {
    sessionStorage.setItem(CLAVE_FILTROS_RAPIDOS, serializarFiltros(f));
    enMemoria = null;
  } catch {
    enMemoria = f;
  }
  oyentes.forEach((o) => o());
}

export function useFiltrosRapidos(): [FiltrosRapidos, (cambio: Partial<FiltrosRapidos>) => void] {
  const f = useSyncExternalStore(suscribir, instantanea, () => SIN_FILTROS);
  const cambiar = useCallback((cambio: Partial<FiltrosRapidos>) => {
    guardarFiltrosRapidos({ ...instantanea(), ...cambio });
  }, []);
  return [f, cambiar];
}
