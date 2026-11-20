"use client";

import { useCallback, useEffect, useRef } from "react";
import { ControlHoja } from "@/lib/control-hoja";

/**
 * El comportamiento común de los paneles que suben desde abajo (Dax y los botones de intención). La lógica está en
 * `lib/control-hoja.ts` (con pruebas); acá sólo se conecta con React y con el navegador:
 *
 * - `popstate` (el «atrás» del teléfono) y `Escape` cierran.
 * - `cerrar()` es lo que llaman el velo, la rayita y «× Cerrar»; `cerrar(despues)` además navega (u otra cosa) cuando
 *   el panel ya bajó, sin dejar una entrada de historial de más.
 * - `usarHistorial` se evalúa al abrir: en la compu, donde el panel de Dax no es modal, no se toca el historial.
 *
 * `history.pushState` pasa por el parche de Next, que le agrega su estado interno: volver a esa entrada no recarga.
 */
export function useHoja(
  abierto: boolean, alCerrar: () => void, usarHistorial: () => boolean = () => true,
): { cerrar: (despues?: () => void) => void } {
  const alCerrarRef = useRef(alCerrar);
  const usarRef = useRef(usarHistorial);
  useEffect(() => { alCerrarRef.current = alCerrar; usarRef.current = usarHistorial; });

  const control = useRef<ControlHoja | null>(null);
  if (control.current === null) {
    control.current = new ControlHoja(
      typeof window === "undefined" ? null : { pushState: (e, t) => window.history.pushState(e, t), back: () => window.history.back() },
      () => alCerrarRef.current(),
    );
  }

  const cerrar = useCallback((despues?: () => void) => control.current?.cerrar(despues), []);

  useEffect(() => {
    const c = control.current;
    if (!abierto || !c) return;
    c.abrir(usarRef.current());
    const alAtras = () => c.alAtras();
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") c.cerrar(); };
    window.addEventListener("popstate", alAtras);
    window.addEventListener("keydown", alTeclear);
    return () => {
      window.removeEventListener("popstate", alAtras);
      window.removeEventListener("keydown", alTeclear);
      c.soltar();
    };
  }, [abierto]);

  return { cerrar };
}
