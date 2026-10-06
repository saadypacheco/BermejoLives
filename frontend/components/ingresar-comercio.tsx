"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { WhatsApp } from "@/components/icons";
import { Ic } from "@/components/ic";
import { ClaveUnaVez } from "@/components/clave-una-vez";
import {
  comercioIngresar, comercioLogin, comercioRecuperar, comercioRecuperarEstado, comercioRecuperarConfirmar,
  VariosNegocios, ClaveAnulada,
  type ComercioSession, type NegocioDelNumero,
} from "@/lib/comercio";
import { CONFIRMACION_VENCE_MS, LARGO_CLAVE, POLL_MS, mensajeDeError, soloClave } from "@/lib/acceso";

/**
 * Ingreso del comerciante, compartido por /mi-comercio y /autoregistro.
 *
 * 1. Lo normal es celular + clave de 6 números: no depende de WhatsApp.
 * 2. «Primera vez o te olvidaste la clave»: confirma con su WhatsApp (mandando
 *    él un mensaje). Si el negocio no tenía clave, ahí se le muestra, una vez.
 * 3. Email y contraseña queda, discreto, para las cuentas viejas que lo tienen.
 */
export function LoginComercio({ onLogged, modoInicial = "clave", whatsappInicial = "" }: {
  onLogged: (s: ComercioSession) => void;
  /** «whatsapp» abre directo «Entrar con tu WhatsApp» (p. ej. tras el 409 del autoregistro). */
  modoInicial?: "clave" | "whatsapp";
  whatsappInicial?: string;
}) {
  const [modo, setModo] = useState<"clave" | "whatsapp" | "email">(modoInicial);
  // El celular se conserva al pasar de «entrar con clave» a «primera vez»: la
  // persona ya lo escribió y no tiene por qué escribirlo dos veces.
  const [whatsapp, setWhatsapp] = useState(whatsappInicial);

  if (modo === "email") return <LoginConEmail onVolver={() => setModo("clave")} onLogged={onLogged} />;
  if (modo === "whatsapp") {
    return <IngresarConWhatsapp whatsapp={whatsapp} setWhatsapp={setWhatsapp} onVolver={() => setModo("clave")} onLogged={onLogged} />;
  }
  return (
    <IngresarConClave whatsapp={whatsapp} setWhatsapp={setWhatsapp}
      onPrimeraVez={() => setModo("whatsapp")} onUsarEmail={() => setModo("email")} onLogged={onLogged} />
  );
}

const linkSecundario: React.CSSProperties = {
  background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer",
};
const tarjeta: React.CSSProperties = { padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 };

/** El campo del celular, con el aviso de que 8 dígitos se toman como Bolivia. */
function CampoCelular({ valor, onChange, idAyuda }: { valor: string; onChange: (v: string) => void; idAyuda: string }) {
  const digitos = valor.replace(/\D/g, "");
  const tomaComo591 = digitos.length === 8;
  return (
    <>
      <input className="adm-input" value={valor} onChange={(e) => onChange(e.target.value)}
        placeholder="Tu celular (ej: 70000000)" inputMode="tel" autoComplete="tel" aria-label="Tu celular"
        aria-describedby={tomaComo591 ? idAyuda : undefined} />
      {tomaComo591 && (
        <span id={idAyuda} style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
          Lo tomamos como un número de Bolivia: <b>+591 {digitos}</b>. Si es de otro país, escribilo con el código del país.
        </span>
      )}
    </>
  );
}

function IngresarConClave({ whatsapp, setWhatsapp, onPrimeraVez, onUsarEmail, onLogged }: {
  whatsapp: string; setWhatsapp: (v: string) => void;
  onPrimeraVez: () => void; onUsarEmail: () => void; onLogged: (s: ComercioSession) => void;
}) {
  const [clave, setClave] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  // La clave se anuló por seguridad: probar otra no sirve, sólo el WhatsApp.
  const [anulada, setAnulada] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!whatsapp.trim()) { setErr("Ingresá tu celular."); return; }
    if (clave.length !== LARGO_CLAVE) { setErr(`La clave tiene ${LARGO_CLAVE} números.`); return; }
    setErr(""); setAnulada(false); setLoading(true);
    try { onLogged(await comercioIngresar(whatsapp.trim(), clave)); }
    // 401 («Celular o clave incorrectos»), 401 de clave anulada y 429
    // («Demasiados intentos…»): el `detail` tal cual.
    catch (ex) {
      setErr(mensajeDeError(ex, "No se pudo entrar. Probá de nuevo."));
      setAnulada(ex instanceof ClaveAnulada);
      setClave("");
    }
    finally { setLoading(false); }
  }

  return (
    <form onSubmit={submit} className="glass" style={tarjeta}>
      <h2 style={{ fontSize: 18, margin: 0 }}>Entrá con tu celular y tu clave</h2>
      <CampoCelular valor={whatsapp} onChange={setWhatsapp} idAyuda="cel-clave-negocio" />
      <input className="adm-input" type="password" value={clave} onChange={(e) => setClave(soloClave(e.target.value))}
        placeholder={`Tu clave de ${LARGO_CLAVE} números`} inputMode="numeric" pattern="[0-9]*" maxLength={LARGO_CLAVE}
        autoComplete="current-password" aria-label={`Tu clave de ${LARGO_CLAVE} números`} />
      {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
      {anulada && (
        <button type="button" className="btn btn-primary" onClick={onPrimeraVez}>
          <WhatsApp style={{ width: 16, height: 16 }} /> Entrar con tu WhatsApp
        </button>
      )}
      <button className={anulada ? "btn" : "btn btn-primary"} type="submit" disabled={loading}
        style={anulada ? { border: "1px solid var(--stroke)" } : undefined}>{loading ? "Entrando…" : "Entrar"}</button>
      <button type="button" onClick={onPrimeraVez} style={{ ...linkSecundario, color: "var(--neon)", fontSize: 14 }}>
        ¿Primera vez o te olvidaste la clave? Entrá con tu WhatsApp
      </button>
      <button type="button" onClick={onUsarEmail} style={{ ...linkSecundario, fontSize: 12 }}>
        Tengo email y contraseña
      </button>
    </form>
  );
}

function LoginConEmail({ onVolver, onLogged }: { onVolver: () => void; onLogged: (s: ComercioSession) => void }) {
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setLoading(true);
    try { onLogged(await comercioLogin(email, pass)); }
    catch { setErr("El email o la contraseña no coinciden."); }
    finally { setLoading(false); }
  }

  return (
    <form onSubmit={submit} className="glass" style={tarjeta}>
      <input className="adm-input" type="email" inputMode="email" autoCapitalize="none"
        autoCorrect="off" spellCheck={false} autoComplete="username"
        value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
      <input className="adm-input" type="password" autoComplete="current-password"
        value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
      {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
      <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Entrando…" : "Entrar"}</button>
      <button type="button" onClick={onVolver} style={linkSecundario}>← Entrar con tu celular y tu clave</button>
    </form>
  );
}

type Paso = "pedir" | "elegir" | "esperando" | "entrando" | "falla" | "vencido" | "clave";

export function IngresarConWhatsapp({ whatsapp, setWhatsapp, onVolver, onLogged }: {
  whatsapp: string; setWhatsapp: (v: string) => void; onVolver: () => void; onLogged: (s: ComercioSession) => void;
}) {
  const [codigo, setCodigo] = useState("");
  const [waLink, setWaLink] = useState("");
  const [paso, setPaso] = useState<Paso>("pedir");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  // Si el número está en varios negocios: la lista para elegir y el elegido.
  const [negocios, setNegocios] = useState<NegocioDelNumero[]>([]);
  const [comercioId, setComercioId] = useState<string | undefined>(undefined);
  // La sesión queda en espera mientras se muestra la clave nueva: si se entrara
  // ya, la pantalla cambiaría y la clave se perdería sin leerla.
  const [entrega, setEntrega] = useState<{ sesion: ComercioSession; clave: string } | null>(null);
  const intervaloRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // El polling puede disparar dos veces antes de que cambie el paso: se entra una sola vez.
  const entrandoRef = useRef(false);

  const parar = () => { if (intervaloRef.current) { clearInterval(intervaloRef.current); intervaloRef.current = null; } };
  useEffect(() => parar, []);

  async function entrar(wa: string, c: string) {
    if (entrandoRef.current) return;
    entrandoRef.current = true;
    parar();
    setPaso("entrando"); setErr("");
    try {
      const { sesion, claveNueva } = await comercioRecuperarConfirmar(wa, c);
      if (claveNueva) { setEntrega({ sesion, clave: claveNueva }); setPaso("clave"); }
      else onLogged(sesion);
    } catch (ex) {
      setErr(mensajeDeError(ex, "No se pudo entrar"));
      setPaso("falla");
    } finally {
      entrandoRef.current = false;
    }
  }

  /** Espera el mensaje de confirmación; a los 15 minutos el código ya no sirve. */
  function esperar(wa: string, c: string) {
    parar();
    const inicio = Date.now();
    intervaloRef.current = setInterval(async () => {
      if (Date.now() - inicio >= CONFIRMACION_VENCE_MS) { parar(); setPaso("vencido"); return; }
      try {
        if (await comercioRecuperarEstado(wa, c)) void entrar(wa, c);
      } catch { /* sin conexión: se reintenta en el próximo ciclo */ }
    }, POLL_MS);
  }

  async function solicitar(wa: string, id?: string) {
    setLoading(true); setErr("");
    try {
      const { codigo: c, wa_link } = await comercioRecuperar(wa, id);
      setCodigo(c); setWaLink(wa_link); setComercioId(id); setPaso("esperando");
      esperar(wa, c);
    } catch (ex) {
      if (ex instanceof VariosNegocios) { setNegocios(ex.negocios); setPaso("elegir"); return; }
      // 404 (el número no es de ningún negocio), 400 (número inválido) o 429: el
      // backend dice qué pasó y se muestra tal cual.
      setErr(mensajeDeError(ex, "No se pudo generar el código. Probá de nuevo."));
    } finally { setLoading(false); }
  }

  function pedirCodigo(e: React.FormEvent) {
    e.preventDefault();
    const wa = whatsapp.trim();
    if (!wa) { setErr("Ingresá el WhatsApp con el que registraste tu negocio"); return; }
    void solicitar(wa);
  }

  function volver() {
    parar();
    setPaso("pedir"); setErr(""); setComercioId(undefined);
  }

  if (paso === "pedir") {
    return (
      <form onSubmit={pedirCodigo} className="glass" style={tarjeta}>
        <h2 style={{ fontSize: 18, margin: 0 }}>Primera vez o te olvidaste la clave</h2>
        <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>
          Confirmás con tu propio WhatsApp, el número con el que está registrado tu negocio.
          Si todavía no tenías clave, te la mostramos al entrar.
        </p>
        <CampoCelular valor={whatsapp} onChange={setWhatsapp} idAyuda="cel-wa-negocio" />
        {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
        <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Generando…" : "Continuar"}</button>
        <button type="button" onClick={onVolver} style={linkSecundario}>← Entrar con tu celular y tu clave</button>
        <Link href="/recuperar-negocio" style={{ color: "var(--txt-3)", fontSize: 13 }}>
          ¿Cambiaste de número de WhatsApp?
        </Link>
      </form>
    );
  }

  if (paso === "elegir") {
    return (
      <div className="glass" style={tarjeta}>
        <h2 style={{ fontSize: 18, margin: 0 }}>Ese número está en más de un negocio</h2>
        <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>Elegí el tuyo para confirmar con tu WhatsApp:</p>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {negocios.map((n) => (
            <button key={n.id} type="button" className="btn" disabled={loading} onClick={() => void solicitar(whatsapp.trim(), n.id)}
              style={{ border: "1px solid var(--stroke)", flexDirection: "column", alignItems: "flex-start", gap: 2, textAlign: "left", padding: "12px 14px" }}>
              <b>{n.nombre}</b>
              {n.direccion && <span style={{ color: "var(--txt-3)", fontSize: 12.5, fontWeight: 400 }}>{n.direccion}</span>}
            </button>
          ))}
        </div>
        {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
        <button type="button" onClick={volver} style={linkSecundario}>← Volver</button>
      </div>
    );
  }

  if (paso === "esperando") {
    return (
      <div className="glass" style={tarjeta}>
        <a className="btn btn-primary" href={waLink} target="_blank" rel="noopener"
          style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          <WhatsApp style={{ width: 18, height: 18 }} /> Confirmar por WhatsApp
        </a>
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0, textAlign: "center" }}>
          Se abre WhatsApp con un mensaje ya escrito — solo tocá enviar y volvé acá: entrás solo.
          El código sirve 15 minutos.
        </p>
        <button type="button" onClick={volver} style={linkSecundario}>← Volver</button>
      </div>
    );
  }

  if (paso === "vencido") {
    return (
      <div className="glass" style={tarjeta}>
        <span role="alert" style={{ color: "var(--amber)", fontSize: 14 }}><Ic n="reloj" s={15} /> El código venció, pedí otro.</span>
        {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
        <button className="btn btn-primary" type="button" disabled={loading} onClick={() => void solicitar(whatsapp.trim(), comercioId)}>
          {loading ? "Generando…" : "Pedir otro código"}
        </button>
        <button type="button" onClick={volver} style={linkSecundario}>← Volver</button>
      </div>
    );
  }

  if (paso === "entrando") {
    return (
      <div className="glass" style={{ padding: 22, borderRadius: 16 }} role="status">
        <p style={{ margin: 0, color: "var(--txt-2)" }}>Listo, confirmamos tu WhatsApp. Entrando…</p>
      </div>
    );
  }

  if (paso === "clave" && entrega) {
    return <ClaveUnaVez clave={entrega.clave} onListo={() => onLogged(entrega.sesion)} />;
  }

  return (
    <div className="glass" style={tarjeta}>
      <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err || "No se pudo entrar."}</span>
      <button className="btn btn-primary" type="button" onClick={() => void entrar(whatsapp.trim(), codigo)}>Reintentar</button>
      <button type="button" onClick={volver} style={linkSecundario}>← Volver</button>
    </div>
  );
}
