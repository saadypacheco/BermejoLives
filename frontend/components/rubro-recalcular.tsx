"use client";

import { useEffect, useState } from "react";
import {
  sugerenciasDeRubro, revisarRubro,
  type SugerenciasRubro, type RubroSimple,
} from "@/lib/api";

/**
 * Recalcular los rubros de un comercio desde su fila, sin salir de la lista.
 *
 * VARIOS RUBROS, Y EL ORDEN IMPORTA
 * =================================
 * Un comercio casi nunca es una sola cosa. El puesto de coca machucada también
 * vende bebidas y golosinas: dejarlo en un solo rubro lo saca de las otras dos
 * búsquedas, y son búsquedas que la gente hace.
 *
 * Por eso se marcan todos los que correspondan y el ORDEN es la respuesta:
 *
 *   1º  el PRINCIPAL — el que sale en la ficha, el color del pin en el mapa y
 *       el que decide en qué categoría aparece.
 *   2º… los demás — no se ven en la ficha, pero el buscador lo encuentra por
 *       ellos.
 *
 * Se guarda con un botón, no al tocar cada rubro: elegir tres cosas y que la
 * ventana se cierre en la primera es lo que hacía imposible dejarlo multirubro.
 *
 * LO QUE SE MUESTRA ARRIBA, Y QUÉ SIGNIFICA
 * =========================================
 * "Por sus palabras" es lo que el sistema deduce SOLO, sin IA, buscando en el
 * texto del comercio las palabras del diccionario. Importa más que la IA: eso
 * es lo que va a pasar automáticamente con el próximo comercio parecido. Si ahí
 * no aparece nada, ninguna palabra guardada alcanza este texto — y ésa es la
 * señal de que hay que agregar una.
 *
 * "La IA propone" es una segunda opinión, y explica en una frase. Sirve sobre
 * todo cuando lo de arriba viene vacío.
 */
export function RubroRecalcular({ comercioId, nombre, rubroActual, rubros, onListo, onCerrar }: {
  comercioId: string;
  nombre: string;
  /** El principal de hoy: lo que la persona tiene a la vista en la fila. */
  rubroActual: string | null;
  rubros: RubroSimple[];
  onListo: (resumen: string) => void;
  onCerrar: () => void;
}) {
  const [d, setD] = useState<SugerenciasRubro | null>(null);
  const [err, setErr] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [filtro, setFiltro] = useState("");
  const [palabras, setPalabras] = useState("");
  /** Los elegidos, EN ORDEN. El primero es el principal. */
  const [sel, setSel] = useState<string[]>([]);

  useEffect(() => {
    let vigente = true;
    sugerenciasDeRubro(comercioId)
      .then((r) => {
        if (!vigente) return;
        setD(r);
        // Arranca con lo que el comercio YA tiene, con el principal adelante:
        // así el trabajo es ajustar, no rearmar desde cero.
        const yaTiene = r.ya_tiene.map((x) => x.slug);
        const orden = rubroActual && yaTiene.includes(rubroActual)
          ? [rubroActual, ...yaTiene.filter((s) => s !== rubroActual)]
          : yaTiene;
        setSel(orden);
        setErr("");
      })
      .catch((e) => { if (vigente) setErr(e instanceof Error ? e.message : "No se pudo calcular"); });
    return () => { vigente = false; };
  }, [comercioId, rubroActual]);

  const nombreDe = (slug: string) =>
    rubros.find((r) => r.slug === slug)?.nombre ?? slug;

  function alternar(slug: string) {
    setSel((prev) => prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]);
  }

  /** Lo pone primero: pasa a ser el principal sin sacarlo de la lista. */
  function hacerPrincipal(slug: string) {
    setSel((prev) => [slug, ...prev.filter((s) => s !== slug)]);
  }

  async function guardar() {
    if (sel.length === 0) return;
    setGuardando(true);
    try {
      await revisarRubro(comercioId, {
        veredicto: "corregido",
        rubro_slugs: sel,
        rubro_antes: rubroActual,
        palabras: palabras.trim() || undefined,
      });
      onListo(sel.map(nombreDe).join(" + "));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
      setGuardando(false);
    }
  }

  async function confirmar() {
    setGuardando(true);
    try {
      await revisarRubro(comercioId, { veredicto: "ok", rubro_antes: rubroActual });
      onCerrar();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
      setGuardando(false);
    }
  }

  const filtrados = filtro.trim()
    ? rubros.filter((r) => r.nombre.toLowerCase().includes(filtro.trim().toLowerCase()))
    : [];

  /** Un rubro proponible: tocarlo lo suma o lo saca de la selección. */
  const Chip = ({ slug, icono }: { slug: string; icono?: string }) => {
    const puesto = sel.indexOf(slug);
    return (
      <button type="button" disabled={guardando} onClick={() => alternar(slug)}
              className={`btn btn-sm ${puesto >= 0 ? "btn-primary" : "btn-ghost"}`}>
        {puesto === 0 && "★ "}
        {puesto > 0 && `${puesto + 1}. `}
        {icono}{icono ? " " : ""}{nombreDe(slug)}
      </button>
    );
  };

  return (
    <div style={{ marginTop: 10, padding: "12px 14px", borderRadius: 12,
                  border: "1px solid var(--border)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <b style={{ fontSize: 13 }}>Rubros de {nombre}</b>
        <button className="btn btn-ghost btn-sm" onClick={onCerrar}>Cerrar</button>
      </div>

      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 8 }}>{err}</div>}
      {!d && !err && <div style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 8 }}>Calculando…</div>}

      {d && (
        <>
          {/* Lo elegido, arriba de todo: es el resultado, y decir cuál es el
              principal con palabras evita tener que adivinar qué significa el
              orden. */}
          <div style={{ marginTop: 10, padding: "8px 10px", borderRadius: 8,
                        border: "1px solid var(--border)" }}>
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 6 }}>
              Va a quedar así {sel.length > 1 && <>· tocá <b>★</b> para cambiar cuál es el principal</>}
            </div>
            {sel.length === 0 ? (
              <div style={{ fontSize: 12.5, color: "var(--amber)" }}>
                Sin ningún rubro. Elegí al menos uno abajo.
              </div>
            ) : (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
                {sel.map((s, i) => (
                  <span key={s} style={{ display: "inline-flex", alignItems: "center", gap: 4,
                                         fontSize: 12.5, padding: "3px 8px", borderRadius: 999,
                                         border: "1px solid var(--border)" }}>
                    {i === 0
                      ? <b style={{ color: "var(--neon)" }}>★ {nombreDe(s)}</b>
                      : (
                        <>
                          <button type="button" title="Hacerlo principal" onClick={() => hacerPrincipal(s)}
                                  style={{ background: "none", border: 0, cursor: "pointer",
                                           color: "var(--txt-3)", padding: 0 }}>☆</button>
                          {nombreDe(s)}
                        </>
                      )}
                    <button type="button" title="Sacar" onClick={() => alternar(s)}
                            style={{ background: "none", border: 0, cursor: "pointer",
                                     color: "var(--txt-3)", padding: 0 }}>×</button>
                  </span>
                ))}
              </div>
            )}
            <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 6 }}>
              El <b>★ principal</b> es el que se ve en la ficha, el color del pin y el filtro.
              Los demás no se ven, pero el buscador lo encuentra por ellos.
            </div>
          </div>

          {/* El texto que se juzga: es lo que explica el error. */}
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 10,
                        padding: "6px 8px", borderRadius: 8, border: "1px solid var(--border)" }}>
            Se clasifica con este texto: {d.texto?.slice(0, 260) || "— no hay texto —"}
          </div>

          <div style={{ fontSize: 12, marginTop: 8 }}>
            <span style={{ color: "var(--txt-3)" }}>Antes de tocar nada estaba en </span>
            <b style={{ color: "var(--amber)" }}>{rubroActual ? nombreDe(rubroActual) : "—"}</b>
          </div>

          {/* 1) El diccionario: lo que el sistema deduce SOLO. */}
          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 4 }}>
              <b>Por sus palabras</b> — lo que el sistema deduce solo, sin IA
            </div>
            {d.diccionario.length === 0 ? (
              <div style={{ fontSize: 12, color: "var(--amber)" }}>
                Ninguna palabra guardada alcanza este texto. Por eso quedó mal clasificado, y
                por eso conviene escribir una abajo.
              </div>
            ) : (
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {d.diccionario.map((r) => <Chip key={r.slug} slug={r.slug} />)}
              </div>
            )}
          </div>

          {/* 2) La IA: segunda opinión, y explica. */}
          {d.ia ? (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 4 }}>
                <b>La IA propone</b> — segunda opinión, no cambia cómo clasifica el sistema
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {d.ia.rubros.map((r) => <Chip key={r.slug} slug={r.slug} icono="✨" />)}
              </div>
              {d.ia.motivo && (
                <div style={{ fontSize: 11.5, color: "var(--txt-2)", marginTop: 5, fontStyle: "italic" }}>
                  “{d.ia.motivo}”
                </div>
              )}
            </div>
          ) : (
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 10 }}>
              La IA no contestó (sin clave o falló). Lo de arriba alcanza igual.
            </div>
          )}

          {/* 3) La lista completa, con buscador: para lo que nadie propuso. */}
          <label style={{ fontSize: 11.5, color: "var(--txt-3)", display: "block", marginTop: 12 }}>
            ¿Falta alguno? Buscalo entre los {rubros.length}
            <input className="adm-input" style={{ marginTop: 4 }} value={filtro}
                   placeholder="escribí para filtrar"
                   onChange={(e) => setFiltro(e.target.value)} />
          </label>
          {filtrados.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6,
                          maxHeight: 130, overflowY: "auto" }}>
              {filtrados.slice(0, 24).map((r) => <Chip key={r.slug} slug={r.slug} />)}
            </div>
          )}

          {/* 4) La palabra: lo único que sirve para el PRÓXIMO comercio. */}
          <label style={{ fontSize: 11.5, color: "var(--txt-3)", display: "block", marginTop: 12 }}>
            Palabra para el diccionario <span style={{ opacity: .7 }}>(opcional — se guarda con el rubro ★)</span>
            <input className="adm-input" style={{ marginTop: 4 }} value={palabras}
                   placeholder="ej.: taller de motos, mecánica de motos"
                   onChange={(e) => setPalabras(e.target.value)} />
          </label>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 5 }}>
            Corregir arregla ESTE comercio; la palabra arregla todos los que vengan. Van las
            formas compuestas, que nombran el negocio y no el producto suelto: “pollo” lo vende
            media comida rápida y “bar” está dentro de “barbería”.
          </div>

          <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button className="btn btn-primary btn-sm" disabled={guardando || sel.length === 0}
                    onClick={guardar}>
              Guardar {sel.length > 1 ? `los ${sel.length} rubros` : "el rubro"}
            </button>
            <button className="btn btn-ghost btn-sm" disabled={guardando} onClick={confirmar}>
              ✓ Ya estaba bien, no tocar
            </button>
          </div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 6 }}>
            Cualquiera de las dos marca el comercio como revisado por una persona, y ninguna
            corrida masiva lo vuelve a tocar.
          </div>
        </>
      )}
    </div>
  );
}
