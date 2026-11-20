"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { marcarUtilAsistente, preguntarAsistente, type RespuestaAsistente } from "@/lib/api";
import { Ic } from "@/components/ic";
import { WaLeadLink } from "@/components/wa-lead-link";
import { useRouter } from "next/navigation";
import { esFotoSegura, esUrlWeb, rutaPropia } from "@/lib/enlace-propio";
import { useHoja } from "@/components/home-ciudad/use-hoja";
import { bienvenidaDax, consultaDeBusqueda, franjaAhora, sugerenciasDeFranja } from "@/lib/home-ciudad-pure";

/**
 * Uruku Ayuda: el botón de abajo a la derecha y el panel de chat.
 *
 * Sin `comercio`, es el asistente de URUKU (dónde consigo, abierto ahora, el
 * dólar, cómo publico). Con `comercio`, es el asistente de ESE local en su
 * ficha —el "asistente 24/7" de los planes que lo incluyen— y contesta con
 * los datos del local. Quién puede tenerlo lo decide el servidor: si el plan no
 * lo incluye, el pedido vuelve con 403 y el panel lo dice.
 *
 * El panel (docs/home-ciudades.md §8): en el celular es una hoja que sube desde abajo (64 % del alto) con
 * «× Cerrar» arriba; se cierra con el velo, la rayita, Escape y el «atrás» del teléfono. En la compu es un panel
 * a la derecha. El botón flotante se esconde mientras está abierto; en las ciudades sin Bermejo no hay botón
 * flotante en el celular (Dax vive en la barra de abajo y abre el panel con el evento `uk-abrir-ayuda`).
 *
 * La sesión es un id guardado en el navegador. Sirve para el tope de
 * preguntas por día y para nada más: no identifica a nadie.
 */
type Mensaje =
  | { de: "yo"; texto: string }
  | { de: "uruku"; texto: string; id?: string; pregunta?: string; verUrl?: string | null; fuentes?: RespuestaAsistente["fuentes"]; sugerencias?: string[]; util?: boolean | null; error?: boolean;
      derivar?: RespuestaAsistente["derivar"] };

/** DAX: la cara del chat. Es la misma del volante y de los videos — que el
 *  que ya la vio en la calle la reconozca en el sitio.
 *
 *  El manual de identidad le pone nombre y dos reglas: se escribe con
 *  mayúscula y SIN artículo («Preguntale a Dax», no «a la Dax»), y habla en
 *  primera persona. Y el glosario prohíbe «chatbot», «asistente virtual» e
 *  «IA»: se dice Dax. Antes acá decía «la mascota de URUKU», que no es un
 *  nombre — es una descripción, y una marca no se recuerda por su descripción. */
const MASCOTA = { imagen: "/dax-avatar.png", grande: "/dax-avatar.png", nombre: "Dax" };

const CLAVE_SESION = "uk-ayuda-sesion";

/** El celular: de 899 px para abajo (la barra de abajo se esconde desde 900). Un solo corte para todo. */
const MEDIA_CELULAR = "(max-width: 899px)";

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

export function Asistente({ comercio, ciudad, rubros = null, flotanteMovil = true }: {
  comercio?: { id: string; nombre: string };
  ciudad?: { slug: string; nombre: string; con_guia: boolean };
  /** Los rubros con comercios de la ciudad: Dax sólo sugiere lo que la ciudad puede contestar. `null` = no se sabe. */
  rubros?: string[] | null;
  /** `false` = en el celular no hay botón flotante (la barra de abajo trae a Dax). En la compu siempre se ve. */
  flotanteMovil?: boolean;
}) {
  const nombreCiudad = ciudad?.nombre ?? "Bermejo";
  const conGuia = ciudad?.con_guia ?? true;
  const [abierto, setAbierto] = useState(false);
  const [texto, setTexto] = useState("");
  const [pensando, setPensando] = useState(false);
  const [mensajes, setMensajes] = useState<Mensaje[]>([]);
  const fin = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  const panel = useRef<HTMLDivElement>(null);
  // El panel es MODAL (con velo) sólo en el celular, donde tapa la pantalla; en la compu es un panel al costado.
  // Sólo el modal toca el historial (para que «atrás» lo cierre) y declara `aria-modal`.
  const [modal, setModal] = useState(false);
  const { cerrar } = useHoja(abierto, () => setAbierto(false), () => window.matchMedia(MEDIA_CELULAR).matches);
  useEffect(() => { if (abierto) setModal(window.matchMedia(MEDIA_CELULAR).matches); }, [abierto]);
  const router = useRouter();
  /** Un enlace interno de adentro del panel: el panel baja PRIMERO (sacando su entrada del historial) y recién
   *  después se navega; así no queda un «atrás» de más. Con Ctrl, Cmd, Shift o botón del medio se deja al navegador. */
  const navegar = (e: React.MouseEvent<HTMLAnchorElement>, ruta: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    cerrar(() => router.push(ruta));
  };
  // La franja del día (hora de Bolivia) se toma al abrir: el saludo y las sugerencias son de ese momento.
  const franja = useMemo(() => franjaAhora(), [abierto]); // eslint-disable-line react-hooks/exhaustive-deps

  const bienvenida: Mensaje = comercio
    ? { de: "uruku", texto: `Hola, soy el asistente de ${comercio.nombre}. Preguntame por horarios, precios, ofertas o cómo llegar.`,
        sugerencias: ["¿Están abiertos ahora?", "¿Qué ofertas tienen?", "¿Dónde quedan?"] }
    : { de: "uruku", texto: bienvenidaDax(franja, nombreCiudad, conGuia),
        sugerencias: conGuia ? SUGERENCIAS : sugerenciasDeFranja(franja, rubros ? new Set(rubros) : null) };

  useEffect(() => {
    // "Preguntale a URUKU" desde el home, la barra de abajo o donde sea: un evento, sin acoplar.
    const abrir = () => setAbierto(true);
    window.addEventListener("uk-abrir-ayuda", abrir);
    return () => window.removeEventListener("uk-abrir-ayuda", abrir);
  }, []);
  // Al abrir en la compu el cursor va al campo; en el celular NO: el teclado taparía la conversación.
  useEffect(() => {
    if (abierto && window.matchMedia?.("(min-width: 900px)").matches) setTimeout(() => input.current?.focus(), 50);
  }, [abierto]);
  useEffect(() => { fin.current?.scrollIntoView({ block: "end" }); }, [mensajes, pensando]);

  // El teclado del celular no achica la pantalla de la página, sólo la visible: sin esto taparía el campo de
  // escribir. `--uk-teclado` sube la hoja lo que mide el teclado.
  useEffect(() => {
    const vv = window.visualViewport;
    if (!abierto || !vv) return;
    const ajustar = () => {
      const teclado = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
      panel.current?.style.setProperty("--uk-teclado", `${teclado}px`);
      if (teclado > 0) fin.current?.scrollIntoView({ block: "end" });
    };
    ajustar();
    vv.addEventListener("resize", ajustar);
    vv.addEventListener("scroll", ajustar);
    return () => { vv.removeEventListener("resize", ajustar); vv.removeEventListener("scroll", ajustar); };
  }, [abierto]);

  // Cambiar de ciudad con el panel abierto: Dax lo dice y las preguntas siguientes van con la ciudad nueva
  // (`preguntar` lee `ciudad?.slug` del render actual).
  const slugPrevio = useRef(ciudad?.slug);
  useEffect(() => {
    if (slugPrevio.current === ciudad?.slug) return;
    slugPrevio.current = ciudad?.slug;
    if (abierto && !comercio && ciudad) {
      setMensajes((m) => [...m, { de: "uruku", texto: `Ahora te ayudo con ${ciudad.nombre}.` }]);
    }
  }, [ciudad?.slug, ciudad, abierto, comercio]);

  async function preguntar(p: string) {
    const pregunta = p.trim();
    if (!pregunta || pensando) return;
    setTexto("");
    setMensajes((m) => [...m, { de: "yo", texto: pregunta }]);
    setPensando(true);
    try {
      const r = await preguntarAsistente(pregunta, sesionId(), comercio?.id, ciudad?.slug);
      setMensajes((m) => [...m, { de: "uruku", texto: r.texto, id: r.id, pregunta, verUrl: r.ver_url ?? null, fuentes: r.fuentes, sugerencias: r.sugerencias, util: null, derivar: r.derivar ?? null }]);
    } catch (e) {
      // "Failed to fetch" es lo que dice el navegador cuando no hay señal; no
      // es algo que se le muestre a alguien. Los mensajes que escribimos
      // nosotros (tope diario, asistente apagado) sí se muestran tal cual.
      const crudo = e instanceof Error ? e.message : "";
      const nuestro = crudo && !/failed to fetch|load failed|networkerror/i.test(crudo);
      setMensajes((m) => [...m, { de: "uruku", error: true,
        texto: nuestro ? crudo : "Me quedé sin señal. Probá de nuevo en un minuto." }]);
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
      {/* El botón flotante se esconde mientras el panel está abierto (el panel tiene su propio «Cerrar»). */}
      {!abierto && (
        <button type="button" className={`uk-ayuda-btn${flotanteMovil ? "" : " uk-ayuda-btn-compu"}`} onClick={() => setAbierto(true)}
                aria-label={`Preguntale a ${MASCOTA.nombre}`} aria-haspopup="dialog" aria-expanded={false}>
          <img className="uk-ayuda-mascota" src={MASCOTA.imagen} alt="" width={34} height={34} />
          <span>Preguntame</span>
        </button>
      )}

      {abierto && (
        <>
        <div className="uk-hoja-velo uk-ayuda-velo" onClick={() => cerrar()} aria-hidden="true" />
        <div ref={panel} className="uk-hoja uk-ayuda" role="dialog" aria-modal={modal ? "true" : undefined}
             aria-label={comercio ? `Asistente de ${comercio.nombre}` : "Uruku Ayuda"}>
          <button type="button" className="uk-hoja-tirador" aria-label="Cerrar" onClick={() => cerrar()} />
          <div className="uk-ayuda-cab">
            {!comercio && <img className="uk-ayuda-mascota-cab" src={MASCOTA.grande} alt="" width={40} height={40} />}
            <div>
              <b>{comercio ? `Preguntale a ${comercio.nombre}` : MASCOTA.nombre}</b>
              <span>{comercio ? "Contesta con los datos del local" : `Tu guía en ${nombreCiudad}`}</span>
            </div>
            <button type="button" className="uk-hoja-cerrar" onClick={() => cerrar()}><Ic n="cerrar" s={15} /> Cerrar</button>
          </div>
          <div className="uk-ayuda-msgs">
            {lista.map((m, i) => (
              <div key={i} className={`uk-ayuda-msg ${m.de}${m.de === "uruku" && m.error ? " error" : ""}${comercio ? " sin-cara" : ""}`}>
                {m.de === "uruku" && !comercio && (
                  <img className="uk-ayuda-mascota-msg" src={MASCOTA.imagen} alt="" width={26} height={26} />
                )}
                <div className="uk-ayuda-burbuja">{linkear(m.texto, navegar)}</div>
                {m.de === "uruku" && !comercio && m.fuentes && m.fuentes.some((f) => f.tipo === "comercio" && f.url) && (
                  <TarjetaComercios fuentes={m.fuentes} ciudad={ciudad} pregunta={m.pregunta} verUrl={m.verUrl} navegar={navegar} />
                )}
                {m.de === "uruku" && m.fuentes && m.fuentes.filter((f) => f.tipo === "comercio" && f.url).length > 0 && (
                  <div className="uk-ayuda-fuentes">
                    {m.fuentes.filter((f) => f.tipo === "comercio" && f.url).slice(0, 5).map((f) => {
                      const ruta = rutaPropia(f.url);
                      // Una dirección que no es del sitio ni web (otro esquema) no se dibuja como enlace.
                      if (!ruta && !esUrlWeb(f.url)) return null;
                      return (
                        <a key={f.url} href={ruta ?? f.url} onClick={ruta ? (e) => navegar(e, ruta) : undefined}
                           target={ruta ? undefined : "_blank"} rel={ruta ? undefined : "noopener noreferrer"}>
                          <b>{f.nombre}</b>{f.detalle ? <span>{f.detalle}</span> : null}
                        </a>
                      );
                    })}
                  </div>
                )}
                {/* Cuando el chatbot del local no supo, el comprador no se queda
                    en la nada: el botón le abre WhatsApp con la pregunta ya
                    escrita. Es el mismo enlace y el mismo registro de contacto
                    que el botón de la ficha. Sin comercio (el asistente de
                    URUKU) nunca hay derivación. */}
                {m.de === "uruku" && comercio && m.derivar?.whatsapp && (
                  <WaLeadLink className="uk-ayuda-derivar" comercioId={comercio.id} nombre={comercio.nombre}
                              whatsapp={m.derivar.whatsapp} mensaje={m.derivar.texto}>
                    <Ic n="whatsapp" s={18} />
                    <span>Preguntarle a {comercio.nombre} por WhatsApp</span>
                  </WaLeadLink>
                )}
                {m.de === "uruku" && m.id && (
                  <div className="uk-ayuda-util">
                    {m.util == null ? (
                      <>
                        <span>¿Te sirvió?</span>
                        <button type="button" onClick={() => votar(i - 1, true)} aria-label="Sí, me sirvió"><Ic n="util" s={16} /></button>
                        <button type="button" onClick={() => votar(i - 1, false)} aria-label="No me sirvió"><Ic n="inutil" s={16} /></button>
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
            <button type="submit" aria-label="Enviar" disabled={pensando || !texto.trim()}><Ic n="enviar" s={20} /></button>
          </form>
        </div>
        </>
      )}
    </>
  );
}

/** Una respuesta con comercios, como tarjeta: la foto del primero (si el servidor la manda), su nombre y el
 *  botón «Ver comercios ›» a la búsqueda. Sin cantidades. La lista de `fuentes` sigue debajo, con cada local. */
function TarjetaComercios({ fuentes, ciudad, pregunta, verUrl, navegar }: {
  fuentes: RespuestaAsistente["fuentes"];
  navegar: Navegar;
  ciudad?: { slug: string; nombre: string };
  pregunta?: string;
  verUrl?: string | null;
}) {
  const comercios = fuentes.filter((f) => f.tipo === "comercio" && f.url);
  const primero = comercios[0];
  if (!primero) return null;
  const q = pregunta ? consultaDeBusqueda(pregunta) : "";
  const propia = rutaPropia(verUrl);
  const ver = propia
    ? propia
    : q ? `/buscar?q=${encodeURIComponent(q)}${ciudad ? `&ciudad=${encodeURIComponent(ciudad.slug)}` : ""}` : "/buscar?vista=mapa";
  return (
    <div className="uk-ayuda-resp">
      <span className="uk-ayuda-resp-foto">
        {esFotoSegura(primero.foto) ? <img src={primero.foto} alt="" loading="lazy" decoding="async" /> : <Ic n="comercios" s={28} />}
      </span>
      <div>
        <b>{primero.nombre}</b>
        <span>{comercios.length > 1 ? `y otros locales${ciudad ? ` de ${ciudad.nombre}` : ""}` : primero.detalle ?? (ciudad ? `En ${ciudad.nombre}` : "En el mapa")}</span>
        <a className="uk-ayuda-resp-btn" href={ver} onClick={(e) => navegar(e, ver)}>Ver comercios ›</a>
      </div>
    </div>
  );
}

type Navegar = (e: React.MouseEvent<HTMLAnchorElement>, ruta: string) => void;

/** Las direcciones que vienen en el texto, como enlaces. Las del sitio (`rutaPropia`: sólo `https://uruku.bo` y su
 *  ruta, pasada por `rutaInternaSegura`) navegan sin salir; todo lo demás —WhatsApp, Maps, y cualquier cosa rara como
 *  `https://uruku.bo//otro-sitio`— va en otra pestaña. */
function linkear(texto: string, navegar: Navegar) {
  const partes = texto.split(/(https?:\/\/[^\s)]+)/g);
  return partes.map((p, i) => {
    if (!/^https?:\/\//.test(p)) return <span key={i}>{p}</span>;
    const propia = rutaPropia(p);
    return (
      <a key={i} href={propia ?? p} onClick={propia ? (e) => navegar(e, propia) : undefined}
         target={propia ? undefined : "_blank"} rel={propia ? undefined : "noopener noreferrer"}>
        {p.replace(/^https?:\/\//, "").replace(/^www\./, "")}
      </a>
    );
  });
}
