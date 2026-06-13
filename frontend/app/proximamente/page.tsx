export const metadata = { title: "Muy pronto — Bermejo" };

export default function Proximamente() {
  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24, textAlign: "center" }}>
      <div style={{ maxWidth: 480 }}>
        <div style={{ fontSize: 12, letterSpacing: ".42em", color: "var(--txt-3)", fontWeight: 700 }}>BERMEJO · LIVE MARKET</div>
        <h1 style={{ fontSize: "clamp(38px,8vw,68px)", fontWeight: 900, lineHeight: 1, margin: "18px 0 0", letterSpacing: "-.03em" }}>
          Muy<br /><span style={{ color: "var(--neon)", textShadow: "0 0 38px rgba(57,255,158,.55)" }}>pronto</span>
        </h1>
        <p style={{ color: "var(--txt-2)", fontSize: 18, marginTop: 22 }}>
          Estamos relevando todos los comercios de Bermejo para mostrártelos en tiempo real.
        </p>
        <p style={{ color: "var(--txt-3)", fontSize: 14, marginTop: 14 }}>
          ¿Tenés un comercio? Pronto vas a poder publicar tus ofertas por WhatsApp.
        </p>
        <div style={{ marginTop: 28, display: "inline-flex", alignItems: "center", gap: 8, color: "var(--neon)", fontSize: 13, fontWeight: 700 }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--neon)", boxShadow: "0 0 12px var(--neon)" }} />
          Cargando la ciudad…
        </div>
      </div>
    </main>
  );
}
