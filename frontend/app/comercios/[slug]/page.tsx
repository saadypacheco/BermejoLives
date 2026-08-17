import Link from "next/link";
import { UrukuShell } from "@/components/uruku-shell";
import { MensajeComercioForm } from "@/components/mensaje-comercio-form";
import { WaLeadLink } from "@/components/wa-lead-link";
import { GuardarBoton } from "@/components/guardar-boton";
import { HorarioBadge } from "@/components/horario-badge";
import { CompartirBoton } from "@/components/compartir-boton";
import { getComercioBySlug, getProductos, getGaleriaComercio } from "@/lib/data";
import { GaleriaFicha } from "@/components/galeria-ficha";
import { VistaLogger } from "@/components/vista-logger";
import { precioFmt, MODALIDAD_LABEL } from "@/lib/types";
import {
  WhatsApp, Verified, Pin, Phone, Globe, Instagram, Facebook, TikTok, Arrow,
} from "@/components/icons";

export const dynamic = "force-dynamic"; // el header (ciudad por cookie) es dinámico

export default async function ComercioPage({ params }: { params: { slug: string } }) {
  const comercio = await getComercioBySlug(params.slug);
  if (!comercio) {
    return (
      <UrukuShell showCatnav={false}>
        <div className="uk-container" style={{ padding: "80px 0" }}>Comercio no encontrado.</div>
      </UrukuShell>
    );
  }
  const [productos, galeria] = await Promise.all([getProductos(comercio.id), getGaleriaComercio(comercio.id)]);

  const redes = [
    comercio.tiktok_url && { label: "TikTok", href: comercio.tiktok_url, Icon: TikTok },
    comercio.instagram_url && { label: "Instagram", href: comercio.instagram_url, Icon: Instagram },
    comercio.facebook_url && { label: "Facebook", href: comercio.facebook_url, Icon: Facebook },
    comercio.sitio_web && { label: "Sitio web", href: comercio.sitio_web, Icon: Globe },
  ].filter(Boolean) as { label: string; href: string; Icon: typeof TikTok }[];

  const mapsHref =
    comercio.como_llegar ??
    (comercio.lat && comercio.lng
      ? `https://www.google.com/maps/search/?api=1&query=${comercio.lat},${comercio.lng}`
      : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(comercio.direccion ?? "Bermejo")}`);

  return (
    <UrukuShell showCatnav={false}>
      <VistaLogger comercioId={comercio.id} />

      <div className="uk-cover">
        {comercio.portada_url && <img src={comercio.portada_url} alt="Portada" />}
      </div>

      <div className="uk-container uk-profile">
        <Link className="uk-back" href="/"><Arrow style={{ transform: "rotate(180deg)" }} /> Volver</Link>

        <div className="uk-profile-head">
          {comercio.logo_url && <img className="uk-profile-logo" src={comercio.logo_url} alt="Logo" />}
          <div className="uk-profile-info">
            <h1>
              {comercio.nombre}
              {comercio.verificado && <span className="uk-verif" title="Negocio verificado"><Verified style={{ width: 20, height: 20 }} /></span>}
            </h1>
            <div className="uk-meta">
              {comercio.rubro_nombre && <span className="uk-pill green">{comercio.rubro_nombre}</span>}
              {comercio.direccion && <span><Pin style={{ width: 14, height: 14 }} />{comercio.direccion}</span>}
              <span style={{ color: "var(--uk-orange)" }}>★ {comercio.rating}</span>
              {comercio.modalidad && <span className="uk-pill blue">{MODALIDAD_LABEL[comercio.modalidad] ?? comercio.modalidad}</span>}
              <HorarioBadge horario={comercio.horario} />
            </div>
          </div>
          <div className="uk-cta">
            {comercio.whatsapp ? (
              <WaLeadLink className="uk-btn-wa" comercioId={comercio.id} whatsapp={comercio.whatsapp} mensaje={`Hola ${comercio.nombre}, te contacto desde URUKU`}>
                <WhatsApp style={{ width: 18, height: 18 }} /> WhatsApp
              </WaLeadLink>
            ) : comercio.telefono ? (
              <a className="uk-btn-wa" href={`tel:${comercio.telefono.replace(/[^\d+]/g, "")}`}>
                <Phone style={{ width: 18, height: 18 }} /> Llamar
              </a>
            ) : null}
            <a className="uk-btn-ghost" href={mapsHref} target="_blank" rel="noopener"><Pin style={{ width: 16, height: 16 }} /> Cómo llegar</a>
            <GuardarBoton comercioId={comercio.id} className="uk-btn-ghost" />
            <CompartirBoton titulo={comercio.nombre} texto={`${comercio.nombre} en URUKU`} className="uk-btn-ghost" />
          </div>
        </div>

        {comercio.descripcion && <p className="uk-desc">{comercio.descripcion}</p>}

        <GaleriaFicha fotos={galeria.fotos} videos={galeria.videos} />

        <div className="uk-info-grid">
          <div className="uk-info-card">
            <h3>Datos de contacto</h3>
            {comercio.whatsapp && (
              <div className="uk-info-row">
                <span className="ic"><WhatsApp style={{ width: 17, height: 17 }} /></span>
                <div><b>WhatsApp</b>+{comercio.whatsapp}</div>
              </div>
            )}
            {comercio.telefono && (
              <div className="uk-info-row"><span className="ic"><Phone style={{ width: 17, height: 17 }} /></span><div><b>Teléfono</b><a href={`tel:${comercio.telefono.replace(/[^\d+]/g, "")}`}>{comercio.telefono}</a></div></div>
            )}
            {comercio.direccion && (
              <div className="uk-info-row"><span className="ic"><Pin style={{ width: 17, height: 17 }} /></span><div><b>Dirección</b>{comercio.direccion}</div></div>
            )}
            {comercio.horario && (
              <div className="uk-info-row">
                <span className="ic" aria-hidden>🕐</span>
                <div><b>Horario</b>{comercio.horario} <HorarioBadge horario={comercio.horario} /></div>
              </div>
            )}
          </div>

          {redes.length > 0 && (
            <div className="uk-info-card">
              <h3>Redes y web</h3>
              {redes.map((r) => (
                <a className="uk-info-row" key={r.label} href={r.href} target="_blank" rel="noopener" style={{ color: "inherit" }}>
                  <span className="ic"><r.Icon style={{ width: 17, height: 17 }} /></span>
                  <div><b>{r.label}</b>{r.href.replace(/^https?:\/\//, "")}</div>
                </a>
              ))}
            </div>
          )}

          <MensajeComercioForm comercioId={comercio.id} nombre={comercio.nombre} />

          <div className="uk-info-card" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <h3>Comentarios y sugerencias</h3>
            <p style={{ color: "var(--uk-ink-soft)", fontSize: 13 }}>¿Tuviste un inconveniente o querés dejar algún comentario sobre este negocio? Contanos.</p>
            <Link className="uk-btn-ghost" style={{ maxWidth: 220 }} href={`/reclamos?comercio_id=${comercio.id}&nombre_comercio=${encodeURIComponent(comercio.nombre)}`}>Dejar un comentario</Link>
          </div>
        </div>

        {comercio.acepta_reservas !== false && productos.length > 0 && (
          <>
            <div className="uk-section-head" style={{ marginTop: 40 }}>
              <h2>Productos</h2>
            </div>
            <div className="uk-product-grid">
              {productos.map((p) => (
                <article className="uk-product" key={p.id}>
                  <a href={p.url ?? undefined} target="_blank" rel="noopener" style={{ color: "inherit" }}>
                    <h4>{p.nombre}</h4>
                  </a>
                  {p.precio != null && <div className="price">{precioFmt(p.precio, p.moneda)}</div>}
                  <div className="foot">
                    <span>{comercio.nombre}</span>
                    {comercio.whatsapp && (
                      <WaLeadLink className="wa-mini" comercioId={comercio.id} whatsapp={comercio.whatsapp} mensaje={`Hola, me interesa ${p.nombre}`}>
                        <WhatsApp style={{ width: 17, height: 17, color: "#fff" }} />
                      </WaLeadLink>
                    )}
                  </div>
                </article>
              ))}
            </div>
          </>
        )}

        <Link className="uk-back" href="/" style={{ marginTop: 24 }}><Arrow style={{ transform: "rotate(180deg)" }} /> Volver al inicio</Link>
      </div>
    </UrukuShell>
  );
}
