"use client";

import { useEffect, useState } from "react";
import { abiertoAhora, etiquetaHorario, type EstadoHorario } from "@/lib/horario";

/** Chip "Abierto ahora / Cerrado" calculado con la hora LOCAL del usuario.
 * Se calcula tras montar (evita mismatch de SSR: la hora del server ≠ la del cliente)
 * y se refresca cada minuto. Si el horario no se puede interpretar, no renderiza nada. */
export function HorarioBadge({ horario, className }: { horario: string | null | undefined; className?: string }) {
  const [e, setE] = useState<EstadoHorario | null>(null);

  useEffect(() => {
    const calc = () => setE(abiertoAhora(horario));
    calc();
    const t = setInterval(calc, 60_000);
    return () => clearInterval(t);
  }, [horario]);

  if (!e || e.estado === "desconocido") return null;
  const abierto = e.estado === "abierto";
  return (
    <span className={`uk-open ${abierto ? "is-open" : "is-closed"}${className ? " " + className : ""}`}>
      <span className="uk-open-dot" aria-hidden />
      {etiquetaHorario(e)}
    </span>
  );
}
