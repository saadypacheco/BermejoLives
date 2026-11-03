"use client";

// Admin › Contenido para redes › Revisión › «Textos del video» (§16.10).
//
// Las piezas con plantilla v2 llevan textos DENTRO del video (frase de arriba, título en
// dos líneas, subtítulo, búsqueda y una frase por foto). Los propone Gemini mirando las
// fotos, pero una persona los ve y los corrige acá antes de aprobar. Lo que se escribe en
// este bloque va al video en español neutro («usted»); el resto del panel sigue con voseo.
//
// La validación de este archivo (`validateVideoTextsPorCampo`) avisa mientras se escribe;
// la que manda es la del backend: ante un 400 se muestra su objeción tal cual.

import { useEffect, useMemo, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Insignia } from "@/components/content/content-ui";
import {
  guardarTextosVideo, leerGeminiContent, mensajeContent, pedirOtraPropuestaVideo,
  type ContentPieceResponse, type ContentPieceSource, type VideoTextsUpdate,
} from "@/lib/content";
import {
  avisoOtraPropuesta, CAMPO_VIDEO_LABEL, chipsEditables, fotoMarcadaPorGemini, origenTextosVideo, urlApiOpt, VIDEO_LIMITES,
  validateVideoTextsPorCampo, type CampoVideo, type VideoTextsEditable,
} from "@/lib/content-pure";

/** La llave de una foto dentro del formulario: su id, o su lugar si el backend no lo manda. */
const llave = (s: ContentPieceSource): string => s.id ?? `pos-${s.position}`;

type Valores = Record<CampoVideo, string>;

function valoresDe(p: ContentPieceResponse): Valores {
  const t = p.video_texts;
  return {
    kick: t?.kick ?? "", title1: t?.title1 ?? "", title2: t?.title2 ?? "",
    subtitle: t?.subtitle ?? "", search_term: t?.search_term ?? "",
  };
}
function chipsDe(p: ContentPieceResponse): Record<string, string> {
  const r: Record<string, string> = {};
  for (const s of p.sources) r[llave(s)] = s.chip_text ?? "";
  return r;
}

const CAMPOS_SIMPLES: { campo: CampoVideo; ayuda: string; opcional: boolean }[] = [
  { campo: "kick", ayuda: "Va arriba del título, en mayúsculas. Puede quedar vacía.", opcional: true },
  { campo: "title1", ayuda: "", opcional: false },
  { campo: "title2", ayuda: "", opcional: false },
  { campo: "subtitle", ayuda: "Va abajo, fijo, mientras pasan las fotos. Puede quedar vacío.", opcional: true },
  { campo: "search_term", ayuda: "Lo que se escribe en el buscador del cierre. Una o dos palabras.", opcional: false },
];

/** Una línea de objeción: ícono y palabras, no sólo color. */
function Objecion({ children }: { children: React.ReactNode }) {
  return (
    <span role="alert" style={{ display: "flex", gap: 5, alignItems: "flex-start", fontSize: 12.5, lineHeight: 1.4, color: "var(--pink)" }}>
      <span style={{ flex: "none", marginTop: 1 }}><Ic n="aviso" s={13} /></span>
      <span>{children}</span>
    </span>
  );
}

/** Un campo de texto con su contador («12/18») y sus objeciones debajo. */
function CampoTexto({ etiqueta, valor, max, opcional, ayuda, objeciones, onChange, deshabilitado }: {
  etiqueta: string; valor: string; max: number; opcional: boolean; ayuda?: string;
  objeciones: readonly string[]; onChange: (v: string) => void; deshabilitado: boolean;
}) {
  const n = Array.from(valor.trim()).length;
  const pasado = n > max;
  return (
    <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
      <span style={{ display: "flex", justifyContent: "space-between", gap: 8, color: "var(--txt-3)", flexWrap: "wrap" }}>
        <span>{etiqueta}{opcional ? " (opcional)" : ""}</span>
        <span style={{ color: pasado ? "var(--pink)" : undefined, fontWeight: pasado ? 700 : 400 }}>
          {n}/{max}{pasado ? " · se pasó" : ""}
        </span>
      </span>
      <input className="adm-input" style={{ minHeight: 48 }} value={valor} disabled={deshabilitado}
             aria-invalid={objeciones.length > 0} autoComplete="off"
             onChange={(e) => onChange(e.target.value)} />
      {ayuda ? <span style={{ color: "var(--txt-3)" }}>{ayuda}</span> : null}
      {objeciones.map((o, i) => <Objecion key={i}>{o}</Objecion>)}
    </label>
  );
}

/**
 * El bloque «Textos del video». `antesDeGuardar` deja guardar primero lo que la persona
 * tenga a medias en los textos de las redes: al volver a armar, la tarjeta se rehace y se
 * perdería. `onSucio` avisa a la tarjeta que hay cambios sin guardar (no se puede aprobar).
 */
export function TextosDelVideo({ pieza, sinArmador, ocupadaAfuera, antesDeGuardar, onCambio, onSucio }: {
  pieza: ContentPieceResponse;
  sinArmador?: boolean;
  /** La tarjeta está haciendo otra cosa (aprobar, saltar…): no se toca nada. */
  ocupadaAfuera?: boolean;
  antesDeGuardar?: () => Promise<void>;
  onCambio: (p: ContentPieceResponse) => void;
  onSucio?: (sucio: boolean) => void;
}) {
  const original = useMemo(() => valoresDe(pieza), [pieza]);
  const chipsOriginal = useMemo(() => chipsDe(pieza), [pieza]);
  const [v, setV] = useState<Valores>(original);
  const [chips, setChips] = useState<Record<string, string>>(chipsOriginal);
  const [okFotos, setOkFotos] = useState<boolean>(pieza.photo_flags_ok ?? false);
  const [ocupado, setOcupado] = useState<"" | "guardar" | "proponer">("");
  const [err, setErr] = useState("");

  const editaChips = chipsEditables(pieza.pillar);
  // Sin `id` de la fuente el backend no puede ubicar la frase: queda de sólo lectura.
  const chipsConId = pieza.sources.every((s) => !!s.id);
  const puedeEditarChips = editaChips && chipsConId;

  const textosCambiaron = (Object.keys(original) as CampoVideo[]).some((c) => v[c].trim() !== original[c].trim())
    || (puedeEditarChips && pieza.sources.some((s) => (chips[llave(s)] ?? "").trim() !== (chipsOriginal[llave(s)] ?? "").trim()));
  const okCambio = okFotos !== (pieza.photo_flags_ok ?? false);
  const sucio = textosCambiaron || okCambio;
  useEffect(() => { onSucio?.(sucio); }, [sucio, onSucio]);

  const hayMarcadas = pieza.sources.some((s) => fotoMarcadaPorGemini(s.photo_flags));
  const editable: VideoTextsEditable = {
    kick: v.kick.trim() || null, title1: v.title1, title2: v.title2,
    subtitle: v.subtitle.trim() || null, search_term: v.search_term,
  };
  const objeciones = validateVideoTextsPorCampo(editable, pieza.sources.map((s) => chips[llave(s)] ?? ""), pieza.pillar);
  const checksBackend = pieza.video_texts_checks ?? [];
  const origen = origenTextosVideo(pieza.video_texts_engine);
  const bloqueado = ocupado !== "" || !!ocupadaAfuera;

  async function guardar() {
    setOcupado("guardar"); setErr("");
    try {
      await antesDeGuardar?.();
      const body: VideoTextsUpdate = {
        kick: v.kick.trim() || null,
        title1: v.title1.trim(),
        title2: v.title2.trim(),
        subtitle: v.subtitle.trim() || null,
        search_term: v.search_term.trim(),
        chips: puedeEditarChips
          ? pieza.sources.flatMap((s) => (s.id ? [{ source_id: s.id, text: (chips[llave(s)] ?? "").trim() || null }] : []))
          : [],
        photo_flags_ok: hayMarcadas ? okFotos : undefined,
      };
      onCambio(await guardarTextosVideo(pieza.id, body));
    } catch (ex) { setErr(mensajeContent(ex, "No se pudieron guardar los textos del video")); setOcupado(""); }
  }

  async function proponer() {
    // El aviso depende del interruptor `gemini_content`: se lee en el momento, no se adivina.
    setOcupado("proponer"); setErr("");
    const gemini = await leerGeminiContent();
    const aviso = avisoOtraPropuesta(gemini, origen === "Escrito a mano" || textosCambiaron);
    if (!window.confirm(aviso)) { setOcupado(""); return; }
    try {
      await antesDeGuardar?.();
      onCambio(await pedirOtraPropuestaVideo(pieza.id));
    } catch (ex) { setErr(mensajeContent(ex, "No se pudo pedir otra propuesta")); setOcupado(""); }
  }

  const soloConfirmacion = okCambio && !textosCambiaron;

  return (
    <section aria-label="Textos del video" style={{ display: "grid", gap: 12, padding: 12, border: "1px solid var(--stroke)", borderRadius: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ fontSize: 14.5 }}>Textos del video</b>
        {origen && (
          <Insignia tono="info" icono={origen === "Escrito a mano" ? "editar" : "dato"}>{origen}</Insignia>
        )}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.45, color: "var(--txt-3)" }}>
        Esto se lee dentro del video, de «usted» y sin precios ni números. Sin voseo (nada de «mirá» ni «buscá»).
      </p>

      {checksBackend.length > 0 && (
        <div style={{ display: "grid", gap: 4, padding: "8px 10px", border: "1px solid var(--pink)", borderRadius: 10 }}>
          <b style={{ fontSize: 13, color: "var(--pink)" }}><Ic n="aviso" s={14} /> El validador objeta estos textos</b>
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--pink)" }}>
            {checksBackend.map((o, i) => <li key={i}>{o}</li>)}
          </ul>
        </div>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {CAMPOS_SIMPLES.map(({ campo, ayuda, opcional }) => (
          <CampoTexto key={campo} etiqueta={CAMPO_VIDEO_LABEL[campo]} valor={v[campo]} max={VIDEO_LIMITES[campo].max}
                      opcional={opcional} ayuda={ayuda} objeciones={objeciones.campos[campo] ?? []}
                      deshabilitado={bloqueado} onChange={(x) => setV((prev) => ({ ...prev, [campo]: x }))} />
        ))}
      </div>

      {/* Una frase por foto, al lado de su miniatura. */}
      {pieza.sources.length > 0 && (
        <div style={{ display: "grid", gap: 10 }}>
          <b style={{ fontSize: 13.5 }}>Frase de cada foto</b>
          {!editaChips && (
            <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{pieza.pillar === "rubro" ? "En un repaso de rubro la frase es el nombre del comercio y no se edita." : "En las ofertas la frase es el nombre del comercio y no se edita."}</span>
          )}
          {editaChips && !chipsConId && (
            <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Las frases de las fotos no se pueden editar desde acá todavía.</span>
          )}
          {pieza.sources.map((s, i) => {
            const k = llave(s);
            const marcada = fotoMarcadaPorGemini(s.photo_flags);
            const nombre = s.chip_text ?? s.comercio_nombre ?? s.caption_fact ?? "";
            return (
              <div key={k} style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                <div style={{ position: "relative", flex: "none", width: 64, height: 64, borderRadius: 10, overflow: "hidden",
                              border: `2px solid ${marcada ? "var(--amber)" : "var(--stroke)"}` }}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={urlApiOpt(s.thumb_url) ?? ""} alt={`Foto ${s.position + 1}`} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  <span style={{ position: "absolute", left: 3, top: 3, fontSize: 11, fontWeight: 700, background: "rgba(0,0,0,.65)", color: "#fff", borderRadius: 6, padding: "0 5px" }}>
                    {s.position + 1}
                  </span>
                </div>
                <div style={{ flex: 1, minWidth: 0, display: "grid", gap: 4 }}>
                  {puedeEditarChips ? (
                    <CampoTexto etiqueta={`Foto ${s.position + 1}`} valor={chips[k] ?? ""} max={VIDEO_LIMITES.chip.max} opcional
                                objeciones={objeciones.chips[i] ?? []} deshabilitado={bloqueado}
                                onChange={(x) => setChips((prev) => ({ ...prev, [k]: x }))} />
                  ) : (
                    <div style={{ display: "grid", gap: 2, fontSize: 13.5 }}>
                      <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Foto {s.position + 1}</span>
                      <span style={{ overflowWrap: "anywhere" }}>{nombre || "Sin frase"}</span>
                    </div>
                  )}
                  {marcada && (
                    <span style={{ justifySelf: "start" }}>
                      <Insignia tono="aviso" icono="aviso">Se ve un precio o un código</Insignia>
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {hayMarcadas && (
        <div style={{ display: "grid", gap: 4 }}>
          <label style={{ display: "flex", gap: 10, alignItems: "flex-start", minHeight: 48, fontSize: 13.5, lineHeight: 1.4, cursor: "pointer" }}>
            <input type="checkbox" checked={okFotos} disabled={bloqueado} onChange={(e) => setOkFotos(e.target.checked)}
                   style={{ width: 24, height: 24, flex: "none", marginTop: 1 }} />
            <span>Revisé las fotos marcadas: no se ve ningún precio ni código</span>
          </label>
          <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
            Si alguna sí lo muestra, quitala arriba con «Rearmar sin las marcadas».
          </span>
        </div>
      )}

      {sinArmador && (
        <Aviso tono="aviso">El armador de videos no está disponible. Lo que guardes espera en la cola hasta que vuelva.</Aviso>
      )}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" style={{ ...BTN_GRANDE, flex: "1 1 200px" }}
                onClick={() => void guardar()} disabled={bloqueado || !sucio}>
          <Ic n="actualizar" s={17} />{" "}
          {ocupado === "guardar" ? "Guardando…" : soloConfirmacion ? "Guardar la confirmación" : "Guardar y volver a armar"}
        </button>
        <button type="button" className="btn btn-ghost" style={{ ...BTN_GRANDE, flex: "1 1 200px" }}
                onClick={() => void proponer()} disabled={bloqueado}>
          <Ic n="editar" s={17} /> {ocupado === "proponer" ? "Pidiendo…" : "Pedir otra propuesta"}
        </button>
        {sucio && (
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={bloqueado}
                  onClick={() => { setV(original); setChips(chipsOriginal); setOkFotos(pieza.photo_flags_ok ?? false); setErr(""); }}>
            Descartar cambios
          </button>
        )}
      </div>
      {!soloConfirmacion && (
        <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Al guardar, el video se vuelve a armar y tarda unos minutos.</span>
      )}
      {err && <Aviso tono="error">{err}</Aviso>}
    </section>
  );
}

/** Los textos del video en sólo lectura: se ven mientras la pieza se está armando. */
export function ResumenTextosVideo({ pieza }: { pieza: ContentPieceResponse }) {
  const t = pieza.video_texts;
  if (!t) return null;
  const lineas = [t.kick, [t.title1, t.title2].filter(Boolean).join(" "), t.subtitle].filter((x): x is string => !!x && x.trim() !== "");
  if (lineas.length === 0) return null;
  return (
    <div style={{ fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.45 }}>
      <span>Textos del video: </span>
      {lineas.map((l, i) => <span key={i}>{i > 0 ? " · " : ""}{l}</span>)}
    </div>
  );
}
