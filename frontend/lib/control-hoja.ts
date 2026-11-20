// La lógica del historial de los paneles que suben desde abajo (Dax y los botones de intención), sin React ni
// navegador, para poder probarla con `npm test` con un historial falso (components/home-ciudad/use-hoja.ts la usa).
//
// - Al abrir (en el celular, donde el panel tapa la pantalla) se hace `pushState`, así el botón «atrás» cierra el
//   panel. En la compu el panel de Dax no es modal: no se toca el historial.
// - `cerrar()` saca esa entrada con `back()`; el cierre real ocurre cuando llega el `popstate`.
// - `cerrando` evita que un doble cierre (Escape sostenido, doble toque en el velo) haga DOS `back()`: el segundo
//   sacaría a la persona de la página.
// - `cerrar(despues)` ejecuta `despues` cuando el panel ya bajó (navegar antes de sacar la entrada dejaría un
//   «atrás» de más, que vuelve a la misma página).

export type HistorialLike = { pushState(estado: unknown, titulo: string): void; back(): void };

export class ControlHoja {
  private empujado = false;
  private cerrando = false;
  private despues: (() => void) | null = null;

  constructor(private readonly historial: HistorialLike | null, private readonly alCerrar: () => void) {}

  /** Se abrió el panel. `usarHistorial` = el panel es modal (celular): se agrega la entrada del historial. */
  abrir(usarHistorial: boolean): void {
    this.cerrando = false;
    this.despues = null;
    this.empujado = false;
    if (!usarHistorial || !this.historial) return;
    try {
      this.historial.pushState({ ukHoja: true }, "");
      this.empujado = true;
    } catch {
      this.empujado = false;
    }
  }

  /** Cierra (velo, rayita, «× Cerrar», Escape o un enlace del panel). Idempotente mientras se está cerrando. */
  cerrar(despues?: () => void): void {
    if (typeof despues === "function") this.despues = despues;
    if (this.cerrando) return;
    this.cerrando = true;
    if (this.empujado && this.historial) {
      try { this.historial.back(); return; } catch { this.empujado = false; }
    }
    this.terminar();
  }

  /** Llegó un `popstate`: el «atrás» del teléfono (o el `back()` de `cerrar`). */
  alAtras(): void {
    this.empujado = false;
    this.cerrando = true;
    this.terminar();
  }

  /** El panel se desmontó o se cerró por otro camino: se olvida el estado. */
  soltar(): void {
    this.empujado = false;
    this.cerrando = false;
    this.despues = null;
  }

  /** ¿Quedó una entrada del historial puesta por el panel? (para las pruebas) */
  get conEntrada(): boolean { return this.empujado; }

  private terminar(): void {
    const d = this.despues;
    this.despues = null;
    this.empujado = false;
    this.cerrando = false;
    this.alCerrar();
    d?.();
  }
}
