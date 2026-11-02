"use client";

import { useEffect, useState } from "react";
import { getVisitas, type ResumenVisitas } from "@/lib/api";

/** Una fuente de asistentes de IA tal como la suma el backend en `ai_sources`
 *  (docs/visibilidad-buscadores-ia.md §3.11). El campo puede faltar: el backend
 *  lo agrega en paralelo y un backend viejo no lo manda. */
type FuenteIa = { source: string; visits: number; people: number; business_views: number; top_routes?: string[] };
type ResumenConIa = ResumenVisitas & { ai_sources?: FuenteIa[] };

const NOMBRE_IA: Record<string, string> = {
  chatgpt: "ChatGPT", perplexity: "Perplexity", gemini: "Gemini", copilot: "Copilot", claude: "Claude",
  meta_ai: "Meta AI", deepseek: "DeepSeek", grok: "Grok", mistral: "Mistral",
};

/**
 * Cuánta gente entra a URUKU — y, sobre todo, cuántos terminan escribiéndole
 * a un comercio.
 *
 * El embudo es el punto de toda la pantalla. Un número de visitas suelto no
 * dice nada: si entran mil y ninguno escribe, el problema no es el tráfico y
 * gastar en publicidad sería tirar la plata. Por eso los cuatro escalones se
 * muestran juntos, con el porcentaje de cada uno contra el anterior.
 *
 * Estilos inline: el panel no carga `uruku.css`.
 */
export function PanelVisitas() {
  const [d, setD] = useState<ResumenConIa | null>(null);
  const [err, setErr] = useState("");
  const [dias, setDias] = useState(30);

  useEffect(() => {
    setErr("");
    getVisitas(dias).then(setD).catch((e) => setErr(e instanceof Error ? e.message : "No se pudo cargar"));
  }, [dias]);

  if (err) return <div className="panel-card glass" style={{ padding: 16, color: "var(--pink)" }}>{err}</div>;
  if (!d) return <div className="panel-card glass" style={{ padding: 16, color: "var(--txt-3)" }}>Cargando visitas…</div>;

  const e = d.embudo;
  const pct = (a: number, b: number) => (b > 0 ? Math.round((a / b) * 100) : 0);
  const maxDia = Math.max(1, ...d.por_dia.map((x) => x.visitas));

  const escalones = [
    { label: "Páginas vistas", n: e.visitas, de: null as number | null, ayuda: "Cada página que alguien abrió." },
    { label: "Personas", n: e.personas, de: null, ayuda: "Sesiones distintas. Sin cookies: se cuenta por pestaña." },
    { label: "Fichas de comercio", n: e.fichas_vistas, de: e.personas, ayuda: "Llegaron a un negocio concreto." },
    { label: "Escribieron o llamaron", n: e.contactos, de: e.fichas_vistas, ayuda: "Salieron de URUKU hacia el local. Es el número que le importa al comerciante." },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: 16 }}>Visitas al sitio</h3>
        <select className="adm-input" style={{ width: "auto" }} value={dias}
                onChange={(ev) => setDias(Number(ev.target.value))}>
          <option value={7}>Últimos 7 días</option>
          <option value={30}>Últimos 30 días</option>
          <option value={90}>Últimos 90 días</option>
        </select>
      </div>

      {/* El embudo */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(170px,1fr))", gap: 12 }}>
        {escalones.map((s) => (
          <div key={s.label} className="panel-card glass" style={{ padding: 16 }} title={s.ayuda}>
            <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{s.label}</div>
            <div style={{ fontSize: 28, fontWeight: 800 }}>{s.n}</div>
            {s.de != null && (
              <div style={{ fontSize: 11.5, color: s.n === 0 ? "var(--amber)" : "var(--txt-3)" }}>
                {pct(s.n, s.de)}% de los anteriores
              </div>
            )}
          </div>
        ))}
      </div>

      {d.visitas === 0 ? (
        <div className="panel-card glass" style={{ padding: 16, color: "var(--txt-3)", fontSize: 13 }}>
          Todavía no hay visitas contadas. El contador empieza a registrar desde que se despliega:
          lo de antes no se puede recuperar.
        </div>
      ) : (
        <>
          {/* Por día. Barras de texto y no un gráfico: se lee igual, pesa cero
              y no hay una librería más que mantener. */}
          <div className="panel-card glass" style={{ padding: 16 }}>
            <h4 style={{ margin: "0 0 10px", fontSize: 14 }}>Por día</h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
              {d.por_dia.slice(-30).reverse().map((x) => (
                <div key={x.dia} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 12 }}>
                  <span style={{ width: 82, color: "var(--txt-3)", flexShrink: 0 }}>{x.dia}</span>
                  <span style={{ height: 12, borderRadius: 3, background: "var(--neon)", opacity: .75,
                                 width: `${Math.max(2, (x.visitas / maxDia) * 100)}%`, flexShrink: 1, minWidth: 2 }} />
                  <b style={{ flexShrink: 0 }}>{x.visitas}</b>
                  <span style={{ color: "var(--txt-3)", flexShrink: 0 }}>· {x.personas} personas</span>
                </div>
              ))}
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(240px,1fr))", gap: 12 }}>
            <Lista titulo="Páginas más vistas" items={d.top_rutas.map((r) => ({ k: r.ruta, n: r.n }))}
                   vacio="Sin datos." />
            {/* De dónde vienen: si Google no aparece, URUKU no existe para el
                buscador, que es una conclusión distinta a «no hay tráfico». */}
            <Lista titulo="De dónde llegan" items={d.top_referidos.map((r) => ({ k: r.referido, n: r.n }))}
                   vacio="Nadie llegó desde otro sitio todavía: entran escribiendo la dirección o por un enlace compartido." />
            <Lista titulo="Por QR o enlace marcado" items={d.top_origenes.map((r) => ({ k: r.origen, n: r.n }))}
                   vacio="Ningún volante ni tarjeta trajo a nadie todavía." />
          </div>
        </>
      )}

      <AsistentesIa fuentes={d.ai_sources} />

      <p style={{ color: "var(--txt-3)", fontSize: 11.5, margin: 0 }}>
        Sin cookies, sin IP y sin user-agent: sólo qué página se vio y un número al azar por pestaña.
        No se cuentan el panel, la app de campo ni /mi-comercio.
      </p>
    </div>
  );
}

function Lista({ titulo, items, vacio }: { titulo: string; items: { k: string; n: number }[]; vacio: string }) {
  return (
    <div className="panel-card glass" style={{ padding: 16 }}>
      <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>{titulo}</h4>
      {items.length === 0 ? (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0 }}>{vacio}</p>
      ) : (
        <ol style={{ margin: 0, paddingLeft: 18, display: "flex", flexDirection: "column", gap: 5 }}>
          {items.map((it) => (
            <li key={it.k} style={{ fontSize: 13, color: "var(--txt-2)", overflowWrap: "anywhere" }}>
              {it.k} <b style={{ color: "var(--neon)" }}>{it.n}</b>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** «Desde asistentes de IA»: quiénes llegaron desde ChatGPT, Perplexity, Gemini y
 *  compañía. Es el panel del admin: acá sí van números. Tolera que `ai_sources`
 *  falte (backend viejo) o venga vacío. */
function AsistentesIa({ fuentes }: { fuentes: FuenteIa[] | undefined }) {
  const lista = Array.isArray(fuentes) ? fuentes : [];
  return (
    <div className="panel-card glass" style={{ padding: 16 }}>
      <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Desde asistentes de IA</h4>
      {fuentes === undefined ? (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0 }}>
          Este dato todavía no llega del servidor: aparece cuando se actualice el backend.
        </p>
      ) : lista.length === 0 ? (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: 0 }}>
          Ninguna visita llegó desde un asistente de IA en este período.
        </p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", color: "var(--txt-3)", fontSize: 12 }}>
                <th style={{ padding: "4px 8px 4px 0" }}>Asistente</th>
                <th style={{ padding: "4px 8px" }}>Visitas</th>
                <th style={{ padding: "4px 8px" }}>Personas</th>
                <th style={{ padding: "4px 8px" }}>Fichas vistas</th>
                <th style={{ padding: "4px 0 4px 8px" }}>Páginas más vistas</th>
              </tr>
            </thead>
            <tbody>
              {lista.map((f) => (
                <tr key={f.source} style={{ borderTop: "1px solid var(--line, rgba(128,128,128,.25))" }}>
                  <td style={{ padding: "6px 8px 6px 0", fontWeight: 700 }}>{NOMBRE_IA[f.source] ?? f.source}</td>
                  <td style={{ padding: "6px 8px" }}>{f.visits}</td>
                  <td style={{ padding: "6px 8px" }}>{f.people}</td>
                  <td style={{ padding: "6px 8px" }}>{f.business_views}</td>
                  <td style={{ padding: "6px 0 6px 8px", color: "var(--txt-2)", overflowWrap: "anywhere" }}>
                    {(f.top_routes ?? []).join(" · ") || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p style={{ color: "var(--txt-3)", fontSize: 11.5, margin: "10px 0 0" }}>
        Límites: las respuestas de IA de Google (AI Overviews y AI Mode) llegan como google.com y no se pueden
        distinguir de una búsqueda común. ChatGPT a veces no manda ni referrer ni UTM, y esa visita cae como «directo».
      </p>
    </div>
  );
}
