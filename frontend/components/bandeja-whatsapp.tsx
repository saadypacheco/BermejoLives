"use client";

import { useCallback, useEffect, useState } from "react";
import { agregarNumeroAGrupos, getBandejaWa, probarCloud,
         type AgregarAGrupos, type BandejaWa } from "@/lib/api";

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
    try { const r = await probarCloud(numero); setMsg(`✓ Enviado a ${r.a}. Miralo en ese teléfono.`); }
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
          {c.ok ? "🟢" : c.configurado ? "🔴" : "○"}{" "}
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
            {msg && <span style={{ fontSize: 12.5, color: msg.startsWith("✓") ? "var(--neon)" : "var(--pink)" }}>{msg}</span>}
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

export function BandejaWhatsApp() {
  const [estado, setEstado] = useState("problemas");
  const [d, setD] = useState<BandejaWa | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true);
    try { setD(await getBandejaWa(estado, 150)); setErr(""); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo cargar"); }
    finally { setCargando(false); }
  }, [estado]);

  useEffect(() => { cargar(); }, [cargar]);

  const total = (d?.resumen ?? []).reduce((a, b) => a + b.n, 0);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {err && <div className="panel-card glass" style={{ padding: 14, color: "var(--pink)", fontSize: 13 }}>{err}</div>}

      {/* LA SESIÓN, EN GRANDE Y PRIMERO. Estuvo caída tres días sin que nadie
          lo supiera: el sitio andaba, el panel andaba, y no entraba una sola
          oferta. Esto es lo primero que tiene que ver quien abra la pestaña. */}
      {d?.sesion && (
        <div className="panel-card glass" style={{
          padding: "14px 16px", display: "flex", gap: 14, alignItems: "center",
          borderLeft: `4px solid ${d.sesion.ok ? "var(--neon)" : "var(--pink)"}`,
        }}>
          <span style={{ fontSize: 26 }}>{d.sesion.ok ? "🟢" : "🔴"}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700 }}>
              {d.sesion.ok
                ? "WhatsApp conectado"
                : !d.sesion.alcanzable
                  ? "WAHA no responde"
                  : `WhatsApp caído · ${d.sesion.estado}`}
            </div>
            <div style={{ fontSize: 12.5, color: "var(--txt-3)", marginTop: 2 }}>
              {d.sesion.ok
                ? <>{d.sesion.nombre ?? "(sin nombre)"} · {d.sesion.numero}</>
                : "No entra ninguna oferta hasta que vuelva. Hay que re-vincular desde la tablet: ver docs/numeros-whatsapp-uruku.md."}
            </div>
          </div>
        </div>
      )}

      {/* El estado del canal. Sin esto, "no llega nada" y "llega y se descarta"
          se ven igual desde acá — y son problemas opuestos: uno se arregla en
          el teléfono y el otro en el panel. */}
      <div className="panel-card glass">
        <div className="ph">
          <h3>Canal de WhatsApp</h3>
          <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>últimos 7 días</span>
        </div>
        <div style={{ padding: "12px 16px", display: "flex", gap: 18, flexWrap: "wrap", fontSize: 13 }}>
          <span><b style={{ fontSize: 18 }}>{total}</b> mensajes</span>
          {(d?.resumen ?? []).map((r) => (
            <span key={r.resultado} style={{ color: ETIQUETA[r.resultado]?.color ?? "var(--txt-2)" }}>
              {ETIQUETA[r.resultado]?.texto ?? r.resultado}: <b>{r.n}</b>
            </span>
          ))}
        </div>
        <div style={{ padding: "0 16px 14px", fontSize: 12, color: "var(--txt-3)" }}>
          {/* Cuántos, no cuáles: el panel lo usa un administrador, pero un
              teléfono en pantalla se saca en una foto. */}
          Números propios configurados: <b>{d?.config.propios ?? 0}</b> ·
          {" "}explorador: <b>{d?.config.explorador ?? 0}</b> ·
          {" "}contacto del explorador: <b>{d?.config.contacto_explorador ? "sí" : "no"}</b>
          {d && d.config.propios === 0 && (
            <div style={{ color: "var(--amber)", marginTop: 6 }}>
              ⚠️ Sin números propios cargados, cualquier mensaje que escriba alguien de URUKU
              dentro de un grupo se publica como oferta del comerciante. Va en
              <code> WA_NUMEROS_PROPIOS</code> del <code>backend/.env</code>, y sin
              placeholders: <code>591XXXXXXXX</code> se normaliza a <code>591</code> y apaga
              la guarda sin avisar.
            </div>
          )}
        </div>

        <div style={{ display: "flex", gap: 8, padding: "0 16px 14px", flexWrap: "wrap" }}>
          {[
            { k: "problemas", t: "Hay que mirarlos" },
            { k: "publicada", t: "Publicadas" },
            { k: "ignorada", t: "Ignoradas" },
            { k: "", t: "Todo" },
          ].map((f) => (
            <button key={f.k} className={`btn btn-sm ${estado === f.k ? "btn-primary" : "btn-ghost"}`}
                    onClick={() => setEstado(f.k)}>
              {f.t}
            </button>
          ))}
          <button className="btn btn-ghost btn-sm" onClick={cargar} disabled={cargando}>
            {cargando ? "…" : "↻ Actualizar"}
          </button>
        </div>
      </div>

      {d?.cloud && <PlanB c={d.cloud} />}

      {/* Con WAHA en sólo lectura, los respaldos se agregan a mano desde la
          tablet, y este botón no puede hacer nada más que fallar. */}
      {d && !d.config.solo_lectura && <AgregarANuevosGrupos />}

      {!cargando && (d?.items.length ?? 0) === 0 && (
        <div className="panel-card glass" style={{ padding: 24, textAlign: "center", color: "var(--txt-3)" }}>
          {estado === "problemas"
            ? "Nada pendiente de mirar. 🎉"
            : "No hay mensajes con ese filtro."}
        </div>
      )}

      {(d?.items ?? []).map((m) => {
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
      })}
    </div>
  );
}
