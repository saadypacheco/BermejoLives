"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import {
  minutosRestantes, motivoBloqueo, textoAviso, textoRestante, type AccionBloqueada,
} from "@/lib/entrar-como";

/** Email del admin cuando «Mi comercio» está abierto con «Entrar como este comercio»; null si es el dueño. */
export const EntradaAdminContext = createContext<string | null>(null);
export const usePorAdmin = (): string | null => useContext(EntradaAdminContext);

/**
 * Aviso fijo de arriba de «Mi comercio» cuando entró un admin. Cuenta los minutos que quedan y avisa
 * (`onVencida`) cuando se acaba el tiempo: quien lo monta cierra la sesión. `onAlto` informa la altura real para
 * que la barra del panel se pegue debajo y no quede tapada.
 */
export function BannerEntradaAdmin({ nombre, email, expiraEn, onSalir, onVencida, onAlto }: {
  nombre: string; email: string; expiraEn: string | null;
  onSalir: () => void; onVencida: () => void; onAlto: (px: number) => void;
}) {
  const [ahora, setAhora] = useState(() => Date.now());
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const t = window.setInterval(() => setAhora(Date.now()), 15_000);
    return () => window.clearInterval(t);
  }, []);

  const quedan = expiraEn ? minutosRestantes(expiraEn, ahora) : null;
  const vencida = expiraEn ? Date.parse(expiraEn) <= ahora : false;
  useEffect(() => { if (vencida) onVencida(); }, [vencida, onVencida]);

  useEffect(() => {
    const el = caja.current;
    if (!el) return;
    const medir = () => onAlto(el.offsetHeight);
    medir();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(medir);
    ro.observe(el);
    return () => ro.disconnect();
  }, [onAlto]);

  return (
    <div ref={caja} role="status" className="mic-entrada">
      <span className="mic-entrada-txt">
        <Ic n="seguridad" s={18} /> <b>{textoAviso(nombre, email)}</b>
        {quedan !== null && <span className="mic-entrada-min"> <Ic n="reloj" s={15} /> {textoRestante(quedan)}</span>}
      </span>
      <button type="button" className="btn btn-sm mic-entrada-salir" onClick={onSalir}>
        <Ic n="cerrar_sesion" s={16} /> Salir
      </button>
    </div>
  );
}

/** Lo que reemplaza a un botón que el servidor rechazaría (403) con una entrada de admin: dice qué es y por qué no. */
export function BloqueadoPorAdmin({ id, titulo }: { id: AccionBloqueada; titulo?: string }) {
  return (
    <div role="note" style={{ display: "flex", gap: 8, alignItems: "flex-start", padding: 12, borderRadius: 12, border: "1px dashed var(--amber)", background: "rgba(255,176,32,.06)", fontSize: 13.5, color: "var(--txt-2)" }}>
      <Ic n="aviso" s={16} />
      <span>{titulo && <b>{titulo}: </b>}{motivoBloqueo(id)}</span>
    </div>
  );
}
