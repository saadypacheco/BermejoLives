"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { Send, WhatsApp } from "@/components/icons";
import {
  comercioLogin, comercioRegistro, getComercioSession, clearComercio, publicar,
  comercioRecuperar, comercioRecuperarConfirmar, generarDescripcion,
  type ComercioSession, type PublicarPayload, type RegistroPayload,
} from "@/lib/comercio";
import { RUBROS } from "@/lib/types";
import { comprimirImagen } from "@/lib/imagen";
import { geoErrorMsg } from "@/lib/geo";

type Msg = { from: "bot" | "user"; text: string };
type Step = "tipo" | "titulo" | "precio" | "descripcion" | "tiktok" | "imagen" | "confirm" | "done";

export default function PublicarPage() {
  const [sess, setSess] = useState<ComercioSession | null>(null);
  useEffect(() => setSess(getComercioSession()), []);

  if (!sess) return <AuthView onLogged={setSess} />;
  return <ChatBot sess={sess} onLogout={() => { clearComercio(); setSess(null); }} />;
}

/* ----------------------------- AUTH (login / registro) ----------------------------- */
// El plan (Básico/PRO/Premium, Bs 200/300/400) ya no se elige en el alta —
// arranca en "gratis" (= Básico) y se cambia después desde Mi Comercio → Suscripción.

function QueOfrecemos() {
  return (
    <div className="glass" style={{ padding: 20, borderRadius: 16, marginBottom: 18 }}>
      <h2 style={{ fontSize: 18, marginBottom: 10 }}>¿Por qué unirte a Encontralo?</h2>
      <ul style={{ display: "flex", flexDirection: "column", gap: 8, color: "var(--txt-2)", fontSize: 14, paddingLeft: 18, listStyle: "none" }}>
        <li>📍 Tu negocio aparece en el mapa.</li>
        <li>📢 Publicá ofertas y productos fácilmente.</li>
        <li>🛒 Accedé a tu propia tienda online.</li>
        <li>🚀 Llegá a más clientes con nuestros planes de promoción.</li>
        <li>💰 Sin comisiones por venta.</li>
      </ul>
    </div>
  );
}

function AuthView({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [mode, setMode] = useState<"login" | "registro">("registro");
  // Abre la pestaña según ?modo=login|registro (sin useSearchParams para no exigir Suspense)
  useEffect(() => {
    const modo = new URLSearchParams(window.location.search).get("modo");
    if (modo === "registro" || modo === "login") setMode(modo);
  }, []);
  return (
    <>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 56 }}>
        <span className="eyebrow"><span className="dot-live" /> Panel del comercio</span>
        <h1 style={{ fontSize: 30, margin: "10px 0 6px" }}>Publicá tus ofertas</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 12 }}>
          {mode === "registro" ? "Creá tu cuenta; nuestro asistente te ayuda a publicar en segundos." : "Ingresá a tu cuenta."}
        </p>

        {mode === "registro" && <QueOfrecemos />}
        {mode === "login" ? <LoginForm onLogged={onLogged} /> : <RegistroForm onLogged={onLogged} />}

        <button
          type="button"
          onClick={() => setMode(mode === "registro" ? "login" : "registro")}
          style={{ background: "none", border: "none", color: "var(--neon)", fontSize: 13, padding: 0, marginTop: 14, cursor: "pointer" }}
        >
          {mode === "registro" ? "¿Ya tenés cuenta? Ingresá acá" : "¿No tenés cuenta? Creala acá"}
        </button>

        <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: 18 }}>
          También podés publicar por{" "}
          <a href="https://wa.me/59170000000?text=Quiero%20publicar" target="_blank" rel="noopener" style={{ color: "var(--wa)" }}>WhatsApp</a>.
        </p>
      </div>
    </>
  );
}

// Login: WhatsApp + código es el camino principal (el alta ya no pide
// email/contraseña). Email+contraseña queda como alternativa para cuentas
// viejas que sí lo tienen cargado.
function LoginForm({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [modoEmail, setModoEmail] = useState(false);

  if (modoEmail) return <LoginConEmail onVolver={() => setModoEmail(false)} onLogged={onLogged} />;
  return <IngresarConWhatsapp onUsarEmail={() => setModoEmail(true)} onLogged={onLogged} />;
}

function LoginConEmail({ onVolver, onLogged }: { onVolver: () => void; onLogged: (s: ComercioSession) => void }) {
  const [email, setEmail] = useState("abc@bermejolive.com");
  const [pass, setPass] = useState("");
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { onLogged(await comercioLogin(email, pass)); }
    catch { setErr("Credenciales incorrectas. ¿Está corriendo el backend?"); }
  }

  return (
    <form onSubmit={submit} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <input className="adm-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
      <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit">Entrar</button>
      <button type="button" onClick={onVolver} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>
        ← Entrar con WhatsApp en cambio
      </button>
      <small style={{ color: "var(--txt-3)" }}>
        Demo: abc@bermejolive.com (confiable) · moda@bermejolive.com (moderación) · clave: comercio1234
      </small>
    </form>
  );
}

function IngresarConWhatsapp({ onUsarEmail, onLogged }: { onUsarEmail: () => void; onLogged: (s: ComercioSession) => void }) {
  const [whatsapp, setWhatsapp] = useState("");
  const [codigo, setCodigo] = useState("");
  const [nueva, setNueva] = useState("");
  const [paso, setPaso] = useState<"pedir" | "confirmar">("pedir");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function pedirCodigo(e: React.FormEvent) {
    e.preventDefault();
    if (!whatsapp.trim()) { setErr("Ingresá tu WhatsApp registrado"); return; }
    setLoading(true); setErr("");
    try { await comercioRecuperar(whatsapp.trim()); setPaso("confirmar"); }
    finally { setLoading(false); }
  }

  async function confirmar(e: React.FormEvent) {
    e.preventDefault();
    if (!codigo.trim() || nueva.length < 6) { setErr("Completá el código y una contraseña de al menos 6 caracteres"); return; }
    setLoading(true); setErr("");
    try {
      onLogged(await comercioRecuperarConfirmar(whatsapp.trim(), codigo.trim(), nueva));
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "No se pudo confirmar"); }
    finally { setLoading(false); }
  }

  if (paso === "pedir") {
    return (
      <form onSubmit={pedirCodigo} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: -4 }}>
          Te mandamos un código de 6 dígitos por WhatsApp al número con el que registraste tu negocio.
        </p>
        <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="WhatsApp registrado (ej: 59170000000)" />
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Enviando…" : "Enviar código"}</button>
        <button type="button" onClick={onUsarEmail} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>
          ¿Tenés email y contraseña? Entrá así
        </button>
        <Link href="/recuperar-negocio" style={{ color: "var(--txt-3)", fontSize: 13 }}>
          ¿Cambiaste de número de WhatsApp?
        </Link>
      </form>
    );
  }

  return (
    <form onSubmit={confirmar} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: -4 }}>
        Te llegó un código por WhatsApp. Ingresalo junto con una contraseña (te va a servir para la próxima vez).
      </p>
      <input className="adm-input" value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Código de 6 dígitos" inputMode="numeric" />
      <input className="adm-input" type="password" value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Contraseña (mín. 6)" />
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Confirmando…" : "Ingresar"}</button>
      <button type="button" onClick={() => setPaso("pedir")} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>← Volver</button>
    </form>
  );
}

const MODALIDADES: { key: RegistroPayload["modalidad"]; label: string }[] = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

type RegistroFormState = { nombre: string; whatsapp: string; modalidad: "mayorista" | "minorista" | "ambos"; direccion: string };

function ChipToggleReg({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} style={{
      padding: "6px 12px", borderRadius: 20, fontSize: 13, border: "1px solid",
      borderColor: active ? "var(--neon)" : "var(--border)",
      background: active ? "rgba(0,255,130,0.12)" : "transparent",
      color: active ? "var(--neon)" : "var(--txt-2)", cursor: "pointer",
    }}>
      {label}
    </button>
  );
}

function RegistroForm({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [f, setF] = useState<RegistroFormState>({ nombre: "", whatsapp: "", modalidad: "mayorista", direccion: "" });
  const set = (k: keyof RegistroFormState, v: string) => setF((s) => ({ ...s, [k]: v }));

  const [queVende, setQueVende] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [rubroSlugs, setRubroSlugs] = useState<string[]>([]);
  const [generando, setGenerando] = useState(false);

  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [geoMsg, setGeoMsg] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const [preview, setPreview] = useState("");
  const [comprimiendo, setComprimiendo] = useState(false);

  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  async function generarConIA() {
    if (!queVende.trim()) { setErr("Contanos primero qué vendés"); return; }
    setGenerando(true); setErr("");
    try {
      const r = await generarDescripcion(f.nombre || "Mi negocio", queVende.trim(), RUBROS);
      setDescripcion(r.descripcion);
      setRubroSlugs(r.rubro_slugs.length > 0 ? r.rubro_slugs : ["otros"]);
    } catch { setErr("No se pudo generar la descripción, probá de nuevo"); }
    finally { setGenerando(false); }
  }

  function ubicar() {
    setGeoMsg("Obteniendo ubicación…");
    if (!navigator.geolocation) { setGeoMsg("Este dispositivo no tiene GPS disponible."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => { setCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude }); setGeoMsg(""); },
      (e) => setGeoMsg(geoErrorMsg(e)),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) { setFoto(null); setPreview(""); return; }
    setPreview(URL.createObjectURL(file));
    setComprimiendo(true);
    const comprimida = await comprimirImagen(file);
    setComprimiendo(false);
    setFoto(comprimida);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!f.nombre.trim() || !f.whatsapp.trim()) { setErr("Completá nombre y WhatsApp."); return; }
    const desc = descripcion || queVende.trim();
    if (!desc) { setErr("Contanos qué vendés."); return; }
    if (!coords) { setErr("Falta la ubicación — tocá \"Usar mi ubicación actual\"."); return; }
    if (comprimiendo) { setErr("Esperá a que termine de comprimir la foto."); return; }
    if (!foto) { setErr("Falta la foto del negocio."); return; }

    setLoading(true);
    try {
      onLogged(await comercioRegistro({
        nombre: f.nombre.trim(), whatsapp: f.whatsapp.trim(), modalidad: f.modalidad,
        rubro_slugs: rubroSlugs.length > 0 ? rubroSlugs : ["otros"],
        descripcion: desc, direccion: f.direccion.trim() || undefined,
        lat: coords.lat, lng: coords.lng, foto,
      }));
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "No se pudo crear la cuenta"); }
    finally { setLoading(false); }
  }

  return (
    <form onSubmit={submit} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del comercio" />
      <input className="adm-input" value={f.whatsapp} onChange={(e) => set("whatsapp", e.target.value)} placeholder="WhatsApp (ej: 59170000000)" />

      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginTop: 4 }}>¿Vendés por mayor o menor?</div>
      <div className="seg">
        {MODALIDADES.map((m) => (
          <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""} onClick={() => set("modalidad", m.key)}>{m.label}</button>
        ))}
      </div>

      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginTop: 4 }}>¿Qué vendés?</div>
      <textarea
        className="adm-input" rows={2}
        value={queVende}
        onChange={(e) => { setQueVende(e.target.value); setDescripcion(""); setRubroSlugs([]); }}
        placeholder="Contanos con tus palabras: ej. 'ropa y calzado para toda la familia' o 'repuestos y gomería'"
      />
      <button type="button" className="btn btn-ghost btn-sm" onClick={generarConIA} disabled={generando} style={{ alignSelf: "flex-start" }}>
        {generando ? "Generando…" : "✨ Generar descripción con IA"}
      </button>
      {descripcion && (
        <div style={{ background: "var(--panel)", border: "1px solid var(--stroke)", borderRadius: 10, padding: 10, fontSize: 13, color: "var(--txt-2)" }}>
          {descripcion}
        </div>
      )}
      {rubroSlugs.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {RUBROS.map((r) => (
            <ChipToggleReg key={r.slug} label={r.nombre} active={rubroSlugs.includes(r.slug)}
              onClick={() => setRubroSlugs((prev) => prev.includes(r.slug) ? prev.filter((s) => s !== r.slug) : [...prev, r.slug])} />
          ))}
        </div>
      )}

      <div>
        <label className="campo-lbl">Ubicación *</label>
        <button type="button" className={`btn ${coords ? "btn-ghost" : "btn-primary"}`} style={{ width: "100%" }} onClick={ubicar}>
          {coords ? "Ubicación tomada ✓ — tomar de nuevo" : "📍 Usar mi ubicación actual"}
        </button>
        {geoMsg && <div style={{ fontSize: 12.5, color: "var(--amber)", marginTop: 6 }}>{geoMsg}</div>}
      </div>

      <div>
        <label className="campo-lbl">Foto del negocio *</label>
        <label className="foto-drop">
          {preview ? <img src={preview} alt="" /> : <span>📷 Sacar foto / elegir</span>}
          <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
        </label>
        {comprimiendo && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Comprimiendo foto…</div>}
        {!comprimiendo && foto && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>{(foto.size / 1024).toFixed(0)} KB</div>}
      </div>

      <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)}
        placeholder="Punto de referencia (ej: frente a la plaza, al lado de la farmacia)" />

      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit" disabled={loading}>
        {loading ? "Creando…" : "Crear cuenta y publicar"}
      </button>
      <small style={{ color: "var(--txt-3)" }}>
        Después, desde "Mi comercio" podés sumar redes sociales, cambiar de plan y completar el resto.
      </small>
    </form>
  );
}

/* ----------------------------- CHATBOT ----------------------------- */
const QUESTIONS: Record<Step, string> = {
  tipo: "¡Hola! 👋 ¿Qué querés publicar hoy?",
  titulo: "Perfecto. ¿Qué nombre o título le ponemos?",
  precio: "¿Cuál es el precio? (escribí solo el número, o 'no' si no aplica)",
  descripcion: "Contame los detalles: descripción, talles, condiciones…",
  tiktok: "Pegá el link del video de TikTok 🎬",
  imagen: "¿Tenés una foto? Pegá el link de la imagen (o escribí 'no')",
  confirm: "Revisá tu publicación 👇",
  done: "",
};

function ChatBot({ sess, onLogout }: { sess: ComercioSession; onLogout: () => void }) {
  const [msgs, setMsgs] = useState<Msg[]>([{ from: "bot", text: QUESTIONS.tipo }]);
  const [step, setStep] = useState<Step>("tipo");
  const [draft, setDraft] = useState<PublicarPayload>({ tipo: "oferta", moneda: "BOB" });
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const say = (from: "bot" | "user", text: string) => setMsgs((m) => [...m, { from, text }]);
  const ask = (s: Step) => { setStep(s); say("bot", QUESTIONS[s]); };

  function pickTipo(tipo: PublicarPayload["tipo"], label: string) {
    say("user", label);
    setDraft((d) => ({ ...d, tipo }));
    ask("titulo");
  }

  function nextFromText() {
    const val = input.trim();
    if (!val) return;
    say("user", val);
    setInput("");

    if (step === "titulo") {
      setDraft((d) => ({ ...d, titulo: val }));
      draft.tipo === "oferta" ? ask("precio") : draft.tipo === "video" ? ask("tiktok") : ask("descripcion");
    } else if (step === "precio") {
      const n = Number(val.replace(/[^\d.]/g, ""));
      setDraft((d) => ({ ...d, precio: val.toLowerCase() === "no" || !n ? null : n }));
      ask("descripcion");
    } else if (step === "descripcion") {
      setDraft((d) => ({ ...d, descripcion: val }));
      draft.tipo === "video" ? ask("tiktok") : ask("imagen");
    } else if (step === "tiktok") {
      setDraft((d) => ({ ...d, tiktok_url: val }));
      ask("imagen");
    } else if (step === "imagen") {
      setDraft((d) => ({ ...d, imagen_url: val.toLowerCase() === "no" ? undefined : val }));
      ask("confirm");
    }
  }

  async function confirmPublish() {
    setSending(true);
    say("user", "Publicar ✅");
    try {
      const res = await publicar(draft);
      if (res.publicado_directo) {
        say("bot", "🎉 ¡Listo! Tu publicación ya está EN VIVO en Encontralo. (Tu comercio es confiable, se publicó directo.)");
      } else {
        say("bot", "✅ ¡Recibido! Tu publicación quedó en revisión. Un moderador la aprueba y aparece en el feed en vivo. Te avisamos.");
      }
      setStep("done");
    } catch {
      say("bot", "⚠️ No pude publicar. Verificá que el backend esté corriendo e intentá de nuevo.");
    } finally {
      setSending(false);
    }
  }

  function reset() {
    setDraft({ tipo: "oferta", moneda: "BOB" });
    setMsgs([{ from: "bot", text: QUESTIONS.tipo }]);
    setStep("tipo");
  }

  const textStep = ["titulo", "precio", "descripcion", "tiktok", "imagen"].includes(step);

  return (
    <>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 680, paddingTop: 28 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
          <div>
            <span className="eyebrow"><span className="dot-live" /> Asistente de publicación</span>
            <h1 style={{ fontSize: 24, margin: "8px 0 0" }}>{sess.nombre}</h1>
            <small style={{ color: sess.confiable ? "var(--neon)" : "var(--txt-3)" }}>
              {sess.confiable ? "✓ Comercio confiable — publicás directo, sin moderación" : "Tus publicaciones pasan por moderación"}
            </small>
          </div>
          <button className="link-more" onClick={onLogout}>Salir</button>
        </div>

        <div className="chat glass">
          <div className="chat-body">
            {msgs.map((m, i) => (
              <div key={i} className={`bubble ${m.from}`}>{m.text}</div>
            ))}

            {/* Quick replies por paso */}
            {step === "tipo" && (
              <div className="quick">
                <button onClick={() => pickTipo("oferta", "Una oferta 🏷️")}>Una oferta 🏷️</button>
                <button onClick={() => pickTipo("video", "Un video 🎬")}>Un video 🎬</button>
                <button onClick={() => pickTipo("novedad", "Una novedad 📣")}>Una novedad 📣</button>
              </div>
            )}

            {step === "confirm" && (
              <div className="confirm-card">
                <div className="cc-row"><b>Tipo</b><span style={{ textTransform: "capitalize" }}>{draft.tipo}</span></div>
                {draft.titulo && <div className="cc-row"><b>Título</b><span>{draft.titulo}</span></div>}
                {draft.precio != null && <div className="cc-row"><b>Precio</b><span>{draft.precio} {draft.moneda}</span></div>}
                {draft.descripcion && <div className="cc-row"><b>Detalle</b><span>{draft.descripcion}</span></div>}
                {draft.tiktok_url && <div className="cc-row"><b>TikTok</b><span className="trunc">{draft.tiktok_url}</span></div>}
                {draft.imagen_url && <div className="cc-row"><b>Imagen</b><span className="trunc">{draft.imagen_url}</span></div>}

                {draft.tipo === "oferta" && (
                  <div className="cc-extra">
                    <div className="cc-extra-f">
                      <label className="campo-lbl">Descuento %</label>
                      <input className="adm-input" type="number" inputMode="numeric" min={1} max={99}
                        value={draft.descuento_pct ?? ""} placeholder="ej: 20 (opcional)"
                        onChange={(e) => setDraft((d) => ({ ...d, descuento_pct: e.target.value ? Math.max(1, Math.min(99, Number(e.target.value))) : null }))} />
                    </div>
                    <div className="cc-extra-f">
                      <label className="campo-lbl">Válido hasta</label>
                      <input className="adm-input" type="date" value={draft.vence_el ?? ""}
                        onChange={(e) => setDraft((d) => ({ ...d, vence_el: e.target.value || null }))} />
                    </div>
                  </div>
                )}

                <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                  <button className="btn btn-primary btn-sm" disabled={sending} onClick={confirmPublish}>
                    {sending ? "Publicando…" : sess.confiable ? "Publicar en vivo" : "Enviar a moderación"}
                  </button>
                  <button className="btn btn-ghost btn-sm" disabled={sending} onClick={reset}>Empezar de nuevo</button>
                </div>
              </div>
            )}

            {step === "done" && (
              <div className="quick">
                <button onClick={reset}>Publicar otra ✨</button>
                <Link href="/" className="btn btn-ghost btn-sm">Ver el feed</Link>
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input de texto cuando el paso lo requiere */}
          {textStep && (
            <form
              className="chat-input"
              onSubmit={(e) => { e.preventDefault(); nextFromText(); }}
            >
              <input
                className="adm-input"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Escribí tu respuesta…"
                autoFocus
              />
              <button className="btn btn-primary btn-sm" type="submit"><Send style={{ width: 16, height: 16 }} /></button>
            </form>
          )}
        </div>

        <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: 16 }}>
          <WhatsApp style={{ width: 14, height: 14, display: "inline", verticalAlign: "-2px", color: "var(--wa)" }} />{" "}
          También podés publicar mandando un mensaje por WhatsApp; llega a este mismo panel.
        </p>
        <div style={{ height: 50 }} />
      </div>
    </>
  );
}
