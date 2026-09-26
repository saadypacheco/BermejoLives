"use client";

import { useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { registrarVisita } from "@/lib/campo";
import { CIUDAD_COOKIE } from "@/lib/ciudad";

/**
 * Cuenta las páginas que se ven en URUKU.
 *
 * Hasta ahora lo único medido era la visita a la FICHA de un comercio. La
 * home, el buscador, /ofertas y /guia no existían para nadie: si alguien
 * entraba, buscaba «zapatillas», no encontraba y se iba, eso no quedaba
 * registrado en ninguna parte.
 *
 * SIN COOKIES Y SIN IP. La «sesión» es un número al azar que vive en la
 * pestaña (sessionStorage) y se pierde al cerrarla. Sirve para no contar diez
 * veces a la misma persona en una recorrida, y para nada más — no identifica
 * a nadie, no sigue a nadie entre visitas, y por eso tampoco hace falta el
 * cartel de cookies.
 *
 * Fuego y olvido, igual que `registrarLead`: si el servidor de métricas está
 * caído, la persona no se entera. Perder un número no puede costar una visita.
 */

const CLAVE_SESION = "uk-sesion";

function sesionDeLaPestania(): { id: string; primera: boolean } {
  try {
    const guardada = sessionStorage.getItem(CLAVE_SESION);
    if (guardada) return { id: guardada, primera: false };
    // `randomUUID` no está en navegadores viejos ni fuera de HTTPS (y el
    // agente de campo abre el sitio por IP más de una vez).
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
    sessionStorage.setItem(CLAVE_SESION, id);
    return { id, primera: true };
  } catch {
    // Modo privado o almacenamiento bloqueado: se cuenta la página igual, con
    // una sesión de un solo uso. Mejor contar de más que perder la visita.
    return { id: `x${Math.random().toString(36).slice(2, 12)}`, primera: true };
  }
}

/** Sólo el HOST de donde vino. La URL entera puede llevar datos de la otra
 *  página y no hace falta para nada: lo que interesa es si vino de Google, de
 *  Facebook o de un WhatsApp. */
function deDondeVino(): string | null {
  try {
    const r = document.referrer;
    if (!r) return null;
    const host = new URL(r).hostname.replace(/^www\./, "");
    return host === window.location.hostname ? null : host;
  } catch {
    return null;
  }
}

function ciudadDeLaCookie(): string | null {
  try {
    const c = document.cookie.split(";").find((x) => x.trim().startsWith(`${CIUDAD_COOKIE}=`));
    return c ? decodeURIComponent(c.split("=")[1]) : null;
  } catch {
    return null;
  }
}

export function ContadorVisitas() {
  const ruta = usePathname();
  const sp = useSearchParams();
  // La última ruta contada. Sin esto, cada vez que el buscador reescribe la
  // dirección —que lo hace en cada tecla— contaría una visita nueva, y
  // /buscar se llevaría el 90% del total.
  const ultima = useRef<string | null>(null);

  useEffect(() => {
    if (!ruta || ultima.current === ruta) return;
    ultima.current = ruta;
    const { id, primera } = sesionDeLaPestania();
    registrarVisita({
      ruta,
      sesion: id,
      primera,
      origen: sp?.get("ref") ?? null,
      referido: primera ? deDondeVino() : null,
      ciudad: ciudadDeLaCookie(),
    });
  }, [ruta, sp]);

  return null;
}
