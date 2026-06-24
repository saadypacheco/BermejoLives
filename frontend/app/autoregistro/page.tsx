"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { Send, WhatsApp } from "@/components/icons";
import {
  comercioLogin, comercioRegistro, getComercioSession, clearComercio, publicar,
  type ComercioSession, type PublicarPayload, type RegistroPayload,
} from "@/lib/comercio";
import { RUBROS } from "@/lib/types";

type Msg = { from: "bot" | "user"; text: string };
type Step = "tipo" | "titulo" | "precio" | "descripcion" | "tiktok" | "imagen" | "confirm" | "done";

export default function PublicarPage() {
  const [sess, setSess] = useState<ComercioSession | null>(null);
  useEffect(() => setSess(getComercioSession()), []);

  if (!sess) return <AuthView onLogged={setSess} />;
  return <ChatBot sess={sess} onLogout={() => { clearComercio(); setSess(null); }} />;
}

/* ----------------------------- AUTH (login / registro) ----------------------------- */
const PLANES: { key: RegistroPayload["plan"]; nombre: string; precio: string; bullets: string }[] = [
  { key: "gratis", nombre: "Gratis", precio: "Bs 0", bullets: "Perfil + publicar (con moderación)" },
  { key: "pro", nombre: "Pro", precio: "Bs 49/mes", bullets: "Más alcance + destacado en zona" },
  { key: "premium", nombre: "Premium", precio: "Bs 99/mes", bullets: "Verificado + publicación directa" },
];

function AuthView({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [mode, setMode] = useState<"login" | "registro">("login");
  // Abre la pestaña según ?modo=login|registro (sin useSearchParams para no exigir Suspense)
  useEffect(() => {
    const modo = new URLSearchParams(window.location.search).get("modo");
    if (modo === "registro" || modo === "login") setMode(modo);
  }, []);
  return (
    <>
      <Nav />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 56 }}>
        <span className="eyebrow"><span className="dot-live" /> Panel del comercio</span>
        <h1 style={{ fontSize: 30, margin: "10px 0 6px" }}>Publicá tus ofertas</h1>
        <p style={{ color: "var(--txt-3)", marginBottom: 20 }}>
          Creá tu cuenta o ingresá; nuestro asistente te ayuda a publicar en segundos.
        </p>

        <div className="auth-tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Ingresar</button>
          <button className={mode === "registro" ? "active" : ""} onClick={() => setMode("registro")}>Crear cuenta</button>
        </div>

        {mode === "login" ? <LoginForm onLogged={onLogged} /> : <RegistroForm onLogged={onLogged} />}

        <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: 18 }}>
          También podés publicar por{" "}
          <a href="https://wa.me/59170000000?text=Quiero%20publicar" target="_blank" rel="noopener" style={{ color: "var(--wa)" }}>WhatsApp</a>.
        </p>
      </div>
    </>
  );
}

function LoginForm({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
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
      <small style={{ color: "var(--txt-3)" }}>
        Demo: abc@bermejolive.com (confiable) · moda@bermejolive.com (moderación) · clave: comercio1234
      </small>
    </form>
  );
}

const MODALIDADES: { key: RegistroPayload["modalidad"]; label: string }[] = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

function RegistroForm({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [f, setF] = useState<RegistroPayload>({ nombre: "", email: "", password: "", whatsapp: "", plan: "gratis", modalidad: "mayorista", rubro_slug: "importadora" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof RegistroPayload, v: string) => setF((s) => ({ ...s, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!f.nombre || !f.email || !f.password || !f.whatsapp) { setErr("Completá nombre, email, contraseña y WhatsApp."); return; }
    setLoading(true);
    try { onLogged(await comercioRegistro(f)); }
    catch (ex) { setErr(ex instanceof Error ? ex.message : "No se pudo crear la cuenta"); }
    finally { setLoading(false); }
  }

  return (
    <form onSubmit={submit} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del comercio" />
      <input className="adm-input" value={f.whatsapp} onChange={(e) => set("whatsapp", e.target.value)} placeholder="WhatsApp (ej: 59170000000)" />
      <input className="adm-input" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="Email" />
      <input className="adm-input" type="password" value={f.password} onChange={(e) => set("password", e.target.value)} placeholder="Contraseña (mín. 6)" />

      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginTop: 4 }}>¿Vendés por mayor o menor?</div>
      <div className="seg">
        {MODALIDADES.map((m) => (
          <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""} onClick={() => set("modalidad", m.key)}>{m.label}</button>
        ))}
      </div>

      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginTop: 4 }}>Rubro</div>
      <select className="adm-input" value={f.rubro_slug} onChange={(e) => set("rubro_slug", e.target.value)}>
        {RUBROS.map((r) => (<option key={r.slug} value={r.slug}>{r.nombre}</option>))}
      </select>

      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginTop: 4 }}>Elegí tu plan</div>
      <div className="plan-grid">
        {PLANES.map((p) => (
          <button type="button" key={p.key} className={`plan ${f.plan === p.key ? "active" : ""}`} onClick={() => set("plan", p.key)}>
            <b>{p.nombre}</b>
            <span className="plan-price">{p.precio}</span>
            <small>{p.bullets}</small>
          </button>
        ))}
      </div>

      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit" disabled={loading}>
        {loading ? "Creando…" : "Crear cuenta y publicar"}
      </button>
      <small style={{ color: "var(--txt-3)" }}>
        📍 Tu ubicación es opcional acá: la compartís fácil mandando tu ubicación por WhatsApp y la cargamos sola.
        Los planes pagos (Pro/Premium) quedan registrados; la activación del pago llega pronto.
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
      <Nav />
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
