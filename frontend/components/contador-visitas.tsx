"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { configurarMedicion, evento, eventoDeEnlace, vistaDePagina } from "@/lib/medicion";

/**
 * Cuenta las páginas que se ven en URUKU. Es sólo el enganche con React: toda la regla (rutas internas, equipo,
 * deduplicación, sendBeacon…) vive en `lib/medicion.ts`.
 *
 * SIN COOKIES Y SIN IP. La «sesión» es un número al azar que vive en la pestaña (sessionStorage) y se pierde al
 * cerrarla. Sirve para no contar diez veces a la misma persona en una recorrida, y para nada más: no identifica
 * a nadie, no sigue a nadie entre visitas, y por eso tampoco hace falta el cartel de cookies.
 *
 * También escucha, para todo el sitio, los toques a los enlaces de URUKU que declaran un evento con
 * `data-uk-evento` y `data-uk-detalle` (el canal, la comunidad y el contacto de URUKU): viven en páginas de
 * servidor, donde no se puede colgar un `onClick`.
 *
 * Fuego y olvido: si el servidor de métricas está caído, la persona no se entera.
 */
export function ContadorVisitas() {
  const ruta = usePathname();

  useEffect(() => { configurarMedicion(); }, []);

  // El buscador reescribe la dirección en cada tecla, pero eso cambia la query y no la ruta: `usePathname` no
  // cambia y el efecto no corre. Sólo cuenta cuando cambia de verdad de página.
  useEffect(() => {
    if (ruta) vistaDePagina(ruta);
  }, [ruta]);

  useEffect(() => {
    function alTocar(e: MouseEvent) {
      const enlace = e.target instanceof Element ? e.target.closest("[data-uk-evento]") : null;
      const ev = eventoDeEnlace(enlace);
      if (ev) evento(ev.nombre, ev.detail);
    }
    document.addEventListener("click", alTocar);
    return () => document.removeEventListener("click", alTocar);
  }, []);

  return null;
}
