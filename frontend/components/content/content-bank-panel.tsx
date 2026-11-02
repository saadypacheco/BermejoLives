"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia } from "@/components/content/content-ui";
import { ContentBankUploader } from "@/components/content/content-bank-uploader";
import { ContentMerchantPicker } from "@/components/content/content-merchant-picker";
import { SocialConsentBox } from "@/components/content/social-consent-box";
import {
  apiBancoAdmin, mensajeContent,
  type ContentAssetListResponse, type ContentAssetResponse, type ContentAssetUploadResponse, type ContentBankApi,
  type ContentMerchantResponse, type SocialConsentResponse,
} from "@/lib/content";
import { urlApi } from "@/lib/content-pure";

const SIN_AUTORIZACION: SocialConsentResponse = { granted: null, via: null, recorded_at: null, recorded_by: null, note: null };

/**
 * Admin › Banco de contenido (celular primero): se elige el comercio UNA vez y se
 * suben todas las fotos que se quieran (§9.2). Es el camino principal para que
 * una foto quede ligada al comercio en el momento en que se saca.
 */
export function ContentBankPanel() {
  const [comercio, setComercio] = useState<ContentMerchantResponse | null>(null);
  return (
    <div style={{ display: "grid", gap: 14, maxWidth: 760 }}>
      {!comercio ? (
        <div className="panel-card glass" style={{ padding: 16 }}>
          <h3 style={{ margin: "0 0 4px", fontSize: 17 }}>Banco de contenido</h3>
          <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
            Elegí el comercio y sacá o subí todas las fotos que quieras. Con esas fotos se arman los videos para las redes de URUKU.
          </p>
          <ContentMerchantPicker onElegir={setComercio} />
        </div>
      ) : (
        <>
          <div>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setComercio(null)}>
              <Ic n="volver" s={15} /> Elegir otro comercio
            </button>
          </div>
          <div className="panel-card glass" style={{ padding: 16 }}>
            <BancoDelComercio
              comercioId={comercio.id} api={apiBancoAdmin}
              titulo={comercio.nombre}
              detalle={[comercio.rubro, comercio.calle, comercio.ciudad_nombre].filter(Boolean).join(" · ")}
              suscriptor={comercio.is_subscriber}
              consentInicial={comercio.social_consent}
              fotosEnFicha={comercio.gallery_photos} />
          </div>
        </>
      )}
    </div>
  );
}

/**
 * Todo el banco de UN comercio: autorización, subida y grilla. Lo usan el panel
 * del admin y «Completar comercio» de la app de campo (el agente), cada uno con
 * su `api` (otro token, otros endpoints).
 */
export function BancoDelComercio({ comercioId, api, titulo, detalle, suscriptor, consentInicial, fotosEnFicha, sinTitulo }: {
  comercioId: string;
  api: ContentBankApi;
  titulo?: string;
  detalle?: string;
  suscriptor?: boolean;
  /** La autorización conocida. Sin ella (app de campo) se dice «sin dato». */
  consentInicial?: SocialConsentResponse;
  /** Cuántas fotos tiene en su ficha: cuentan para los videos aunque no estén en el banco. */
  fotosEnFicha?: number;
  /** Sin el encabezado con el nombre (cuando ya está dicho arriba). */
  sinTitulo?: boolean;
}) {
  const [consent, setConsent] = useState<SocialConsentResponse>(consentInicial ?? SIN_AUTORIZACION);
  const [lista, setLista] = useState<ContentAssetListResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [abierta, setAbierta] = useState<string | null>(null);   // foto con el menú abierto
  const vivo = useRef(true);
  useEffect(() => { vivo.current = true; return () => { vivo.current = false; }; }, []);
  const ultimaRecarga = useRef(0);

  const cargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    setErr("");
    try {
      const r = await api.listar(comercioId);
      if (vivo.current) setLista(r);
    } catch (ex) {
      if (vivo.current) setErr(mensajeContent(ex, "No se pudieron cargar las fotos"));
    } finally {
      if (vivo.current) setCargando(false);
    }
  }, [api, comercioId]);

  useEffect(() => { setLista(null); setAbierta(null); void cargar(); }, [comercioId]);   // eslint-disable-line react-hooks/exhaustive-deps

  /** Las URLs firmadas vencen a los 15 min: si una miniatura no carga, se pide la
   *  lista de nuevo (con firmas nuevas), a lo sumo una vez cada 20 s. */
  const miniaturaRota = useCallback(() => {
    if (Date.now() - ultimaRecarga.current < 20000) return;
    ultimaRecarga.current = Date.now();
    void cargar(true);
  }, [cargar]);

  function alSubir(r: ContentAssetUploadResponse) {
    // La foto nueva aparece ya (sin esperar la recarga); la lista real llega después.
    setLista((l) => (l && !l.items.some((a) => a.id === r.asset.id)
      ? { ...l, items: [r.asset, ...l.items], usable_for_video: l.usable_for_video + (r.asset.usable_for_social && !r.asset.too_small ? 1 : 0) }
      : l));
    void cargar(true);
  }

  const items = lista?.items ?? [];
  const sirven = lista?.usable_for_video ?? 0;
  const minimo = lista?.min_for_video ?? 4;
  const hayFicha = typeof fotosEnFicha === "number" ? fotosEnFicha : null;
  // La app de campo no puede leer la autorización: sin dato no se afirma que falte.
  const sinDato = !consentInicial && consent.granted === null;

  return (
    <div style={{ display: "grid", gap: 14 }}>
      {!sinTitulo && titulo && (
        <div style={{ display: "grid", gap: 4 }}>
          <h3 style={{ margin: 0, fontSize: 17 }}>{titulo}</h3>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 13, color: "var(--txt-3)" }}>
            {detalle && <span>{detalle}</span>}
            {suscriptor && <Insignia tono="ok" icono="estrella">Suscriptor</Insignia>}
          </div>
        </div>
      )}

      <SocialConsentBox consent={consent} api={api.consent(comercioId)} onChange={setConsent} estadoDesconocido={sinDato} />

      {consent.granted !== true && !sinDato && (
        <Aviso tono="aviso">Se guardan igual, pero las fotos no salen en redes hasta registrar la autorización.</Aviso>
      )}

      <ContentBankUploader comercioId={comercioId} api={api} onSubida={alSubir} />

      <div>
        <div style={{ display: "flex", gap: 10, alignItems: "baseline", flexWrap: "wrap", marginBottom: 8 }}>
          <b style={{ fontSize: 14 }}>Fotos para redes: {items.length}</b>
          <span style={{ fontSize: 13, color: "var(--txt-3)" }}>· sirven para video: {sirven}</span>
        </div>
        {lista && sirven < minimo && (
          <Aviso tono="aviso">Para armar un video hacen falta al menos {minimo} fotos que sirvan. Faltan {minimo - sirven}.</Aviso>
        )}

        {cargando && !lista && <Cargando texto="Cargando las fotos…" />}
        {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar()} />}

        {!cargando && !err && items.length === 0 && (
          <p style={{ margin: "8px 0 0", fontSize: 14, color: "var(--txt-3)", lineHeight: 1.45 }}>
            Todavía no hay fotos para redes de este comercio.
            {hayFicha !== null ? ` Las de la ficha ya cuentan: ${hayFicha}.` : ""}
          </p>
        )}

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(92px, 1fr))", gap: 8, marginTop: 10 }}>
          {items.map((a) => (
            <Miniatura key={a.id} a={a} abierta={abierta === a.id}
                       onAbrir={() => setAbierta((x) => (x === a.id ? null : a.id))}
                       onRota={miniaturaRota} />
          ))}
        </div>

        {abierta && (() => {
          const a = items.find((x) => x.id === abierta);
          return a ? (
            <MenuFoto key={a.id} a={a} api={api}
                      onCambio={(nueva) => { setLista((l) => (l ? { ...l, items: l.items.map((x) => (x.id === nueva.id ? nueva : x)) } : l)); void cargar(true); }}
                      onBaja={() => { setLista((l) => (l ? { ...l, items: l.items.filter((x) => x.id !== a.id) } : l)); setAbierta(null); void cargar(true); }}
                      onCerrar={() => setAbierta(null)} />
          ) : null;
        })()}
      </div>
    </div>
  );
}

function Miniatura({ a, abierta, onAbrir, onRota }: { a: ContentAssetResponse; abierta: boolean; onAbrir: () => void; onRota: () => void }) {
  const marcas: string[] = [];
  if (a.too_small) marcas.push("Chica");
  if (!a.usable_for_social) marcas.push("No sale en redes");
  if (a.has_people) marcas.push("Personas");
  return (
    <button type="button" onClick={onAbrir} aria-pressed={abierta} aria-label={`Foto del ${a.created_at.slice(0, 10)}${marcas.length ? ": " + marcas.join(", ") : ""}. Tocá para ver las opciones.`}
            style={{ position: "relative", padding: 0, aspectRatio: "1 / 1", borderRadius: 10, overflow: "hidden", cursor: "pointer",
                     border: `2px solid ${abierta ? "var(--neon)" : "var(--stroke)"}`, background: "var(--panel)", opacity: a.usable_for_social ? 1 : 0.55 }}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={urlApi(a.thumb_url)} alt="" loading="lazy" onError={onRota} style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
      {marcas.length > 0 && (
        <span style={{ position: "absolute", left: 0, right: 0, bottom: 0, fontSize: 10.5, fontWeight: 700, padding: "2px 4px", background: "rgba(0,0,0,.72)", color: "#fff", textAlign: "left", lineHeight: 1.25 }}>
          {marcas.join(" · ")}
        </span>
      )}
    </button>
  );
}

/** Las acciones sobre una foto (sólo el panel las tiene; el agente ve la grilla y nada más). */
function MenuFoto({ a, api, onCambio, onBaja, onCerrar }: {
  a: ContentAssetResponse; api: ContentBankApi;
  onCambio: (a: ContentAssetResponse) => void; onBaja: () => void; onCerrar: () => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");

  async function cambiar(patch: Parameters<NonNullable<ContentBankApi["actualizar"]>>[1]) {
    if (!api.actualizar) return;
    setOcupado(true); setErr("");
    try { onCambio(await api.actualizar(a.id, patch)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo cambiar la foto")); }
    finally { setOcupado(false); }
  }

  function personas() {
    if (a.has_people) { void cambiar({ has_people: false, people_ok: null }); return; }
    const ok = window.confirm("¿Las personas que se reconocen en la foto aceptaron aparecer?\n\nAceptar = sí aceptaron.\nCancelar = no aceptaron (la foto no se usa en videos).");
    void cambiar({ has_people: true, people_ok: ok });
  }

  async function baja() {
    if (!api.baja) return;
    if (!window.confirm("¿Dar de baja esta foto? Deja de usarse en redes (se borra del disco a los 30 días).")) return;
    setOcupado(true); setErr("");
    try { await api.baja(a.id); onBaja(); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo dar de baja la foto")); setOcupado(false); }
  }

  return (
    <div className="glass" style={{ marginTop: 10, padding: 12, borderRadius: 12, border: "1px solid var(--stroke)", display: "grid", gap: 10 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", fontSize: 13 }}>
        <span>{a.width}×{a.height} px</span>
        <span>· usada {a.use_count} {a.use_count === 1 ? "vez" : "veces"}</span>
        {a.too_small && <Insignia tono="aviso" icono="aviso">Chica: no entra en videos</Insignia>}
        {!a.usable_for_social && <Insignia tono="aviso" icono="cerrar">No sale en redes</Insignia>}
        {a.has_people && <Insignia tono={a.people_ok ? "ok" : "aviso"} icono="usuario">{a.people_ok ? "Personas (aceptaron)" : "Personas (sin confirmar)"}</Insignia>}
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <a className="btn btn-ghost btn-sm" style={BTN_GRANDE} href={urlApi(a.file_url)} target="_blank" rel="noopener noreferrer">
          <Ic n="abrir" s={15} /> Ver la foto
        </a>
        {api.actualizar && (
          <>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado}
                    onClick={() => void cambiar({ usable_for_social: !a.usable_for_social })}>
              {a.usable_for_social ? <><Ic n="cerrar" s={15} /> No usar en redes</> : <><Ic n="si" s={15} /> Volver a usar en redes</>}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado} onClick={personas}>
              <Ic n="usuario" s={15} /> {a.has_people ? "Ya no hay personas" : "Hay personas"}
            </button>
          </>
        )}
        {api.baja && (
          <button type="button" className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, color: "var(--pink)" }} disabled={ocupado} onClick={() => void baja()}>
            <Ic n="cerrar" s={15} /> Dar de baja
          </button>
        )}
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onCerrar}>Cerrar</button>
      </div>
      {err && <Aviso tono="error">{err}</Aviso>}
    </div>
  );
}
