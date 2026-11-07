"use client";

import { useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { adminEntradasDelComercio } from "@/lib/api";
import { fechaHoraBolivia, type EntradaDelEquipo } from "@/lib/entrar-como";

/**
 * «Últimas entradas del equipo» a este comercio (`GET /admin/comercios/{id}/entradas`), en Admin › Editar negocio.
 * Sólo se monta con el permiso `equipo`. Si el pedido falla (403, 404, sin conexión) o no hay nada que mostrar,
 * el bloque no aparece: es información de apoyo, no tiene que estorbar.
 */
export function EntradasDelEquipo({ comercioId }: { comercioId: string }) {
  const [filas, setFilas] = useState<EntradaDelEquipo[] | null>(null);

  useEffect(() => {
    let vivo = true;
    setFilas(null);
    adminEntradasDelComercio(comercioId)
      .then((f) => { if (vivo) setFilas(f); })
      .catch(() => { if (vivo) setFilas(null); });
    return () => { vivo = false; };
  }, [comercioId]);

  if (!filas || filas.length === 0) return null;
  return (
    <section aria-label="Últimas entradas del equipo" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>
        <Ic n="reloj" s={13} /> Últimas entradas del equipo
      </div>
      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 4 }}>
        {filas.slice(0, 5).map((f, i) => (
          <li key={`${f.at}-${i}`} style={{ fontSize: 12.5, color: "var(--txt-2)", overflowWrap: "anywhere" }}>
            <b>{f.admin}</b> · {fechaHoraBolivia(f.at)} (hora de Bolivia){f.motivo ? <> · «{f.motivo}»</> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
