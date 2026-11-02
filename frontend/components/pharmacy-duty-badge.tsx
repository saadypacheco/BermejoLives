"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { estaDeTurno, etiquetaHasta, fechaCorta, turnosFuturos, type TurnoFarmacia } from "@/lib/turnos-farmacia";

/** Un turno tal como viaja del servidor al navegador (sin la farmacia anidada). */
export type TurnoDeFicha = { id: string; comercio_id: string; fecha: string; inicio: string; fin: string };

/**
 * El sello «De turno ahora» de la ficha de una farmacia (docs/farmacias-de-turno.md).
 *
 * Es CLIENTE a propósito: la ficha se sirve por ISR (se regenera cada 5 minutos),
 * y un «de turno» calculado en el servidor se quedaba congelado en el HTML con el
 * turno ya vencido. Acá la hora «ahora» la decide el navegador (se recalcula cada
 * minuto), con los turnos que trae la página. Antes de montar no dibuja nada (el
 * HTML del servidor no puede saber qué hora es para quien lo lee).
 *
 * Ícono + texto: el verde solo no alcanza para quien no distingue colores.
 */
export function PharmacyDutyBadge({ turnos }: { turnos: readonly TurnoDeFicha[] }) {
  const [ahora, setAhora] = useState<Date | null>(null);

  useEffect(() => {
    const calc = () => setAhora(new Date());
    calc();
    const t = setInterval(calc, 60_000);
    return () => clearInterval(t);
  }, []);

  if (!ahora || turnos.length === 0) return null;

  const todos: TurnoFarmacia[] = turnos.map((t) => ({ ...t, comercios: null }));
  const vigente = todos.find((t) => estaDeTurno(t, ahora)) ?? null;
  const proximos = turnosFuturos(todos, ahora).slice(0, 4);

  if (vigente) {
    return (
      <p className="uk-ficha-turno">
        <span className="uk-turno-sello">
          <Ic n="turno_farmacia" s={18} peso="fill" />
          De turno ahora · {etiquetaHasta(vigente.fin, ahora)} · atiende las 24 h
        </span>
      </p>
    );
  }
  if (proximos.length === 0) return null;
  return (
    <p className="uk-ficha-turno">
      <span className="uk-turno-sello proximos">
        <Ic n="calendario" s={18} />
        <span>Próximos turnos: {proximos.map((t) => fechaCorta(t.fecha)).join(", ")}
          <Link href="/farmacias-de-turno">Ver quién está hoy</Link></span>
      </span>
    </p>
  );
}
