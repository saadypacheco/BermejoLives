"use client";

import { useEffect } from "react";
import { reportarError } from "@/lib/observabilidad";

export default function Error({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    reportarError(error.message || "Error de render", { stack: error.stack });
  }, [error]);

  return (
    <div style={{ minHeight: "60vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 12, padding: 24, textAlign: "center" }}>
      <p style={{ fontSize: 15, color: "#e4e4e7" }}>Algo salió mal.</p>
      <button
        onClick={reset}
        style={{ background: "#22c55e", color: "#0e0e0e", fontWeight: 600, padding: "8px 18px", borderRadius: 999, border: "none" }}
      >
        Reintentar
      </button>
    </div>
  );
}
