"use client";

import { useEffect, useState } from "react";
import { abiertoAhora, etiquetaHorario, type EstadoHorario } from "@/lib/horario";

/** Chip "Abierto ahora / Cerrado" calculado con la hora de BOLIVIA.
 * Se calcula tras montar (evita mismatch de SSR: la hora del server ≠ la del cliente)
 * y se refresca cada minuto. Si el horario no se puede interpretar, no renderiza nada.
 *
 * `estimado` cambia lo que promete. Un horario puesto por lote —el habitual de
 * la calle— no lo confirmó nadie en el local, así que el chip no puede decir
 * «Abierto ahora» con la misma cara: dice «Suele estar abierto». La diferencia
 * la paga el que cruzó el puente y manejó veinte cuadras. */
export function HorarioBadge({ horario, estimado, className }: {
  horario: string | null | undefined; estimado?: boolean; className?: string;
}) {
  const [e, setE] = useState<EstadoHorario | null>(null);

  useEffect(() => {
    const calc = () => setE(abiertoAhora(horario));
    calc();
    const t = setInterval(calc, 60_000);
    return () => clearInterval(t);
  }, [horario]);

  if (!e || e.estado === "desconocido") return null;
  const abierto = e.estado === "abierto";
  const texto = etiquetaHorario(e);
  return (
    <span className={`uk-open ${abierto ? "is-open" : "is-closed"}${estimado ? " is-estimado" : ""}${className ? " " + className : ""}`}
          title={estimado ? "Horario habitual de la calle. Nadie lo confirmó en el local: confirmá antes de ir." : undefined}>
      <span className="uk-open-dot" aria-hidden />
      {estimado ? `Suele estar ${(texto ?? "").toLowerCase()}` : texto}
    </span>
  );
}
