"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { supabase, hasSupabase } from "@/lib/supabase";
import { type FeedItem, precioFmt, waLink } from "@/lib/types";
import { WhatsApp, Verified, Pin, Play } from "@/components/icons";

/**
 * Feed en vivo. Render inicial server-side (props), y se suscribe a Supabase
 * Realtime DIRECTO (lesson KB): cuando una publicación pasa a 'aprobado',
 * aparece arriba sin recargar. RLS asegura que solo lleguen filas aprobadas.
 */
export function LiveFeed({ initial }: { initial: FeedItem[] }) {
  const [items, setItems] = useState<FeedItem[]>(initial);

  useEffect(() => {
    if (!hasSupabase) return;
    const channel = supabase
      .channel("feed-publicaciones")
      .on(
        // INSERT (confiables que publican directo) + UPDATE (aprobadas en moderación)
        "postgres_changes",
        { event: "*", schema: "public", table: "publicaciones", filter: "estado=eq.aprobado" },
        async (payload) => {
          const row = payload.new as { id: string };
          if (!row?.id) return;
          // Traemos la fila enriquecida desde la vista feed_publico
          const { data } = await supabase.from("feed_publico").select("*").eq("id", row.id).limit(1);
          if (data && data[0]) {
            setItems((prev) => [data[0] as FeedItem, ...prev.filter((p) => p.id !== row.id)]);
          }
        }
      )
      .subscribe();
    return () => {
      supabase.removeChannel(channel);
    };
  }, []);

  return (
    <div className="feed">
      {items.map((p) => (
        <article className="post" key={p.id}>
          <div className="phead">
            <img src={p.comercio_logo ?? ""} alt="" />
            <div style={{ flex: 1 }}>
              <b>
                {p.comercio_nombre}{" "}
                {p.comercio_verificado && (
                  <span className="pverif"><Verified style={{ width: 14, height: 14 }} /></span>
                )}
              </b>
              <small>{p.zona_nombre ?? "Bermejo"}</small>
            </div>
            <span className="pill" style={{ textTransform: "capitalize" }}>{p.tipo}</span>
          </div>
          {p.imagen_url && (
            <div className="pmedia" style={{ position: "relative" }}>
              <img src={p.imagen_url} alt={p.titulo ?? ""} />
              {p.tiktok_url && (
                <span className="vid-play-overlay"><Play style={{ width: 18, height: 18, color: "#fff" }} /></span>
              )}
            </div>
          )}
          <div className="pbody">
            {p.descripcion && <p>{p.descripcion}</p>}
            <div className="pmeta">
              {p.precio != null && <span className="pprice">{precioFmt(p.precio, p.moneda)}</span>}
              <span><Pin style={{ width: 14, height: 14 }} />{p.zona_nombre ?? "Bermejo"}</span>
            </div>
            <div className="pactions">
              <a
                className="btn btn-wa btn-sm"
                href={waLink(p.comercio_whatsapp, `Hola, vi "${p.titulo ?? "tu publicación"}" en Encontralo`)}
                target="_blank"
                rel="noopener"
              >
                <WhatsApp style={{ width: 16, height: 16 }} /> WhatsApp
              </a>
              <Link className="btn btn-ghost btn-sm" href={`/comercios/${p.comercio_slug}`}>Ver comercio</Link>
              {p.tiktok_url && (
                <a className="btn btn-ghost btn-sm" href={p.tiktok_url} target="_blank" rel="noopener">Ver en TikTok</a>
              )}
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}
