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

type Msg = { from: "bot" | "user"; text: string };
type Step = "tipo" | "titulo" | "precio" | "descripcion" | "tiktok" | "imagen" | "confirm" | "done";

export default function PublicarPage() {
  const [sess, setSess] = useState<ComercioSession | null>(null);
  useEffect(() => setSess(getComercioSession()), []);

  if (!sess) return <AuthView onLogged={setSess} />;
  return <ChatBot sess={sess} onLogout={() => { clearComercio(); setSess(null); }} />;
}

/* ----------------------------- AUTH (login / registro) ----------------------------- */
// Los "key" (gratis/pro/premium) son el identificador interno en la base — no se
// tocan para no romper el check constraint de comercios.plan. Nombre/precio son
// el plan real que se cobra.
const PLANES: { key: RegistroPayload["plan"]; nombre: string; precio: string; bullets: string }[] = [
  { key: "gratis", nombre: "Básico", precio: "Bs 200", bullets: "Tu negocio en el mapa, con tus datos visibles (dirección, WhatsApp, horario)" },
  { key: "pro", nombre: "PRO", precio: "Bs 300", bullets: "Todo lo de Básico + publicamos en nuestras redes (Instagram/TikTok/Facebook) y en el feed de Encontralo" },
  { key: "premium", nombre: "Premium", precio: "Bs 400", bullets: "Todo lo de PRO + ofertas ilimitadas" },
];

function QueOfrecemos() {
  return (
    <div className="glass" style={{ padding: 20, borderRadius: 16, marginBottom: 18 }}>
      <h2 style={{ fontSize: 18, marginBottom: 10 }}>¿Qué ofrece Encontralo?</h2>
      <ul style={{ display: "flex", flexDirection: "column", gap: 8, color: "var(--txt-2)", fontSize: 14, paddingLeft: 18 }}>
        <li>Publicá tus productos u ofertas <b style={{ color: "var(--txt)" }}>gratis</b>, sin límite de publicaciones en el plan Premium</li>
        <li>Tu negocio y sus datos quedan visibles en el <b style={{ color: "var(--txt)" }}>mapa</b> para que te encuentren cerca tuyo</li>
        <li>Con el plan PRO o Premium, publicamos en las <b style={{ color: "var(--txt)" }}>redes de Encontralo</b> (anuncios, TikTok, Instagram, Facebook)</li>
        <li>Tus productos y servicios quedan visibles para <b style={{ color: "var(--txt)" }}>toda Argentina</b></li>
        <li>Si tu negocio se verifica, te ofrecemos tu <b style={{ color: "var(--txt)" }}>propia tienda online</b>, con compra y envío directo desde la página</li>
      </ul>
      <p style={{ color: "var(--txt-3)", fontSize: 12.5, marginTop: 10 }}>
        No cobramos comisión por tus ventas — solo pagás el plan mensual que elijas.
      </p>
    </div>
  );
}

function AuthView({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [mode, setMode] = useState<"login" | "registro">("login");
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
        <p style={{ color: "var(--txt-3)", marginBottom: 20 }}>
          Creá tu cuenta o ingresá; nuestro asistente te ayuda a publicar en segundos.
        </p>

        <div className="auth-tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}>Ingresar</button>
          <button className={mode === "registro" ? "active" : ""} onClick={() => setMode("registro")}>Crear cuenta</button>
        </div>

        {mode === "registro" && <QueOfrecemos />}
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
  const [recuperar, setRecuperar] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { onLogged(await comercioLogin(email, pass)); }
    catch { setErr("Credenciales incorrectas. ¿Está corriendo el backend?"); }
  }

  if (recuperar) return <RecuperarForm onDone={() => setRecuperar(false)} onLogged={onLogged} />;

  return (
    <form onSubmit={submit} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <input className="adm-input" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email" />
      <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit">Entrar</button>
      <button type="button" onClick={() => setRecuperar(true)} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>
        ¿Olvidaste tu contraseña?
      </button>
      <small style={{ color: "var(--txt-3)" }}>
        Demo: abc@bermejolive.com (confiable) · moda@bermejolive.com (moderación) · clave: comercio1234
      </small>
    </form>
  );
}

function RecuperarForm({ onDone, onLogged }: { onDone: () => void; onLogged: (s: ComercioSession) => void }) {
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
          Te mandamos un código de 6 dígitos por WhatsApp al número con el que te registraste.
        </p>
        <input className="adm-input" value={whatsapp} onChange={(e) => setWhatsapp(e.target.value)} placeholder="WhatsApp registrado (ej: 59170000000)" />
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Enviando…" : "Enviar código"}</button>
        <button type="button" onClick={onDone} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>← Volver a ingresar</button>
      </form>
    );
  }

  return (
    <form onSubmit={confirmar} className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
      <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: -4 }}>
        Si el número está registrado, te llegó un código por WhatsApp. Ingresalo junto con tu nueva contraseña.
      </p>
      <input className="adm-input" value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="Código de 6 dígitos" inputMode="numeric" />
      <input className="adm-input" type="password" value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="Nueva contraseña (mín. 6)" />
      {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
      <button className="btn btn-primary" type="submit" disabled={loading}>{loading ? "Confirmando…" : "Cambiar contraseña"}</button>
      <button type="button" onClick={onDone} style={{ background: "none", border: "none", color: "var(--txt-3)", fontSize: 13, textAlign: "left", padding: 0, cursor: "pointer" }}>← Volver a ingresar</button>
    </form>
  );
}

const MODALIDADES: { key: RegistroPayload["modalidad"]; label: string }[] = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

function RegistroForm({ onLogged }: { onLogged: (s: ComercioSession) => void }) {
  const [f, setF] = useState<RegistroPayload>({ nombre: "", email: "", password: "", whatsapp: "", plan: "gratis", modalidad: "mayorista" });
  const [queVende, setQueVende] = useState("");
  const [generando, setGenerando] = useState(false);
  const [generado, setGenerado] = useState(false);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const set = (k: keyof RegistroPayload, v: string) => setF((s) => ({ ...s, [k]: v }));

  async function generarConIA() {
    if (!queVende.trim()) { setErr("Contanos primero qué vendés"); return; }
    setGenerando(true); setErr(""); setGenerado(false);
    try {
      const { descripcion, rubro_slug } = await generarDescripcion(f.nombre || "Mi negocio", queVende.trim(), RUBROS);
      setF((s) => ({ ...s, descripcion, rubro_slug: rubro_slug ?? s.rubro_slug }));
      setGenerado(true);
    } catch { setErr("No se pudo generar la descripción, probá de nuevo"); }
    finally { setGenerando(false); }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    if (!f.nombre || !f.email || !f.password || !f.whatsapp) { setErr("Completá nombre, email, contraseña y WhatsApp."); return; }
    setLoading(true);
    const payload = f.descripcion ? f : { ...f, descripcion: queVende.trim() || undefined };
    try { onLogged(await comercioRegistro(payload)); }
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

      <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".05em", marginTop: 4 }}>¿Qué vendés?</div>
      <textarea
        className="adm-input" rows={2}
        value={queVende}
        onChange={(e) => { setQueVende(e.target.value); setGenerado(false); }}
        placeholder="Contanos con tus palabras: ej. 'ropa y calzado para toda la familia' o 'repuestos y gomería'"
      />
      <button type="button" className="btn btn-ghost btn-sm" onClick={generarConIA} disabled={generando} style={{ alignSelf: "flex-start" }}>
        {generando ? "Generando…" : "✨ Generar descripción con IA"}
      </button>
      {generado && f.descripcion && (
        <div style={{ background: "var(--panel)", border: "1px solid var(--stroke)", borderRadius: 10, padding: 10, fontSize: 13, color: "var(--txt-2)" }}>
          {f.descripcion}
          {f.rubro_slug && <div style={{ marginTop: 4, color: "var(--neon)", fontSize: 12 }}>Rubro sugerido: {RUBROS.find((r) => r.slug === f.rubro_slug)?.nombre ?? f.rubro_slug}</div>}
        </div>
      )}

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
