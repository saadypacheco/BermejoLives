"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Arrow } from "@/components/icons";

/**
 * «← Volver» para las pantallas a las que se llega desde un acceso del home
 * (Taxis, Cajeros, Baños…): el buscador con un rubro puesto no tenía cómo
 * volver salvo la flecha del navegador, que en el celular instalado como
 * app no existe.
 *
 * Si se llegó navegando dentro del sitio, vuelve atrás de verdad (la página
 * anterior, con su scroll). Si se llegó de afuera —un enlace compartido, un
 * QR— no hay atrás que valga: va al inicio.
 */
export function VolverAtras({ fallback = "/" }: { fallback?: string }) {
  const router = useRouter();
  const [propio, setPropio] = useState(false);
  useEffect(() => {
    try {
      const ref = document.referrer;
      setPropio(window.history.length > 1 && !!ref && new URL(ref).origin === window.location.origin);
    } catch { /* sin referrer: al inicio */ }
  }, []);
  return (
    <button type="button" className="uk-back uk-volver-atras" onClick={() => (propio ? router.back() : router.push(fallback))}>
      <Arrow style={{ transform: "rotate(180deg)" }} /> Volver
    </button>
  );
}
