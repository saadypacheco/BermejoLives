"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { Send, WhatsApp } from "@/components/icons";
import {
  comercioRegistro, getComercioSession, clearComercio, publicar, PublicarBloqueado, generarDescripcion, NumeroYaRegistrado,
  type ComercioSession, type PublicarPayload, type RegistroPayload, type RegistroResult,
} from "@/lib/comercio";
import { mensajeDeError } from "@/lib/acceso";
import { ClaveUnaVez } from "@/components/clave-una-vez";
import { RUBROS } from "@/lib/types";
import { comprimirImagen } from "@/lib/imagen";
import { useObjectUrl } from "@/lib/object-url";
import { geoErrorMsg } from "@/lib/geo";
import { waUruku } from "@/lib/contacto";
import { PermisoUbicacion } from "@/components/permiso-ubicacion";
import { Ic } from "@/components/ic";
import { LoginComercio } from "@/components/ingresar-comercio";

// `kind` marca los mensajes del plan (aviso de cobro, publicación bloqueada):
// se dibujan aparte, con ícono y rótulo, para que no se pierdan entre la charla.
type Msg = { from: "bot" | "user"; text: string; kind?: "aviso" | "bloqueado" };
type Step = "tipo" | "titulo" | "precio" | "descripcion" | "tiktok" | "imagen" | "confirm" | "done";

export default function PublicarPage() {
  const [sess, setSess] = useState<ComercioSession | null>(null);
  // El código del negocio recién creado: se muestra una vez, antes del chatbot.
  const [codigoNuevo, setCodigoNuevo] = useState<string | null>(null);
  // La clave de entrada del negocio recién creado: va ANTES que el código, se
  // muestra una vez y vive sólo en memoria (nunca en localStorage).
  const [claveNueva, setClaveNueva] = useState<string | null>(null);
  useEffect(() => setSess(getComercioSession()), []);

  if (!sess) {
    return <AuthView onLogged={setSess} onRegistrado={({ sesion, claveInicial }) => {
      setCodigoNuevo(codigoVisible(sesion)); setClaveNueva(claveInicial); setSess(sesion);
    }} />;
  }
  if (claveNueva) return <ClaveDelNegocio clave={claveNueva} nombre={sess.nombre} onListo={() => setClaveNueva(null)} />;
  if (codigoNuevo) return <CodigoDelNegocio codigo={codigoNuevo} nombre={sess.nombre} onSeguir={() => setCodigoNuevo(null)} />;
  return <ChatBot sess={sess} onLogout={() => { clearComercio(); setSess(null); }} />;
}

/** `URUKU-XXXX` listo para mostrar (el backend manda `codigo_formateado`; si faltara, se arma desde `codigo`). */
function codigoVisible(s: ComercioSession): string | null {
  if (s.codigo_formateado) return s.codigo_formateado;
  if (!s.codigo) return null;
  return /^URUKU-/i.test(s.codigo) ? s.codigo.toUpperCase() : `URUKU-${s.codigo.toUpperCase()}`;
}

/** La clave con la que el dueño entra a su panel, una vez, antes del código. */
function ClaveDelNegocio({ clave, nombre, onListo }: { clave: string; nombre: string; onListo: () => void }) {
  return (
    <>
      <Nav />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 56 }}>
        <span className="eyebrow"><Ic n="listo" s={14} /> Negocio creado</span>
        <h1 style={{ fontSize: 28, margin: "10px 0 14px" }}>{nombre} ya está en URUKU</h1>
        <ClaveUnaVez clave={clave} titulo="Tu clave para entrar" onListo={onListo} textoListo="Ya la guardé" />
      </div>
    </>
  );
}

function CodigoDelNegocio({ codigo, nombre, onSeguir }: { codigo: string; nombre: string; onSeguir: () => void }) {
  const [copiado, setCopiado] = useState(false);
  async function copiar() {
    try { await navigator.clipboard.writeText(codigo); setCopiado(true); } catch { /* sin portapapeles: el código está a la vista */ }
  }
  return (
    <>
      <Nav />
      <div className="wrap" style={{ maxWidth: 480, paddingTop: 56 }}>
        <span className="eyebrow"><Ic n="listo" s={14} /> Negocio creado</span>
        <h1 style={{ fontSize: 28, margin: "10px 0 6px" }}>{nombre} ya está en URUKU</h1>
        <div className="glass" style={{ padding: 22, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12, textAlign: "center" }}>
          <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700 }}>EL CÓDIGO DE TU NEGOCIO</div>
          <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: ".04em", color: "var(--neon)" }} aria-label={`Código ${codigo}`}>{codigo}</div>
          <p style={{ color: "var(--txt-2)", fontSize: 14, margin: 0 }}>
            Mandalo en un mensaje de WhatsApp para publicar una oferta o para atar tu grupo a tu negocio.
            Guardalo: lo vas a necesitar.
          </p>
          <button type="button" className="btn" onClick={copiar} style={{ border: "1px solid var(--stroke)" }}>
            {copiado ? "Código copiado" : "Copiar código"}
          </button>
          <button type="button" className="btn btn-primary" onClick={onSeguir}>Seguir a publicar <Send style={{ width: 15, height: 15 }} /></button>
        </div>
      </div>
    </>
  );
}

/* ----------------------------- AUTH (login / registro) ----------------------------- */
// El plan ya no se elige en el alta —
// arranca en "gratis" (= Básico) y se cambia después desde Mi Comercio → Suscripción.

function QueOfrecemos() {
  return (
    <div className="glass" style={{ padding: 20, borderRadius: 16, marginBottom: 18 }}>
      <h2 style={{ fontSize: 18, marginBottom: 10 }}>¿Por qué unirte a URUKU?</h2>
      <ul style={{ display: "flex", flexDirection: "column", gap: 8, color: "var(--txt-2)", fontSize: 14, paddingLeft: 18, listStyle: "none" }}>
        <li><Ic n="ubicacion" s={16} /> Tu negocio aparece en el mapa y en el buscador.</li>
        <li><Ic n="novedades" s={16} /> Publicás ofertas mandando una foto por WhatsApp.</li>
        <li><Ic n="whatsapp" s={16} /> El comprador te escribe directo a tu WhatsApp.</li>
        <li><Ic n="destacado" s={16} /> Con <a href="/autoregistro" rel="noopener">las funciones para comercios</a>: ficha completa y un chatbot que atiende por vos.</li>
        <li><Ic n="plata" s={16} /> Sin comisiones por venta.</li>
      </ul>
    </div>
  );
}

function AuthView({ onLogged, onRegistrado }: { onLogged: (s: ComercioSession) => void; onRegistrado: (r: RegistroResult) => void }) {
  const [mode, setMode] = useState<"login" | "registro">("registro");
  // Tras el 409 («ese número ya tiene un negocio») se abre el ingreso directo por
  // WhatsApp, con el número ya escrito. `n` cambia la `key` para remontar el login.
  const [directo, setDirecto] = useState<{ whatsapp: string; n: number } | null>(null);
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
        <p style={{ color: "var(--txt-3)", marginBottom: 12 }}>
          {mode === "registro" ? "Creá tu cuenta; nuestro asistente te ayuda a publicar en segundos." : "Ingresá a tu cuenta."}
        </p>

        {mode === "registro" && (
          <div className="glass" style={{ padding: "12px 16px", borderRadius: 12, marginBottom: 14, fontSize: 13.5, color: "var(--txt-2)" }}>
            <Ic n="aviso" s={15} /> Si tu negocio ya está en el mapa, no lo crees de nuevo: {" "}
            <button type="button" onClick={() => setMode("login")} style={{ background: "none", border: "none", color: "var(--neon)", padding: 0, cursor: "pointer", font: "inherit", textDecoration: "underline" }}>
              entrá con tu celular y tu clave
            </button>.
          </div>
        )}
        {mode === "registro" && <QueOfrecemos />}
        {mode === "login"
          ? <LoginComercio key={directo?.n ?? 0} onLogged={onLogged}
              modoInicial={directo ? "whatsapp" : "clave"} whatsappInicial={directo?.whatsapp ?? ""} />
          : <RegistroForm onLogged={onRegistrado}
              onYaTieneNegocio={(whatsapp) => { setDirecto((d) => ({ whatsapp, n: (d?.n ?? 0) + 1 })); setMode("login"); }} />}

        {mode === "login" && (
          <p style={{ color: "var(--txt-3)", fontSize: 13, margin: "14px 0 0" }}>
            Si tu negocio ya está en el mapa, no lo crees de nuevo: entrá con tu celular y tu clave,
            o confirmá con tu WhatsApp si es la primera vez.
          </p>
        )}
        <button
          type="button"
          onClick={() => setMode(mode === "registro" ? "login" : "registro")}
          style={{ background: "none", border: "none", color: "var(--neon)", fontSize: 13, padding: 0, marginTop: 14, cursor: "pointer" }}
        >
          {mode === "registro" ? "¿Ya tenés cuenta? Ingresá acá" : "¿No tenés cuenta? Creala acá"}
        </button>

        <p style={{ color: "var(--txt-3)", fontSize: 13, marginTop: 18 }}>
          También podés publicar por{" "}
          <a href={waUruku("Hola, quiero publicar mi negocio en URUKU")} target="_blank" rel="noopener" style={{ color: "var(--wa)" }}>WhatsApp</a>.
        </p>
      </div>
    </>
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

function RegistroForm({ onLogged, onYaTieneNegocio }: { onLogged: (r: RegistroResult) => void; onYaTieneNegocio: (whatsapp: string) => void }) {
  const [f, setF] = useState<RegistroFormState>({ nombre: "", whatsapp: "", modalidad: "mayorista", direccion: "" });
  const set = (k: keyof RegistroFormState, v: string) => setF((s) => ({ ...s, [k]: v }));

  const [queVende, setQueVende] = useState("");
  const [descripcion, setDescripcion] = useState("");
  const [rubroSlugs, setRubroSlugs] = useState<string[]>([]);
  const [generando, setGenerando] = useState(false);

  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [geoMsg, setGeoMsg] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  // El File, no la URL: el hook la revoca solo (ver lib/object-url.ts).
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const preview = useObjectUrl(previewFile);
  const [comprimiendo, setComprimiendo] = useState(false);

  const [err, setErr] = useState("");
  // 409: ese número ya tiene un negocio. Se muestra su `detail` y la salida.
  const [yaTiene, setYaTiene] = useState("");
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
    if (!file) { setFoto(null); setPreviewFile(null); return; }
    setPreviewFile(file);
    setComprimiendo(true);
    const comprimida = await comprimirImagen(file);
    setComprimiendo(false);
    setFoto(comprimida);
    setPreviewFile(comprimida);   // se suelta la original de 12 MP
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(""); setYaTiene("");
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
    } catch (ex) {
      if (ex instanceof NumeroYaRegistrado) setYaTiene(ex.message);
      else setErr(mensajeDeError(ex, "No se pudo crear la cuenta"));
    }
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
        {generando ? "Generando…" : <><Ic n="destacado" s={15} /> Generar descripción con IA</>}
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
          {coords ? <><Ic n="listo" s={15} /> Ubicación tomada — tomar de nuevo</> : <><Ic n="ubicacion" s={15} /> Usar mi ubicación actual</>}
        </button>
        {geoMsg && <PermisoUbicacion mensaje={geoMsg} onPedir={ubicar} motivo="Para poner tu negocio en el mapa" />}
      </div>

      <div>
        <label className="campo-lbl">Foto del negocio *</label>
        <label className="foto-drop">
          {preview ? <img src={preview} alt="" /> : <span><Ic n="foto" s={16} /> Sacar foto / elegir</span>}
          <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
        </label>
        {comprimiendo && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Comprimiendo foto…</div>}
        {!comprimiendo && foto && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>{(foto.size / 1024).toFixed(0)} KB</div>}
      </div>

      <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)}
        placeholder="Punto de referencia (ej: frente a la plaza, al lado de la farmacia)" />

      {err && <span role="alert" style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={14} /> {err}</span>}
      {yaTiene && (
        <div role="alert" style={{ display: "flex", flexDirection: "column", gap: 10, padding: 12, borderRadius: 12, border: "1px solid var(--amber)", background: "rgba(255,176,32,.08)" }}>
          <span style={{ fontSize: 13.5, color: "var(--txt)" }}><Ic n="aviso" s={15} /> {yaTiene}</span>
          <button type="button" className="btn btn-primary" onClick={() => onYaTieneNegocio(f.whatsapp.trim())}>
            <WhatsApp style={{ width: 16, height: 16 }} /> Entrar con mi WhatsApp
          </button>
        </div>
      )}
      <button className="btn btn-primary" type="submit" disabled={loading}>
        {loading ? "Creando…" : "Crear cuenta y publicar"}
      </button>
      <small style={{ color: "var(--txt-3)" }}>
        Después, desde "Mi negocio" podés sumar redes sociales, cambiar de plan y completar el resto.
      </small>
    </form>
  );
}

/* ----------------------------- CHATBOT ----------------------------- */
const QUESTIONS: Record<Step, string> = {
  tipo: "¡Hola! ¿Qué querés publicar hoy?",
  titulo: "Perfecto. ¿Qué nombre o título le ponemos?",
  precio: "¿Cuál es el precio? (escribí solo el número, o 'no' si no aplica)",
  descripcion: "Contame los detalles: descripción, talles, condiciones…",
  tiktok: "Pegá el link del video de TikTok",
  imagen: "¿Tenés una foto? Pegá el link de la imagen (o escribí 'no')",
  confirm: "Revisá tu publicación acá abajo",
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

  const say = (from: "bot" | "user", text: string, kind?: Msg["kind"]) => setMsgs((m) => [...m, { from, text, kind }]);
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
    say("user", "Publicar");
    try {
      const res = await publicar(draft);
      if (res.publicado_directo) {
        say("bot", "¡Listo! Tu publicación ya está EN VIVO en URUKU. (Tu comercio es confiable, se publicó directo.)");
      } else {
        say("bot", "¡Recibido! Tu publicación quedó en revisión. Un moderador la aprueba y aparece en el feed en vivo.");
      }
      // El aviso queda como mensaje del chat (no un toast): es plata, y tiene
      // que poder releerse después de publicar.
      if (res.aviso) say("bot", res.aviso, "aviso");
      setStep("done");
    } catch (e) {
      // Un 402 trae el motivo y qué hacer; se muestra tal cual, sin reescribirlo.
      // Cualquier otro fallo es de red o del servidor: ahí sí el mensaje genérico.
      if (e instanceof PublicarBloqueado) say("bot", e.message, "bloqueado");
      else say("bot", "No pude publicar. Verificá que el backend esté corriendo e intentá de nuevo.");
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
              {sess.confiable ? "Comercio confiable — publicás directo, sin moderación" : "Tus publicaciones pasan por moderación"}
            </small>
          </div>
          <button className="link-more" onClick={onLogout}>Salir</button>
        </div>

        <div className="chat glass">
          <div className="chat-body">
            {msgs.map((m, i) => (
              m.kind ? (
                <div key={i} className={`bubble ${m.from}`} role="alert"
                  style={{ border: "1px solid var(--amber)", display: "grid", gap: 4 }}>
                  <b style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--amber)" }}>
                    <Ic n="aviso" s={16} /> {m.kind === "aviso" ? "Aviso sobre tu plan" : "No se publicó"}
                  </b>
                  <span>{m.text}</span>
                </div>
              ) : (
                <div key={i} className={`bubble ${m.from}`}>{m.text}</div>
              )
            ))}

            {/* Quick replies por paso */}
            {step === "tipo" && (
              <div className="quick">
                <button onClick={() => pickTipo("oferta", "Una oferta")}>Una oferta</button>
                <button onClick={() => pickTipo("video", "Un video")}>Un video</button>
                <button onClick={() => pickTipo("novedad", "Una novedad")}>Una novedad</button>
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
                <button onClick={reset}>Publicar otra</button>
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
