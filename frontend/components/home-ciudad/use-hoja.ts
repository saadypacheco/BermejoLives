"use client";

import { useCallback, useEffect, useRef } from "react";

/**
 * El comportamiento común de los paneles que suben desde abajo (Dax y los botones de intención):
 *
 * - Al abrir se hace `history.pushState`, así el botón «atrás» del teléfono cierra el panel en vez de sacar
 *   a la persona de la página. Al cerrar con «atrás» (`popstate`) se baja el panel.
 * - `Escape` también cierra.
 * - `cerrar()` es lo que llaman el velo, la rayita y el botón «× Cerrar»: si había una entrada del historial
 *   puesta por el panel, la saca con `history.back()` (que dispara `popstate` y recién ahí se cierra), para
 *   no dejar una entrada de más.
 * - `cerrar(despues)` hace lo mismo y, cuando el panel ya bajó, ejecuta `despues` (por ejemplo, navegar a la
 *   opción elegida): navegar antes de sacar la entrada dejaría un «atrás» de más.
 *
 * `history.pushState` pasa por el parche de Next, que le agrega su estado interno: volver a esa entrada no
 * recarga la página.
 */
export function useHoja(abierto: boolean, alCerrar: () => void): { cerrar: (despues?: () => void) => void } {
  const empujado = useRef(false);
  const alCerrarRef = useRef(alCerrar);
  const despuesRef = useRef<(() => void) | null>(null);
  useEffect(() => { alCerrarRef.current = alCerrar; }, [alCerrar]);

  const terminar = useCallback(() => {
    alCerrarRef.current();
    const d = despuesRef.current;
    despuesRef.current = null;
    d?.();
  }, []);

  const cerrar = useCallback((despues?: () => void) => {
    despuesRef.current = typeof despues === "function" ? despues : null;
    if (empujado.current) {
      try { history.back(); return; } catch { empujado.current = false; }
    }
    terminar();
  }, [terminar]);

  useEffect(() => {
    if (!abierto) return;
    try { history.pushState({ ukHoja: true }, ""); empujado.current = true; } catch { empujado.current = false; }
    const alAtras = () => { empujado.current = false; terminar(); };
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") cerrar(); };
    window.addEventListener("popstate", alAtras);
    window.addEventListener("keydown", alTeclear);
    return () => {
      window.removeEventListener("popstate", alAtras);
      window.removeEventListener("keydown", alTeclear);
      empujado.current = false;
    };
  }, [abierto, cerrar, terminar]);

  return { cerrar };
}
