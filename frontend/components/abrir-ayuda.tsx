"use client";

/** Un botón que abre Uruku Ayuda desde cualquier página. */
export function AbrirAyuda({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <button type="button" className={className} onClick={() => window.dispatchEvent(new Event("uk-abrir-ayuda"))}>
      {children}
    </button>
  );
}
