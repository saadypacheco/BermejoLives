"use client";

import { useEffect, useState } from "react";
import { Bookmark } from "@/components/icons";
import { getUsuarioSession, listarFavoritos, agregarFavorito, quitarFavorito } from "@/lib/usuario";
import { CompradorAuthModal } from "@/components/comprador-auth";

export function GuardarBoton({ comercioId, className, style }: { comercioId: string; className?: string; style?: React.CSSProperties }) {
  const [guardado, setGuardado] = useState(false);
  const [cargando, setCargando] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => {
    if (!getUsuarioSession()) return;
    listarFavoritos().then((items) => setGuardado(items.some((i) => i.id === comercioId))).catch(() => {});
  }, [comercioId]);

  async function toggle() {
    setCargando(true);
    try {
      if (guardado) { await quitarFavorito(comercioId); setGuardado(false); }
      else { await agregarFavorito(comercioId); setGuardado(true); }
    } catch { /* best-effort: no bloquea la navegación */ }
    finally { setCargando(false); }
  }

  function onClick(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!getUsuarioSession()) { setModalOpen(true); return; }
    toggle();
  }

  return (
    <>
      <button
        type="button"
        onClick={onClick}
        disabled={cargando}
        className={className}
        aria-label={guardado ? "Quitar de guardados" : "Guardar"}
        style={style}
      >
        <Bookmark filled={guardado} style={{ width: 18, height: 18, color: guardado ? "var(--neon)" : undefined }} />
      </button>
      {modalOpen && (
        <CompradorAuthModal
          onClose={() => setModalOpen(false)}
          onOk={async () => { setModalOpen(false); await toggle(); }}
        />
      )}
    </>
  );
}
