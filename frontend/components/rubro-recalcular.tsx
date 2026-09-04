"use client";

import { useEffect, useState } from "react";
import {
  sugerenciasDeRubro, revisarRubro,
  type SugerenciasRubro, type RubroSimple,
} from "@/lib/api";

/**
 * Recalcular el rubro de un comercio desde su fila, sin salir de la lista.
 *
 * EL PROBLEMA QUE RESUELVE NO ES CLASIFICAR: ES ELEGIR
 * ====================================================
 * Son 56 rubros. Corregir uno significaba abrir la ficha, desplegar una lista
 * larga y buscar a ojo — cuarenta veces seguidas. Eso no se termina: se
 * abandona a la mitad, y una cola que no baja se deja de mirar.
 *
 * Acá las opciones vienen propuestas y se aplican con un toque. La lista
 * completa sigue estando, pero como salida de emergencia y con buscador, no
 * como el camino normal.
 *
 * DOS OPINIONES, SEPARADAS
 * ========================
 * El **diccionario** es lo que clasifica de verdad: si dice "hospedaje", el
 * próximo comercio con ese texto va a caer solo en hospedaje. La **IA** es una
 * segunda opinión, útil sobre todo cuando el diccionario no dice nada.
 *
 * Mostrarlas mezcladas taparía el caso importante —el diccionario no sabe— que
 * es justo el que indica qué palabra hay que agregar.
 *
 * Y arriba de todo, el TEXTO que se está clasificando: es lo que explica el
 * error. "Hotel Reina" cayó en blanquería porque la foto describía sábanas.
 */
export function RubroRecalcular({ comercioId, nombre, rubroActual, rubros, onListo, onCerrar }: {
  comercioId: string;
  nombre: string;
  /** El rubro que la ficha muestra hoy: lo que la persona tiene a la vista. */
  rubroActual: string | null;
  rubros: RubroSimple[];
  onListo: (rubroNuevo: string, nombreNuevo: string) => void;
  onCerrar: () => void;
}) {
  const [d, setD] = useState<SugerenciasRubro | null>(null);
  const [err, setErr] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [filtro, setFiltro] = useState("");
  const [palabras, setPalabras] = useState("");

  useEffect(() => {
    let vigente = true;
    sugerenciasDeRubro(comercioId)
      .then((r) => { if (vigente) { setD(r); setErr(""); } })
      .catch((e) => { if (vigente) setErr(e instanceof Error ? e.message : "No se pudo calcular"); });
    return () => { vigente = false; };
  }, [comercioId]);

  async function aplicar(slug: string, nombreRubro: string) {
    setGuardando(true);
    try {
      await revisarRubro(comercioId, {
        veredicto: "corregido",
        rubro_slug: slug,
        rubro_antes: rubroActual,
        palabras: palabras.trim() || undefined,
      });
      onListo(slug, nombreRubro);
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

  return (
    <div style={{ marginTop: 10, padding: "12px 14px", borderRadius: 12,
                  border: "1px solid var(--border)", background: "var(--bg-2, transparent)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <b style={{ fontSize: 13 }}>Recalcular rubro · {nombre}</b>
        <button className="btn btn-ghost btn-sm" onClick={onCerrar}>Cerrar</button>
      </div>

      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 8 }}>{err}</div>}
      {!d && !err && <div style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 8 }}>Calculando…</div>}

      {d && (
        <>
          {/* El texto que se juzga. Sin esto la corrección es a ciegas y el
              mismo error vuelve mañana con otro comercio. */}
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8,
                        padding: "6px 8px", borderRadius: 8, border: "1px solid var(--border)" }}>
            Se clasifica con: {d.texto?.slice(0, 260) || "— sin texto —"}
          </div>

          <div style={{ fontSize: 12.5, marginTop: 10 }}>
            <span style={{ color: "var(--txt-3)" }}>Hoy está en </span>
            <b style={{ color: "var(--amber)" }}>{rubroActual || "—"}</b>
          </div>

          {/* 1) El diccionario: lo que va a pasar solo de acá en adelante. */}
          <div style={{ marginTop: 10 }}>
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 4 }}>
              El diccionario dice {d.diccionario.length === 0 && "— nada. Ninguna palabra guardada alcanza a este texto."}
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {d.diccionario.map((r) => (
                <button key={r.slug} className="btn btn-primary btn-sm" disabled={guardando}
                        onClick={() => aplicar(r.slug, r.nombre)}>
                  {r.nombre}
                </button>
              ))}
            </div>
          </div>

          {/* 2) La IA: segunda opinión, y explica. */}
          {d.ia && (
            <div style={{ marginTop: 10 }}>
              <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 4 }}>
                La IA propone
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {d.ia.rubros.map((r) => (
                  <button key={r.slug} className="btn btn-ghost btn-sm" disabled={guardando}
                          onClick={() => aplicar(r.slug, r.nombre)}>
                    ✨ {r.nombre}
                  </button>
                ))}
              </div>
              {d.ia.motivo && (
                <div style={{ fontSize: 11.5, color: "var(--txt-2)", marginTop: 5, fontStyle: "italic" }}>
                  “{d.ia.motivo}”
                </div>
              )}
            </div>
          )}

          {!d.ia && (
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 8 }}>
              La IA no contestó (sin clave configurada o falló). El diccionario alcanza igual.
            </div>
          )}

          {/* 3) La palabra: lo único que hace que esto sirva para el próximo. */}
          <label style={{ fontSize: 11.5, color: "var(--txt-3)", display: "block", marginTop: 12 }}>
            Palabra para el diccionario <span style={{ opacity: .7 }}>(opcional, se guarda con la corrección)</span>
            <input className="adm-input" style={{ marginTop: 4 }} value={palabras}
                   placeholder="taller de motos, motos"
                   onChange={(e) => setPalabras(e.target.value)} />
          </label>

          {/* 4) La lista completa, como salida de emergencia y con buscador: el
              camino normal son los botones de arriba. */}
          <label style={{ fontSize: 11.5, color: "var(--txt-3)", display: "block", marginTop: 10 }}>
            ¿Es otro? Buscalo
            <input className="adm-input" style={{ marginTop: 4 }} value={filtro}
                   placeholder="escribí para filtrar los 56 rubros"
                   onChange={(e) => setFiltro(e.target.value)} />
          </label>
          {filtrados.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6,
                          maxHeight: 120, overflowY: "auto" }}>
              {filtrados.slice(0, 20).map((r) => (
                <button key={r.slug} className="btn btn-ghost btn-sm" disabled={guardando}
                        onClick={() => aplicar(r.slug, r.nombre)}>
                  {r.nombre}
                </button>
              ))}
            </div>
          )}

          <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
            <button className="btn btn-ghost btn-sm" disabled={guardando} onClick={confirmar}>
              ✓ Está bien como está
            </button>
          </div>
          <div style={{ fontSize: 11, color: "var(--txt-3)", marginTop: 6 }}>
            Cualquiera de las dos cosas marca el comercio como revisado por una persona,
            y ninguna corrida masiva lo vuelve a tocar.
          </div>
        </>
      )}
    </div>
  );
}
