"use client";

/**
 * La ficha de un local para el agente (spec docs/que-hay-aca.md): lo que ve al
 * tocar un comercio en «Qué hay acá».
 *
 * Es una pantalla, no una ventana: el agente está de pie, con una mano, y lo
 * que importa va en orden de la charla con el dueño — quién es, qué le falta,
 * en qué plan está y cómo ofrecerle URUKU. Los precios NO aparecen.
 *
 * «Le falta» usa la misma cuenta que «Completar comercio» (lib/faltas.ts) y
 * «Completar» abre esa pantalla; lo que se guarda vuelve por `onGuardado` y la
 * ficha se actualiza sola.
 */
import { useEffect, useState } from "react";
import {
  listarFotosCampo, type ComercioAgente, type FotoGaleria, type Lugar,
} from "@/lib/campo";
import type { Rubro } from "@/lib/types";
import { calcularFaltas } from "@/lib/faltas";
import { CompletarComercio } from "@/components/completar-comercio";
import { OfrecerComercio } from "@/components/ofrecer-comercio";
import { PLAN_CFG, SelloPlan } from "@/components/sello-plan";
import { Ic, type NombreIcono } from "@/components/ic";

const titulo: React.CSSProperties = { display: "flex", alignItems: "center", gap: 6, fontSize: 14, fontWeight: 700, margin: "0 0 10px" };
const caja: React.CSSProperties = { padding: 12, borderRadius: 12, background: "var(--panel)", border: "1px solid var(--stroke)" };

function Fila({ icono, children }: { icono: NombreIcono; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13.5, lineHeight: 1.4 }}>
      <span style={{ flexShrink: 0, marginTop: 1, color: "var(--txt-3)" }}><Ic n={icono} s={15} /></span>
      <span style={{ minWidth: 0, overflowWrap: "anywhere" }}>{children}</span>
    </div>
  );
}

/** «Lo que suma» tal como se lo describe el agente. Sólo lo tildado. */
function loQueSuma(c: ComercioAgente): { icono: NombreIcono; texto: string }[] {
  const r: { icono: NombreIcono; texto: string }[] = [];
  if (c.tiene_pasero) r.push({ icono: "pasero", texto: "Tiene pasero" });
  if (c.envios_internacionales) r.push({ icono: "envios", texto: "Hace envíos" });
  if (c.tiene_factura) r.push({ icono: "factura", texto: "Da factura" });
  if (c.talles_especiales) r.push({ icono: "ropa", texto: "Trabaja talles especiales" });
  if ((c.pedido_minimo ?? "").trim()) r.push({ icono: "comprar", texto: `Pedido mínimo: ${(c.pedido_minimo ?? "").trim()}` });
  if ((c.catalogo_url ?? "").trim()) r.push({ icono: "catalogo", texto: "Tiene catálogo" });
  return r;
}

export function FichaAgente({ c, distancia, rubros, lugares, onVolver, onGuardado }: {
  c: ComercioAgente;
  /** Metros desde donde está parado el agente; null si no hay GPS. */
  distancia: number | null;
  rubros: Rubro[];
  lugares: Lugar[];
  onVolver: () => void;
  onGuardado: (patch: Partial<ComercioAgente>) => void;
}) {
  const [completando, setCompletando] = useState(false);
  const [fotos, setFotos] = useState<FotoGaleria[] | null>(null);
  const [fotosErr, setFotosErr] = useState(false);

  useEffect(() => { window.scrollTo(0, 0); }, [completando]);
  useEffect(() => {
    let vivo = true;
    setFotos(null); setFotosErr(false);
    listarFotosCampo(c.id)
      .then((l) => { if (vivo) setFotos(l.items ?? []); })
      .catch(() => { if (vivo) setFotosErr(true); });
    return () => { vivo = false; };
  }, [c.id, c.portada_url]);

  if (completando) {
    return (
      <CompletarComercio
        key={c.id} comercio={c} rubros={rubros} lugares={lugares} abrirEn="arriba"
        onVolver={() => setCompletando(false)} onGuardado={onGuardado}
      />
    );
  }

  // De la galería real si respondió; si no, del conteo que trae la lista.
  const nFotos = fotos ? fotos.length : (c.fotos_count ?? null);
  const faltas = calcularFaltas(c, nFotos);
  const suma = loQueSuma(c);
  const portada = c.portada_url || c.portada_thumb_url;
  const subtitulo = [c.rubros?.nombre ?? "Sin rubro",
    c.lugares?.nombre ? `${c.lugares.nombre}${c.puesto ? ` #${c.puesto}` : ""}` : (c.calle ?? "")].filter(Boolean).join(" · ");
  const todasLasRedes: { icono: NombreIcono; label: string; url: string }[] = [
    { icono: "instagram", label: "Instagram", url: c.instagram_url ?? "" },
    { icono: "facebook", label: "Facebook", url: c.facebook_url ?? "" },
    { icono: "tiktok", label: "TikTok", url: c.tiktok_url ?? "" },
    { icono: "web", label: "Sitio web", url: c.sitio_web ?? "" },
    { icono: "whatsapp", label: "Canal de WhatsApp", url: c.canal_wa_url ?? "" },
  ];
  const redes = todasLasRedes.filter((r) => /^https?:\/\//i.test(r.url.trim()));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, textAlign: "left" }}>
      <button type="button" className="link-more" style={{ alignSelf: "flex-start", minHeight: 44, display: "inline-flex", alignItems: "center", gap: 6 }} onClick={onVolver}>
        <Ic n="volver" s={15} /> Volver a «Qué hay acá»
      </button>

      {/* Fotos: la portada entera (sin recortar flyers) y la galería al costado. */}
      <div>
        <div style={{ background: "#0b1411", borderRadius: 14, overflow: "hidden", display: "grid", placeItems: "center", minHeight: 150, maxHeight: 280, color: "var(--txt-3)" }}>
          {portada
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={portada} alt="" onError={(e) => { e.currentTarget.style.display = "none"; }} style={{ width: "100%", maxHeight: 280, objectFit: "contain", display: "block" }} />
            : <div style={{ textAlign: "center", padding: 16, fontSize: 13 }}><Ic n="foto" s={28} /><div>Sin foto de la vidriera</div></div>}
        </div>
        {fotos && fotos.length > 0 && (
          <div style={{ display: "flex", gap: 8, overflowX: "auto", marginTop: 8, paddingBottom: 4 }} aria-label="Galería de fotos">
            {fotos.map((f, i) => (
              <a key={f.id} href={f.url} target="_blank" rel="noopener noreferrer" aria-label={`Abrir la foto ${i + 1} en grande`}
                 style={{ flex: "0 0 72px", height: 72, borderRadius: 10, overflow: "hidden", background: "#0b1411", border: "1px solid var(--stroke)" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={f.thumb_url || f.url} alt="" loading="lazy" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }} />
              </a>
            ))}
          </div>
        )}
        {fotos && fotos.length === 0 && <p style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "6px 0 0" }}>Todavía no tiene fotos en la galería.</p>}
        {!fotos && !fotosErr && <p style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "6px 0 0" }}><Ic n="reloj" s={12} /> Mirando la galería…</p>}
        {fotosErr && <p style={{ fontSize: 12.5, color: "var(--amber)", margin: "6px 0 0" }}><Ic n="aviso" s={12} /> No se pudo traer la galería (¿señal?).</p>}
      </div>

      {/* Quién es */}
      <div>
        <h1 style={{ fontSize: 20, margin: "0 0 2px", overflowWrap: "anywhere" }}>{c.nombre || "Sin nombre"}</h1>
        <div style={{ fontSize: 13, color: "var(--txt-3)" }}>{subtitulo}</div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginTop: 6 }}>
          <SelloPlan plan={c.estado_plan} />
          <span style={{ fontSize: 11.5, fontWeight: 700, color: c.verificado ? "var(--neon)" : "var(--amber)" }}>
            <Ic n={c.verificado ? "verificado" : "reloj"} s={12} peso="fill" /> {c.verificado ? "Verificado" : "Pendiente de verificar"}
          </span>
          {distancia != null && Number.isFinite(distancia) && (
            <span style={{ fontSize: 11.5, fontWeight: 700, color: "var(--neon)" }}><Ic n="ubicacion" s={12} /> a {Math.round(distancia)} m</span>
          )}
        </div>
      </div>

      {/* Datos */}
      <section style={caja} aria-label="Datos del local">
        <h2 style={titulo}><Ic n="dato" s={16} /> Datos</h2>
        <div style={{ display: "grid", gap: 8 }}>
          {(c.whatsapp ?? "").trim() && <Fila icono="whatsapp">+{(c.whatsapp ?? "").replace(/\D/g, "")}</Fila>}
          {(c.telefono ?? "").trim() && <Fila icono="telefono">{c.telefono}</Fila>}
          {(c.direccion ?? "").trim() && <Fila icono="ubicacion">{c.direccion}</Fila>}
          {!(c.direccion ?? "").trim() && (c.calle ?? "").trim() && <Fila icono="ubicacion">{c.calle}</Fila>}
          {(c.horario ?? "").trim() && <Fila icono="reloj">{c.horario}</Fila>}
          {(c.prod_obs_human ?? "").trim() && <Fila icono="comprar">{c.prod_obs_human}</Fila>}
          {redes.map((r) => (
            <Fila key={r.label} icono={r.icono}>
              <a href={r.url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--neon)" }}>{r.label}</a>
            </Fila>
          ))}
          {c.cargado_por && <Fila icono="usuario">Cargado por {c.cargado_por.split("@")[0]}</Fila>}
          {!(c.whatsapp ?? "").trim() && !(c.telefono ?? "").trim() && !(c.horario ?? "").trim() && !(c.prod_obs_human ?? "").trim() && (
            <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)" }}>Todavía no tiene datos cargados además del punto en el mapa.</p>
          )}
        </div>
      </section>

      {/* Lo que suma */}
      <section style={caja} aria-label="Lo que suma">
        <h2 style={titulo}><Ic n="destacado" s={16} /> Lo que suma</h2>
        {suma.length === 0
          ? <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)" }}>Todavía no se marcó nada (pasero, envíos, factura…). Se carga en «Completar».</p>
          : <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {suma.map((s) => (
                <span key={s.texto} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12.5, padding: "5px 11px", borderRadius: 999, border: "1px solid var(--neon)", color: "var(--neon)", background: "rgba(57,255,158,.08)" }}>
                  <Ic n={s.icono} s={14} /> {s.texto}
                </span>
              ))}
            </div>}
      </section>

      {/* Le falta */}
      <section role="region" aria-label="Lo que le falta al comercio"
               style={{ padding: 12, borderRadius: 12, border: `1px solid ${faltas.length ? "var(--amber)" : "var(--neon)"}`, background: faltas.length ? "rgba(255,176,32,.08)" : "rgba(57,255,158,.08)" }}>
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
              {faltas.map((f) => (
                <span key={f.clave} className="mchip" style={{ borderColor: "var(--amber)", color: "var(--amber)", padding: "6px 14px" }}>{f.label}</span>
              ))}
            </div>
          </>
        )}
        <button type="button" className={`btn ${faltas.length ? "btn-primary" : "btn-ghost"}`} style={{ width: "100%", minHeight: 48, marginTop: 10 }} onClick={() => setCompletando(true)}>
          <Ic n="editar" s={16} /> {faltas.length ? "Completar" : "Revisar o editar"}
        </button>
      </section>

      {/* Plan y estado, sin precios */}
      <section style={caja} aria-label="Plan y estado">
        <h2 style={titulo}><Ic n="estrella" s={16} /> Plan y estado</h2>
        {c.estado_plan && PLAN_CFG[c.estado_plan]
          ? <div style={{ display: "grid", gap: 6 }}>
              <div><SelloPlan plan={c.estado_plan} /></div>
              <p style={{ margin: 0, fontSize: 13, color: "var(--txt-2)" }}>{PLAN_CFG[c.estado_plan].detalle}</p>
            </div>
          : <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)" }}>El plan no está disponible todavía.</p>}
        <p style={{ margin: "8px 0 0", fontSize: 12.5, color: "var(--txt-3)" }}>
          {c.verificado ? "Ya fue verificado por URUKU." : "Todavía está pendiente de verificar."}
        </p>
      </section>

      <OfrecerComercio comercio={{ id: c.id, nombre: c.nombre, slug: c.slug, whatsapp: c.whatsapp, rubroSlug: c.rubro_slug ?? c.rubros?.slug ?? null }} />
      <div style={{ height: 30 }} />
    </div>
  );
}
