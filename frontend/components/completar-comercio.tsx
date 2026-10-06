"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  actualizarFotoComercioAgente, editarComercioAgente,
  listarFotosCampo, listarVideosCampo, subirFotoCampo, subirVideoCampo, borrarFotoCampo, borrarVideoCampo,
  type ComercioAgente, type EditarComercioBody, type Lugar,
} from "@/lib/campo";
import type { Rubro } from "@/lib/types";
import { comprimirImagen } from "@/lib/imagen";
import { GaleriaUploader, type GaleriaApi } from "@/components/galeria-uploader";
import { EditorHorario, recordarUltimoHorario } from "@/components/editor-horario";
import { Ic, type NombreIcono } from "@/components/ic";

/** La galería del local desde la app del agente. Exportada porque el final del
 *  alta la muestra sola cuando no pudo abrir «Completar comercio»: las fotos
 *  del local se sacan ahí, parado en la puerta, haya señal o no. */
export function apiGaleriaCampo(id: string): GaleriaApi {
  return {
    cargarFotos: () => listarFotosCampo(id),
    subirFoto: (file, onP) => subirFotoCampo(id, file, onP),
    borrarFoto: (fid) => borrarFotoCampo(id, fid),
    cargarVideos: () => listarVideosCampo(id),
    subirVideo: (file, dur, onP) => subirVideoCampo(id, file, dur, onP),
    borrarVideo: (vid) => borrarVideoCampo(id, vid),
  };
}

/**
 * «COMPLETAR COMERCIO»: la única pantalla para cargar todo lo que le falta a un
 * comercio que ya está en el mapa.
 *
 * Reemplaza al «Editar» de la lista y a la segunda pasada suelta: eran dos
 * editores que no se veían entre sí y ninguno cargaba el horario, que es el dato
 * más preguntado. Se abre desde «Es este», desde «Editar» en «Comercios de mi
 * ciudad» (incluido el filtro «Sin horario») y al final del alta.
 *
 * CÓMO GUARDA. Todo junto, con UN botón fijo abajo que siempre se ve, y manda
 * sólo lo que el agente tocó. Por sección habría que bajar a buscar el botón de
 * cada una; con uno solo por campo se pierde el hilo de la charla con el dueño.
 * Y mandar sólo lo tocado es lo que impide pisar lo que otro cargó mientras
 * tanto (el dueño desde Mi comercio, el admin desde el panel).
 *
 * SI FALLA LA RED, el error se dice en pantalla y TODO lo escrito queda en el
 * formulario: nada se resetea salvo después de un guardado exitoso.
 */

const CAMPOS_TEXTO = [
  "horario", "telefono", "direccion", "prod_obs_human", "puesto", "email",
  "instagram_url", "facebook_url", "tiktok_url", "sitio_web", "canal_wa_url", "catalogo_url",
] as const;
type CampoTexto = (typeof CAMPOS_TEXTO)[number];
type Campos = Record<CampoTexto, string> & { nombre: string; modalidad: string; lugar_id: string };

function desdeComercio(c: ComercioAgente): Campos {
  const t = (v: string | null | undefined) => v ?? "";
  return {
    nombre: t(c.nombre), modalidad: t(c.modalidad), lugar_id: t(c.lugar_id),
    horario: t(c.horario), telefono: t(c.telefono), direccion: t(c.direccion),
    prod_obs_human: t(c.prod_obs_human), puesto: t(c.puesto), email: t(c.email),
    instagram_url: t(c.instagram_url), facebook_url: t(c.facebook_url), tiktok_url: t(c.tiktok_url),
    sitio_web: t(c.sitio_web), canal_wa_url: t(c.canal_wa_url), catalogo_url: t(c.catalogo_url),
  };
}

const MODALIDADES = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

// Bolivia y Argentina (frontera). Argentina lleva el 9 de móvil: sin él el
// enlace de WhatsApp no abre ningún chat.
const PREFIJOS: { p: string; label: string }[] = [
  { p: "591", label: "+591 Bolivia" },
  { p: "549", label: "+549 Argentina" },
];

type ClaveFalta = "horario" | "contacto" | "vidriera" | "fotos" | "vende" | "rubro" | "puesto";
type Falta = { clave: ClaveFalta; label: string; ir: string; foco?: string };

/** Lo que el comercio NO tiene, en el orden de la charla con el dueño. Se calcula
 *  de lo GUARDADO (el comercio que llega por props), no de lo que está tipeado:
 *  un ítem sale de la lista cuando el dato ya está a salvo. */
function calcularFaltas(c: ComercioAgente, nFotos: number | null): Falta[] {
  const r: Falta[] = [];
  if (!(c.horario ?? "").trim()) r.push({ clave: "horario", label: "Horario", ir: "cc-horario" });
  if (!(c.whatsapp ?? "").trim() && !(c.telefono ?? "").trim()) r.push({ clave: "contacto", label: "Contacto", ir: "cc-contacto", foco: "cc-wa" });
  if (!c.portada_url) r.push({ clave: "vidriera", label: "Foto de la vidriera", ir: "cc-fotos" });
  // null = la galería todavía no respondió: no se afirma que falta.
  if (nFotos === 0) r.push({ clave: "fotos", label: "Fotos del local", ir: "cc-galeria" });
  if (!(c.prod_obs_human ?? "").trim()) r.push({ clave: "vende", label: "Qué vende", ir: "cc-vende", foco: "cc-vende-txt" });
  if (!c.rubros) r.push({ clave: "rubro", label: "Rubro", ir: "cc-rubros" });
  if (c.lugar_id && !(c.puesto ?? "").trim()) r.push({ clave: "puesto", label: "Puesto", ir: "cc-mercado", foco: "cc-puesto" });
  return r;
}

function textoError(e: unknown): string {
  const sinRed = (typeof navigator !== "undefined" && !navigator.onLine) || e instanceof TypeError;
  if (sinRed) return "Sin conexión: no se guardó. Lo que escribiste sigue acá; probá de nuevo cuando haya señal.";
  return e instanceof Error ? e.message : "No se pudo guardar";
}

const hintStyle = { color: "var(--txt-3)", fontSize: 11.5, margin: "6px 0 0", lineHeight: 1.4 } as const;

function Seccion({ id, titulo, icono, falta, destacada, children }: {
  id: string; titulo: string; icono: NombreIcono; falta?: boolean; destacada?: boolean; children: React.ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-t`}
             style={{ scrollMarginTop: 8, padding: 12, borderRadius: 12, background: "var(--panel)",
                      border: `1px solid ${destacada ? "var(--neon)" : "var(--stroke)"}` }}>
      <h2 id={`${id}-t`} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 700, margin: "0 0 10px" }}>
        <Ic n={icono} s={16} /> {titulo}
        {falta && (
          <span style={{ marginLeft: "auto", fontSize: 11, fontWeight: 700, color: "var(--amber)" }}>
            <Ic n="aviso" s={11} /> Falta
          </span>
        )}
      </h2>
      <div style={{ display: "grid", gap: 12 }}>{children}</div>
    </section>
  );
}

export function CompletarComercio({ comercio, rubros, lugares, abrirEn, sinWhatsapp, onGuardado, onVolver }: {
  /** El comercio como está GUARDADO. Al guardar, quien lo usa le suma el parche
   *  (`onGuardado`) y lo vuelve a pasar: así «Le falta» se actualiza solo. */
  comercio: ComercioAgente;
  rubros: Rubro[];
  lugares: Lugar[];
  /** Dónde pararse al abrir: «horario» (filtro «Sin horario»), «arriba» (al
   *  venir de la lista) o nada (al final del alta, que ya está en pantalla). */
  abrirEn?: "horario" | "arriba";
  /** Al final del alta el WhatsApp se pide arriba, en su propia tarjeta. */
  sinWhatsapp?: boolean;
  onGuardado: (patch: Partial<ComercioAgente>) => void;
  /** Sin esto no hay botón «Volver» (al final del alta no hay lista a la que volver). */
  onVolver?: () => void;
}) {
  const [base, setBase] = useState<Campos>(() => desdeComercio(comercio));
  const [f, setF] = useState<Campos>(base);
  // Todos los rubros, el principal primero: si sólo se tomara el principal,
  // guardar los rubros borraría los secundarios sin que el agente lo vea.
  const [baseRubros, setBaseRubros] = useState<string[]>(() => {
    const todos = (comercio.comercio_rubros ?? []).map((x) => x.rubros?.slug).filter((x): x is string => !!x);
    const principal = comercio.rubros?.slug;
    return principal ? [principal, ...todos.filter((x) => x !== principal)] : todos;
  });
  const [rubroSlugs, setRubroSlugs] = useState<string[]>(baseRubros);
  const [waPref, setWaPref] = useState("591");
  const [waCel, setWaCel] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [guardado, setGuardado] = useState(false);
  const [err, setErr] = useState("");
  const [online, setOnline] = useState(true);
  const [nFotos, setNFotos] = useState<number | null>(null);
  const [fotosSinDato, setFotosSinDato] = useState(false);
  // La foto de la vidriera sube sola al elegirla (su propio endpoint). Si falla
  // se guarda el archivo para reintentar sin volver a sacarla.
  const [subiendoPortada, setSubiendoPortada] = useState(false);
  const [portadaFalla, setPortadaFalla] = useState<{ file: File; msg: string } | null>(null);
  const portadaInput = useRef<HTMLInputElement>(null);

  const set = (k: keyof Campos, v: string) => { setF((p) => ({ ...p, [k]: v })); setGuardado(false); setErr(""); };

  useEffect(() => {
    setOnline(typeof navigator === "undefined" || navigator.onLine);
    const on = () => setOnline(true), off = () => setOnline(false);
    window.addEventListener("online", on); window.addEventListener("offline", off);
    return () => { window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);

  useEffect(() => {
    if (abrirEn === "horario") {
      // Sin foco: en el celular abriría el teclado y los atajos de un toque
      // quedarían tapados. Se deja el horario a la vista y se elige ahí.
      document.getElementById("cc-horario")?.scrollIntoView({ block: "start" });
    } else if (abrirEn === "arriba") {
      window.scrollTo(0, 0);
    }
    // Una sola vez, al abrir.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const tieneWa = !!(comercio.whatsapp ?? "").trim();
  const waDigitos = waCel.replace(/\D/g, "");
  const faltas = useMemo(() => calcularFaltas(comercio, nFotos), [comercio, nFotos]);
  const falta = (k: ClaveFalta) => faltas.some((x) => x.clave === k);

  // Lo que la lista del servidor no trae no se puede mostrar: se avisa en vez de
  // dejar un campo vacío que parece decir «no tiene».

  const rubrosCambiaron = [...rubroSlugs].sort().join("|") !== [...baseRubros].sort().join("|");
  const cambiados: string[] = [
    ...(Object.keys(f) as (keyof Campos)[]).filter((k) => f[k].trim() !== base[k].trim()),
    ...(rubrosCambiaron ? ["rubros"] : []),
    ...(!tieneWa && !sinWhatsapp && waDigitos ? ["whatsapp"] : []),
  ];
  const sucio = cambiados.length > 0;

  function irA(x: Falta) {
    document.getElementById(x.ir)?.scrollIntoView({ behavior: "smooth", block: "start" });
    if (x.foco) {
      const id = x.foco === "cc-wa" && tieneWa ? "cc-tel" : x.foco;
      window.setTimeout(() => document.getElementById(id)?.focus({ preventScroll: true }), 350);
    }
  }

  function volver() {
    if (sucio && !window.confirm("Tenés cambios sin guardar. Si salís, se pierden. ¿Salir igual?")) return;
    onVolver?.();
  }

  async function guardar() {
    if (guardando || !sucio) return;
    setErr("");
    const cambio = (k: keyof Campos) => f[k].trim() !== base[k].trim();
    const body: EditarComercioBody = {};
    const patch: Partial<ComercioAgente> = {};

    if (cambio("nombre")) {
      const n = f.nombre.trim();
      if (!n) { setErr("El nombre no puede quedar vacío."); document.getElementById("cc-nombre")?.focus(); return; }
      body.nombre = n; patch.nombre = n;
    }
    if (cambio("modalidad")) { body.modalidad = f.modalidad; patch.modalidad = f.modalidad; }
    if (cambio("lugar_id")) {
      body.lugar_id = f.lugar_id || null; patch.lugar_id = f.lugar_id || null;
      const l = lugares.find((x) => x.id === f.lugar_id);
      patch.lugares = l ? { nombre: l.nombre, tipo: l.tipo, lat: l.lat, lng: l.lng, portada_thumb_url: l.portada_thumb_url ?? null } : null;
    }
    for (const k of CAMPOS_TEXTO) {
      if (!cambio(k)) continue;
      const v = f[k].trim() || null;   // vacío BORRA el dato (deshacer una red mal pegada)
      body[k] = v; patch[k] = v;
    }
    if (rubrosCambiaron) {
      if (rubroSlugs.length === 0) { setErr("Dejá al menos un rubro."); document.getElementById("cc-rubros")?.scrollIntoView({ block: "start" }); return; }
      body.rubro_slugs = rubroSlugs;
      patch.rubros = rubros.find((r) => r.slug === rubroSlugs[0]) ?? comercio.rubros ?? null;
      // TODOS los rubros, no sólo el principal: la lista guarda lo que se le
      // manda acá, y al reabrir el comercio la pantalla arranca de eso. Sin
      // esto, reabrir y volver a guardar borraba un rubro secundario.
      patch.comercio_rubros = rubroSlugs.map((sl) => ({ rubros: rubros.find((r) => r.slug === sl) ?? { nombre: sl, slug: sl } }));
    }
    if (!tieneWa && !sinWhatsapp && waDigitos) {
      // Con menos de 7 dígitos es un número a medio dictar.
      if (waDigitos.length < 7) { setErr("El WhatsApp está incompleto."); document.getElementById("cc-wa")?.focus(); return; }
      body.whatsapp = waPref + waDigitos; patch.whatsapp = waPref + waDigitos;
    }

    setGuardando(true);
    let avisoWa = "";
    try {
      try {
        await editarComercioAgente(comercio.id, body);
      } catch (e) {
        // El dueño pudo haber cargado su WhatsApp mientras tanto (la lista de
        // este celular no lo sabía). El backend no deja cambiar un número ya
        // cargado, y eso no puede tirar abajo el horario y todo lo demás: se
        // reintenta sin el WhatsApp y se avisa.
        if (!body.whatsapp || !/ya tiene WhatsApp/i.test(textoError(e))) throw e;
        delete body.whatsapp; delete patch.whatsapp;
        await editarComercioAgente(comercio.id, body);
        avisoWa = "Lo demás se guardó. El WhatsApp no: este comercio ya tenía uno cargado.";
      }
    } catch (e) {
      setErr(textoError(e));   // NO se toca el formulario: lo escrito queda
      setGuardando(false);
      return;
    }
    if (avisoWa) setErr(avisoWa);
    setGuardando(false);
    if (body.horario) recordarUltimoHorario(f.horario);
    setBase({ ...f }); setBaseRubros(rubroSlugs);
    setWaCel(""); setGuardado(true);
    onGuardado(patch);
  }

  async function subirPortada(file: File) {
    setSubiendoPortada(true); setPortadaFalla(null);
    try {
      const comp = await comprimirImagen(file).catch(() => file);
      const url = await actualizarFotoComercioAgente(comercio.id, comp);
      onGuardado({ portada_url: url });
    } catch (e) {
      setPortadaFalla({ file, msg: textoError(e).replace("no se guardó", "no se subió") });
    } finally { setSubiendoPortada(false); }
  }
  function elegirPortada() {
    // Reemplazarla no tiene vuelta atrás: se confirma si ya hay una.
    if (comercio.portada_url && !window.confirm("Ya tiene foto de la vidriera. ¿Reemplazarla por una nueva?")) return;
    portadaInput.current?.click();
  }

  const lugarActual = lugares.find((l) => l.id === f.lugar_id);
  const subtitulo = [comercio.rubros?.nombre ?? "Sin rubro",
    comercio.lugares?.nombre ? `${comercio.lugares.nombre}${comercio.puesto ? ` #${comercio.puesto}` : ""}` : (comercio.calle ?? "")]
    .filter(Boolean).join(" · ");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, textAlign: "left" }}>
      {onVolver && (
        <button type="button" className="link-more" style={{ alignSelf: "flex-start", minHeight: 44, display: "inline-flex", alignItems: "center", gap: 6 }} onClick={volver}>
          <Ic n="volver" s={15} /> Volver a la lista
        </button>
      )}

      {/* Quién es: la foto es lo que mejor lo identifica desde la vereda. */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ width: 52, height: 52, borderRadius: 10, overflow: "hidden", background: "var(--panel)", flexShrink: 0, display: "grid", placeItems: "center" }}>
          {(comercio.portada_thumb_url || comercio.portada_url)
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={(comercio.portada_thumb_url || comercio.portada_url) as string} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
            : <Ic n="comercios" s={24} />}
        </div>
        <div style={{ minWidth: 0 }}>
          <div className="eyebrow">Completar comercio</div>
          <div style={{ fontWeight: 700, fontSize: 16, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{comercio.nombre || "Sin nombre"}</div>
          <div style={{ fontSize: 12, color: "var(--txt-3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{subtitulo}</div>
        </div>
      </div>

      {/* LE FALTA: cada ítem lleva a su campo. Lo que ya está no se vuelve a pedir. */}
      <div role="region" aria-label="Lo que le falta al comercio"
           style={{ padding: 12, borderRadius: 12, border: `1px solid ${faltas.length ? "var(--amber)" : "var(--neon)"}`,
                    background: faltas.length ? "rgba(255,176,32,.08)" : "rgba(57,255,158,.08)" }}>
        {faltas.length === 0 ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, fontWeight: 700, color: "var(--neon)" }}>
            <Ic n="listo" s={18} /> No le falta nada de lo básico.
          </div>
        ) : (
          <>
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700, fontSize: 14, color: "var(--amber)", marginBottom: 8 }}>
              <Ic n="aviso" s={15} /> Le falta ({faltas.length})
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {faltas.map((x) => (
                <button key={x.clave} type="button" className="mchip"
                        style={{ minHeight: 40, padding: "6px 14px", cursor: "pointer", borderColor: "var(--amber)", color: "var(--amber)" }}
                        onClick={() => irA(x)}>
                  {x.label}
                </button>
              ))}
            </div>
            {nFotos === null && !fotosSinDato && <p style={hintStyle}>Mirando las fotos del local…</p>}
            {nFotos === null && fotosSinDato && <p style={hintStyle}>No se pudo ver si ya tiene fotos del local (¿señal?). Igual podés sacarlas abajo.</p>}
          </>
        )}
      </div>

      {/* 1. HORARIO */}
      <Seccion id="cc-horario" titulo="Horario" icono="reloj" falta={falta("horario")} destacada={abrirEn === "horario" && falta("horario")}>
        <div>
          <label className="campo-lbl" htmlFor="cc-horario-txt">Cuándo abre</label>
          <EditorHorario value={f.horario} onChange={(v) => set("horario", v)} inputId="cc-horario-txt" />
          <p style={hintStyle}>Al guardarlo deja de ser un horario estimado.</p>
        </div>
      </Seccion>

      {/* 2. CONTACTO */}
      <Seccion id="cc-contacto" titulo="Contacto" icono="telefono" falta={falta("contacto")}>
        {!sinWhatsapp && (tieneWa ? (
          <div>
            <div className="campo-lbl">WhatsApp</div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontFamily: "monospace", fontSize: 15 }}>
                <Ic n="whatsapp" s={16} /> +{(comercio.whatsapp ?? "").replace(/\D/g, "")}
              </span>
              <span style={{ fontSize: 11.5, color: "var(--txt-3)" }}>Ya cargado: no se cambia desde acá.</span>
            </div>
            {/* En otra pestaña: salir de acá tiraría lo que está escrito. */}
            <a href="/recuperar-negocio" target="_blank" rel="noopener noreferrer" className="link-more"
               style={{ display: "inline-flex", alignItems: "center", minHeight: 44, marginTop: 6 }}>
              Cambié de número
            </a>
          </div>
        ) : (
          <div>
            <label className="campo-lbl" htmlFor="cc-wa">WhatsApp</label>
            <div style={{ display: "flex", gap: 8 }}>
              <select className="adm-input" style={{ width: "auto", flexShrink: 0 }} value={waPref}
                      onChange={(e) => { setWaPref(e.target.value); setGuardado(false); }} aria-label="País del número">
                {PREFIJOS.map((x) => <option key={x.p} value={x.p}>{x.label}</option>)}
              </select>
              <input id="cc-wa" className="adm-input" type="tel" inputMode="numeric" autoComplete="off" value={waCel}
                     onChange={(e) => { setWaCel(e.target.value); setGuardado(false); setErr(""); }} placeholder="Número de celular" />
            </div>
            <p style={hintStyle}>Si no quiere darlo, dejalo vacío: el local igual queda en el mapa.</p>
          </div>
        ))}
        <div>
          <label className="campo-lbl" htmlFor="cc-tel">Otro teléfono (fijo o de quien atiende)</label>
          <input id="cc-tel" className="adm-input" type="tel" inputMode="tel" value={f.telefono}
                 onChange={(e) => set("telefono", e.target.value)} placeholder="Para llamar, si el WhatsApp es otro" />
        </div>
      </Seccion>

      {/* 3. QUÉ VENDE */}
      <Seccion id="cc-vende" titulo="Qué vende" icono="comprar" falta={falta("vende")}>
        <div>
          <label className="campo-lbl" htmlFor="cc-vende-txt">Productos</label>
          <textarea id="cc-vende-txt" className="adm-input" rows={3} value={f.prod_obs_human}
                    onChange={(e) => set("prod_obs_human", e.target.value)}
                    placeholder="zapatillas, zapatos de vestir, ojotas, mochilas" style={{ resize: "vertical" }} />
          {/* Es el campo que más decide si lo encuentran: la búsqueda mira esto.
              Por eso la ayuda dice CÓMO escribirlo y no sólo qué es. */}
          <p style={hintStyle}>Separado por comas y como lo diría un cliente. Nadie busca «indumentaria»: busca «campera».</p>
        </div>
        <div>
          <div className="campo-lbl">¿Vende por mayor o menor?</div>
          <div className="seg" role="group" aria-label="Mayor o menor">
            {MODALIDADES.map((m) => (
              <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""} aria-pressed={f.modalidad === m.key}
                      style={{ minHeight: 44 }} onClick={() => set("modalidad", m.key)}>{m.label}</button>
            ))}
          </div>
        </div>
      </Seccion>

      {/* 4. RUBROS */}
      <Seccion id="cc-rubros" titulo="Rubro" icono="comercios" falta={falta("rubro")}>
        {rubros.length === 0 ? (
          <p style={{ ...hintStyle, margin: 0 }}><Ic n="reloj" s={12} /> Cargando los rubros…</p>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {rubros.map((r) => {
              const on = rubroSlugs.includes(r.slug);
              return (
                <button key={r.slug} type="button" className={`mchip ${on ? "active" : ""}`} aria-pressed={on}
                        style={{ minHeight: 40, cursor: "pointer" }}
                        onClick={() => { setRubroSlugs((s) => (on ? s.filter((x) => x !== r.slug) : [...s, r.slug])); setGuardado(false); setErr(""); }}>
                  {on && <Ic n="si" s={12} />} {r.nombre}
                </button>
              );
            })}
          </div>
        )}
      </Seccion>

      {/* 5. MERCADO, PUESTO Y REFERENCIA */}
      <Seccion id="cc-mercado" titulo="Mercado, puesto y referencia" icono="mercado" falta={falta("puesto")}>
        <div>
          <label className="campo-lbl" htmlFor="cc-lugar">¿Está dentro de un mercado o galería?</label>
          <select id="cc-lugar" className="adm-input" value={f.lugar_id}
                  onChange={(e) => { const v = e.target.value; setF((p) => ({ ...p, lugar_id: v, puesto: v ? p.puesto : "" })); setGuardado(false); setErr(""); }}>
            <option value="">No — local a la calle</option>
            {/* Si la lista de lugares no llegó, el actual igual tiene que verse. */}
            {f.lugar_id && !lugarActual && <option value={f.lugar_id}>{comercio.lugares?.nombre ?? "Mercado / galería"}</option>}
            {lugares.map((l) => (
              <option key={l.id} value={l.id}>{l.nombre}{l.n_comercios ? ` (${l.n_comercios})` : ""}</option>
            ))}
          </select>
          {f.lugar_id && (
            <input id="cc-puesto" className="adm-input" style={{ marginTop: 8 }} value={f.puesto} aria-label="Número de puesto o pasillo"
                   onChange={(e) => set("puesto", e.target.value)} placeholder="N° de puesto / pasillo" />
          )}
        </div>
        <div>
          <label className="campo-lbl" htmlFor="cc-ref">Punto de referencia</label>
          <input id="cc-ref" className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)}
                 placeholder="Frente a la plaza, al lado de la farmacia…" />
          <p style={hintStyle}>La calle ya la sabemos por el GPS. Esto es para lo difícil de encontrar.</p>
        </div>
      </Seccion>

      {/* 6. FOTOS Y VIDEOS */}
      <Seccion id="cc-fotos" titulo="Fotos y videos" icono="foto" falta={falta("vidriera") || falta("fotos")}>
        <div>
          <div className="campo-lbl">Foto de la vidriera (portada)</div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            {(comercio.portada_thumb_url || comercio.portada_url) && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={(comercio.portada_thumb_url || comercio.portada_url) as string} alt="Portada actual" style={{ width: 64, height: 64, objectFit: "cover", borderRadius: 8 }} />
            )}
            <button type="button" className="btn btn-ghost" style={{ minHeight: 48 }} disabled={subiendoPortada} onClick={elegirPortada}>
              <Ic n="foto" s={16} /> {subiendoPortada ? "Subiendo…" : comercio.portada_url ? "Cambiar foto" : "Sacar foto / elegir"}
            </button>
            <input ref={portadaInput} type="file" accept="image/*" capture="environment" hidden
                   onChange={(e) => { const file = e.target.files?.[0]; e.target.value = ""; if (file) void subirPortada(file); }} />
          </div>
          {portadaFalla && (
            <div role="alert" style={{ marginTop: 8, color: "var(--pink)", fontSize: 12.5 }}>
              <Ic n="aviso" s={12} /> {portadaFalla.msg}{" "}
              <button type="button" className="link-more" style={{ minHeight: 40 }} disabled={subiendoPortada}
                      onClick={() => void subirPortada(portadaFalla.file)}>Reintentar con la misma foto</button>
            </div>
          )}
        </div>
        <div id="cc-galeria" style={{ scrollMarginTop: 8 }}>
          <GaleriaUploader comercioId={comercio.id} onFotos={(n) => { setNFotos(n); setFotosSinDato(false); }} onFotosError={() => setFotosSinDato(true)} api={apiGaleriaCampo(comercio.id)} />
        </div>
      </Seccion>

      {/* 7. REDES, CATÁLOGO Y CANAL */}
      <Seccion id="cc-redes" titulo="Redes, catálogo y canal" icono="instagram">
        <div>
          <label className="campo-lbl" htmlFor="cc-cat">Su catálogo</label>
          <input id="cc-cat" className="adm-input" value={f.catalogo_url} onChange={(e) => set("catalogo_url", e.target.value)}
                 placeholder="Enlace a un PDF, Drive o su tienda" />
          <p style={hintStyle}>Muchos mayoristas ya tienen uno armado y lo mandan por WhatsApp. Pedíselo.</p>
        </div>
        <div>
          <label className="campo-lbl" htmlFor="cc-canal">Su canal de WhatsApp</label>
          <input id="cc-canal" className="adm-input" value={f.canal_wa_url} onChange={(e) => set("canal_wa_url", e.target.value)}
                 placeholder="Enlace de su canal o comunidad" />
          <p style={hintStyle}>El de él, donde publica sus ofertas. No el de URUKU.</p>
        </div>
        <div>
          <div className="campo-lbl">Sus redes</div>
          {/* Se guardan como las escribe el agente: el comerciante dice
              "@mitienda" o pega el enlace entero, y pedirle que lo normalice
              sería perder el dato. Lo arma bien el sitio al mostrarlo. */}
          <div style={{ display: "grid", gap: 8 }}>
            <input className="adm-input" aria-label="Instagram" value={f.instagram_url} onChange={(e) => set("instagram_url", e.target.value)} placeholder="Instagram: @usuario o enlace" />
            <input className="adm-input" aria-label="Facebook" value={f.facebook_url} onChange={(e) => set("facebook_url", e.target.value)} placeholder="Facebook: usuario o enlace" />
            <input className="adm-input" aria-label="TikTok" value={f.tiktok_url} onChange={(e) => set("tiktok_url", e.target.value)} placeholder="TikTok: @usuario o enlace" />
            <input className="adm-input" aria-label="Página web" value={f.sitio_web} onChange={(e) => set("sitio_web", e.target.value)} placeholder="Página web" />
          </div>
        </div>
      </Seccion>

      {/* 8. NOMBRE Y CORREO */}
      <Seccion id="cc-correo" titulo="Nombre y correo" icono="documento">
        <div>
          <label className="campo-lbl" htmlFor="cc-nombre">Nombre del cartel</label>
          <input id="cc-nombre" className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre" />
        </div>
        <div>
          <label className="campo-lbl" htmlFor="cc-email">Correo (opcional)</label>
          <input id="cc-email" className="adm-input" type="email" inputMode="email" autoCapitalize="none" value={f.email}
                 onChange={(e) => set("email", e.target.value)} placeholder="correo@ejemplo.com" />
        </div>
      </Seccion>

      {/* GUARDAR: fijo abajo, siempre a un toque. Con el formulario largo, bajar
          hasta el final para guardar dos datos haría que se dejen sin guardar. */}
      <div style={{ position: "sticky", bottom: 0, zIndex: 5, background: "var(--bg-2, #0e1320)", border: "1px solid var(--stroke)",
                    borderRadius: 14, padding: "10px 12px", paddingBottom: "max(10px, env(safe-area-inset-bottom))",
                    display: "flex", flexDirection: "column", gap: 8 }}>
        {!online && (
          <div role="status" style={{ fontSize: 12.5, color: "var(--amber)" }}>
            <Ic n="aviso" s={13} /> Sin conexión. Lo que escribas queda acá; guardá cuando vuelva la señal.
          </div>
        )}
        {err && (
          <div role="alert" style={{ fontSize: 12.5, color: "var(--pink)", lineHeight: 1.4 }}>
            <Ic n="aviso" s={13} /> {err}
          </div>
        )}
        {guardado && !sucio && !err && (
          <div role="status" style={{ fontSize: 13, color: "var(--neon)", fontWeight: 700 }}>
            <Ic n="listo" s={15} /> Guardado
          </div>
        )}
        {sucio ? (
          <>
            <div style={{ fontSize: 12, color: "var(--amber)" }}>
              {cambiados.length} {cambiados.length === 1 ? "cambio" : "cambios"} sin guardar
            </div>
            <button type="button" className="btn btn-primary" style={{ width: "100%", padding: 14, minHeight: 50 }}
                    disabled={guardando} onClick={guardar}>
              {guardando ? "Guardando…" : err ? "Reintentar guardar" : "Guardar"}
            </button>
          </>
        ) : onVolver ? (
          <button type="button" className={guardado ? "btn btn-primary" : "btn btn-ghost"} style={{ width: "100%", padding: 14, minHeight: 50 }} onClick={volver}>
            Volver a la lista
          </button>
        ) : (
          !guardado && <div style={{ fontSize: 12, color: "var(--txt-3)" }}>Completá lo que el dueño te vaya diciendo. Podés guardar y seguir después.</div>
        )}
      </div>
    </div>
  );
}
