"use client";

import { useState } from "react";
import { editarComercioAgente, type Lugar } from "@/lib/campo";
import { Ic } from "@/components/ic";

/**
 * La SEGUNDA PASADA: todo lo que no se carga parado en la vereda.
 *
 * El alta de la calle tiene que ser rápida — foto, GPS, rubro — porque el
 * agente está de pie, el dueño atendiendo y la pantalla llena de campos hace
 * que se salteen la mitad. Lo que convierte un punto en el mapa en un comercio
 * que sirve se carga en la segunda visita, con el dueño presente y con tiempo:
 * sus números, sus redes, qué vende, su catálogo.
 *
 * TODO acá es opcional. Por eso el botón de guardar está ARRIBA y ABAJO: con
 * todos los campos vacíos la pantalla es larga, y quien completa dos cosas no
 * tiene por qué bajar hasta el final para guardarlas.
 */

type Campos = {
  telefono: string;
  modalidad: string;
  direccion: string;
  prodObs: string;
  lugar_id: string;
  puesto: string;
  instagram_url: string;
  facebook_url: string;
  tiktok_url: string;
  sitio_web: string;
  canal_wa_url: string;
  catalogo_url: string;
  email: string;
};

const VACIO: Campos = {
  telefono: "", modalidad: "", direccion: "", prodObs: "", lugar_id: "", puesto: "",
  instagram_url: "", facebook_url: "", tiktok_url: "", sitio_web: "",
  canal_wa_url: "", catalogo_url: "", email: "",
};

const MODALIDADES = [
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

export function SegundaPasada({ comercioId, lugares, inicial }: {
  comercioId: string;
  lugares: Lugar[];
  /** Lo que ya tiene cargado, para no pedirlo de nuevo ni pisarlo. */
  inicial?: Partial<Campos>;
}) {
  const [f, setF] = useState<Campos>({ ...VACIO, ...inicial });
  const [guardando, setGuardando] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const set = (k: keyof Campos, v: string) => { setF((p) => ({ ...p, [k]: v })); setMsg(""); };

  async function guardar() {
    setErr(""); setMsg(""); setGuardando(true);
    try {
      await editarComercioAgente(comercioId, {
        telefono: f.telefono.trim() || null,
        modalidad: f.modalidad || undefined,
        direccion: f.direccion.trim() || null,
        prod_obs_human: f.prodObs.trim() || null,
        lugar_id: f.lugar_id || null,
        puesto: f.puesto.trim() || null,
        email: f.email.trim() || null,
        // Las redes se guardan como las escribe el agente: el comerciante dice
        // "@mitienda" o pega el enlace entero, y pedirle que lo normalice sería
        // perder el dato. Lo arma bien el sitio al mostrarlo.
        instagram_url: f.instagram_url.trim() || null,
        facebook_url: f.facebook_url.trim() || null,
        tiktok_url: f.tiktok_url.trim() || null,
        sitio_web: f.sitio_web.trim() || null,
        canal_wa_url: f.canal_wa_url.trim() || null,
        catalogo_url: f.catalogo_url.trim() || null,
      });
      setMsg("Guardado");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
    } finally {
      setGuardando(false);
    }
  }

  const Guardar = () => (
    <button type="button" className="btn btn-primary" style={{ width: "100%", padding: 13 }}
            disabled={guardando} onClick={guardar}>
      {guardando ? "Guardando…" : "Guardar estos datos"}
    </button>
  );

  return (
    <div style={{ textAlign: "left", marginBottom: 12, padding: 12, borderRadius: 12,
                  background: "var(--panel)", border: "1px solid var(--stroke)" }}>
      <p style={{ color: "var(--txt-2)", fontSize: 12.5, margin: "0 0 4px" }}>
        <Ic n="documento" s={16} /> Datos del comercio <span style={{ color: "var(--txt-3)" }}>— todo opcional</span>
      </p>
      <p style={{ color: "var(--txt-3)", fontSize: 11.5, margin: "0 0 10px", lineHeight: 1.4 }}>
        Completá lo que el dueño te vaya diciendo. Podés guardar y seguir después.
      </p>

      {/* Arriba, porque con todo vacío esto es largo y el que carga dos cosas
          no tiene por qué bajar hasta el final. */}
      <Guardar />
      {msg && <div style={{ color: "var(--neon)", fontSize: 12.5, marginTop: 6 }}>{msg}</div>}
      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 6 }}>{err}</div>}

      <div style={{ display: "grid", gap: 12, marginTop: 14 }}>

        <div>
          <label className="campo-lbl">Otro teléfono (fijo o de quien atiende)</label>
          <input className="adm-input" type="tel" inputMode="tel" value={f.telefono}
                 onChange={(e) => set("telefono", e.target.value)} placeholder="Para llamar, si el WhatsApp es otro" />
        </div>

        <div>
          <label className="campo-lbl">¿Vende por mayor o menor?</label>
          <div className="seg">
            {MODALIDADES.map((m) => (
              <button type="button" key={m.key} className={f.modalidad === m.key ? "active" : ""}
                      onClick={() => set("modalidad", m.key)}>{m.label}</button>
            ))}
          </div>
        </div>

        <div>
          <label className="campo-lbl">¿Está dentro de un mercado o galería?</label>
          <select className="adm-input" value={f.lugar_id} onChange={(e) => set("lugar_id", e.target.value)}>
            <option value="">No — local a la calle</option>
            {lugares.map((l) => (
              <option key={l.id} value={l.id}>{l.nombre}{l.n_comercios ? ` (${l.n_comercios})` : ""}</option>
            ))}
          </select>
          {f.lugar_id && (
            <input className="adm-input" style={{ marginTop: 8 }} value={f.puesto}
                   onChange={(e) => set("puesto", e.target.value)} placeholder="N° de puesto / pasillo" />
          )}
        </div>

        <div>
          <label className="campo-lbl">Punto de referencia</label>
          <input className="adm-input" value={f.direccion} onChange={(e) => set("direccion", e.target.value)}
                 placeholder="Frente a la plaza, al lado de la farmacia…" />
          <p className="campo-hint">La calle ya la sabemos por el GPS. Esto es para lo difícil de encontrar.</p>
        </div>

        <div>
          <label className="campo-lbl">¿Qué vende?</label>
          <textarea className="adm-input" rows={3} value={f.prodObs} onChange={(e) => set("prodObs", e.target.value)}
                    placeholder="zapatillas, zapatos de vestir, ojotas, mochilas" style={{ resize: "vertical" }} />
          {/* Es el campo que más decide si lo encuentran: la búsqueda mira esto.
              Por eso la ayuda dice CÓMO escribirlo y no sólo qué es. */}
          <p className="campo-hint">
            Separado por comas y como lo diría un cliente. Nadie busca «indumentaria»: busca «campera».
          </p>
        </div>

        <div>
          <label className="campo-lbl">Su catálogo</label>
          <input className="adm-input" value={f.catalogo_url} onChange={(e) => set("catalogo_url", e.target.value)}
                 placeholder="Enlace a un PDF, Drive o su tienda" />
          <p className="campo-hint">Muchos mayoristas ya tienen uno armado y lo mandan por WhatsApp. Pedíselo.</p>
        </div>

        <div>
          <label className="campo-lbl">Su canal de WhatsApp</label>
          <input className="adm-input" value={f.canal_wa_url} onChange={(e) => set("canal_wa_url", e.target.value)}
                 placeholder="Enlace de su canal o comunidad" />
          <p className="campo-hint">El de él, donde publica sus ofertas. No el de URUKU.</p>
        </div>

        <div>
          <label className="campo-lbl">Sus redes</label>
          <div style={{ display: "grid", gap: 8 }}>
            <input className="adm-input" value={f.instagram_url} onChange={(e) => set("instagram_url", e.target.value)} placeholder="Instagram: @usuario o enlace" />
            <input className="adm-input" value={f.facebook_url} onChange={(e) => set("facebook_url", e.target.value)} placeholder="Facebook: usuario o enlace" />
            <input className="adm-input" value={f.tiktok_url} onChange={(e) => set("tiktok_url", e.target.value)} placeholder="TikTok: @usuario o enlace" />
            <input className="adm-input" value={f.sitio_web} onChange={(e) => set("sitio_web", e.target.value)} placeholder="Página web" />
            <input className="adm-input" type="email" value={f.email} onChange={(e) => set("email", e.target.value)} placeholder="Correo (opcional)" />
          </div>
        </div>
      </div>

      <div style={{ marginTop: 14 }}><Guardar /></div>
      {msg && <div style={{ color: "var(--neon)", fontSize: 12.5, marginTop: 6 }}>{msg}</div>}
      {err && <div style={{ color: "var(--pink)", fontSize: 12.5, marginTop: 6 }}>{err}</div>}
    </div>
  );
}
