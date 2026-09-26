"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Ciudad } from "@/lib/types";
import { CIUDAD_COOKIE, ciudadMasCercana } from "@/lib/ciudad";

function setCookie(slug: string) {
  document.cookie = `${CIUDAD_COOKIE}=${slug};path=/;max-age=31536000;samesite=lax`;
}
function hasCookie() {
  return document.cookie.split(";").some((c) => c.trim().startsWith(`${CIUDAD_COOKIE}=`));
}

/**
 * Selector de ciudad. Cambiar de ciudad recarga los datos del servidor (labels + mapa).
 * En la primera visita (sin cookie) intenta geolocalizar y elegir la ciudad ACTIVA más
 * cercana. Las ciudades inactivas se muestran como "próximamente".
 */
export function CitySelector({ actual, ciudades }: { actual: Ciudad | null; ciudades: Ciudad[] }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const geoDone = useRef(false);

  const activas = ciudades.filter((c) => c.activa);
  const proximas = ciudades.filter((c) => !c.activa);

  const elegir = (slug: string) => {
    setCookie(slug);
    setOpen(false);
    if (slug === actual?.slug) return;
    // La pantalla de resultados lleva la ciudad EN LA DIRECCIÓN (?ciudad=tarija),
    // para que una búsqueda se pueda compartir. Ese parámetro le gana a la
    // cookie, así que cambiar de ciudad acá y no tocarlo dejaba el combo
    // diciendo "Bermejo" y la búsqueda corriendo en Tarija: cero resultados
    // hasta recargar a mano. Si la URL trae ciudad, se cambia también.
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.get("ciudad")) {
        url.searchParams.set("ciudad", slug);
        // replaceState y no router.replace: cambia la dirección en el acto y
        // useSearchParams lo ve (Next 14.1+), sin pedirle la página al
        // servidor ni dejar una navegación en vuelo que pise lo que sigue.
        window.history.replaceState(null, "", url.pathname + url.search);
      }
    } catch { /* si algo raro pasa con la URL, el refresh de abajo igual va */ }
    router.refresh();
  };

  // Default por geolocalización (solo primera visita, sin cookie previa).
  useEffect(() => {
    if (geoDone.current || hasCookie() || !("geolocation" in navigator)) return;
    geoDone.current = true;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const cerca = ciudadMasCercana(ciudades, pos.coords.latitude, pos.coords.longitude);
        if (cerca) {
          setCookie(cerca.slug);
          if (cerca.slug !== actual?.slug) router.refresh();
        }
      },
      () => { /* si rechaza permiso, queda la ciudad por defecto */ },
      { timeout: 6000, maximumAge: 3600000 },
    );
  }, [ciudades, actual, router]);

  // Cerrar al clickear afuera.
  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("click", h);
    return () => document.removeEventListener("click", h);
  }, []);

  return (
    <div className="uk-city" ref={ref}>
      <button type="button" className="uk-pill uk-city-btn" onClick={() => setOpen((o) => !o)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0zM12 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4z" /></svg>
        {actual?.nombre ?? "Elegí tu ciudad"}
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="14" height="14"><path d="M6 9l6 6 6-6" /></svg>
      </button>

      {open && (
        <div className="uk-city-menu">
          {activas.map((c) => (
            <button key={c.slug} type="button" className={`uk-city-item ${c.slug === actual?.slug ? "on" : ""}`} onClick={() => elegir(c.slug)}>
              <span>{c.nombre}</span>
              <small>{c.departamento}{c.pais ? ` · ${c.pais}` : ""}</small>
            </button>
          ))}
          {proximas.length > 0 && (
            <>
              <div className="uk-city-sep">Próximamente</div>
              {proximas.map((c) => (
                <div key={c.slug} className="uk-city-item soon">
                  <span>{c.nombre}</span>
                  <small>{c.departamento}{c.pais ? ` · ${c.pais}` : ""}</small>
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
