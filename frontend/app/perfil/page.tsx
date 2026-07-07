"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { BottomNav } from "@/components/bottom-nav";
import { CompradorAuthForm } from "@/components/comprador-auth";
import { Bookmark, User } from "@/components/icons";
import { getUsuarioSession, clearUsuario, type UsuarioSession } from "@/lib/usuario";

export default function PerfilPage() {
  const [sesion, setSesion] = useState<UsuarioSession | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSesion(getUsuarioSession());
    setReady(true);
  }, []);

  if (!ready) return null;

  return (
    <>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 40, paddingBottom: 100 }}>
        <span className="eyebrow"><User style={{ width: 14, height: 14 }} /> Perfil</span>

        {!sesion ? (
          <>
            <h1 style={{ fontSize: 26, margin: "10px 0 6px" }}>Entrá con tu WhatsApp</h1>
            <p style={{ color: "var(--txt-3)", marginBottom: 20 }}>
              Sin contraseña — solo tu celular, para guardar locales y recibir avisos de ofertas.
            </p>
            <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
              <CompradorAuthForm onOk={() => setSesion(getUsuarioSession())} />
            </div>
          </>
        ) : (
          <>
            <h1 style={{ fontSize: 26, margin: "10px 0 20px" }}>Hola 👋</h1>
            <div className="glass" style={{ padding: 20, borderRadius: 16, marginBottom: 16 }}>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginBottom: 4 }}>WHATSAPP</div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>+{sesion.whatsapp}</div>
            </div>
            <Link href="/guardados" className="glass" style={{ padding: 18, borderRadius: 16, display: "flex", alignItems: "center", gap: 12, marginBottom: 16, color: "inherit" }}>
              <Bookmark style={{ width: 20, height: 20, color: "var(--neon)" }} />
              <span style={{ fontWeight: 600 }}>Ver mis locales guardados</span>
            </Link>
            <button
              type="button"
              className="btn btn-ghost"
              style={{ width: "100%" }}
              onClick={() => { clearUsuario(); setSesion(null); }}
            >
              Cerrar sesión
            </button>
          </>
        )}
      </div>
      <BottomNav active="Perfil" />
    </>
  );
}
