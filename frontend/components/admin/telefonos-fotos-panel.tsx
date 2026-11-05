"use client";

// Admin › Comercios › «Teléfonos en fotos» (docs/telefonos-en-fotos.md › Panel).
//
// Muestra los números de celular que el lector (Tesseract gratis, o Gemini si está
// prendido) encontró en las portadas, como PROPUESTAS: nada se escribe solo en la ficha.
// Una persona los usa como WhatsApp, como teléfono, o los descarta. Hecho para el
// celular: filas en columna, botones de 48 px, miniatura que se amplía al tocarla.
//
// Un estado nunca se dice sólo con color: siempre ícono + palabra.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Ic } from "@/components/ic";
import { hrefSeccion } from "@/components/admin/admin-shell";
import { ImageLightbox } from "@/components/image-lightbox";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia, SinConexion, useOnline } from "@/components/content/content-ui";
import { urlApi } from "@/lib/content-pure";
import {
  ESTADOS_FILTRO, ESTADO_LABEL, TAMANO_PAGINA,
  aplicarLote, aplicarResultadoALista, aplicarTelefono, alternar, alternarTodos, descartarTelefono,
  esConflicto, filaAplicada, filaDescartada, idsDelLote, listarTelefonos, mensajeDeError, motivoLegible,
  motorActivoLabel, numeroParaMostrar, preguntaReemplazo, puedeEnLote, rangoPagina, resumenLoteTexto,
  resumenTelefonos, textoCompartido, textoWorker, valorActual,
  type ComoAplicar, type EstadoTelefono, type ResultadoLote, type ResumenTelefonos, type TelefonoDetectado,
} from "@/lib/telefonos-detectados";

type Pregunta = "reemplazar-whatsapp" | "reemplazar-telefono" | "descartar";
type Fila = { ocupada?: boolean; error?: string; pregunta?: Pregunta };

const fmt = (n: number) => n.toLocaleString("es-BO");

export function TelefonosFotosPanel({ ciudadSlug, ciudadNombre }: { ciudadSlug: string | null; ciudadNombre: string | null }) {
  const online = useOnline();
  const [estado, setEstado] = useState<EstadoTelefono | "">("pendiente");
  const [sinWhatsapp, setSinWhatsapp] = useState(false);
  const [offset, setOffset] = useState(0);

  const [items, setItems] = useState<TelefonoDetectado[] | null>(null);
  const [total, setTotal] = useState(0);
  const [err, setErr] = useState("");

  const [resumen, setResumen] = useState<ResumenTelefonos | null>(null);
  const [errResumen, setErrResumen] = useState("");

  const [filas, setFilas] = useState<Record<string, Fila>>({});
  const [marcados, setMarcados] = useState<Set<string>>(new Set());
  const [confirmaLote, setConfirmaLote] = useState(false);
  const [aplicandoLote, setAplicandoLote] = useState(false);
  const [resultadoLote, setResultadoLote] = useState<{ r: ResultadoLote; nombres: Record<string, string> } | null>(null);
  const [errLote, setErrLote] = useState("");
  const [foto, setFoto] = useState<{ src: string; alt: string } | null>(null);

  // Cada pedido lleva un número: si llega una respuesta vieja (cambiaste el filtro
  // mientras cargaba) no pisa a la nueva.
  const pedido = useRef(0);

  const cargar = useCallback(async () => {
    const n = ++pedido.current;
    setErr("");
    try {
      const p = await listarTelefonos({ ciudad: ciudadSlug, estado, sinWhatsapp, limit: TAMANO_PAGINA, offset });
      if (n !== pedido.current) return;
      setItems(p.items); setTotal(p.total);
      setFilas({}); setMarcados(new Set()); setConfirmaLote(false);
    } catch (ex) {
      if (n !== pedido.current) return;
      setErr(mensajeDeError(ex, "No se pudo cargar la lista de teléfonos"));
      setItems((x) => x ?? []);
    }
  }, [ciudadSlug, estado, sinWhatsapp, offset]);

  const cargarResumen = useCallback(async () => {
    setErrResumen("");
    try { setResumen(await resumenTelefonos()); }
    catch (ex) { setErrResumen(mensajeDeError(ex, "No se pudo cargar el resumen")); }
  }, []);

  useEffect(() => { setItems(null); void cargar(); }, [cargar]);
  useEffect(() => { void cargarResumen(); }, [cargarResumen]);

  // Un filtro nuevo vuelve a la primera página.
  function cambiarFiltro(fn: () => void) { fn(); setOffset(0); }

  const lista = items ?? [];
  const marcables = useMemo(() => lista.filter(puedeEnLote), [lista]);
  const idsLote = useMemo(() => idsDelLote(lista, marcados), [lista, marcados]);
  const todosMarcados = marcables.length > 0 && marcables.every((t) => marcados.has(t.id));
  const pag = rangoPagina(offset, lista.length, total);

  function ponerFila(id: string, f: Fila) { setFilas((m) => ({ ...m, [id]: f })); }
  function cambiarItem(id: string, fn: (t: TelefonoDetectado) => TelefonoDetectado) {
    setItems((xs) => xs && xs.map((t) => (t.id === id ? fn(t) : t)));
  }

  async function aplicar(t: TelefonoDetectado, como: ComoAplicar, reemplazar = false) {
    ponerFila(t.id, { ocupada: true });
    try {
      await aplicarTelefono(t.id, como, reemplazar);
      cambiarItem(t.id, (x) => filaAplicada(x, como));
      setMarcados((m) => { const n = new Set(m); n.delete(t.id); return n; });
      ponerFila(t.id, {});
      void cargarResumen();
    } catch (ex) {
      if (esConflicto(ex) && !reemplazar) {
        ponerFila(t.id, { pregunta: como === "whatsapp" ? "reemplazar-whatsapp" : "reemplazar-telefono" });
      } else {
        ponerFila(t.id, { error: mensajeDeError(ex, "No se pudo guardar el número") });
      }
    }
  }

  async function descartar(t: TelefonoDetectado) {
    ponerFila(t.id, { ocupada: true });
    try {
      await descartarTelefono(t.id);
      cambiarItem(t.id, filaDescartada);
      setMarcados((m) => { const n = new Set(m); n.delete(t.id); return n; });
      ponerFila(t.id, {});
      void cargarResumen();
    } catch (ex) {
      ponerFila(t.id, { error: mensajeDeError(ex, "No se pudo descartar") });
    }
  }

  async function aplicarMarcados() {
    const ids = idsLote;
    if (ids.length === 0) return;
    const nombres: Record<string, string> = {};
    for (const t of lista) nombres[t.id] = t.comercio.nombre;
    setAplicandoLote(true); setErrLote(""); setConfirmaLote(false);
    try {
      const r = await aplicarLote(ids);
      setResultadoLote({ r, nombres });
      setItems((xs) => (xs ? aplicarResultadoALista(xs, r) : xs));
      setMarcados(new Set());
      void cargarResumen();
    } catch (ex) {
      setErrLote(mensajeDeError(ex, "No se pudo aplicar el lote"));
    } finally {
      setAplicandoLote(false);
    }
  }

  const motor = resumen ? motorActivoLabel(resumen.motor_activo) : null;
  const worker = resumen ? textoWorker(resumen.worker) : null;

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <section className="panel-card glass" style={{ padding: 16, display: "grid", gap: 12 }} aria-label="Resumen de teléfonos en fotos">
        <div>
          <h3 style={{ margin: "0 0 4px", fontSize: 17, display: "flex", alignItems: "center", gap: 8 }}>
            <Ic n="telefono" s={18} /> Teléfonos en fotos
          </h3>
          <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
            Números de celular que se leyeron en las portadas. Son propuestas: no se escribe nada en la ficha hasta que vos lo confirmás.
          </p>
        </div>

        <SinConexion />
        {!resumen && !errResumen && <Cargando texto="Cargando resumen…" />}
        {errResumen && <ErrorConReintento mensaje={errResumen} onReintentar={() => void cargarResumen()} />}
        {resumen && (
          <>
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
              <Dato icono="foto" etiqueta="Fotos escaneadas" valor={fmt(resumen.escaneadas)} />
              <Dato icono="reloj" etiqueta="Faltan escanear" valor={fmt(resumen.pendientes_de_escanear)} />
              <Dato icono="telefono" etiqueta="Números encontrados" valor={fmt(resumen.numeros)} />
              <Dato icono="whatsapp" etiqueta="Sin WhatsApp, con número propuesto" valor={fmt(resumen.sin_whatsapp_con_numero)} />
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <span style={{ fontSize: 13, color: "var(--txt-2)" }}>Lector activo:</span>
              {motor && <Insignia icono={motor.costo ? "aviso" : "listo"} tono={motor.costo ? "aviso" : "ok"}>{motor.texto}</Insignia>}
              {worker && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{worker}</span>}
              <Link href={hrefSeccion("redes")} className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Ic n="pagos" s={15} /> Servicios con costo
              </Link>
            </div>
            <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.45 }}>
              Para leer con Gemini, prendé «Leer teléfonos en las fotos con Gemini» en Servicios con costo (Contenido para redes). Apagado, se usa el lector gratis.
            </p>
          </>
        )}
      </section>

      <section className="panel-card glass" style={{ padding: 16, display: "grid", gap: 12 }} aria-label="Lista de teléfonos detectados">
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label style={{ display: "grid", gap: 4, fontSize: 13, color: "var(--txt-2)", flex: "1 1 200px" }}>
            Estado
            <select className="adm-input" style={BTN_GRANDE} value={estado}
                    onChange={(e) => cambiarFiltro(() => setEstado(e.target.value as EstadoTelefono | ""))}>
              {ESTADOS_FILTRO.map((o) => <option key={o.valor || "todos"} value={o.valor}>{o.label}</option>)}
            </select>
          </label>
          <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14, minHeight: 48, flex: "1 1 200px", cursor: "pointer" }}>
            <input type="checkbox" checked={sinWhatsapp} style={{ width: 22, height: 22, flex: "none" }}
                   onChange={(e) => cambiarFiltro(() => setSinWhatsapp(e.target.checked))} />
            Sólo comercios sin WhatsApp
          </label>
        </div>
        <span style={{ fontSize: 12.5, color: "var(--txt-3)", display: "inline-flex", gap: 6, alignItems: "center" }}>
          <Ic n="ciudad" s={14} /> {ciudadNombre ? `Ciudad: ${ciudadNombre}` : "Todas las ciudades"} (se cambia en la barra de arriba)
        </span>

        {/* Acciones sobre varios */}
        {marcables.length > 0 && (
          <div style={{ display: "grid", gap: 8, padding: "10px 12px", borderRadius: 12, border: "1px solid var(--border)" }}>
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
              <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 14, minHeight: 48, flex: "1 1 220px", cursor: "pointer" }}>
                <input type="checkbox" checked={todosMarcados} style={{ width: 22, height: 22, flex: "none" }}
                       onChange={() => setMarcados((m) => alternarTodos(lista, m))} />
                Marcar los que se pueden usar de una ({marcables.length})
              </label>
              <button type="button" className="btn btn-primary btn-sm" style={{ ...BTN_GRANDE, flex: "1 1 220px" }}
                      disabled={idsLote.length === 0 || aplicandoLote || !online}
                      onClick={() => setConfirmaLote(true)}>
                <Ic n="whatsapp" s={16} /> Usar como WhatsApp los marcados ({idsLote.length})
              </button>
            </div>
            <span style={{ fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.4 }}>
              Sólo se marcan los celulares de comercios sin WhatsApp y que no aparecen en varios comercios.
            </span>
            {confirmaLote && (
              <Aviso tono="aviso" accion={
                <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => void aplicarMarcados()}>
                    <Ic n="si" s={15} /> Sí, usar los {idsLote.length}
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setConfirmaLote(false)}>Cancelar</button>
                </span>
              }>
                Vas a escribir {idsLote.length} {idsLote.length === 1 ? "número" : "números"} como WhatsApp en las fichas de sus comercios. ¿Seguimos?
              </Aviso>
            )}
            {aplicandoLote && <Cargando texto="Aplicando los marcados…" />}
          </div>
        )}
        {errLote && <Aviso tono="error">{errLote}</Aviso>}
        {resultadoLote && <ResultadoDelLote res={resultadoLote.r} nombres={resultadoLote.nombres} onCerrar={() => setResultadoLote(null)} />}

        {items === null && <Cargando texto="Cargando teléfonos…" />}
        {err && <ErrorConReintento mensaje={err} onReintentar={() => { setItems(null); void cargar(); }} />}
        {items && items.length === 0 && !err && (
          <div role="status" style={{ display: "flex", gap: 8, alignItems: "flex-start", color: "var(--txt-3)", fontSize: 14, padding: "8px 2px" }}>
            <Ic n="dato" s={16} />
            <span>
              {estado === "pendiente" && !sinWhatsapp
                ? "No hay teléfonos pendientes para revisar con estos filtros."
                : "No hay teléfonos para estos filtros."}
              {resumen && resumen.pendientes_de_escanear > 0 && " Todavía faltan fotos por escanear: volvé a mirar más tarde."}
            </span>
          </div>
        )}

        {items && items.length > 0 && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 10 }}>
            {lista.map((t) => (
              <FilaTelefono key={t.id} t={t} fila={filas[t.id] ?? {}} online={online}
                marcado={marcados.has(t.id)}
                onMarcar={() => setMarcados((m) => alternar(m, t.id))}
                onAmpliar={() => setFoto({ src: urlApi(t.foto_url), alt: `Portada de ${t.comercio.nombre}` })}
                onAplicar={(como, reemplazar) => void aplicar(t, como, reemplazar)}
                onDescartar={() => void descartar(t)}
                onPreguntar={(p) => ponerFila(t.id, p ? { pregunta: p } : {})} />
            ))}
          </ul>
        )}

        {items && total > 0 && (
          <nav aria-label="Páginas" style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13, color: "var(--txt-2)" }}>
              {pag.desde}–{pag.hasta} de {fmt(total)}
            </span>
            <span style={{ display: "flex", gap: 8 }}>
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={!pag.hayAnterior}
                      onClick={() => setOffset(Math.max(0, offset - TAMANO_PAGINA))}>
                <Ic n="volver" s={15} /> Anteriores
              </button>
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={!pag.haySiguiente}
                      onClick={() => setOffset(offset + TAMANO_PAGINA)}>
                Siguientes <Ic n="seguir" s={15} />
              </button>
            </span>
          </nav>
        )}
      </section>

      {foto && <ImageLightbox src={foto.src} alt={foto.alt} onClose={() => setFoto(null)} />}
    </div>
  );
}

function Dato({ icono, etiqueta, valor }: { icono: "foto" | "reloj" | "telefono" | "whatsapp"; etiqueta: string; valor: string }) {
  return (
    <div style={{ padding: "10px 12px", borderRadius: 12, border: "1px solid var(--border)", display: "grid", gap: 2 }}>
      <span style={{ fontSize: 12.5, color: "var(--txt-3)", display: "flex", gap: 6, alignItems: "center" }}><Ic n={icono} s={14} /> {etiqueta}</span>
      <b style={{ fontSize: 22, lineHeight: 1.2 }}>{valor}</b>
    </div>
  );
}

function ResultadoDelLote({ res, nombres, onCerrar }: { res: ResultadoLote; nombres: Record<string, string>; onCerrar: () => void }) {
  return (
    <div role="status" style={{ display: "grid", gap: 8, padding: "10px 12px", borderRadius: 12, border: "1px solid var(--neon)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
        <b style={{ fontSize: 14, display: "flex", gap: 6, alignItems: "center" }}><Ic n="listo" s={16} /> {resumenLoteTexto(res)}</b>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onCerrar}><Ic n="cerrar" s={14} /> Cerrar</button>
      </div>
      {res.saltados.length > 0 && (
        <details open={res.saltados.length <= 5}>
          <summary style={{ cursor: "pointer", fontSize: 13.5, minHeight: 40, display: "flex", alignItems: "center", gap: 6 }}>
            <Ic n="aviso" s={14} /> Saltados ({res.saltados.length})
          </summary>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18, display: "grid", gap: 4, fontSize: 13, color: "var(--txt-2)" }}>
            {res.saltados.map((s) => (
              <li key={s.id}><b>{nombres[s.id] ?? "Comercio de otra página"}</b>: {motivoLegible(s.motivo)}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function FilaTelefono({ t, fila, online, marcado, onMarcar, onAmpliar, onAplicar, onDescartar, onPreguntar }: {
  t: TelefonoDetectado;
  fila: Fila;
  online: boolean;
  marcado: boolean;
  onMarcar: () => void;
  onAmpliar: () => void;
  onAplicar: (como: ComoAplicar, reemplazar?: boolean) => void;
  onDescartar: () => void;
  onPreguntar: (p: Pregunta | null) => void;
}) {
  const enLote = puedeEnLote(t);
  const accionable = t.estado === "pendiente";
  const waActual = valorActual(t, "whatsapp");
  const telActual = valorActual(t, "telefono");
  const deshabilitar = fila.ocupada || !online;
  const comoPregunta: ComoAplicar | null =
    fila.pregunta === "reemplazar-whatsapp" ? "whatsapp" : fila.pregunta === "reemplazar-telefono" ? "telefono" : null;

  return (
    <li style={{ display: "grid", gap: 10, padding: 12, borderRadius: 12, border: "1px solid var(--border)", opacity: accionable ? 1 : 0.85 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        {enLote && (
          <input type="checkbox" checked={marcado} onChange={onMarcar} style={{ width: 24, height: 24, flex: "none", marginTop: 4 }}
                 aria-label={`Marcar ${t.comercio.nombre} para usar como WhatsApp`} />
        )}
        <button type="button" onClick={onAmpliar} aria-label={`Ampliar la foto de ${t.comercio.nombre}`}
                style={{ flex: "none", width: 76, height: 76, padding: 0, borderRadius: 10, overflow: "hidden", border: "1px solid var(--border)", background: "transparent", cursor: "zoom-in" }}>
          {t.foto_url
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={urlApi(t.foto_url)} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
            : <Ic n="foto" s={24} />}
        </button>
        <div style={{ minWidth: 0, flex: 1, display: "grid", gap: 4 }}>
          <b style={{ fontSize: 15, overflowWrap: "anywhere" }}>{t.comercio.nombre}</b>
          <span style={{ fontSize: 13, color: "var(--txt-2)", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <Ic n="whatsapp" s={14} /> {waActual ? `WhatsApp: ${waActual}` : <b style={{ color: "var(--amber)" }}>Sin WhatsApp</b>}
          </span>
          {telActual && (
            <span style={{ fontSize: 13, color: "var(--txt-2)", display: "flex", gap: 6, alignItems: "center" }}>
              <Ic n="telefono" s={14} /> Teléfono: {telActual}
            </span>
          )}
          <span style={{ fontSize: 22, fontWeight: 800, letterSpacing: ".01em", overflowWrap: "anywhere" }}>{numeroParaMostrar(t)}</span>
          {t.texto_leido && (
            <span style={{ fontSize: 12, color: "var(--txt-3)", overflowWrap: "anywhere" }}>Leído en la foto: «{t.texto_leido}»</span>
          )}
        </div>
      </div>

      <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        <Insignia icono={estadoIcono(t.estado)} tono={estadoTono(t.estado)}>{ESTADO_LABEL[t.estado]}</Insignia>
        {t.tipo === "fijo" && <Insignia icono="telefono" tono="info">Fijo</Insignia>}
        {t.compartido && <Insignia icono="aviso" tono="aviso">{textoCompartido(t)}</Insignia>}
      </div>

      {fila.error && <Aviso tono="error">{fila.error}</Aviso>}

      {comoPregunta && (
        <Aviso tono="aviso" accion={
          <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={deshabilitar}
                    onClick={() => onAplicar(comoPregunta, true)}>
              <Ic n="cambio" s={15} /> Reemplazar
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => onPreguntar(null)}>Dejarlo como está</button>
          </span>
        }>
          {preguntaReemplazo(t, comoPregunta)}
        </Aviso>
      )}

      {fila.pregunta === "descartar" && (
        <Aviso tono="aviso" accion={
          <span style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={deshabilitar} onClick={onDescartar}>
              <Ic n="si" s={15} /> Sí, descartar
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => onPreguntar(null)}>Cancelar</button>
          </span>
        }>
          ¿Descartar {numeroParaMostrar(t)} de {t.comercio.nombre}? No va a volver a aparecer como pendiente.
        </Aviso>
      )}

      {accionable && !comoPregunta && fila.pregunta !== "descartar" && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-primary btn-sm" style={{ ...BTN_GRANDE, flex: "1 1 170px" }}
                  disabled={deshabilitar || t.tipo === "fijo"}
                  title={t.tipo === "fijo" ? "Es un teléfono fijo: usalo como teléfono" : undefined}
                  onClick={() => onAplicar("whatsapp")}>
            <Ic n="whatsapp" s={16} /> Usar como WhatsApp
          </button>
          <button type="button" className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, flex: "1 1 170px" }}
                  disabled={deshabilitar} onClick={() => onAplicar("telefono")}>
            <Ic n="telefono" s={16} /> Usar como teléfono
          </button>
          <button type="button" className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, flex: "1 1 130px", color: "var(--pink)" }}
                  disabled={deshabilitar} onClick={() => onPreguntar("descartar")}>
            <Ic n="cerrar" s={15} /> Descartar
          </button>
        </div>
      )}
      {fila.ocupada && <Cargando texto="Guardando…" />}
    </li>
  );
}

function estadoIcono(e: EstadoTelefono): "dato" | "listo" | "cerrar" {
  if (e === "pendiente") return "dato";
  return e === "descartado" ? "cerrar" : "listo";
}
function estadoTono(e: EstadoTelefono): "ok" | "info" | "aviso" {
  if (e === "pendiente") return "aviso";
  return e === "descartado" ? "info" : "ok";
}
