"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import "@/app/uruku.css";
import { Nav } from "@/components/nav";
import { BottomNav } from "@/components/bottom-nav";
import { ThemeToggle, ThemeNoFlash } from "@/components/uruku-theme";
import { alCambiar, leerReservas, porComercio, quitarReserva, vaciarComercio, type GrupoReserva } from "@/lib/reservas";
import { precioFmt, waLink } from "@/lib/types";
import { registrarLead } from "@/lib/campo";

export default function ReservasPage() {
  const [grupos, setGrupos] = useState<GrupoReserva[]>([]);
  const [listo, setListo] = useState(false);
  const [enviados, setEnviados] = useState<string[]>([]);

  useEffect(() => {
    const leer = () => { setGrupos(porComercio(leerReservas())); setListo(true); };
    leer();
    return alCambiar(leer);
  }, []);

  /** Arma el mensaje y abre el WhatsApp DEL COMERCIO.
   *
   * El lead se registra antes de salir; es fire-and-forget, así que si el
   * registro se cae la persona igual manda su reserva. Perder una métrica no
   * puede costar una venta. */
  function enviar(g: GrupoReserva) {
    const lineas = g.items.map((i) =>
      `• ${i.titulo ?? "Oferta"}${i.precio != null ? ` — ${precioFmt(i.precio, i.moneda)}` : ""}`);
    const texto = [
      `Hola ${g.comercio_nombre}, quiero reservar (los vi en URUKU):`,
      "",
      ...lineas,
      "",
      "¿Me confirmás si los tenés disponibles?",
    ].join("\n");
    registrarLead(g.comercio_id, "reserva");
    setEnviados((prev) => [...prev, g.comercio_id]);
    window.open(waLink(g.comercio_whatsapp, texto), "_blank", "noopener");
  }

  return (
    <div id="ukroot" className="uk uk-app">
      <ThemeNoFlash />
      <div className="uk-app-toggle"><ThemeToggle /></div>
      <Nav mapOnly />
      <div className="wrap" style={{ maxWidth: 640, paddingTop: 32, paddingBottom: 110 }}>
        <h1 style={{ fontSize: 22, margin: "0 0 4px" }}>Tu reserva</h1>
        <p style={{ color: "var(--uk-ink-soft)", fontSize: 13, marginTop: 0 }}>
          Se guarda en este celular, sin cuenta. Una reserva por comercio: el mensaje va al WhatsApp de cada local.
        </p>

        {listo && grupos.length === 0 && (
          <div className="uk-info-card" style={{ textAlign: "center", padding: 32 }}>
            <p style={{ margin: "0 0 14px" }}>Todavía no elegiste nada.</p>
            <Link className="uk-btn-ghost" style={{ maxWidth: 220, margin: "0 auto" }} href="/buscar">Buscar productos</Link>
          </div>
        )}

        {grupos.map((g) => {
          const conPrecio = g.items.filter((i) => i.precio != null);
          const aConsultar = g.items.length - conPrecio.length;
          // Sólo se suma dentro de la misma moneda: mezclar Bs con USD daría un
          // número que no significa nada, y acá conviven las tres.
          const monedas = new Set(conPrecio.map((i) => i.moneda));
          const total = monedas.size === 1
            ? conPrecio.reduce((n, i) => n + (i.precio ?? 0), 0)
            : null;

          return (
            <div key={g.comercio_id} className="uk-info-card" style={{ marginTop: 16, padding: 16 }}>
              <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
                <Link href={`/comercios/${g.comercio_slug}`} style={{ fontWeight: 700, fontSize: 16 }}>
                  {g.comercio_nombre}
                </Link>
                <button type="button" className="uk-linkbtn" onClick={() => vaciarComercio(g.comercio_id)}>
                  Vaciar
                </button>
              </div>

              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
                {g.items.map((i) => (
                  <div key={i.id} style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    {i.imagen_url
                      ? <img src={i.imagen_url} alt="" style={{ width: 52, height: 52, objectFit: "cover", borderRadius: 8, flexShrink: 0 }} />
                      : <span style={{ width: 52, height: 52, borderRadius: 8, background: "var(--uk-line)", flexShrink: 0 }} />}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{i.titulo ?? "Oferta"}</div>
                      <div style={{ fontSize: 13, color: i.precio != null ? "var(--uk-neon, #39ff9e)" : "var(--uk-ink-soft)", fontWeight: i.precio != null ? 800 : 400 }}>
                        {i.precio != null ? precioFmt(i.precio, i.moneda) : "Precio a consultar"}
                      </div>
                    </div>
                    <button type="button" className="uk-linkbtn" onClick={() => quitarReserva(i.id)} aria-label="Quitar">✕</button>
                  </div>
                ))}
              </div>

              {total != null && (
                <div style={{ marginTop: 12, fontSize: 14 }}>
                  Subtotal <b>{precioFmt(total, conPrecio[0].moneda)}</b>
                  {aConsultar > 0 && <span style={{ color: "var(--uk-ink-soft)" }}> · {aConsultar} a consultar</span>}
                </div>
              )}

              <button type="button" className="uk-btn-wa" style={{ marginTop: 12, width: "100%" }} onClick={() => enviar(g)}>
                {enviados.includes(g.comercio_id) ? "Volver a enviar por WhatsApp" : "Enviar reserva por WhatsApp"}
              </button>

              {/* Nada queda apartado hasta que el vendedor conteste, y la
                  pantalla no puede insinuar lo contrario. Si alguien camina
                  veinte cuadras creyendo que tiene algo guardado y no está, se
                  pierden el comprador y el comercio de una sola vez. */}
              {enviados.includes(g.comercio_id) && (
                <p style={{ fontSize: 12.5, color: "var(--uk-ink-soft)", marginTop: 10, marginBottom: 0 }}>
                  Le mandaste el pedido a {g.comercio_nombre}. <b>Todavía no está reservado</b>: queda
                  apartado recién cuando el vendedor te conteste que sí.
                </p>
              )}
            </div>
          );
        })}

        {grupos.length > 0 && (
          <p style={{ fontSize: 12, color: "var(--uk-ink-soft)", marginTop: 18 }}>
            URUKU te conecta con el comercio: el precio, la entrega y el pago los acordás
            directamente con el vendedor. La plataforma no participa de la operación.
          </p>
        )}
      </div>
      <BottomNav active="Guardados" />
    </div>
  );
}
