"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { agregarNumeroAGrupos, atarGrupo, getBandejaWa, probarCloud, reprocesarEntrante,
         type AgregarAGrupos, type BandejaWa, type WaEntrante } from "@/lib/api";
import { buscarComercioPorNombre, type ComercioBusqueda } from "@/lib/comercio";
import { assignNumber, getInboxMedia, getUnknown,
         type Unknown, type UnknownGroup, type UnknownMessage, type UnknownPhone } from "@/lib/reception";

const ETIQUETA: Record<string, { texto: string; color: string }> = {
  publicada: { texto: "Publicada", color: "var(--neon)" },
  ignorada: { texto: "Ignorada", color: "var(--txt-3)" },
  sin_comercio: { texto: "No se supo de quién es", color: "var(--amber)" },
  sin_permiso: { texto: "El plan no alcanza", color: "var(--amber)" },
  error: { texto: "Error", color: "var(--pink)" },
  sin_registrar: { texto: "Sin registrar", color: "var(--txt-3)" },
};

/**
 * Qué entró por WhatsApp y qué pasó con cada mensaje.
 *
 * POR QUÉ ESTA PANTALLA
 * =====================
 * La ingesta está construida y era ciega. Cuando algo no se publica —el grupo
 * no está atado, el mensaje vino sin el código, el plan no alcanza— el crudo se
 * guarda y el motivo se va en una línea de log. Con el canal apagado alcanzaba.
 *
 * Encendido, la primera pregunta de cada día es "le dije al de la ferretería
 * que mande la foto, ¿llegó?". Contestarla por SSH significa que no la contesta
 * nadie: se le pide al comerciante que mande de nuevo, y la segunda vez tampoco
 * se publica por la misma razón que la primera. Ahí es donde se pierde un
 * comerciante que ya había aceptado.
 *
 * El filtro arranca en "hay que mirarlos": es lo único que pide acción.
 */

/**
 * Sumar un número de URUKU a los grupos que ya existen.
 *
 * POR QUÉ EXISTE ESTE BOTÓN
 * =========================
 * Al crear un grupo, el sistema mete adentro a los respaldos que estén
 * configurados EN ESE MOMENTO. Un respaldo dado de alta después queda afuera de
 * todos los grupos anteriores, y meterlo a mano en cien grupos es trabajo que
 * no se hace nunca. La factura llega tarde y entera: el día que banean al
 * operativo, cada grupo sin respaldo es un comerciante perdido — y una cuenta
 * ya baneada tampoco puede agregar a nadie.
 *
 * POR QUÉ DE A POCO Y NO TODOS DE GOLPE
 * =====================================
 * Agregar un número a cien grupos seguidos es justo el patrón que WhatsApp lee
 * como automatización, y lo que banea es la cuenta que agrega: la operativa, la
 * que sostiene el canal entero. Por eso el tope arranca chico y se corre varias
 * veces a lo largo de días. Los grupos donde el número ya está se saltean, así
 * que repetir no cuesta nada.
 */
function AgregarANuevosGrupos() {
  const [numero, setNumero] = useState("");
  const [tope, setTope] = useState(20);
  const [r, setR] = useState<AgregarAGrupos | null>(null);
  const [err, setErr] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const correr = async (aplicar: boolean) => {
    setOcupado(true); setErr("");
    try { setR(await agregarNumeroAGrupos(numero, aplicar, tope)); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo"); setR(null); }
    finally { setOcupado(false); }
  };

  return (
    <div className="panel-card glass">
      <div className="ph"><h3>Agregar un número a los grupos</h3></div>
      <div style={{ padding: "12px 16px", fontSize: 12.5, color: "var(--txt-3)" }}>
        Para los <b>respaldos</b>: los números de URUKU que tienen que estar adentro de cada
        grupo el día que se caiga el operativo. Un número nuevo no entra solo a los grupos
        viejos — esto los recorre.
      </div>
      <div style={{ display: "flex", gap: 8, padding: "0 16px 12px", flexWrap: "wrap", alignItems: "center" }}>
        <input className="input" placeholder="59168727584" value={numero}
               onChange={(e) => { setNumero(e.target.value); setR(null); }}
               style={{ width: 170 }} />
        <label style={{ fontSize: 12.5, color: "var(--txt-3)", display: "flex", gap: 6, alignItems: "center" }}>
          de a
          <input className="input" type="number" min={1} max={200} value={tope}
                 onChange={(e) => setTope(Math.max(1, Number(e.target.value) || 1))}
                 style={{ width: 70 }} />
          grupos
        </label>
        <button className="btn btn-sm btn-ghost" disabled={!numero.trim() || ocupado}
                onClick={() => correr(false)}>Ver a cuáles entraría</button>
        <button className="btn btn-sm btn-primary"
                disabled={!numero.trim() || ocupado || !r || r.aplicado || !r.a_agregar}
                onClick={() => correr(true)}>
          Agregar a {r?.a_agregar ?? 0}
        </button>
      </div>

      {err && <div style={{ padding: "0 16px 12px", color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      {r && (
        <div style={{ padding: "0 16px 14px", fontSize: 13 }}>
          <div style={{ color: "var(--txt-2)" }}>
            {r.grupos_totales} grupos en total · ya estaba en <b>{r.ya_estaba}</b>
            {r.aplicado
              ? <> · agregado a <b style={{ color: "var(--neon)" }}>{r.agregados}</b></>
              : <> · entraría a <b>{r.a_agregar}</b></>}
            {r.quedan_despues > 0 && (
              <> · quedan <b style={{ color: "var(--amber)" }}>{r.quedan_despues}</b> para otra corrida</>
            )}
          </div>

          {/* Los que fallaron van con nombre y motivo. "18 de 20" sin decir
              cuáles dos faltaron es un número que no sirve para nada: nadie
              puede ir a arreglar un grupo que no sabe cuál es. */}
          {!!r.fallaron?.length && (
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: "var(--pink)" }}>
              {r.fallaron.map((f, i) => <li key={i}>{f.grupo}: {f.motivo}</li>)}
            </ul>
          )}

          {!r.aplicado && !!r.grupos?.length && (
            <ul style={{ margin: "8px 0 0", paddingLeft: 18, color: "var(--txt-3)", fontSize: 12.5 }}>
              {r.grupos.map((g) => <li key={g.jid}>{g.nombre}</li>)}
            </ul>
          )}

          {r.quedan_despues > 0 && (
            <div style={{ marginTop: 8, color: "var(--amber)", fontSize: 12 }}>
              Dejá pasar un rato antes de la próxima tanda. Agregar un número a muchos grupos
              seguidos es el patrón que dispara el baneo, y el baneado sería el operativo.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * El Plan B: la API oficial de Meta, verificable desde acá.
 *
 * Un interruptor que nadie puede probar es una promesa. Esta tarjeta dice si
 * el token vale y a qué número corresponde (sin mandar nada), cuándo entró el
 * último mensaje por ahí (la prueba de que RECIBE), y tiene el botón para
 * mandar uno de prueba a un número propio (la prueba de que MANDA). Con las
 * tres en verde, el día que haga falta el cambio es una variable.
 */
function PlanB({ c }: { c: BandejaWa["cloud"] }) {
  const [numero, setNumero] = useState("");
  const [msg, setMsg] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const probar = async () => {
    setOcupado(true); setMsg("");
    try { const r = await probarCloud(numero); setMsg(`Enviado a ${r.a}. Miralo en ese teléfono.`); }
    catch (e) { setMsg(e instanceof Error ? e.message : "No se pudo"); }
    finally { setOcupado(false); }
  };

  const hace = (iso: string | null) => {
    if (!iso) return "nunca";
    const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    return min < 1 ? "recién" : min < 60 ? `hace ${min} min` : min < 1440 ? `hace ${Math.round(min / 60)} h` : `hace ${Math.round(min / 1440)} días`;
  };

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Plan B · API oficial de Meta</h3>
        <span style={{ fontSize: 12.5, color: c.activo ? "var(--neon)" : "var(--txt-3)" }}>
          {c.activo ? "ACTIVO: lo que sale va por acá" : "en espera · lo que sale va por WAHA"}
        </span>
      </div>
      <div style={{ padding: "12px 16px", fontSize: 13, display: "flex", flexDirection: "column", gap: 6 }}>
        <div>
          <Ic n={c.ok ? "listo" : c.configurado ? "aviso" : "ayuda"} s={14} />{" "}
          {!c.configurado ? "Sin configurar — faltan WHATSAPP_CLOUD_PHONE_ID y WHATSAPP_CLOUD_TOKEN"
            : c.estado === "TOKEN_INVALIDO" ? "El token venció o se revocó: hay que rehacerlo en la consola de Meta"
            : c.estado === "META_NO_RESPONDE" ? "Meta no responde"
            : <>Token válido · <b>{c.nombre ?? "(sin nombre verificado)"}</b> · {c.numero}
                {c.calidad && <> · calidad <b style={{ color: c.calidad === "GREEN" ? "var(--neon)" : "var(--amber)" }}>{c.calidad}</b></>}</>}
        </div>
        <div style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
          Último mensaje recibido por la API oficial: <b>{hace(c.ultimo_entrante)}</b>
          {!c.ultimo_entrante && " — mandale un WhatsApp al número de Meta y tiene que aparecer acá."}
        </div>
        {c.configurado && (
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
            <input className="input" placeholder="59175314737" value={numero}
                   onChange={(e) => setNumero(e.target.value)} style={{ width: 170 }} />
            <button className="btn btn-sm btn-ghost" disabled={!numero.trim() || ocupado || !c.ok}
                    onClick={probar}>
              Mandar un mensaje de prueba
            </button>
            {msg && <span style={{ fontSize: 12.5, color: msg.startsWith("No") ? "var(--pink)" : "var(--neon)" }}>{msg}</span>}
          </div>
        )}
        <div style={{ color: "var(--txt-3)", fontSize: 11.5 }}>
          Sólo a números de URUKU. Recibir funciona siempre que el webhook esté enganchado en
          Meta; mandar por acá recién cuando se ponga <code>WHATSAPP_PROVIDER=cloud_api</code>.
        </div>
      </div>
    </div>
  );
}


/** Una fila de la bandeja. Separada para poder listarla suelta o agrupada. */
function FilaEntrante({ m, reprocesando, reprocesar }: {
  m: WaEntrante; reprocesando: string | null; reprocesar: (id: string) => void;
}) {
  const et = ETIQUETA[m.resultado ?? "sin_registrar"] ?? ETIQUETA.sin_registrar;
  return (
      <div key={m.id} className="panel-card glass" style={{ padding: 12 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          {m.media_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={m.media_url} alt="" width={72} height={72}
                 style={{ borderRadius: 8, objectFit: "cover", flexShrink: 0 }} />
          )}
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
              <b style={{ color: et.color }}>{et.texto}</b>
              <span style={{ color: "var(--txt-3)", fontSize: 12 }}>
                {new Date(m.created_at).toLocaleString("es-BO", {
                  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                })}
              </span>
              {m.comercios?.nombre && (
                <span style={{ fontSize: 12.5 }}>
                  · {m.comercios.nombre}
                  {m.comercios.codigo && (
                    <span style={{ color: "var(--neon)", fontFamily: "monospace" }}>
                      {" "}URUKU-{m.comercios.codigo}
                    </span>
                  )}
                </span>
              )}
            </div>

            {m.motivo && (
              <div style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 3 }}>{m.motivo}</div>
            )}
            {!m.resultado && (
              <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, color: "var(--amber)" }}>
                  Se guardó pero la ingesta no terminó. Se puede volver a procesar.
                </span>
                <button className="btn btn-sm btn-ghost"
                        disabled={reprocesando === m.wa_message_id}
                        onClick={() => reprocesar(m.wa_message_id)}>
                  {reprocesando === m.wa_message_id ? "…" : "Reprocesar"}
                </button>
              </div>
            )}

            {/* De dónde vino. El grupo importa más que el número: un grupo
                sin atar es el caso que más se repite y se arregla desde la
                ficha del comercio, en "Grupo de WhatsApp". */}
            <div style={{ fontSize: 11.5, color: "var(--txt-3)", marginTop: 4, fontFamily: "monospace" }}>
              {m.wa_jid?.endsWith("@g.us") ? `grupo ${m.wa_jid}` : `de ${m.phone ?? m.wa_jid}`}
              {m.tipo ? ` · ${m.tipo}` : ""}
            </div>

            {m.body && (
              <div style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 5,
                            maxHeight: 60, overflow: "hidden" }}>
                {m.body}
              </div>
            )}
          </div>
        </div>
      </div>
  );
}

/**
 * La bandeja agrupada por comercio.
 *
 * Con un comercio, la lista plana alcanza. Con treinta, cada uno mandando
 * varias fotos por día, es infinita y no se ve nada. Agrupada, cada comercio
 * es un renglón con su cantidad y su último mensaje, y se abre el que hace
 * falta. Lo que no tiene comercio (grupos sin atar, números sueltos) va en un
 * grupo aparte al final — es lo que más pide acción.
 */
function Agrupada({ items, reprocesando, reprocesar }: {
  items: WaEntrante[]; reprocesando: string | null; reprocesar: (id: string) => void;
}) {
  const grupos = new Map<string, { titulo: string; codigo: string | null; filas: WaEntrante[] }>();
  for (const m of items) {
    const clave = m.comercios?.slug ?? `sin:${m.wa_jid ?? "?"}`;
    if (!grupos.has(clave)) {
      grupos.set(clave, {
        titulo: m.comercios?.nombre ?? `Sin comercio · ${(m.wa_jid ?? "").split("@")[0] || "?"}`,
        codigo: m.comercios?.codigo ?? null,
        filas: [],
      });
    }
    grupos.get(clave)!.filas.push(m);
  }
  // Los que tienen comercio primero, ordenados por el más reciente; los sin
  // comercio al final.
  const orden = [...grupos.entries()].sort((a, b) => {
    const sa = a[0].startsWith("sin:") ? 1 : 0, sb = b[0].startsWith("sin:") ? 1 : 0;
    if (sa !== sb) return sa - sb;
    return b[1].filas[0].created_at.localeCompare(a[1].filas[0].created_at);
  });

  return (
    <>
      {orden.map(([clave, g]) => {
        const pendientes = g.filas.filter((f) => !f.resultado || f.resultado === "sin_comercio" || f.resultado === "error").length;
        return (
          <details key={clave} className="panel-card glass" open={clave.startsWith("sin:") || pendientes > 0}
                   style={{ padding: 0 }}>
            <summary style={{ padding: "12px 16px", cursor: "pointer", listStyle: "none",
                              display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap" }}>
              <b style={{ fontSize: 14 }}>{g.titulo}</b>
              {g.codigo && <span style={{ fontFamily: "monospace", color: "var(--neon)", fontSize: 12 }}>URUKU-{g.codigo}</span>}
              <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
                {g.filas.length} {g.filas.length === 1 ? "mensaje" : "mensajes"}
                {" · último "}
                {new Date(g.filas[0].created_at).toLocaleString("es-BO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
              </span>
              {pendientes > 0 && (
                <span style={{ color: "var(--amber)", fontSize: 12.5 }}>· {pendientes} para mirar</span>
              )}
            </summary>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "0 10px 10px" }}>
              {g.filas.map((m) => (
                <FilaEntrante key={m.id} m={m} reprocesando={reprocesando} reprocesar={reprocesar} />
              ))}
            </div>
          </details>
        );
      })}
    </>
  );
}

/**
 * Recepción: lo que llega por WhatsApp, organizado para miles de comercios.
 *
 * TRES PREGUNTAS, EN ESTE ORDEN
 * =============================
 * 1. ¿Está vivo el canal? — la sesión, en grande y primero. Estuvo caída tres
 *    días sin que nadie lo supiera.
 * 2. ¿Qué pide acción? — sólo lo que llegó y no se publicó, agrupado por
 *    comercio. Es la vista por defecto y es chica aunque haya mil comercios:
 *    los problemas son la excepción.
 * 3. ¿Le llegó lo de tal comercio? — la búsqueda. Es la pregunta de soporte
 *    número uno ("el de la ferretería dice que mandó la foto"), y con miles
 *    de comercios no se contesta listando: se contesta buscando.
 *
 * Lo publicado y lo ignorado NO se listan solos: son miles de filas que no
 * piden nada. Aparecen cuando se busca un comercio, o a pedido.
 */
function Entrantes() {
  const [estado, setEstado] = useState("problemas");
  const [q, setQ] = useState("");
  const [qAplicada, setQAplicada] = useState("");
  const [d, setD] = useState<BandejaWa | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const [vista, setVista] = useState<"agrupada" | "plana">("agrupada");

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setD(await getBandejaWa(estado, 150, qAplicada)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
    finally { setCargando(false); }
  }, [estado, qAplicada]);

  useEffect(() => { cargar(); }, [cargar]);

  // La búsqueda se aplica al soltar el tecleo, no en cada letra: cada letra
  // es una consulta al servidor que busca comercios y mensajes.
  useEffect(() => {
    const t = setTimeout(() => {
      setQAplicada(q.trim());
      // Buscar un comercio muestra TODO lo suyo, no sólo los problemas: la
      // pregunta es "¿llegó?", y la respuesta puede ser "sí, y se publicó".
      if (q.trim() && estado === "problemas") setEstado("");
      if (!q.trim() && estado === "") setEstado("problemas");
    }, 350);
    return () => clearTimeout(t);
  }, [q]); // eslint-disable-line react-hooks/exhaustive-deps

  const [reprocesando, setReprocesando] = useState<string | null>(null);
  const reprocesar = async (id: string) => {
    setReprocesando(id);
    try { await reprocesarEntrante(id); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo reprocesar"); }
    finally { setReprocesando(null); }
  };

  const total = (d?.resumen ?? []).reduce((a, b) => a + b.n, 0);
  const problemas = (d?.resumen ?? [])
    .filter((r) => ["sin_comercio", "sin_permiso", "error", "sin_registrar"].includes(r.resultado))
    .reduce((a, b) => a + b.n, 0);
  const buscando = qAplicada.length > 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      {/* 1. ¿Está vivo? — sesión y Plan B en una tira compacta. */}
      {d?.sesion && (
        <div className="panel-card glass" style={{
          padding: "12px 16px", display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap",
          borderLeft: `4px solid ${d.sesion.ok ? "var(--neon)" : "var(--pink)"}`,
        }}>
          <Ic n={d.sesion.ok ? "listo" : "aviso"} s={22} />
          <div style={{ flex: 1, minWidth: 220 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>
              {d.sesion.ok ? "WhatsApp conectado"
                : !d.sesion.alcanzable ? "WAHA no responde"
                : `WhatsApp caído · ${d.sesion.estado}`}
            </div>
            <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 2 }}>
              {d.sesion.ok
                ? <>{d.sesion.nombre ?? "(sin nombre)"} · {d.sesion.numero}</>
                : "No entra ninguna oferta hasta que vuelva. Manual operativo, sección 5."}
            </div>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--txt-3)", textAlign: "right" }}>
            <div>últimos 7 días: <b style={{ color: "var(--txt)" }}>{total}</b> mensajes</div>
            <div>{d.config.propios} propios · {d.config.explorador} explorador · {d.config.solo_lectura ? "sólo lectura" : "con envíos"}</div>
          </div>
        </div>
      )}

      {d && d.config.propios === 0 && (
        <div className="panel-card glass" style={{ padding: 12, fontSize: 12.5, color: "var(--amber)" }}>
          <Ic n="aviso" s={15} /> Sin números propios cargados, cualquier mensaje que escriba alguien de URUKU dentro de
          un grupo se publica como oferta del comerciante. Va en <code>WA_NUMEROS_PROPIOS</code>.
        </div>
      )}

      {/* 3. ¿Le llegó lo de tal comercio? — la búsqueda, arriba de la lista. */}
      <div className="panel-card glass" style={{ padding: "12px 16px", display: "flex", gap: 10,
                                                   alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" style={{ flex: 1, minWidth: 240 }}
               placeholder="Buscar un comercio: nombre, código URUKU-XXXX o teléfono"
               value={q} onChange={(e) => setQ(e.target.value)} />
        {buscando && (
          <button className="btn btn-sm btn-ghost" onClick={() => setQ("")}><Ic n="cerrar" s={13} /> Limpiar</button>
        )}
        <button className="btn btn-ghost btn-sm" onClick={cargar} disabled={cargando}>
          {cargando ? "…" : "↻"}
        </button>
      </div>

      {/* 2. ¿Qué pide acción? — filtros: "Para mirar" por defecto. Lo demás,
          a pedido o dentro de una búsqueda. */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        {[
          { k: "problemas", t: `Para mirar${problemas ? ` (${problemas})` : ""}` },
          { k: "publicada", t: "Publicadas" },
          { k: "ignorada", t: "Ignoradas" },
          { k: "", t: buscando ? "Todo lo del comercio" : "Últimas 150" },
        ].map((f) => (
          <button key={f.k} className={`btn btn-sm ${estado === f.k ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setEstado(f.k)}>
            {f.t}
          </button>
        ))}
        <button className="btn btn-ghost btn-sm" style={{ marginLeft: "auto" }}
                onClick={() => setVista(vista === "agrupada" ? "plana" : "agrupada")}>
          {vista === "agrupada" ? "Lista plana" : "Por comercio"}
        </button>
      </div>

      {!cargando && (d?.items.length ?? 0) === 0 && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          {buscando ? `Nada de "${qAplicada}" con ese filtro.`
            : estado === "problemas" ? "Nada pendiente de mirar."
            : "No hay mensajes con ese filtro."}
        </div>
      )}

      {vista === "agrupada"
        ? <Agrupada items={d?.items ?? []} reprocesando={reprocesando} reprocesar={reprocesar} />
        : (d?.items ?? []).map((m) => (
            <FilaEntrante key={m.id} m={m} reprocesando={reprocesando} reprocesar={reprocesar} />
          ))}

      {/* Lo que no es del día a día, abajo y plegado. */}
      {d?.cloud && (
        <details className="panel-card glass" style={{ padding: 0 }}>
          <summary style={{ padding: "12px 16px", cursor: "pointer", listStyle: "none", fontSize: 13.5,
                            display: "flex", gap: 10, alignItems: "baseline" }}>
            <b>Plan B · API oficial de Meta</b>
            <span style={{ color: d.cloud.ok ? "var(--neon)" : "var(--txt-3)", fontSize: 12.5 }}>
              {d.cloud.activo ? "ACTIVO" : d.cloud.ok ? "probado, en espera" : d.cloud.configurado ? "configurado con error" : "sin configurar"}
            </span>
          </summary>
          <div style={{ padding: "0 4px 4px" }}><PlanB c={d.cloud} /></div>
        </details>
      )}

      {d && !d.config.solo_lectura && <AgregarANuevosGrupos />}
    </div>
  );
}

/* ───────────────────────── Sin dueño ─────────────────────────
 *
 * Fotos y grupos que llegaron y no se supo de quién son (docs/grupos-por-comercio.md
 * §9.4). Sin esto la foto de un comerciante que escribió desde un número nuevo se
 * perdía en silencio: acá se ve y, con «Es de…», se le pone dueño y se publica.
 */

const fechaCorta = (iso: string) =>
  new Date(iso).toLocaleString("es-BO", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });

/** Sigue el estado de la conexión: sin red no se puede asignar nada. */
function useOnline(): boolean {
  const [on, setOn] = useState(true);
  useEffect(() => {
    const act = () => setOn(navigator.onLine);
    act();
    window.addEventListener("online", act);
    window.addEventListener("offline", act);
    return () => { window.removeEventListener("online", act); window.removeEventListener("offline", act); };
  }, []);
  return on;
}

/**
 * Miniatura PRIVADA: se baja con el token del panel y se muestra como `blob:`.
 * La URL se revoca al desmontar o cuando cambia la foto. Se pide recién cuando
 * entra en pantalla, para no bajar 60 fotos de una al abrir la pestaña.
 */
function Miniatura({ m }: { m: UnknownMessage }) {
  const caja = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);
  const [intento, setIntento] = useState(0);
  const [url, setUrl] = useState("");
  const [estado, setEstado] = useState<"espera" | "cargando" | "ok" | "purgada" | "error">("espera");
  const [grande, setGrande] = useState(false);

  useEffect(() => {
    const el = caja.current;
    if (!el || typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const io = new IntersectionObserver((es) => {
      if (es.some((e) => e.isIntersecting)) { setVisible(true); io.disconnect(); }
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!visible || !m.has_media) return;
    let vivo = true;
    let creada = "";
    setEstado("cargando");
    getInboxMedia(m.wa_message_id)
      .then((b) => {
        if (!vivo) return;
        if (!b) { setEstado("purgada"); return; }
        creada = URL.createObjectURL(b);
        setUrl(creada);
        setEstado("ok");
      })
      .catch(() => { if (vivo) setEstado("error"); });
    return () => {
      vivo = false;
      if (creada) URL.revokeObjectURL(creada);
      setUrl("");
    };
  }, [visible, intento, m.has_media, m.wa_message_id]);

  useEffect(() => {
    if (!grande) return;
    const f = (e: KeyboardEvent) => { if (e.key === "Escape") setGrande(false); };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [grande]);

  const marco: React.CSSProperties = {
    width: 72, height: 72, borderRadius: 8, flexShrink: 0, display: "flex", flexDirection: "column",
    alignItems: "center", justifyContent: "center", gap: 2, fontSize: 10.5, textAlign: "center",
    color: "var(--txt-3)", background: "rgba(127,127,127,.12)",
  };

  return (
    <div ref={caja} style={{ flexShrink: 0 }}>
      {estado === "ok" ? (
        <>
          <button type="button" onClick={() => setGrande(true)} aria-label="Ver la foto en grande"
                  style={{ padding: 0, border: 0, background: "none", cursor: "zoom-in", display: "block" }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={url} alt="Foto recibida" width={72} height={72}
                 style={{ borderRadius: 8, objectFit: "cover", display: "block" }} />
          </button>
          {grande && (
            <div role="dialog" aria-modal="true" aria-label="Foto recibida" onClick={() => setGrande(false)}
                 style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.85)",
                          display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setGrande(false)}
                      style={{ position: "absolute", top: 12, right: 12 }}>
                <Ic n="cerrar" s={14} /> Cerrar
              </button>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={url} alt="Foto recibida" style={{ maxWidth: "100%", maxHeight: "100%", borderRadius: 8 }} />
            </div>
          )}
        </>
      ) : !m.has_media ? (
        <div style={marco}><Ic n="foto" s={16} />sin foto</div>
      ) : estado === "purgada" ? (
        <div style={marco}><Ic n="foto" s={16} />ya se borró</div>
      ) : estado === "error" ? (
        <button type="button" onClick={() => setIntento((n) => n + 1)} style={{ ...marco, border: 0, cursor: "pointer" }}>
          <Ic n="aviso" s={16} />no cargó · reintentar
        </button>
      ) : (
        <div style={marco} aria-busy="true"><Ic n="foto" s={16} />cargando</div>
      )}
    </div>
  );
}

/** El buscador de comercio + confirmación de «Es de…». */
function AsignarPanel({ it, offline, onCancelar, onHecho }: {
  it: UnknownPhone | UnknownGroup; offline: boolean; onCancelar: () => void; onHecho: (texto: string) => void;
}) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<ComercioBusqueda[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [errBusq, setErrBusq] = useState("");
  const [elegido, setElegido] = useState<ComercioBusqueda | null>(null);
  const [label, setLabel] = useState("Encargado/a");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const t = q.trim();
    if (t.length < 2) { setRes(null); setErrBusq(""); return; }
    let vivo = true;
    const h = setTimeout(() => {
      setBuscando(true);
      buscarComercioPorNombre(t)
        .then((r) => { if (vivo) { setRes(r); setErrBusq(""); } })
        .catch(() => { if (vivo) setErrBusq("No se pudo buscar. Revisá la conexión."); })
        .finally(() => { if (vivo) setBuscando(false); });
    }, 300);
    return () => { vivo = false; clearTimeout(h); };
  }, [q]);

  const quien = it.kind === "phone" ? it.phone_masked : `el grupo ${it.group_name || it.group_jid.split("@")[0]}`;

  const confirmar = async () => {
    if (!elegido) return;
    setEnviando(true); setError("");
    try {
      if (it.kind === "phone") {
        const r = await assignNumber(it.phone, elegido.id, label.trim());
        onHecho(
          `Listo: ${it.phone_masked} es de ${elegido.nombre}. ` +
          (r.reprocessed > 0
            ? `Se reprocesaron ${r.reprocessed} ${r.reprocessed === 1 ? "mensaje" : "mensajes"} ` +
              `(${r.published} publicados, ${r.ignored} ignorados).`
            : "No había mensajes para reprocesar."));
      } else {
        await atarGrupo(elegido.id, it.group_jid, it.group_name ?? undefined);
        onHecho(`Listo: el grupo quedó atado a ${elegido.nombre}. Lo que mande de ahora en más entra solo.`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo asignar");
    } finally { setEnviando(false); }
  };

  return (
    <div style={{ marginTop: 10, padding: 12, borderRadius: 10, background: "rgba(127,127,127,.08)" }}>
      <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6 }}>
        ¿De qué comercio es {quien}?
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input className="input" style={{ flex: 1, minWidth: 200 }} autoFocus
               placeholder="Buscá el comercio por nombre" aria-label="Buscar comercio"
               value={q} onChange={(e) => { setQ(e.target.value); setElegido(null); setError(""); }} />
        <button type="button" className="btn btn-sm btn-ghost" onClick={onCancelar} disabled={enviando}>
          <Ic n="cerrar" s={13} /> Cancelar
        </button>
      </div>

      {buscando && <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 6 }}>Buscando…</div>}
      {errBusq && <div style={{ fontSize: 12.5, color: "var(--pink)", marginTop: 6 }}><Ic n="aviso" s={13} /> {errBusq}</div>}
      {!buscando && !errBusq && res && res.length === 0 && (
        <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 6 }}>No hay comercios con ese nombre.</div>
      )}

      {!elegido && res && res.length > 0 && (
        <ul style={{ listStyle: "none", margin: "8px 0 0", padding: 0, display: "flex", flexDirection: "column", gap: 6 }}>
          {res.map((c) => (
            <li key={c.id}>
              <button type="button" className="btn btn-ghost" onClick={() => { setElegido(c); setError(""); }}
                      style={{ width: "100%", justifyContent: "flex-start", textAlign: "left", minHeight: 44 }}>
                <b>{c.nombre}</b>
                {c.direccion && <span style={{ color: "var(--txt-3)", fontSize: 12 }}> · {c.direccion}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {elegido && (
        <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <div style={{ fontSize: 13 }}>
            <Ic n="comercios" s={14} />{" "}
            {it.kind === "phone"
              ? <>Vas a dejar <b>{it.phone_masked}</b> como número de <b>{elegido.nombre}</b> y se van a publicar sus fotos.</>
              : <>Vas a atar este grupo a <b>{elegido.nombre}</b>.</>}
          </div>
          {it.kind === "phone" && (
            <label style={{ fontSize: 12.5, color: "var(--txt-3)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              Quién es
              <input className="input" style={{ width: 200 }} value={label} maxLength={60}
                     onChange={(e) => setLabel(e.target.value)} />
            </label>
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary" style={{ minHeight: 44 }}
                    disabled={enviando || offline} onClick={confirmar}>
              {enviando ? "Guardando…" : <><Ic n="listo" s={15} /> Confirmar</>}
            </button>
            <button type="button" className="btn btn-ghost" style={{ minHeight: 44 }}
                    disabled={enviando} onClick={() => { setElegido(null); setError(""); }}>
              Elegir otro
            </button>
          </div>
        </div>
      )}

      {error && (
        <div role="alert" style={{ marginTop: 8, fontSize: 13, color: "var(--pink)" }}>
          <Ic n="aviso" s={14} /> {error}
        </div>
      )}
      {offline && <div style={{ marginTop: 8, fontSize: 12.5, color: "var(--amber)" }}>Sin conexión: no se puede confirmar ahora.</div>}
    </div>
  );
}

const MAX_MINIATURAS = 4;

function FilaSinDueno({ it, offline, abierta, onAbrir, onCerrar, onHecho }: {
  it: Unknown; offline: boolean; abierta: boolean;
  onAbrir: () => void; onCerrar: () => void; onHecho: (texto: string) => void;
}) {
  // Entradas a la comunidad (E2): se muestran, pero se resuelven con su propio flujo.
  if (it.kind === "community_join") {
    return (
      <div className="panel-card glass" style={{ padding: 12, fontSize: 13 }}>
        <b>Entró a la comunidad de comercios</b>
        <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
          {" · "}{it.phone_masked ?? "número oculto"} · {fechaCorta(it.at)}
        </span>
        {it.candidates[0] && (
          <div style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 3 }}>
            Probable: {it.candidates[0].nombre} ({it.candidates[0].why})
          </div>
        )}
      </div>
    );
  }

  const fotos = it.messages.filter((m) => m.has_media);
  const textos = it.messages.filter((m) => m.body).slice(0, 2);
  const titulo = it.kind === "phone"
    ? <><Ic n="telefono" s={14} /> <b>{it.phone_masked}</b></>
    : <><Ic n="gente" s={14} /> <b>Grupo sin atar</b> <span style={{ fontFamily: "monospace", fontSize: 12, color: "var(--txt-3)" }}>
        {it.group_name || it.group_jid}</span></>;

  return (
    <div className="panel-card glass" style={{ padding: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "baseline", flexWrap: "wrap" }}>
        {titulo}
        <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
          · {it.count} {it.count === 1 ? "mensaje" : "mensajes"} · último {fechaCorta(it.at)}
        </span>
        {!abierta && (
          <button type="button" className="btn btn-sm btn-primary" style={{ marginLeft: "auto", minHeight: 40 }}
                  disabled={offline} onClick={onAbrir}>
            Es de…
          </button>
        )}
      </div>

      {it.messages.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8 }}>
          {it.messages.slice(0, MAX_MINIATURAS).map((m) => <Miniatura key={m.wa_message_id} m={m} />)}
          {it.messages.length > MAX_MINIATURAS && (
            <span style={{ alignSelf: "center", fontSize: 12, color: "var(--txt-3)" }}>
              +{it.messages.length - MAX_MINIATURAS} más
            </span>
          )}
        </div>
      )}
      {fotos.length === 0 && it.messages.length > 0 && (
        <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Sin fotos guardadas.</div>
      )}
      {textos.map((m) => (
        <div key={m.wa_message_id} style={{ fontSize: 12.5, color: "var(--txt-2)", marginTop: 4, maxHeight: 40, overflow: "hidden" }}>
          «{m.body}»
        </div>
      ))}

      {abierta && <AsignarPanel it={it} offline={offline} onCancelar={onCerrar} onHecho={onHecho} />}
    </div>
  );
}

function SinDueno({ items, cargando, err, dias, setDias, recargar, offline }: {
  items: Unknown[] | null; cargando: boolean; err: string; dias: number;
  setDias: (n: number) => void; recargar: () => void; offline: boolean;
}) {
  const [abierta, setAbierta] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div className="panel-card glass" style={{ padding: "12px 16px", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 220, fontSize: 12.5, color: "var(--txt-3)" }}>
          Fotos y grupos que llegaron y no se sabe de quién son. Con <b>Es de…</b> se les pone
          dueño y lo que estaba guardado se publica.
        </div>
        <label style={{ fontSize: 12.5, color: "var(--txt-3)", display: "flex", gap: 6, alignItems: "center" }}>
          últimos
          <select className="input" value={dias} onChange={(e) => setDias(Number(e.target.value))} style={{ width: 100 }}>
            <option value={7}>7 días</option>
            <option value={14}>14 días</option>
            <option value={30}>30 días</option>
          </select>
        </label>
        <button type="button" className="btn btn-sm btn-ghost" onClick={recargar} disabled={cargando} aria-label="Actualizar">
          {cargando ? "…" : <Ic n="actualizar" s={14} />}
        </button>
      </div>

      {offline && (
        <div className="panel-card glass" role="status" style={{ padding: 12, fontSize: 13, color: "var(--amber)" }}>
          <Ic n="aviso" s={15} /> Sin conexión. Podés mirar lo que ya cargó, pero no asignar hasta que vuelva.
        </div>
      )}

      {aviso && (
        <div className="panel-card glass" role="status" style={{ padding: 12, fontSize: 13, color: "var(--neon)",
                                                                  display: "flex", gap: 8, alignItems: "center" }}>
          <Ic n="listo" s={16} /> <span style={{ flex: 1 }}>{aviso}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setAviso("")} aria-label="Cerrar aviso">
            <Ic n="cerrar" s={13} />
          </button>
        </div>
      )}

      {err && (
        <div className="panel-card glass" role="alert" style={{ padding: 14, color: "var(--pink)", fontSize: 13,
                                                                  display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <Ic n="aviso" s={15} /> <span style={{ flex: 1 }}>{err}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={recargar}>Reintentar</button>
        </div>
      )}

      {cargando && !items && (
        <div className="panel-card glass" aria-busy="true" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          Cargando lo que está sin dueño…
        </div>
      )}

      {items && items.length === 0 && !err && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          <Ic n="listo" s={18} /> No hay nada sin dueño en los últimos {dias} días.
        </div>
      )}

      {(items ?? []).map((it) => (
        <FilaSinDueno key={it.key} it={it} offline={offline} abierta={abierta === it.key}
                      onAbrir={() => setAbierta(it.key)} onCerrar={() => setAbierta(null)}
                      onHecho={(t) => { setAviso(t); setAbierta(null); recargar(); }} />
      ))}
    </div>
  );
}

/** Recepción: lo que llegó (Entrantes) y lo que no tiene dueño (Sin dueño). */
export function BandejaWhatsApp() {
  const [pestana, setPestana] = useState<"entrantes" | "sin_dueno">("entrantes");
  const [dias, setDias] = useState(30);
  const [items, setItems] = useState<Unknown[] | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);
  const offline = !useOnline();

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setItems(await getUnknown(dias)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar lo que está sin dueño"); }
    finally { setCargando(false); }
  }, [dias]);

  useEffect(() => { cargar(); }, [cargar]);

  const n = items?.length ?? 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div role="tablist" aria-label="Recepción" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" role="tab" aria-selected={pestana === "entrantes"}
                className={`btn btn-sm ${pestana === "entrantes" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setPestana("entrantes")}>
          Entrantes
        </button>
        <button type="button" role="tab" aria-selected={pestana === "sin_dueno"}
                className={`btn btn-sm ${pestana === "sin_dueno" ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setPestana("sin_dueno")}>
          Sin dueño{n > 0 ? ` (${n})` : ""}
        </button>
      </div>

      {pestana === "entrantes"
        ? <Entrantes />
        : <SinDueno items={items} cargando={cargando} err={err} dias={dias} setDias={setDias}
                    recargar={cargar} offline={offline} />}
    </div>
  );
}
