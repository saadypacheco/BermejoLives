"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRevisionRubros, revisarRubro, recalcularPrincipal,
  type FilaRevision, type ResumenRevision, type RubroSimple, type RecalculoPrincipal,
} from "@/lib/api";
import { RubroRecalcular } from "@/components/rubro-recalcular";

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
  // Cuál tiene el editor abierto. Uno por vez: dos formularios abiertos en una
  // cola de 200 filas es cómo se termina guardando el rubro de otro comercio.
  const [editando, setEditando] = useState<string | null>(null);
  // La vista previa del recálculo. `null` = todavía no se pidió.
  const [prev, setPrev] = useState<RecalculoPrincipal | null>(null);
  const [corriendo, setCorriendo] = useState(false);
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
      setEditando(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  const nombreDe = (slug: string) => rubros.find((r) => r.slug === slug)?.nombre ?? slug;

  async function verQueCambiaria() {
    setCorriendo(true); setErr("");
    try { setPrev(await recalcularPrincipal(false)); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo calcular"); }
    finally { setCorriendo(false); }
  }

  async function aplicarRecalculo() {
    if (!prev) return;
    if (!confirm(
      `Se va a cambiar el rubro principal de ${prev.candidatos} comercios.

` +
      `Sólo los que tienen UNA sugerencia. Los ${prev.ambiguos} con dos o más ` +
      `quedan en la cola para revisar a mano.

No se borra ningún rubro: ` +
      `los que ya tenían quedan como secundarios.

¿Seguimos?`)) return;
    setCorriendo(true); setErr("");
    try { setPrev(await recalcularPrincipal(true)); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo aplicar"); }
    finally { setCorriendo(false); }
  }

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

      {/* El atajo que resuelve la mitad de la cola sin decidir nada.
          Va acá arriba y con vista previa obligatoria: escribe sobre cien
          fichas de una, y la única forma honesta de ofrecer eso es mostrar
          antes la lista exacta de lo que va a cambiar. */}
      {estado === "dudosos" && (
        <div className="panel-card glass" style={{ padding: 14 }}>
          <div style={{ fontSize: 12.5 }}>
            <b>Los que no tienen nada que decidir</b>
            <div style={{ color: "var(--txt-3)", marginTop: 4 }}>
              Cuando el texto dispara <b>un solo</b> rubro y la ficha muestra otro, no falta
              criterio: falta escribirlo. Con dos o más sugerencias no se toca nada — el
              diccionario las devuelve en orden alfabético, así que “la primera” no quiere
              decir nada, y elegir entre tres es tu decisión.
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            <button className="btn btn-ghost btn-sm" disabled={corriendo} onClick={verQueCambiaria}>
              Ver qué cambiaría
            </button>
            {prev && !prev.aplicado && prev.candidatos > 0 && (
              <button className="btn btn-primary btn-sm" disabled={corriendo} onClick={aplicarRecalculo}>
                Aplicar los {prev.candidatos}
              </button>
            )}
          </div>

          {prev && (
            <div style={{ marginTop: 10, fontSize: 12.5 }}>
              {prev.aplicado ? (
                <div style={{ color: "var(--neon)" }}>
                  Listo: {prev.cambiados} comercios con el principal corregido.
                  Quedan {prev.ambiguos} para revisar a mano, abajo.
                </div>
              ) : (
                <div>
                  <b>{prev.candidatos}</b> cambiarían · <b>{prev.ambiguos}</b> quedan para vos
                  {prev.salteados.length > 0 && (
                    <span style={{ color: "var(--amber)" }}>
                      {" "}· {prev.salteados.length} salteados por tener ya 6 rubros
                    </span>
                  )}
                </div>
              )}

              {!prev.aplicado && prev.detalle.length > 0 && (
                <div style={{ marginTop: 8, maxHeight: 260, overflowY: "auto",
                              border: "1px solid var(--border)", borderRadius: 8, padding: 8 }}>
                  <div style={{ fontSize: 11, color: "var(--txt-3)", paddingBottom: 5,
                                borderBottom: "1px solid var(--border)", marginBottom: 5 }}>
                    Comercio · <span style={{ color: "var(--amber)" }}>rubro que tiene hoy</span> →{" "}
                    <span style={{ color: "var(--neon)" }}>al que pasa</span> · con qué texto se dedujo
                  </div>
                  {prev.detalle.map((x) => (
                    <div key={x.comercio_id} style={{ padding: "3px 0", color: "var(--txt-2)" }}>
                      <b>{x.nombre || "Comercio"}</b>{" "}
                      <span style={{ color: "var(--amber)" }}>{x.de}</span>
                      {" → "}
                      <span style={{ color: "var(--neon)" }}>{nombreDe(x.a)}</span>
                      <span style={{ color: "var(--txt-3)" }}> — {x.texto}</span>
                    </div>
                  ))}
                  {prev.detalle_recortado > 0 && (
                    <div style={{ color: "var(--txt-3)", marginTop: 4 }}>
                      …y {prev.detalle_recortado} más que no entran en esta lista.
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

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
                {/* Un toque y listo. En la mayoría de los casos el diccionario
                    ya acertó, y obligar a abrir un formulario para confirmarlo
                    convierte una cola de 200 en una tarde. */}
                {f.sugeridos.slice(0, 3).map((s) => (
                  <button key={s} className="btn btn-ghost btn-sm" disabled={guardando}
                          onClick={() => corregirA(f, s)}>
                    → {nombreDe(s)}
                  </button>
                ))}
                {/* Los atajos de arriba sólo SUMAN un rubro. Cuando hay que
                    sacar alguno —"quitá supermercado y café, dejá el resto"—
                    hace falta el editor completo, que es el mismo de la lista
                    de Negocios: casillas, orden y la ★ del principal. Tener dos
                    editores distintos para lo mismo era la mitad del problema. */}
                <button className="btn btn-ghost btn-sm" disabled={guardando}
                        onClick={() => setEditando(editando === f.comercio_id ? null : f.comercio_id)}>
                  ✏️ Editar los rubros
                </button>
              </div>

              {editando === f.comercio_id && (
                <RubroRecalcular
                  comercioId={f.comercio_id}
                  nombre={f.nombre || "Comercio"}
                  rubroActual={f.principal}
                  rubros={rubros}
                  onListo={() => { sacarDeLaLista(f.comercio_id); setEditando(null); }}
                  onCerrar={() => setEditando(null)}
                />
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
