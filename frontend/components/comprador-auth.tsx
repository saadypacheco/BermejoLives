"use client";

import { useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { ClaveUnaVez } from "@/components/clave-una-vez";
import { ingresarUsuario, solicitarCodigoUsuario, verificarCodigoUsuario } from "@/lib/usuario";
import { CONFIRMACION_VENCE_MS, LARGO_CLAVE, POLL_MS, mensajeDeError, soloClave } from "@/lib/acceso";

type Paso = "clave" | "telefono" | "confirmar" | "vencido" | "clave-nueva";

const linkSecundario: React.CSSProperties = {
  background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, cursor: "pointer", padding: 0, textAlign: "left",
};

/**
 * Ingreso del comprador. Lo normal es celular + clave de 6 números. La primera
 * vez (y si la olvidó) confirma con su WhatsApp, y al confirmar se le muestra la
 * clave, una sola vez: recién cuando la guarda se llama a `onOk`.
 */
export function CompradorAuthForm({ onOk, titulo, onMostrandoClave }: {
  onOk: () => void; titulo?: string;
  /** Avisa cuando se está mostrando la clave nueva: quien lo envuelve en un
   *  modal no tiene que dejar cerrarlo hasta que la persona la guarde. */
  onMostrandoClave?: (mostrando: boolean) => void;
}) {
  const [paso, setPaso] = useState<Paso>("clave");
  const [whatsapp, setWhatsapp] = useState("");
  const [clave, setClave] = useState("");
  const [claveNueva, setClaveNueva] = useState("");
  const [waLink, setWaLink] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [err, setErr] = useState("");
  // Quien escribe sus 8 dígitos locales: el sistema los toma como Bolivia (+591).
  const digitos = whatsapp.replace(/\D/g, "");
  const tomaComo591 = digitos.length === 8;
  const intervaloRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // El polling puede disparar dos veces antes de que cambie el paso: se entra una sola vez.
  const confirmadoRef = useRef(false);

  useEffect(() => { onMostrandoClave?.(paso === "clave-nueva"); }, [paso, onMostrandoClave]);

  const parar = () => { if (intervaloRef.current) { clearInterval(intervaloRef.current); intervaloRef.current = null; } };
  useEffect(() => parar, []);

  const campoCelular = (id: string) => (
    <>
      <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)}
        placeholder="Tu celular (ej: 70000000)" inputMode="tel" autoComplete="tel" aria-label="Tu celular"
        aria-describedby={tomaComo591 ? id : undefined} />
      {tomaComo591 && (
        <span id={id} style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
          Lo tomamos como un número de Bolivia: <b>+591 {digitos}</b>. Si es de otro país, escribilo con el código del país.
        </span>
      )}
    </>
  );

  async function entrarConClave(e: React.FormEvent) {
    e.preventDefault();
    if (!whatsapp.trim()) { setErr("Ingresá tu celular"); return; }
    if (clave.length !== LARGO_CLAVE) { setErr(`La clave tiene ${LARGO_CLAVE} números`); return; }
    setEnviando(true); setErr("");
    try { await ingresarUsuario(whatsapp.trim(), clave); onOk(); }
    // 401 («Celular o clave incorrectos») y 429 («Demasiados intentos…»): tal cual.
    catch (ex) { setErr(mensajeDeError(ex, "No se pudo entrar, probá de nuevo")); setClave(""); }
    finally { setEnviando(false); }
  }

  /** Espera el mensaje de confirmación; a los 15 minutos el código ya no sirve. */
  function esperar(wa: string, c: string) {
    parar();
    confirmadoRef.current = false;
    const inicio = Date.now();
    intervaloRef.current = setInterval(async () => {
      if (Date.now() - inicio >= CONFIRMACION_VENCE_MS) { parar(); setPaso("vencido"); return; }
      try {
        const r = await verificarCodigoUsuario(wa, c);
        if (!r || confirmadoRef.current) return;
        confirmadoRef.current = true;
        parar();
        // Con clave nueva se la muestra ANTES de seguir: `onOk` suele cambiar la
        // pantalla, y la clave se perdería sin leerla.
        if (r.claveNueva) { setClaveNueva(r.claveNueva); setPaso("clave-nueva"); }
        else onOk();
      } catch { /* sin conexión: se reintenta en el próximo ciclo */ }
    }, POLL_MS);
  }

  async function pedirCodigo(e?: React.FormEvent) {
    e?.preventDefault();
    if (!whatsapp.trim()) { setErr("Ingresá tu WhatsApp"); return; }
    setEnviando(true); setErr("");
    try {
      const { codigo: c, wa_link, whatsapp: wa } = await solicitarCodigoUsuario(whatsapp.trim());
      setWaLink(wa_link); setPaso("confirmar");
      // arranca a pollear apenas se muestra el botón — no hace falta que el
      // usuario haga nada más que tocar "Confirmar por WhatsApp" y volver
      esperar(wa, c);
    } catch (ex) { setErr(mensajeDeError(ex, "No se pudo generar el código, probá de nuevo")); }
    finally { setEnviando(false); }
  }

  function irA(p: Paso) {
    parar();
    setPaso(p); setErr("");
  }

  if (paso === "clave-nueva") {
    return (
      <ClaveUnaVez clave={claveNueva} titulo="Tu clave para entrar"
        aviso="Guardala: no se vuelve a mostrar. La próxima vez entrás con tu celular y esta clave, sin esperar el WhatsApp."
        onListo={onOk} />
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <h3 style={{ margin: 0 }}>{titulo ?? "Entrá con tu celular"}</h3>

      {paso === "clave" && (
        <>
          <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>
            Tu celular y tu clave de {LARGO_CLAVE} números. Lo usamos para guardar tus locales favoritos
            — nada más.
          </p>
          <form onSubmit={entrarConClave} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {campoCelular("wa-prefijo-clave")}
            <input className="adm-input" type="password" value={clave} onChange={(e) => setClave(soloClave(e.target.value))}
              placeholder={`Tu clave de ${LARGO_CLAVE} números`} inputMode="numeric" pattern="[0-9]*" maxLength={LARGO_CLAVE}
              autoComplete="current-password" aria-label={`Tu clave de ${LARGO_CLAVE} números`} />
            {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
            <button className="btn btn-primary" type="submit" disabled={enviando}>{enviando ? "Entrando…" : "Entrar"}</button>
          </form>
          <button type="button" onClick={() => irA("telefono")} style={{ ...linkSecundario, color: "var(--neon)", fontSize: 14 }}>
            ¿Primera vez o te olvidaste la clave? Confirmá con tu WhatsApp
          </button>
        </>
      )}

      {paso === "telefono" && (
        <>
          <p style={{ color: "var(--txt-3)", fontSize: 13, margin: 0 }}>
            Confirmás con tu propio WhatsApp y te mostramos tu clave de {LARGO_CLAVE} números, una sola vez.
          </p>
          <form onSubmit={pedirCodigo} style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {campoCelular("wa-prefijo")}
            {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
            <button className="btn btn-primary" type="submit" disabled={enviando}>{enviando ? "Generando…" : "Continuar"}</button>
          </form>
          <button type="button" onClick={() => irA("clave")} style={linkSecundario}>← Entrar con celular y clave</button>
        </>
      )}

      {paso === "confirmar" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <a
            className="btn btn-primary"
            href={waLink}
            target="_blank"
            rel="noopener"
            style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}
          >
            Confirmar por WhatsApp
          </a>
          <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0, textAlign: "center" }}>
            Se abre WhatsApp con un mensaje ya escrito — solo tocá enviar y volvé acá. El código sirve 15 minutos.
          </p>
          {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
          <button type="button" onClick={() => irA("telefono")} style={linkSecundario}>← Usar otro número</button>
        </div>
      )}

      {paso === "vencido" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span role="alert" style={{ color: "var(--amber)", fontSize: 14 }}><Ic n="reloj" s={15} /> El código venció, pedí otro.</span>
          {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
          <button className="btn btn-primary" type="button" disabled={enviando} onClick={() => void pedirCodigo()}>
            {enviando ? "Generando…" : "Pedir otro código"}
          </button>
          <button type="button" onClick={() => irA("telefono")} style={linkSecundario}>← Usar otro número</button>
        </div>
      )}
    </div>
  );
}

export function CompradorAuthModal({ onClose, onOk, titulo }: { onClose: () => void; onOk: () => void; titulo?: string }) {
  // Mientras se muestra la clave nueva no se puede cerrar de un toque afuera ni
  // con «Cancelar»: se perdería y no se vuelve a mostrar. Sólo «Ya la guardé».
  const [mostrandoClave, setMostrandoClave] = useState(false);
  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 999, background: "rgba(0,0,0,.6)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
      onClick={mostrandoClave ? undefined : onClose}
    >
      <div className="glass" style={{ padding: 22, borderRadius: 16, maxWidth: 380, width: "100%" }} onClick={(e) => e.stopPropagation()}>
        <CompradorAuthForm onOk={onOk} titulo={titulo} onMostrandoClave={setMostrandoClave} />
        {!mostrandoClave && (
          <button type="button" onClick={onClose} style={{ marginTop: 14, background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, cursor: "pointer" }}>
            Cancelar
          </button>
        )}
      </div>
    </div>
  );
}
