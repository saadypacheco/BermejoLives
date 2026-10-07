"use client";

// Ciudad elegida en el panel de administración.
//
// POR QUÉ UN CONTEXTO
// ===================
//
// El panel nació para una sola ciudad y hoy hay comercios de varias. Cada
// pestaña que filtra (Negocios, Lugares, Adornos, Importados) necesita saber
// cuál se está mirando, y el selector vive en la cabecera, lejos de todas. Un
// estado local por pestaña obligaba a elegir la ciudad de nuevo en cada una.
//
// ES UN FILTRO, NO UN PERMISO: elegir «Santa Cruz» no impide ver otra ciudad,
// sólo ordena lo que se muestra. Y NO toca la cookie `ciudad` del sitio público
// (lib/ciudad.ts): mirar Tarija desde el panel no debe cambiar la ciudad con la
// que el sitio recibe a los visitantes.

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getCiudadesReales } from "@/lib/data";
import { miCiudad } from "@/lib/api";
import type { Ciudad } from "@/lib/types";
import { Ic } from "@/components/ic";

/** Clave en localStorage. Distinta de la cookie del sitio público, a propósito. */
const CLAVE = "uk-admin-ciudad";
/** «Todas» se guarda como valor explícito: sin él no se podría distinguir
 *  «eligió todas» de «nunca eligió», y el panel volvería a pararse en la ciudad
 *  del usuario cada vez que alguien quiso ver todo. */
const TODAS = "todas";

type Contexto = {
  /** Todas las ciudades de la tabla, activas o no, en su orden. */
  ciudades: Ciudad[];
  /** No se pudo leer la tabla de ciudades. El panel sigue andando con «todas»,
   *  pero lo dice: una lista vacía sin aviso se lee como «no hay ciudades». */
  sinCiudades: boolean;
  /** Slug elegido; null = todas las ciudades. */
  slug: string | null;
  /** La ciudad elegida como objeto; null con «todas» (o si no se resolvió). */
  ciudad: Ciudad | null;
  /** Ya se leyeron las ciudades y se resolvió el valor inicial. Quien pide
   *  datos según la ciudad espera a esto: si no, la primera consulta sale con
   *  «todas» y la segunda con la ciudad real. */
  listo: boolean;
  /** Cambia la ciudad (null = todas) y la recuerda en este navegador. */
  elegir: (slug: string | null) => void;
  /** Se llama cuando hay sesión. El valor inicial depende del token (la ciudad
   *  del usuario), que recién existe después del login: resolverlo antes
   *  dejaba a todos en «todas». */
  arrancar: () => void;
};

const Ctx = createContext<Contexto | null>(null);

function leer(): string | null {
  try { return window.localStorage.getItem(CLAVE); } catch { return null; }
}
function guardar(valor: string) {
  try { window.localStorage.setItem(CLAVE, valor); } catch { /* modo privado: no se recuerda y listo */ }
}

export function AdminCiudadProvider({ children }: { children: React.ReactNode }) {
  const [ciudades, setCiudades] = useState<Ciudad[] | null>(null);
  const [sinCiudades, setSinCiudades] = useState(false);
  const [slug, setSlug] = useState<string | null>(null);
  const [arrancado, setArrancado] = useState(false);
  const [listo, setListo] = useState(false);

  useEffect(() => {
    let vivo = true;
    // La tabla real o nada: `getCiudades` cae en una lista de demostración
    // cuando la base no contesta, y en el panel eso sería elegir entre
    // ciudades con ids inventados.
    const fallo = () => { if (vivo) { setCiudades([]); setSinCiudades(true); } };
    getCiudadesReales()
      .then((c) => { if (!vivo) return; if (c) setCiudades(c); else fallo(); })
      .catch(fallo);
    return () => { vivo = false; };
  }, []);

  // Valor inicial: lo guardado (si sigue existiendo) → la ciudad del usuario →
  // todas. Corre una sola vez, cuando hay sesión Y llegaron las ciudades.
  useEffect(() => {
    if (!arrancado || ciudades === null || listo) return;
    const existe = (s: string | null): s is string => !!s && ciudades.some((c) => c.slug === s);
    const guardado = leer();
    const propia = miCiudad();
    setSlug(guardado === TODAS ? null
      : existe(guardado) ? guardado
      : existe(propia) ? propia
      : null);
    setListo(true);
  }, [arrancado, ciudades, listo]);

  const elegir = useCallback((s: string | null) => {
    setSlug(s);
    guardar(s ?? TODAS);
  }, []);
  const arrancar = useCallback(() => setArrancado(true), []);

  const valor = useMemo<Contexto>(() => {
    const lista = ciudades ?? [];
    return {
      ciudades: lista,
      sinCiudades,
      slug,
      ciudad: slug ? lista.find((c) => c.slug === slug) ?? null : null,
      listo, elegir, arrancar,
    };
  }, [ciudades, sinCiudades, slug, listo, elegir, arrancar]);

  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>;
}

export function useAdminCiudad(): Contexto {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAdminCiudad se usa dentro de <AdminCiudadProvider>");
  return c;
}

/** Cómo se comporta cada pestaña frente a la ciudad elegida. */
export type ModoCiudad = "filtra" | "global" | "pendiente";

/** El nombre en el selector: las ciudades que todavía no abrieron se marcan, así
 *  nadie las toma por activas. */
export function nombreCiudad(c: Ciudad): string {
  return c.activa ? c.nombre : `${c.nombre} (sin abrir)`;
}

/** Lo que hay que decirle a quien mira sobre cómo se porta esta sección con la
 *  ciudad elegida. null = nada que avisar (la sección filtra). El fallo de carga
 *  va primero: sin ciudades no hay nada que elegir, y eso importa más que el
 *  modo de la sección. */
function leyendaDe(modo: ModoCiudad, sinCiudades: boolean): { texto: string; aviso: boolean } | null {
  if (sinCiudades) return { texto: "No se pudieron cargar las ciudades: el panel muestra todas", aviso: true };
  if (modo === "global") return { texto: "Esta sección no depende de la ciudad", aviso: false };
  if (modo === "pendiente") return { texto: "Esta sección todavía muestra todas las ciudades", aviso: true };
  return null;
}

/** Selector de la cabecera. El `modo` lo decide la sección activa (ver
 *  `components/admin/secciones.ts`):
 *   - filtra:    funciona normal.
 *   - global:    atenuado; la sección no depende de la ciudad.
 *   - pendiente: la sección todavía muestra todas las ciudades. La leyenda es
 *     obligatoria: un selector que dice «Santa Cruz» sobre una lista que muestra
 *     todo estaría mintiendo.
 *
 *  `sinLeyenda`: la barra de arriba es de alto fijo y no tiene dónde apoyar un
 *  renglón de texto; ahí el selector va solo y la leyenda la dibuja `AvisoCiudad`
 *  en otro lugar de la pantalla. */
export function SelectorCiudad({ modo, sinLeyenda = false }: { modo: ModoCiudad; sinLeyenda?: boolean }) {
  const { ciudades, sinCiudades, slug, elegir } = useAdminCiudad();
  const leyenda = leyendaDe(modo, sinCiudades);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, minWidth: 0 }}>
      <label style={{ display: "flex", alignItems: "center", gap: 6, opacity: modo === "global" ? 0.5 : 1 }}>
        <Ic n="ubicacion" s={16} />
        <select className="adm-input" style={{ width: "auto", minWidth: 0, maxWidth: "100%", padding: "8px 12px" }}
                aria-label="Ciudad del panel" aria-describedby={leyenda ? "admin-ciudad-leyenda" : undefined}
                value={slug ?? ""} onChange={(e) => elegir(e.target.value || null)}>
          <option value="">Todas las ciudades</option>
          {ciudades.map((c) => <option key={c.slug} value={c.slug}>{nombreCiudad(c)}</option>)}
        </select>
      </label>
      {leyenda && !sinLeyenda && <LeyendaCiudad leyenda={leyenda} />}
    </div>
  );
}

function LeyendaCiudad({ leyenda }: { leyenda: { texto: string; aviso: boolean } }) {
  return (
    <span id="admin-ciudad-leyenda"
          style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 12, color: leyenda.aviso ? "var(--amber)" : "var(--txt-3)" }}>
      <Ic n={leyenda.aviso ? "aviso" : "dato"} s={13} /> {leyenda.texto}
    </span>
  );
}

/** La leyenda del selector, suelta: para cuando el selector va en la barra de
 *  arriba (`sinLeyenda`) y el aviso se dibuja con el contenido. Texto + ícono,
 *  no sólo color. Sin aviso que dar no dibuja nada. */
export function AvisoCiudad({ modo }: { modo: ModoCiudad }) {
  const { sinCiudades } = useAdminCiudad();
  const leyenda = leyendaDe(modo, sinCiudades);
  return leyenda ? <LeyendaCiudad leyenda={leyenda} /> : null;
}

/** Lo que muestran Lugares y Adornos con «todas»: en vez de caer en Bermejo (que
 *  es lo que hacían), piden elegir. Un botón por ciudad la elige en el selector. */
export function ElegirCiudad({ que }: { que: string }) {
  const { ciudades, elegir } = useAdminCiudad();
  if (ciudades.length === 0) {
    // Sin botones no hay cómo seguir: decirlo en vez de dejar el título solo.
    return (
      <div className="panel-card glass" style={{ padding: 20 }}>
        <p style={{ color: "var(--amber)" }}>
          <Ic n="aviso" s={15} /> No se pudieron cargar las ciudades, y los {que} se trabajan de a una ciudad. Recargá el panel.
        </p>
      </div>
    );
  }
  return (
    <div className="panel-card glass" style={{ padding: 20 }}>
      <p style={{ fontWeight: 600, marginBottom: 12 }}>Elegí una ciudad para trabajar con sus {que}</p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {ciudades.map((c) => (
          <button key={c.slug} type="button" className="btn btn-ghost btn-sm" onClick={() => elegir(c.slug)}>
            <Ic n="ubicacion" s={14} /> {nombreCiudad(c)}
          </button>
        ))}
      </div>
    </div>
  );
}
