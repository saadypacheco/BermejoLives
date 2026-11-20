"use client";

import { useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { pedirUbicacion, ubicacionGuardada } from "@/lib/ubicacion";
import { useFiltrosRapidos } from "./use-filtros-rapidos";

/**
 * Los interruptores «Abiertos» y «Más cerca» de la segunda fila del encabezado (docs/home-ciudades.md §3).
 *
 * Prendido se pinta de verde, lleva un tilde (no sólo color) y `aria-pressed="true"`. «Más cerca» pide la
 * ubicación la primera vez: si la persona no la da, se queda apagado y aparece un aviso corto.
 */
export function FiltrosRapidosToggles() {
  const [f, cambiar] = useFiltrosRapidos();
  const [aviso, setAviso] = useState("");
  const [pidiendo, setPidiendo] = useState(false);
  const temporizador = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(temporizador.current), []);

  function avisar(texto: string) {
    setAviso(texto);
    window.clearTimeout(temporizador.current);
    temporizador.current = window.setTimeout(() => setAviso(""), 5000);
  }

  async function alternarCerca() {
    if (f.cerca) { cambiar({ cerca: false }); return; }
    if (pidiendo) return;
    setPidiendo(true);
    try {
      if (!ubicacionGuardada()) await pedirUbicacion();
      cambiar({ cerca: true });
    } catch {
      cambiar({ cerca: false });
      avisar("No pudimos ver dónde estás, así que dejamos «Más cerca» apagado.");
    } finally {
      setPidiendo(false);
    }
  }

  return (
    <div className="uk-rapidos" role="group" aria-label="Filtros rápidos">
      <button type="button" className="uk-tog" aria-pressed={f.abiertos} onClick={() => cambiar({ abiertos: !f.abiertos })}>
        <Ic n={f.abiertos ? "si" : "reloj"} s={16} /> Abiertos
      </button>
      <button type="button" className="uk-tog" aria-pressed={f.cerca} aria-busy={pidiendo} onClick={alternarCerca}>
        <Ic n={f.cerca ? "si" : "ubicacion"} s={16} /> Más cerca
      </button>
      <span className="uk-rapidos-aviso" role="status" aria-live="polite">{aviso}</span>
    </div>
  );
}
