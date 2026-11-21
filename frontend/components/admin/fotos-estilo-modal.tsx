"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Ic, type NombreIcono } from "@/components/ic";
import { Aviso, BTN_GRANDE, BotonCopiar, Cargando, ErrorConReintento, Insignia, SinConexion, useOnline } from "@/components/content/content-ui";
import {
  armarEstilo, descartarEstilo, getFotosEstilo, quitarEstilo, subirImagenExterna, usarEstilo,
  type Objetivo, type PhotoStyleState, type Resultado,
} from "@/lib/fotos-estilo";
import {
  aplicarResultado, avisoPropuesta, estadoFoto, etiquetaConIA, nombreDescarga, problemaArchivoExterno,
  puedeIA, resumenIA, textoCosto, TIPOS_EXTERNA, type ClaveEstado, type Method,
} from "@/lib/fotos-estilo-pure";

/**
 * El botón «Fotos» de cada negocio en Admin › Comercios (docs/fotos-estilo-uruku.md §7).
 *
 * Una ventana con la portada y la galería del negocio. Cada foto se transforma al estilo URUKU por tres
 * caminos (Gratis = la plantilla, Con IA = Gemini, paga, y ChatGPT a mano) y TODOS terminan en una
 * propuesta privada que una persona mira y aprueba con «Usar en la ficha». Nada se publica solo.
 *
 * Con la IA no disponible (interruptor apagado, sin modelo o tope del día) se dice el motivo y se siguen
 * pudiendo usar Gratis y ChatGPT. Las acciones que gastan o borran piden confirmación en el mismo botón.
 * Un solo pedido a la vez: el servidor tiene un solo lock y Gemini lo retiene hasta un minuto.
 */
type Accion = "free" | "gemini" | "externa" | "usar" | "descartar" | "quitar";
type Ocupado = { clave: string; accion: Accion };
type Msg = { clave: string; tono: "ok" | "error"; texto: string };

const TEXTO_OCUPADO: Record<Accion, string> = {
  free: "Armando la foto con la plantilla…",
  gemini: "Armando la foto con IA… Puede tardar hasta un minuto.",
  externa: "Subiendo la imagen y armando la foto…",
  usar: "Poniéndola en la ficha…",
  descartar: "Descartando la propuesta…",
  quitar: "Volviendo a la foto original…",
};

const TEXTO_LISTO: Record<Accion, string> = {
  free: "Propuesta lista: mirala abajo antes de usarla.",
  gemini: "Propuesta lista: mirala abajo antes de usarla.",
  externa: "Propuesta lista con la imagen que subiste: mirala abajo antes de usarla.",
  usar: "Listo: ya se ve en la ficha.",
  descartar: "Propuesta descartada.",
  quitar: "La ficha volvió a mostrar la foto original.",
};

const CLAVE_PORTADA = "cover";
const claveDe = (o: Objetivo) => (o.tipo === "cover" ? CLAVE_PORTADA : o.id);

/** Un error de red (sin respuesta) no trae mensaje útil: se dice con palabras. */
function mensajeDe(e: unknown, defecto: string): string {
  if (e instanceof TypeError) return "No se pudo conectar con el servidor. Revisá la conexión y probá de nuevo.";
  return e instanceof Error && e.message ? e.message : defecto;
}

const ETIQUETA_ESTADO: Record<ClaveEstado, { icono: NombreIcono; tono: "info" | "ok" | "aviso" }> = {
  original: { icono: "foto", tono: "info" },
  con_diseno: { icono: "listo", tono: "ok" },
  propuesta: { icono: "aviso", tono: "aviso" },
};

export function FotosEstiloModal({ comercio, onCerrar }: {
  comercio: { id: string; nombre: string };
  onCerrar: () => void;
}) {
  const online = useOnline();
  const caja = useRef<HTMLDivElement>(null);
  const vez = useRef(0);
  const [estado, setEstado] = useState<PhotoStyleState | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errCarga, setErrCarga] = useState("");
  const [ocupado, setOcupado] = useState<Ocupado | null>(null);
  const [msg, setMsg] = useState<Msg | null>(null);
  const [abierta, setAbierta] = useState<string | null>(null);

  // Escape cierra, el fondo no scrollea y el foco entra a la hoja (igual que «Video»).
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    document.addEventListener("keydown", alTeclear);
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    caja.current?.focus();
    return () => { document.removeEventListener("keydown", alTeclear); document.body.style.overflow = previo; };
  }, [onCerrar]);

  const cargar = useCallback(async () => {
    const n = ++vez.current;
    setCargando(true); setErrCarga("");
    try {
      const r = await getFotosEstilo(comercio.id);
      if (n === vez.current) setEstado(r);
    } catch (e) {
      if (n === vez.current) setErrCarga(mensajeDe(e, "No se pudieron leer las fotos del negocio"));
    } finally {
      if (n === vez.current) setCargando(false);
    }
  }, [comercio.id]);

  useEffect(() => { void cargar(); }, [cargar]);

  /** Después de un `gemini` (salió bien o no, el intento cuenta) se pone al día sólo el contador de la IA. */
  const refrescarIA = useCallback(async () => {
    try {
      const r = await getFotosEstilo(comercio.id);
      setEstado((e) => (e ? { ...e, gemini: r.gemini } : e));
    } catch { /* el contador se corrige en la próxima apertura */ }
  }, [comercio.id]);

  async function correr(o: Objetivo, accion: Accion, llamar: () => Promise<Resultado>) {
    if (ocupado) return;
    const clave = claveDe(o);
    setMsg(null); setOcupado({ clave, accion });
    try {
      const r = await llamar();
      setEstado((e) => (e ? aplicarResultado(e, o, r) : e));
      setMsg({ clave, tono: "ok", texto: TEXTO_LISTO[accion] });
    } catch (e) {
      // 409 «ya se está armando otra», 429 tope, 503 IA no disponible, 504 Gemini no contestó…: el servidor lo dice en español.
      setMsg({ clave, tono: "error", texto: mensajeDe(e, "No se pudo completar la acción. Probá de nuevo.") });
    } finally {
      setOcupado(null);
      if (accion === "gemini") void refrescarIA();
    }
  }

  const acciones = (o: Objetivo): Acciones => ({
    armar: (m) => void correr(o, m, () => armarEstilo(comercio.id, o, m)),
    externa: (f) => void correr(o, "externa", () => subirImagenExterna(comercio.id, o, f)),
    usar: () => void correr(o, "usar", () => usarEstilo(comercio.id, o)),
    descartar: () => void correr(o, "descartar", () => descartarEstilo(comercio.id, o)),
    quitar: () => void correr(o, "quitar", () => quitarEstilo(comercio.id, o)),
    error: (texto) => setMsg({ clave: claveDe(o), tono: "error", texto }),
    aviso: (texto) => setMsg({ clave: claveDe(o), tono: "ok", texto }),
  });

  const ia = useMemo(() => (estado ? puedeIA(estado.gemini) : null), [estado]);
  const seleccionada = estado && abierta ? estado.gallery.find((f) => f.foto_id === abierta) ?? null : null;
  const indiceSel = estado && seleccionada ? estado.gallery.indexOf(seleccionada) : -1;
  const slug = estado?.comercio.slug || "negocio";
  const nombre = comercio.nombre || "este negocio";

  return (
    <div onClick={onCerrar}
         style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.6)", display: "flex",
                  alignItems: "flex-end", justifyContent: "center" }}>
      <div ref={caja} role="dialog" aria-modal="true" aria-label={`Fotos de ${nombre}`} tabIndex={-1}
           onClick={(e) => e.stopPropagation()}
           style={{ background: "var(--bg)", color: "var(--txt)", width: "100%", maxWidth: 760, maxHeight: "92dvh", overflowY: "auto",
                    borderRadius: "18px 18px 0 0", border: "1px solid var(--stroke-2)", padding: "16px 16px calc(20px + env(safe-area-inset-bottom, 0px))",
                    display: "grid", gap: 14, alignContent: "start", outline: "none" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <h3 style={{ margin: 0, fontSize: 18, display: "flex", alignItems: "center", gap: 8 }}>
            <Ic n="foto" s={18} /> Fotos de {nombre}
          </h3>
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onCerrar}>
            <Ic n="cerrar" s={15} /> Cerrar
          </button>
        </div>

        <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.5 }}>
          Lo armás, lo mirás y recién con «Usar en la ficha» se publica. Los listados, el buscador y el mapa siguen con la foto real.
        </p>

        <SinConexion />
        {cargando && !estado && <Cargando texto="Leyendo las fotos del negocio…" />}
        {errCarga && <ErrorConReintento mensaje={errCarga} onReintentar={() => void cargar()} />}

        {estado && ia && (
          <>
            <div style={{ display: "grid", gap: 8 }}>
              <div style={{ fontSize: 12.5, color: "var(--txt-2)", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                <Ic n="ia" s={14} /> <span><strong>IA:</strong> {resumenIA(estado.gemini)}</span>
              </div>
              {!ia.puede && (
                <Aviso tono="aviso">
                  <strong>Con IA no está disponible.</strong> {ia.motivo} Podés usar «Gratis» o armarla con ChatGPT.
                </Aviso>
              )}
            </div>

            <PanelObjetivo
              key={CLAVE_PORTADA}
              titulo="Portada"
              sinFoto="Este negocio no tiene foto de portada: subila desde «Editar» y después armá el estilo."
              objetivo={{ tipo: "cover" }}
              aspecto="1600 / 1000"
              original={estado.cover.photo_url}
              design={estado.cover.design_url}
              proposal={estado.cover.proposal_url}
              method={estado.cover.proposal_method}
              ia={ia} gemini={estado.gemini}
              instruccion={estado.instructions.cover}
              nombreArchivo={nombreDescarga(slug, { tipo: "cover" })}
              ocupado={ocupado} msg={msg} online={online}
              acciones={acciones({ tipo: "cover" })} />

            <section aria-labelledby="fe-galeria" style={{ display: "grid", gap: 10 }}>
              <h4 id="fe-galeria" style={{ margin: 0, fontSize: 14, display: "flex", alignItems: "center", gap: 6 }}>
                <Ic n="foto" s={15} /> Galería ({estado.gallery.length})
              </h4>
              {estado.gallery.length === 0 ? (
                <Aviso tono="info">Este negocio todavía no tiene fotos en la galería. Las que cargue o le cargues van a aparecer acá.</Aviso>
              ) : (
                <>
                  <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>Tocá una foto para armarle el estilo.</p>
                  <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8,
                               gridTemplateColumns: "repeat(auto-fill, minmax(104px, 1fr))" }}>
                    {estado.gallery.map((f, i) => {
                      const e = estadoFoto(f);
                      const marca = ETIQUETA_ESTADO[e.clave];
                      const src = f.design_url ? (f.design_thumb_url ?? f.design_url) : (f.thumb_url ?? f.photo_url);
                      const activa = f.foto_id === abierta;
                      return (
                        <li key={f.foto_id}>
                          <button type="button" aria-pressed={activa}
                                  aria-label={`Foto ${i + 1}: ${e.texto}`}
                                  onClick={() => setAbierta(activa ? null : f.foto_id)}
                                  style={{ all: "unset", cursor: "pointer", display: "grid", gap: 4, width: "100%", boxSizing: "border-box",
                                           padding: 4, borderRadius: 10, border: `2px solid ${activa ? "var(--neon)" : "var(--border)"}` }}>
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={src} alt="" loading="lazy" decoding="async"
                                 style={{ width: "100%", aspectRatio: "4 / 5", objectFit: "cover", borderRadius: 7, background: "var(--bg-2, rgba(128,128,128,.15))" }} />
                            <span style={{ justifySelf: "start" }}>
                              <Insignia icono={marca.icono} tono={marca.tono}>{e.texto}</Insignia>
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}

              {seleccionada && (
                <PanelObjetivo
                  key={seleccionada.foto_id}
                  titulo={`Foto ${indiceSel + 1} de ${estado.gallery.length}`}
                  sinFoto="No se pudo leer la foto original."
                  objetivo={{ tipo: "foto", id: seleccionada.foto_id }}
                  aspecto="4 / 5"
                  original={seleccionada.photo_url || null}
                  design={seleccionada.design_url}
                  proposal={seleccionada.proposal_url}
                  method={seleccionada.proposal_method}
                  ia={ia} gemini={estado.gemini}
                  instruccion={estado.instructions.gallery}
                  nombreArchivo={nombreDescarga(slug, { tipo: "foto", id: seleccionada.foto_id }, indiceSel + 1)}
                  ocupado={ocupado} msg={msg} online={online}
                  acciones={acciones({ tipo: "foto", id: seleccionada.foto_id })} />
              )}
            </section>
          </>
        )}
      </div>
    </div>
  );
}

type Acciones = {
  armar: (m: "free" | "gemini") => void;
  externa: (f: File) => void;
  usar: () => void;
  descartar: () => void;
  quitar: () => void;
  error: (texto: string) => void;
  aviso: (texto: string) => void;
};

/**
 * La botonera de una foto (la portada o una de la galería): original, lo que hay en la ficha, la propuesta y
 * los tres caminos. Es la misma para las dos; sólo cambian el formato (3:2 o 4:5) y la instrucción de ChatGPT.
 */
function PanelObjetivo({ titulo, sinFoto, objetivo, aspecto, original, design, proposal, method, ia, gemini, instruccion,
                         nombreArchivo, ocupado, msg, online, acciones }: {
  titulo: string;
  sinFoto: string;
  objetivo: Objetivo;
  aspecto: string;
  original: string | null;
  design: string | null;
  proposal: string | null;
  method: Method | null;
  ia: { puede: boolean; motivo: string | null };
  gemini: PhotoStyleState["gemini"];
  instruccion: string;
  nombreArchivo: string;
  ocupado: Ocupado | null;
  msg: Msg | null;
  online: boolean;
  acciones: Acciones;
}) {
  const clave = claveDe(objetivo);
  const entrada = useRef<HTMLInputElement>(null);
  const panel = useRef<HTMLElement>(null);
  const [confirmando, setConfirmando] = useState<Accion | null>(null);
  const propios = ocupado?.clave === clave ? ocupado : null;
  const quieto = ocupado !== null || !online;
  const sinOriginal = !original;
  const aviso = proposal ? avisoPropuesta(method) : null;
  const mio = msg?.clave === clave ? msg : null;

  // Una confirmación que nadie toca se apaga sola: así un toque suelto no queda armado.
  useEffect(() => {
    if (!confirmando) return;
    const t = setTimeout(() => setConfirmando(null), 6000);
    return () => clearTimeout(t);
  }, [confirmando]);

  // Al abrir una foto de la galería, que se vea (puede haber 300 miniaturas arriba).
  useEffect(() => {
    if (objetivo.tipo === "foto") panel.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [objetivo.tipo]);

  /** Dos toques: el primero arma la confirmación en el mismo botón, el segundo ejecuta. */
  function conConfirmar(accion: Accion, hacer: () => void) {
    if (confirmando !== accion) { setConfirmando(accion); return; }
    setConfirmando(null);
    hacer();
  }

  function elegirArchivo(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    e.target.value = "";                         // permite volver a elegir el mismo archivo
    if (!f) return;
    const problema = problemaArchivoExterno(f);
    if (problema) { acciones.error(problema); return; }
    acciones.externa(f);
  }

  // «Descargar la foto»: se baja como blob para que el navegador la guarde con nombre. Si el servidor de fotos no
  // lo permite (otro origen sin CORS), se abre en otra pestaña para guardarla desde ahí.
  async function descargar() {
    if (!original) return;
    try {
      const r = await fetch(original);
      if (!r.ok) throw new Error(String(r.status));
      const url = URL.createObjectURL(await r.blob());
      const a = document.createElement("a");
      a.href = url; a.download = nombreArchivo;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    } catch {
      window.open(original, "_blank", "noopener");
      acciones.aviso("Se abrió la foto en otra pestaña: guardala desde ahí (clic derecho o mantené apretado › Guardar imagen).");
    }
  }

    return (
    <section ref={panel} aria-label={titulo} className="panel-card glass"
             style={{ padding: 12, display: "grid", gap: 12, border: "1px solid var(--border)", borderRadius: 12 }}>
      <h4 style={{ margin: 0, fontSize: 14, display: "flex", alignItems: "center", gap: 6 }}>
        <Ic n="foto" s={15} /> {titulo.toUpperCase()}
      </h4>

      {sinOriginal && <Aviso tono="aviso">{sinFoto}</Aviso>}

      {/* Original · en la ficha · propuesta */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
        <Figura titulo="Original" ancho={160}>
          {original
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={original} alt="Foto original" loading="lazy" decoding="async"
                   style={{ ...ESTILO_IMG, aspectRatio: aspecto, objectFit: "contain" }} />
            : <Hueco aspecto={aspecto} texto="Sin foto" />}
        </Figura>
        <Figura titulo="En la ficha" ancho={160}>
          {design
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={design} alt="Versión con estilo que se ve en la ficha" loading="lazy" decoding="async"
                   style={{ ...ESTILO_IMG, aspectRatio: aspecto, objectFit: "cover" }} />
            : <Hueco aspecto={aspecto} texto="Sin diseño" />}
        </Figura>
        {proposal && (
          <Figura titulo="Propuesta (todavía no se ve en la ficha)" ancho={320}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={proposal} alt="Vista previa de la propuesta" decoding="async"
                 style={{ ...ESTILO_IMG, aspectRatio: aspecto, objectFit: "cover" }} />
          </Figura>
        )}
      </div>

      {aviso && <Aviso tono="aviso">{aviso}</Aviso>}

      {/* Los tres caminos */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE}
                disabled={quieto || sinOriginal} onClick={() => acciones.armar("free")}>
          <Ic n="documento" s={15} /> Gratis
        </button>
        <button type="button" className={confirmando === "gemini" ? "btn btn-primary btn-sm" : "btn btn-ghost btn-sm"} style={BTN_GRANDE}
                disabled={quieto || sinOriginal || !ia.puede}
                title={ia.puede ? "Arma la foto con IA (tiene costo)" : (ia.motivo ?? "Con IA no está disponible")}
                onClick={() => conConfirmar("gemini", () => acciones.armar("gemini"))}>
          <Ic n="ia" s={15} /> {etiquetaConIA(gemini, confirmando === "gemini")}
        </button>
        {instruccion
          ? <BotonCopiar texto={instruccion} etiqueta="Copiar instrucción para ChatGPT" />
          : <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled>
              <Ic n="copiar" s={15} /> Instrucción para ChatGPT no disponible
            </button>}
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE}
                disabled={sinOriginal} onClick={() => void descargar()}>
          <Ic n="descargar" s={15} /> Descargar la foto
        </button>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE}
                disabled={quieto || sinOriginal} onClick={() => entrada.current?.click()}>
          <Ic n="subir" s={15} /> Subir imagen hecha afuera
        </button>
        <input ref={entrada} type="file" accept={TIPOS_EXTERNA.join(",")} hidden onChange={elegirArchivo} />
        {confirmando !== null && (
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setConfirmando(null)}>
            Cancelar
          </button>
        )}
      </div>
      {confirmando === "gemini" && (
        <div role="status" style={{ fontSize: 12.5, color: "var(--txt-2)" }}>
          <Ic n="dato" s={13} /> La IA tiene costo{gemini.cost_usd > 0 ? ` (${textoCosto(gemini.cost_usd)} por foto)` : ""} y cuenta para el tope del día aunque falle. Tocá «{etiquetaConIA(gemini, true)}» para seguir.
        </div>
      )}

      {propios && (
        <div role="status" aria-live="polite" style={{ fontSize: 13 }}>
          <Ic n="reloj" s={14} /> {TEXTO_OCUPADO[propios.accion]}
        </div>
      )}
      {!propios && ocupado && (
        <div role="status" style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
          <Ic n="reloj" s={13} /> Se está armando otra foto: esperá a que termine.
        </div>
      )}
      {mio && !propios && (
        mio.tono === "error"
          ? <Aviso tono="error">{mio.texto}</Aviso>
          : <Aviso tono="ok">{mio.texto}</Aviso>
      )}

      {/* La decisión */}
      {(proposal || design) && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          {proposal && (
            <>
              <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={quieto}
                      onClick={() => acciones.usar()}>
                <Ic n="si" s={15} /> Usar en la ficha
              </button>
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={quieto}
                      onClick={() => conConfirmar("descartar", acciones.descartar)}>
                <Ic n="cerrar" s={15} /> {confirmando === "descartar" ? "Confirmar: descartar" : "Descartar"}
              </button>
            </>
          )}
          {design && (
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={quieto}
                    onClick={() => conConfirmar("quitar", acciones.quitar)}>
              <Ic n="volver" s={15} /> {confirmando === "quitar" ? "Confirmar: volver a la original" : "Volver a la original"}
            </button>
          )}
        </div>
      )}
    </section>
  );
}

const ESTILO_IMG: React.CSSProperties = {
  display: "block", width: "100%", borderRadius: 8, border: "1px solid var(--border)", background: "rgba(128,128,128,.12)",
};

function Figura({ titulo, ancho, children }: { titulo: string; ancho: number; children: React.ReactNode }) {
  return (
    <figure style={{ margin: 0, display: "grid", gap: 4, flex: `0 1 ${ancho}px`, minWidth: 120, maxWidth: "100%" }}>
      <figcaption style={{ fontSize: 12, fontWeight: 600, color: "var(--txt-2)" }}>{titulo}</figcaption>
      {children}
    </figure>
  );
}

/** El lugar de lo que no existe: dice «Sin diseño» con palabras, no sólo con un recuadro vacío. */
function Hueco({ aspecto, texto }: { aspecto: string; texto: string }) {
  return (
    <div style={{ ...ESTILO_IMG, aspectRatio: aspecto, display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 12.5, color: "var(--txt-3)", borderStyle: "dashed" }}>
      {texto}
    </div>
  );
}
