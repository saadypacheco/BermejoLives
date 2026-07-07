"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { BottomNav } from "@/components/bottom-nav";
import { CompradorAuthForm } from "@/components/comprador-auth";
import { WhatsApp, X } from "@/components/icons";
import { getUsuarioSession, listarFavoritos, quitarFavorito, type FavoritoComercio, type UsuarioSession } from "@/lib/usuario";

const wa = (s?: string | null) => (s || "").replace(/\D/g, "");

export default function GuardadosPage() {
  const [sesion, setSesion] = useState<UsuarioSession | null>(null);
  const [items, setItems] = useState<FavoritoComercio[] | null>(null);
  const [err, setErr] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSesion(getUsuarioSession());
    setReady(true);
  }, []);

  useEffect(() => {
    if (!sesion) return;
    listarFavoritos().then(setItems).catch((e) => setErr(e instanceof Error ? e.message : "Error"));
  }, [sesion]);

  async function quitar(comercioId: string) {
    try { await quitarFavorito(comercioId); setItems((prev) => prev?.filter((x) => x.id !== comercioId) ?? prev); }
    catch { /* best-effort */ }
  }

  if (!ready) return null;

  return (
    <>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 40, paddingBottom: 100 }}>
        <span className="eyebrow"><span className="dot-live" /> Guardados</span>
        <h1 style={{ fontSize: 26, margin: "10px 0 6px" }}>Tus locales guardados</h1>

        {!sesion ? (
          <>
            <p style={{ color: "var(--txt-3)", marginBottom: 20 }}>
              Todavía no guardaste ningún local. Registrate con tu WhatsApp para guardar los que te interesen
              y no perderlos, aunque cambies de celular.
            </p>
            <div className="glass" style={{ padding: 22, borderRadius: 16 }}>
              <CompradorAuthForm onOk={() => setSesion(getUsuarioSession())} titulo="Registrate para guardar" />
            </div>
          </>
        ) : (
          <>
            {err && <p style={{ color: "var(--pink)", fontSize: 13 }}>{err}</p>}
            {!items && !err && <p style={{ color: "var(--txt-3)" }}>Cargando…</p>}
            {items && items.length === 0 && (
              <p style={{ color: "var(--txt-3)" }}>Todavía no guardaste ningún local. Tocá el ícono de guardar en cualquier comercio del mapa.</p>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {items?.map((c) => (
                <div key={c.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", gap: 12, alignItems: "center" }}>
                  <Link href={`/comercios/${c.slug}`} style={{ display: "flex", gap: 12, alignItems: "center", flex: 1, minWidth: 0, color: "inherit" }}>
                    <div style={{ width: 48, height: 48, borderRadius: 10, overflow: "hidden", background: "var(--panel)", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 20 }}>
                      {(c.portada_url || c.logo_url) ? <img src={(c.portada_url || c.logo_url) as string} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : "🏪"}
                    </div>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nombre}</div>
                      <div style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{c.direccion ?? "—"} · ★ {c.rating}</div>
                    </div>
                  </Link>
                  {wa(c.whatsapp) && (
                    <a className="mab wa" href={`https://wa.me/${wa(c.whatsapp)}`} target="_blank" rel="noopener" aria-label="WhatsApp">
                      <WhatsApp style={{ width: 18, height: 18 }} />
                    </a>
                  )}
                  <button type="button" className="mclose" onClick={() => quitar(c.id)} aria-label="Quitar de guardados"><X style={{ width: 16, height: 16 }} /></button>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
      <BottomNav active="Guardados" />
    </>
  );
}
