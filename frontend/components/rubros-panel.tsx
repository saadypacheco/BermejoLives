"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getRubrosPropuestos, crearRubro, agregarPalabrasRubro, completarRubros,
  previsualizarPalabras, aplicarPatron,
  type PropuestaRubro, type RubroSimple, type InformeRubros, type PreviewPalabras,
} from "@/lib/api";

/** "Carnicería y pollería" → "carniceria-y-polleria". */
function aSlug(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40);
}

export function RubrosPanel() {
  const [data, setData] = useState<{ propuestas: PropuestaRubro[]; rubros: RubroSimple[] } | null>(null);
  const [err, setErr] = useState("");
  const [abierta, setAbierta] = useState<string | null>(null);
  const [informe, setInforme] = useState<InformeRubros | null>(null);
  const [corriendo, setCorriendo] = useState(false);

  const cargar = useCallback(async () => {
    // `?? []` a propósito: si la respuesta viene sin el campo —una ruta
    // duplicada devolviendo otra forma, como pasó— el panel se dibuja vacío en
    // vez de tirar abajo el /admin entero al leer `.length` de undefined.
    try {
      const d = await getRubrosPropuestos();
      setData({ propuestas: d.propuestas ?? [], rubros: d.rubros ?? [] });
      setErr("");
    }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
  }, []);
  useEffect(() => { cargar(); }, [cargar]);

  async function simular() {
    setCorriendo(true); setErr("");
    try { setInforme(await completarRubros(false)); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo analizar"); setInforme(null); }
    finally { setCorriendo(false); }
  }

  async function aplicar() {
    if (!informe) return;
    if (!confirm(
      `Se van a agregar ${informe.rubros_a_agregar} rubros en ` +
      `${informe.comercios_a_completar} comercios.\n\n` +
      `Sólo SUMA rubros: no quita ninguno de los que ya tienen. ` +
      `Si alguno sobra se saca después desde la ficha.\n\n¿Seguimos?`)) return;
    setCorriendo(true); setErr("");
    try { setInforme(await completarRubros(true)); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo aplicar"); }
    finally { setCorriendo(false); }
  }

  if (!data) {
    return <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
      {err || "Cargando…"}
    </div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      {/* 1) QUÉ FALTA, medido.
          Estas son las categorías que la IA pidió mirando vidrieras reales y no
          existían. Cada fila puede ser dos cosas muy distintas —un rubro que
          falta, u otra forma de decir uno que ya existe— y confundirlas es cómo
          se llega a rubros vacíos que después hay que apagar. Por eso hay dos
          botones y no uno. */}
      <div className="panel-card glass">
        <div className="ph">
          <h3>Categorías que la IA pidió y no existen</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>{data.propuestas.length} sin resolver</span>
        </div>
        <p style={{ padding: "10px 16px 0", margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>
          Salen de vidrieras reales, ordenadas por cuántas veces se pidieron. Cada una es
          un rubro que falta <b>o</b> sólo otra forma de decir uno que ya existe —
          &ldquo;lubricentro&rdquo; es neumáticos, &ldquo;bijouterie&rdquo; es joyería—.
          Crear un rubro por cada nombre distinto es cómo se llega a rubros vacíos.
        </p>

        {data.propuestas.length === 0 && (
          <div style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
            Nada pendiente. Vuelve a llenarse sola cuando la IA analice comercios nuevos.
          </div>
        )}

        {data.propuestas.map((p) => (
          <div key={p.normalizado} style={{ borderBottom: "1px solid var(--border)" }}>
            <div style={{ display: "flex", gap: 12, alignItems: "center", padding: "10px 16px", flexWrap: "wrap" }}>
              <b style={{ fontSize: 14.5, flex: "1 1 180px" }}>{p.normalizado}</b>
              <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
                {p.veces} {p.veces === 1 ? "vez" : "veces"}
              </span>
              <button className="btn btn-ghost btn-sm"
                onClick={() => setAbierta(abierta === p.normalizado ? null : p.normalizado)}>
                {abierta === p.normalizado ? "Cerrar" : "Resolver"}
              </button>
            </div>
            {abierta === p.normalizado && (
              <Resolver propuesta={p} rubros={data.rubros}
                onListo={() => { setAbierta(null); cargar(); }}
                onError={setErr} />
            )}
          </div>
        ))}
      </div>

      {/* 2) APLICAR EL DICCIONARIO.
          Después de crear rubros o agregar palabras, esto es lo que las hace
          efecto sobre los comercios que ya están cargados: el diccionario nuevo
          no reclasifica nada solo. */}
      <div className="panel-card glass">
        <div className="ph">
          <h3>Completar rubros</h3>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={simular} disabled={corriendo}>
              {corriendo ? "Analizando…" : "Analizar"}
            </button>
            {informe && !informe.aplicado && informe.rubros_a_agregar > 0 && (
              <button className="btn btn-primary btn-sm" onClick={aplicar} disabled={corriendo}>
                Aplicar
              </button>
            )}
          </div>
        </div>
        <p style={{ padding: "10px 16px 0", margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>
          Le agrega a cada comercio los rubros que sus productos sugieren y todavía no tiene.
          <b> Sólo suma</b>: nunca quita uno elegido a mano. Después de tocar el diccionario
          hay que correr esto, porque las palabras nuevas no reclasifican nada solas.
        </p>

        {informe && (
          <div style={{ padding: 16 }}>
            {informe.aplicado ? (
              <div style={{ color: "var(--neon)", fontWeight: 700, marginBottom: 10 }}>
                Aplicado: {informe.rubros_agregados} rubros en {informe.comercios_a_completar} comercios.
              </div>
            ) : (
              <div style={{ fontSize: 14, marginBottom: 10 }}>
                <b>{informe.rubros_a_agregar}</b> rubros en <b>{informe.comercios_a_completar}</b> comercios
                {informe.salteados > 0 && (
                  <span style={{ color: "var(--txt-3)" }}>
                    {" "}· {informe.salteados} salteados por quedar con más de 6 rubros
                  </span>
                )}
              </div>
            )}

            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginBottom: 12 }}>
              Leídas {informe.asignaciones_leidas} de {informe.asignaciones_en_tabla} asignaciones
              · {informe.comercios} comercios activos
            </div>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 14 }}>
              {informe.por_rubro.map((r) => (
                <span key={r.slug} className="mchip">{r.slug} <b>{r.comercios}</b></span>
              ))}
            </div>

            {/* El detalle NO es adorno: es lo que permite ver que "papa frita"
                metió un kiosco en comida rápida antes de escribirlo. */}
            <div style={{ maxHeight: 320, overflowY: "auto", fontSize: 12.5 }}>
              {informe.detalle.map((d, i) => (
                <div key={`${d.codigo}-${i}`} style={{ padding: "6px 0", borderTop: "1px solid var(--border)" }}>
                  <span style={{ fontFamily: "monospace", color: "var(--neon)" }}>URUKU-{d.codigo ?? "????"}</span>{" "}
                  <b>{d.nombre || "Comercio"}</b>{" "}
                  <span style={{ color: "var(--amber)" }}>+{d.agregar.join(", ")}</span>
                  <div style={{ color: "var(--txt-3)" }}>vende: {d.vende}</div>
                </div>
              ))}
            </div>
            {informe.detalle_recortado > 0 && (
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>
                … y {informe.detalle_recortado} comercios más, no listados acá.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/** Las dos salidas de una propuesta, una al lado de la otra. */
function Resolver({ propuesta, rubros, onListo, onError }: {
  propuesta: PropuestaRubro;
  rubros: RubroSimple[];
  onListo: () => void;
  onError: (m: string) => void;
}) {
  const [nombre, setNombre] = useState(propuesta.normalizado);
  const [icono, setIcono] = useState("");
  const [comercial, setComercial] = useState(true);
  const [palabras, setPalabras] = useState(propuesta.normalizado);
  const [destino, setDestino] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [prev, setPrev] = useState<PreviewPalabras | null>(null);
  const slug = aSlug(nombre);

  // Se prueba la palabra ANTES de guardarla, y sola: el error que más caro
  // salió del diccionario no fue de criterio sino de alcance — una palabra
  // correcta que además aparece en otro lado. "papa frita" describe bien la
  // comida rápida y está en todos los kioscos.
  //
  // Eso es contable, no opinable, así que lo cuenta una consulta y no un
  // modelo: un modelo puede advertirlo o no; esto acierta siempre.
  useEffect(() => {
    const t = setTimeout(async () => {
      if (!palabras.trim()) { setPrev(null); return; }
      try { setPrev(await previsualizarPalabras(palabras, destino || slug)); }
      catch { setPrev(null); }
    }, 600);
    return () => clearTimeout(t);
  }, [palabras, destino, slug]);

  // Crear el rubro y APLICARLO en el mismo acto, sobre los comercios que la
  // vista previa acaba de mostrar.
  //
  // Antes había que acordarse de ir a "Completar rubros" después. Si nadie lo
  // hacía, el rubro quedaba con cero comercios y parecía roto: el rubro
  // existía, el diccionario existía, y en la fila de chips prometía algo que no
  // había. Nada avisaba — es el mismo silencio de siempre.
  async function nuevo() {
    setOcupado(true);
    try {
      await crearRubro({ slug, nombre, icono: icono || undefined, comercial,
                         palabras, resolver: propuesta.normalizado });
      if (prev && prev.nuevos > 0) {
        const r = await aplicarPatron(slug, palabras);
        if (r.salteados.length > 0) {
          onError(`Rubro creado y aplicado a ${r.agregados}. ` +
                  `${r.salteados.length} quedaron afuera por tener ya 6 rubros: ` +
                  r.salteados.map((x) => x.nombre || x.codigo).join(", "));
        }
      }
      onListo();
    } catch (e) { onError(e instanceof Error ? e.message : "No se pudo crear"); }
    finally { setOcupado(false); }
  }

  async function sinonimo() {
    if (!destino) return;
    setOcupado(true);
    try {
      await agregarPalabrasRubro({ rubro_slug: destino, palabras, resolver: propuesta.normalizado });
      if (prev && prev.nuevos > 0) {
        const r = await aplicarPatron(destino, palabras);
        if (r.salteados.length > 0) {
          onError(`Palabras agregadas y aplicadas a ${r.agregados}. ` +
                  `${r.salteados.length} quedaron afuera por tener ya 6 rubros.`);
        }
      }
      onListo();
    } catch (e) { onError(e instanceof Error ? e.message : "No se pudo guardar"); }
    finally { setOcupado(false); }
  }

  return (
    <div style={{ padding: "4px 16px 16px", display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
      <div>
        <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>Es un rubro nuevo</div>
        <input className="adm-input" value={nombre} onChange={(e) => setNombre(e.target.value)}
               placeholder="Nombre visible" style={{ marginBottom: 6 }} />
        <div style={{ display: "flex", gap: 6, marginBottom: 6 }}>
          <input className="adm-input" style={{ width: 70 }} value={icono}
                 onChange={(e) => setIcono(e.target.value)} placeholder="🥩" />
          <span style={{ alignSelf: "center", fontSize: 11.5, color: "var(--txt-3)",
                         fontFamily: "monospace" }}>{slug}</span>
        </div>
        <label style={{ display: "flex", gap: 7, alignItems: "flex-start", fontSize: 12,
                        color: "var(--txt-3)", marginBottom: 8 }}>
          <input type="checkbox" checked={!comercial} onChange={(e) => setComercial(!e.target.checked)} />
          {/* La bandera existe para que un baño público no quede marcado "sin
              contacto · sin productos" para siempre. */}
          <span>No es un negocio (baño, trámite, plaza): no se le pide WhatsApp ni productos</span>
        </label>
        <button className="btn btn-primary btn-sm" onClick={nuevo} disabled={ocupado || !nombre.trim()}>
          {prev && prev.nuevos > 0 ? `Crear y aplicar a ${prev.nuevos}` : "Crear rubro"}
        </button>
      </div>

      <div>
        <div style={{ fontSize: 12.5, fontWeight: 700, marginBottom: 8 }}>
          Es otra forma de decir uno que existe
        </div>
        <select className="adm-input" value={destino} onChange={(e) => setDestino(e.target.value)}
                style={{ marginBottom: 6 }}>
          <option value="">Elegí el rubro…</option>
          {rubros.map((r) => <option key={r.slug} value={r.slug}>{r.nombre}</option>)}
        </select>
        <button className="btn btn-ghost btn-sm" onClick={sinonimo} disabled={ocupado || !destino}>
          {prev && prev.nuevos > 0 ? `Agregar y aplicar a ${prev.nuevos}` : "Agregar como palabra"}
        </button>
      </div>

      <div style={{ gridColumn: "1 / -1" }}>
        <label style={{ fontSize: 12, color: "var(--txt-3)" }}>
          Palabras que lo detectan (separadas por coma)
          <input className="adm-input" style={{ marginTop: 4 }} value={palabras}
                 onChange={(e) => setPalabras(e.target.value)} />
        </label>
        {/* La lección más cara del diccionario, dicha donde se escribe. */}
        <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 6 }}>
          Van las formas compuestas, que nombran el negocio y no el producto suelto:
          &ldquo;pollo&rdquo; lo vende media comida rápida y &ldquo;bar&rdquo; está dentro de
          &ldquo;barbería&rdquo;.
        </div>

        {prev && (
          <div style={{ marginTop: 8, padding: "10px 12px", borderRadius: 10,
                        border: "1px solid var(--border)", fontSize: 12.5 }}>
            <div>
              Alcanza <b>{prev.alcanza}</b> comercios
              {prev.ya_lo_tienen > 0 && <> · {prev.ya_lo_tienen} ya lo tienen</>}
              {" · "}<b style={{ color: "var(--neon)" }}>{prev.nuevos} nuevos</b>
              {prev.recortado && <span style={{ color: "var(--txt-3)" }}> (tope de 200)</span>}
            </div>

            {/* Si los que alcanzaría son casi todos de OTRO rubro, la palabra
                está arrastrando y no clasificando. Es la señal que buscamos. */}
            {prev.conviven_con.length > 0 && (
              <div style={{ marginTop: 6, color: "var(--amber)" }}>
                ⚠️ De los nuevos, ya están en:{" "}
                {prev.conviven_con.map((c) => `${c.slug} (${c.comercios})`).join(" · ")}
                <div style={{ color: "var(--txt-3)", marginTop: 3 }}>
                  Si son casi todos del mismo rubro ajeno, la palabra está arrastrando.
                </div>
              </div>
            )}

            {prev.ejemplos.length > 0 && (
              <div style={{ marginTop: 8, maxHeight: 150, overflowY: "auto" }}>
                {prev.ejemplos.map((e, i) => (
                  <div key={`${e.codigo}-${i}`} style={{ padding: "3px 0", color: "var(--txt-2)" }}>
                    <b>{e.nombre || "Comercio"}</b>
                    {e.otros_rubros.length > 0 && (
                      <span style={{ color: "var(--amber)" }}> [{e.otros_rubros.join(", ")}]</span>
                    )}
                    <span style={{ color: "var(--txt-3)" }}> — {e.vende}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
