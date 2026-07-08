"use client";

import { useEffect } from "react";
import { reportarError } from "@/lib/observabilidad";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    reportarError(error.message || "Error global de render", { stack: error.stack });
  }, [error]);

  return (
    <html lang="es">
      <body style={{ background: "#0d1117", color: "#e4e4e7", minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12 }}>
        <p>Algo salió mal. Probá de nuevo.</p>
        <button
          onClick={reset}
          style={{ background: "#22c55e", color: "#0e0e0e", fontWeight: 600, padding: "8px 18px", borderRadius: 999, border: "none" }}
        >
          Reintentar
        </button>
      </body>
    </html>
  );
}
