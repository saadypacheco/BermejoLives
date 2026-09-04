"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRevisionRubros, revisarRubro,
  type FilaRevision, type ResumenRevision, type RubroSimple,
} from "@/lib/api";

/**
 * Revisar la clasificación de a uno, con una persona decidiendo.
 *
 * POR QUÉ NO ES UN BOTÓN QUE ARREGLA TODO
 * =======================================
 * El botón existe y sería una línea: recalcular el principal de los 229 que no
 * cierran. No se hace porque no habría forma de distinguir sus cambios de las
 * +200 correcciones hechas a mano — el trabajo de semanas desaparecería sin dar
 * un error, y nadie se enteraría hasta abrir una ficha suelta.
 *
 * QUÉ SE VE, Y POR QUÉ ESO
 * ========================
 * El TEXTO que se clasificó, arriba de todo. Es la única forma de entender por
 * qué el clasificador dijo lo que dijo: "Hotel Reina" cayó en blanquería porque
 * la foto describía sábanas y toallas. Sin el texto a la vista, la corrección es
 * a ciegas y se repite mañana.
 *
 * Y AL LADO, LO QUE APRENDE
 * =========================
 * Acá no hay ningún modelo que aprenda solo: el clasificador es un diccionario
 * de palabras (`rubro_palabras`) y "aprender" significa escribir en él. Por eso
 * al corregir se puede mandar la palabra que lo hubiera clasificado bien — una
 * corrección arregla un comercio, una palabra arregla todos los que vengan.
 */
export function RevisionRubros() {
  const [estado, setEstado] = useState<"dudosos" | "sin-datos">("dudosos");
  const [items, setItems] = useState<FilaRevision[]>([]);
  const [resumen, setResumen] = useState<ResumenRevision>({});
  const [rubros, setRubros] = useState<RubroSimple[]>([]);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  // Cuál está abierto para corregir, y con qué. Uno por vez: dos formularios
  // abiertos en una cola de 200 filas es cómo se termina guardando el rubro de
  // otro comercio.
  const [editando, setEditando] = useState<string | null>(null);
  const [elegido, setElegido] = useState("");
  const [palabras, setPalabras] = useState("");
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true);
    try {
      const d = await getRevisionRubros(estado, 100);
      setItems(d.items ?? []);
      setResumen(d.resumen ?? {});
      setRubros(d.rubros ?? []);
      setErr("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo cargar la cola");
    } finally {
      setCargando(false);
    }
  }, [estado]);

  useEffect(() => { cargar(); }, [cargar]);

  /** Saca la fila de la lista sin recargar todo: la cola tiene 100 filas y
   *  recargarla en cada veredicto hace perder el lugar donde ibas. */
  function sacarDeLaLista(comercioId: string) {
    setItems((prev) => prev.filter((i) => i.comercio_id !== comercioId));
    setResumen((r) => ({
      ...r,
      revisados: (r.revisados ?? 0) + 1,
      ...(estado === "dudosos"
        ? { dudosos: Math.max(0, (r.dudosos ?? 1) - 1) }
        : { sin_datos: Math.max(0, (r.sin_datos ?? 1) - 1) }),
    }));
  }

  async function marcarOk(f: FilaRevision) {
    setGuardando(true);
    try {
      await revisarRubro(f.comercio_id, { veredicto: "ok", rubro_antes: f.principal });
      sacarDeLaLista(f.comercio_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  async function corregirA(f: FilaRevision, slug: string, conPalabras?: string) {
    setGuardando(true);
    try {
      await revisarRubro(f.comercio_id, {
        veredicto: "corregido",
        rubro_slug: slug,
        rubro_antes: f.principal,
        palabras: conPalabras?.trim() || undefined,
      });
      sacarDeLaLista(f.comercio_id);
      setEditando(null); setElegido(""); setPalabras("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  const nombreDe = (slug: string) => rubros.find((r) => r.slug === slug)?.nombre ?? slug;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      <div className="panel-card glass">
        <div className="ph">
          <h3>Revisar la clasificación</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
            {resumen.revisados ?? 0} revisados de {resumen.total ?? 0}
          </span>
        </div>

        <p style={{ padding: "10px 16px 0", margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>
          El rubro principal se fija en el alta y no se recalcula nunca: los rubros
          creados después no llegan a los comercios cargados antes. Acá están los que
          <b> no cierran</b> — el resto ya coincide con lo que el diccionario diría hoy,
          y no hace falta mirarlos.
        </p>

        <div style={{ display: "flex", gap: 8, padding: "12px 16px" }}>
          <button className={`btn btn-sm ${estado === "dudosos" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setEstado("dudosos")}>
            No cierran {resumen.dudosos != null && <>({resumen.dudosos})</>}
          </button>
          <button className={`btn btn-sm ${estado === "sin-datos" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setEstado("sin-datos")}>
            Sin datos {resumen.sin_datos != null && <>({resumen.sin_datos})</>}
          </button>
        </div>

        {estado === "sin-datos" && (
          <p style={{ padding: "0 16px 12px", margin: 0, fontSize: 12, color: "var(--amber)" }}>
            Estos no producen ninguna sugerencia: no les falta clasificación, les falta
            texto (nadie describió lo que venden) o falta el rubro. No se resuelven con
            un clic.
          </p>
        )}
      </div>

      {cargando && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          Cargando…
        </div>
      )}

      {!cargando && items.length === 0 && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          No queda nada por revisar acá. 🎉
        </div>
      )}

      {items.map((f) => (
        <div key={f.comercio_id} className="panel-card glass" style={{ padding: 14 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
            {f.portada && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={f.portada} alt="" width={64} height={64}
                   style={{ borderRadius: 8, objectFit: "cover", flexShrink: 0 }} />
            )}
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
                <b>{f.nombre || "Sin nombre"}</b>
                <span style={{ color: "var(--txt-3)", fontSize: 12 }}>{f.codigo}</span>
              </div>

              <div style={{ fontSize: 12.5, marginTop: 6 }}>
                <span style={{ color: "var(--txt-3)" }}>Está en </span>
                <b style={{ color: "var(--amber)" }}>{f.principal_nombre || f.principal || "—"}</b>
                {f.sugeridos.length > 0 && (
                  <>
                    <span style={{ color: "var(--txt-3)" }}> · el diccionario dice </span>
                    <b style={{ color: "var(--neon)" }}>
                      {f.sugeridos.map(nombreDe).join(", ")}
                    </b>
                  </>
                )}
              </div>

              {/* El texto que se juzgó. Es lo que explica el error: sin esto, la
                  corrección es a ciegas y el mismo caso vuelve mañana. */}
              {f.texto && (
                <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6,
                              padding: "6px 8px", borderRadius: 8,
                              border: "1px solid var(--border)" }}>
                  {f.texto.slice(0, 240)}{f.texto.length > 240 ? "…" : ""}
                </div>
              )}

              {f.ya_tiene.length > 1 && (
                <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 5 }}>
                  Ya tiene: {f.ya_tiene.map(nombreDe).join(" · ")}
                </div>
              )}

              <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
                <button className="btn btn-ghost btn-sm" disabled={guardando} onClick={() => marcarOk(f)}>
                  ✓ Está bien
                </button>
                {/* Los sugeridos como atajo: en la mayoría de los casos el
                    diccionario ya acertó y el trabajo es un solo toque. */}
                {/* Un toque y listo. En la mayoría de los casos el diccionario
                    ya acertó, y obligar a abrir un formulario para confirmarlo
                    convierte una cola de 200 en una tarde. */}
                {f.sugeridos.slice(0, 3).map((s) => (
                  <button key={s} className="btn btn-ghost btn-sm" disabled={guardando}
                          onClick={() => corregirA(f, s)}>
                    → {nombreDe(s)}
                  </button>
                ))}
                <button className="btn btn-ghost btn-sm" disabled={guardando}
                        onClick={() => {
                          setEditando(editando === f.comercio_id ? null : f.comercio_id);
                          setElegido(""); setPalabras("");
                        }}>
                  Es otro…
                </button>
              </div>

              {editando === f.comercio_id && (
                <div style={{ marginTop: 10, padding: "10px 12px", borderRadius: 10,
                              border: "1px solid var(--border)" }}>
                  <label style={{ fontSize: 12, color: "var(--txt-3)" }}>
                    Rubro correcto
                    <select className="adm-input" style={{ marginTop: 4 }} value={elegido}
                            onChange={(e) => setElegido(e.target.value)}>
                      <option value="">Elegir…</option>
                      {rubros.map((r) => (
                        <option key={r.slug} value={r.slug}>{r.nombre}</option>
                      ))}
                    </select>
                  </label>

                  <label style={{ fontSize: 12, color: "var(--txt-3)", display: "block", marginTop: 8 }}>
                    Palabra que lo hubiera clasificado bien <span style={{ opacity: .7 }}>(opcional)</span>
                    <input className="adm-input" style={{ marginTop: 4 }} value={palabras}
                           placeholder="taller de motos, motos"
                           onChange={(e) => setPalabras(e.target.value)} />
                  </label>
                  <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 6 }}>
                    Esto es lo que hace que la corrección sirva para el próximo. Van las
                    formas compuestas, que nombran el negocio y no el producto suelto:
                    &ldquo;pollo&rdquo; lo vende media comida rápida y &ldquo;bar&rdquo; está
                    dentro de &ldquo;barbería&rdquo;. Si dudás del alcance, agregala desde
                    <b> Rubros → vista previa</b>, que cuenta a cuántos llega antes de guardarla.
                  </div>

                  <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                    <button className="btn btn-primary btn-sm" disabled={!elegido || guardando}
                            onClick={() => corregirA(f, elegido, palabras)}>
                      Guardar corrección
                    </button>
                    <button className="btn btn-ghost btn-sm" disabled={guardando}
                            onClick={() => { setEditando(null); setElegido(""); setPalabras(""); }}>
                      Cancelar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
