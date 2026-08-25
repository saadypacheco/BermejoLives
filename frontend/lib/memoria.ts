"use client";

/** Medición de memoria del recolector, para verificar en el celular real.
 *
 * POR QUÉ NO ALCANZA CON MIRAR EL CÓDIGO
 * ======================================
 *
 * Las fugas de memoria en el navegador se arreglan a ciegas si no se miden: uno
 * cierra un `ImageBitmap`, la app "parece" mejor, y en el celular del agente
 * sigue muriendo a los treinta comercios. El síntoma que reportan —"memoria
 * insuficiente" en un Samsung de 4 GB— no se reproduce en una laptop con 16.
 *
 * Esto imprime el heap después de cada comercio guardado. Lo que importa NO es
 * el número absoluto sino **la pendiente**: si después de cincuenta altas el
 * valor vuelve más o menos al mismo lugar, no hay fuga. Si sube escalón por
 * escalón y nunca baja, la hay — y el tamaño del escalón dice cuánto queda
 * colgado por comercio.
 *
 * CÓMO SE USA (en el celular, sin instalar nada)
 * ==============================================
 *
 *   1. Abrir el recolector con `?debugmem=1` — queda prendido para esa pestaña.
 *   2. Cargar comercios normalmente.
 *   3. Conectar el celular por USB y abrir chrome://inspect en la compu, o
 *      mirar el resumen que queda en `window.__memoriaUruku`.
 *
 * `performance.memory` sólo existe en Chrome/Android, que es lo que usan los
 * agentes. En otro navegador esto no hace nada y no molesta.
 */

type Muestra = { n: number; heapMB: number; etiqueta: string; t: number };

const CLAVE = "uruku-debugmem";

function activo(): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (new URLSearchParams(window.location.search).get("debugmem") === "1") {
      window.sessionStorage.setItem(CLAVE, "1");
    }
    return window.sessionStorage.getItem(CLAVE) === "1";
  } catch {
    return false;
  }
}

function heapMB(): number | null {
  const perf = performance as Performance & { memory?: { usedJSHeapSize: number } };
  if (!perf.memory) return null;
  return Math.round((perf.memory.usedJSHeapSize / 1048576) * 10) / 10;
}

/** Anota una muestra. `etiqueta` es lo que acaba de pasar ("comercio 12 guardado"). */
export function medirMemoria(etiqueta: string): void {
  if (!activo()) return;
  const mb = heapMB();
  if (mb === null) {
    console.info(`[memoria] ${etiqueta} — este navegador no expone performance.memory`);
    return;
  }
  const w = window as Window & { __memoriaUruku?: Muestra[] };
  const serie = (w.__memoriaUruku ??= []);
  const muestra: Muestra = { n: serie.length + 1, heapMB: mb, etiqueta, t: Date.now() };
  serie.push(muestra);

  const primera = serie[0].heapMB;
  const delta = Math.round((mb - primera) * 10) / 10;
  const porComercio = serie.length > 1
    ? Math.round((delta / (serie.length - 1)) * 10) / 10
    : 0;

  // El "por comercio" es el número que decide: si se queda cerca de 0, no hay
  // fuga. Si es 5 o 10 MB, en cincuenta altas son 250-500 MB y el celular muere.
  console.info(
    `[memoria] #${muestra.n} ${etiqueta} — heap ${mb} MB · ` +
    `desde el arranque ${delta >= 0 ? "+" : ""}${delta} MB · ` +
    `${porComercio >= 0 ? "+" : ""}${porComercio} MB por comercio`,
  );
}

/** El resumen para pegar en un reporte. */
export function resumenMemoria(): string {
  const w = window as Window & { __memoriaUruku?: Muestra[] };
  const serie = w.__memoriaUruku ?? [];
  if (serie.length < 2) return "Sin muestras suficientes.";
  const primera = serie[0], ultima = serie[serie.length - 1];
  const pico = serie.reduce((a, b) => (b.heapMB > a.heapMB ? b : a));
  const crecimiento = ultima.heapMB - primera.heapMB;
  return [
    `Muestras: ${serie.length}`,
    `Inicio: ${primera.heapMB} MB · Final: ${ultima.heapMB} MB · Pico: ${pico.heapMB} MB (en #${pico.n})`,
    `Crecimiento total: ${crecimiento >= 0 ? "+" : ""}${Math.round(crecimiento * 10) / 10} MB`,
    `Por comercio: ${Math.round((crecimiento / (serie.length - 1)) * 10) / 10} MB`,
    ``,
    `Cómo leerlo: por comercio cerca de 0 = sin fuga. El pico importa aparte:`,
    `es el momento de comprimir, y es el que dispara "memoria insuficiente".`,
  ].join("\n");
}
