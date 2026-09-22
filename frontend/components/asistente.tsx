"use client";

import { useEffect, useRef, useState } from "react";
import { marcarUtilAsistente, preguntarAsistente, type RespuestaAsistente } from "@/lib/api";

/**
 * Uruku Ayuda: el botón de abajo a la derecha y el panel de chat.
 *
 * Sin `comercio`, es el asistente de URUKU (dónde consigo, abierto ahora, el
 * dólar, cómo publico). Con `comercio`, es el asistente de ESE local en su
 * ficha —el "asistente 24/7" del plan Empleado Digital— y contesta con los
 * datos del local. Quién puede tenerlo lo decide el servidor: si el plan no
 * lo incluye, el pedido vuelve con 403 y el panel lo dice.
 *
 * La sesión es un id guardado en el navegador. Sirve para el tope de
 * preguntas por día y para nada más: no identifica a nadie.
 */
type Mensaje =
  | { de: "yo"; texto: string }
  | { de: "uruku"; texto: string; id?: string; fuentes?: RespuestaAsistente["fuentes"]; sugerencias?: string[]; util?: boolean | null; error?: boolean };

const CLAVE_SESION = "uk-ayuda-sesion";
const CLAVE_ABIERTO = "uk-ayuda-abierto";

function sesionId(): string {
  try {
    let s = localStorage.getItem(CLAVE_SESION);
    if (!s) {
      s = Math.random().toString(36).slice(2) + Date.now().toString(36);
      localStorage.setItem(CLAVE_SESION, s);
    }
    return s;
  } catch {
    return "sin-storage-" + Date.now().toString(36);
  }
}

const SUGERENCIAS = ["¿Dónde cambio dólares?", "¿Qué hay abierto ahora?", "Busco zapatillas", "¿Cómo publico mi negocio?"];
const SUGERENCIAS_SIN_GUIA = ["¿Dónde hay una farmacia?", "Busco zapatillas", "¿Dónde como?", "¿Cómo publico mi negocio?"];

export function Asistente({ comercio, ciudad }: { comercio?: { id: string; nombre: string }; ciudad?: { slug: string; nombre: string; con_guia: boolean } }) {
  const nombreCiudad = ciudad?.nombre ?? "Bermejo";
  const conGuia = ciudad?.con_guia ?? true;
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const fin = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  const bienvenida: Mensaje = comercio
    ? { de: "uruku", texto: `Hola, soy el asistente de ${comercio.nombre}. Preguntame por horarios, precios, ofertas o cómo llegar.`,
        sugerencias: ["¿Están abiertos ahora?", "¿Qué ofertas tienen?", "¿Dónde quedan?"] }
    : { de: "uruku", texto: `Hola, soy la ayuda de URUKU. Preguntame dónde conseguir algo en ${nombreCiudad}, si un local está abierto, ${conGuia ? "el dólar" : "cómo llegar"}, o cómo publicar tu negocio.`,
        sugerencias: conGuia ? SUGERENCIAS : SUGERENCIAS_SIN_GUIA };

  useEffect(() => {
    try { if (sessionStorage.getItem(CLAVE_ABIERTO) === "1") setAbierto(true); } catch { /* modo privado */ }
    // "Preguntale a URUKU" desde el home o donde sea: un evento, sin acoplar.
    const abrir = () => setAbierto(true);
    window.addEventListener("uk-abrir-ayuda", abrir);
    return () => window.removeEventListener("uk-abrir-ayuda", abrir);
  }, []);
  useEffect(() => {
    try { sessionStorage.setItem(CLAVE_ABIERTO, abierto ? "1" : "0"); } catch { /* modo privado */ }
    if (abierto) setTimeout(() => input.current?.focus(), 50);
  }, [abierto]);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [mensajes, pensando]);

  async function preguntar(p: string) {
    const pregunta = p.trim();
    if (!pregunta || pensando) return;
    setTexto("");
    setMensajes((m) => [...m, { de: "yo", texto: pregunta }]);
    setPensando(true);
    try {
      const r = await preguntarAsistente(pregunta, sesionId(), comercio?.id, ciudad?.slug);
      setMensajes((m) => [...m, { de: "uruku", texto: r.texto, id: r.id, fuentes: r.fuentes, sugerencias: r.sugerencias, util: null }]);
    } catch (e) {
      setMensajes((m) => [...m, { de: "uruku", texto: e instanceof Error ? e.message : "No pude contestar ahora.", error: true }]);
    } finally {
      setPensando(false);
    }
  }

  function votar(i: number, util: boolean) {
    setMensajes((m) => m.map((x, j) => (j === i && x.de === "uruku" ? { ...x, util } : x)));
    const msg = mensajes[i];
    if (msg.de === "uruku" && msg.id) marcarUtilAsistente(msg.id, util);
  }

  const lista = [bienvenida, ...mensajes];

  return (
    <>
      <button type="button" className={`uk-ayuda-btn${abierto ? " abierto" : ""}`} onClick={() => setAbierto((a) => !a)}
              aria-label={abierto ? "Cerrar la ayuda" : "Abrir la ayuda"} aria-expanded={abierto}>
        {abierto ? "×" : <><span aria-hidden>💬</span> Ayuda</>}
      </button>

      {abierto && (
        <div className="uk-ayuda" role="dialog" aria-label={comercio ? `Asistente de ${comercio.nombre}` : "Uruku Ayuda"}>
          <div className="uk-ayuda-cab">
            <b>{comercio ? `Preguntale a ${comercio.nombre}` : "Uruku Ayuda"}</b>
            <span>{comercio ? "Contesta con los datos del local" : "Contesta con lo que hay en URUKU"}</span>
          </div>
          <div className="uk-ayuda-msgs">
            {lista.map((m, i) => (
              <div key={i} className={`uk-ayuda-msg ${m.de}${m.de === "uruku" && m.error ? " error" : ""}`}>
                <div className="uk-ayuda-burbuja">{linkear(m.texto)}</div>
                {m.de === "uruku" && m.fuentes && m.fuentes.filter((f) => f.tipo === "comercio" && f.url).length > 0 && (
                  <div className="uk-ayuda-fuentes">
                    {m.fuentes.filter((f) => f.tipo === "comercio" && f.url).slice(0, 5).map((f) => (
                      <a key={f.url} href={f.url.replace("https://uruku.bo", "")}>
                        <b>{f.nombre}</b>{f.detalle ? <span>{f.detalle}</span> : null}
                      </a>
                    ))}
                  </div>
                )}
                {m.de === "uruku" && m.id && (
                  <div className="uk-ayuda-util">
                    {m.util == null ? (
                      <>
                        <span>¿Te sirvió?</span>
                        <button type="button" onClick={() => votar(i - 1, true)} aria-label="Sí, me sirvió">👍</button>
                        <button type="button" onClick={() => votar(i - 1, false)} aria-label="No me sirvió">👎</button>
                      </>
                    ) : <span>{m.util ? "¡Gracias!" : "Anotado, lo mejoramos."}</span>}
                  </div>
                )}
                {m.de === "uruku" && m.sugerencias && m.sugerencias.length > 0 && i === lista.length - 1 && (
                  <div className="uk-ayuda-sug">
                    {m.sugerencias.map((s) => <button key={s} type="button" onClick={() => preguntar(s)}>{s}</button>)}
                  </div>
                )}
              </div>
            ))}
            {pensando && <div className="uk-ayuda-msg uruku"><div className="uk-ayuda-burbuja pensando">…</div></div>}
            <div ref={fin} />
          </div>
          <form className="uk-ayuda-form" onSubmit={(e) => { e.preventDefault(); preguntar(texto); }}>
            <input ref={input} value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={500}
                   placeholder={comercio ? "Preguntale algo al local…" : "¿Qué necesitás?"} aria-label="Tu pregunta" />
            <button type="submit" disabled={pensando || !texto.trim()}>Enviar</button>
          </form>
        </div>
      )}
    </>
  );
}

/** Las direcciones que vienen en el texto, como enlaces. Las de uruku.bo, sin
 *  salir del sitio; las de WhatsApp y Maps, en otra pestaña. */
function linkear(texto: string) {
  const partes = texto.split(/(https?:\/\/[^\s)]+)/g);
  return partes.map((p, i) => {
    if (!/^https?:\/\//.test(p)) return <span key={i}>{p}</span>;
    const propia = p.startsWith("https://uruku.bo");
    return (
      <a key={i} href={propia ? p.replace("https://uruku.bo", "") : p}
         target={propia ? undefined : "_blank"} rel={propia ? undefined : "noopener"}>
        {p.replace(/^https?:\/\//, "").replace(/^www\./, "")}
      </a>
    );
  });
}
