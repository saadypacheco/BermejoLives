"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { hasSupabase } from "@/lib/supabase";
import { getFeed } from "@/lib/data";
import { type FeedItem, precioFmt, waLink } from "@/lib/types";
import { WhatsApp, Verified, Pin, Play } from "@/components/icons";
import { registrarLead } from "@/lib/campo";

const POLL_MS = 25_000;

/**
 * Feed en vivo. Render inicial server-side (props), y refresca por polling
 * cada 25s (antes usaba Supabase Realtime/WebSocket — con self-host y
 * usuarios con señal inestable, polling es más robusto: si se corta un
 * request se reintenta solo en el próximo ciclo, sin quedar "colgado" como
 * puede pasar con una conexión WebSocket en un celular con mala señal).
 */
export function LiveFeed({ initial }: { initial: FeedItem[] }) {
  const [items, setItems] = useState<FeedItem[]>(initial);
  const idsConocidos = useRef(new Set(initial.map((i) => i.id)));

  useEffect(() => {
    if (!hasSupabase) return;
    const intervalo = setInterval(async () => {
      const frescos = await getFeed(20);
      const nuevos = frescos.filter((f) => !idsConocidos.current.has(f.id));
      if (nuevos.length === 0) return;
      nuevos.forEach((n) => idsConocidos.current.add(n.id));
      setItems((prev) => [...nuevos, ...prev]);
    }, POLL_MS);
    return () => clearInterval(intervalo);
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
                onClick={() => registrarLead(p.comercio_id)}
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
