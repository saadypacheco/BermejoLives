"use client";

import { useEffect, useState } from "react";

/**
 * «Comprobado hoy dd/mm · hh:mm:ss» con el reloj corriendo.
 *
 * Es lo que vuelve inútil una captura de pantalla vieja: quien se hace pasar
 * por agente no puede mostrar una captura, porque la hora no se mueve. Parte de
 * la hora del SERVIDOR (`checkedAt`) y la sigue con el cronómetro del navegador,
 * así un celular con la hora mal puesta no muestra una hora falsa. Hora de
 * Bolivia (UTC-4, sin horario de verano), calculada a mano para que el servidor
 * y el navegador dibujen exactamente lo mismo.
 */
const dos = (n: number) => String(n).padStart(2, "0");

function formato(ms: number): { fecha: string; hora: string } {
  const d = new Date(ms - 4 * 3600 * 1000);
  return {
    fecha: `${dos(d.getUTCDate())}/${dos(d.getUTCMonth() + 1)}`,
    hora: `${dos(d.getUTCHours())}:${dos(d.getUTCMinutes())}:${dos(d.getUTCSeconds())}`,
  };
}

export function RelojCredencial({ checkedAt }: { checkedAt: string }) {
  const base = Date.parse(checkedAt);
  const [ms, setMs] = useState(Number.isNaN(base) ? 0 : base);
  const [sinRed, setSinRed] = useState(false);

  useEffect(() => {
    if (Number.isNaN(base)) return;
    const t0 = performance.now();
    const id = window.setInterval(() => setMs(base + (performance.now() - t0)), 1000);
    const alRed = () => setSinRed(!navigator.onLine);
    alRed();
    window.addEventListener("online", alRed);
    window.addEventListener("offline", alRed);
    return () => {
      window.clearInterval(id);
      window.removeEventListener("online", alRed);
      window.removeEventListener("offline", alRed);
    };
  }, [base]);

  if (Number.isNaN(base)) return null;
  const { fecha, hora } = formato(ms);
  return (
    <>
      <p className="ag-reloj">
        <span className="ag-pulso" aria-hidden="true" />
        Comprobado hoy {fecha} · <b>{hora}</b>
      </p>
      {sinRed && (
        <p className="ag-reloj ag-reloj-viejo" role="status">
          Sin conexión: esta comprobación puede estar desactualizada. Volvé a abrir la página con señal.
        </p>
      )}
    </>
  );
}
