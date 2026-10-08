"use client";

// Admin › Manuales: abrir (y mandar) los manuales de uso — docs/manuales.md §3.
//
//  - Manual del agente: uno por agente del equipo, con su nombre, ciudad y
//    correo ya puestos. «Abrir manual» lo abre en otra pestaña, listo para
//    «Guardar como PDF» y mandarlo por WhatsApp.
//  - Manual del admin y del comerciante: «Abrir» y «Copiar enlace». El del
//    comerciante se manda tal cual por WhatsApp, con la dirección completa.
//
// La lista de agentes sale de `/admin/equipo`, que pide el permiso `equipo`. Si
// la persona no lo tiene (o falla la red) no se esconde nada: se avisa por qué
// no está la lista y queda la versión genérica del manual del agente.

import { useEffect, useState } from "react";
import { getEquipo, type EquipoData, type UsuarioPanel } from "@/lib/api";
import { Ic } from "@/components/ic";
import { CargandoSeccion, mensajeDeError, useCarga } from "@/components/admin/estado-seccion";
import { rutaManualAgente, type TipoManual } from "@/lib/manuales";

/** Los del equipo que cargan comercios: tienen el rol «agente» o un rol con el
 *  permiso de cargar (el mismo criterio con el que Equipo pide la ciudad). */
function agentesDe(data: EquipoData): UsuarioPanel[] {
  const rolesQueCargan = new Set(data.roles.filter((r) => (r.permisos ?? []).includes("comercios.cargar")).map((r) => r.slug));
  return data.usuarios
    .filter((u) => u.activo && (u.roles ?? []).some((r) => r === "agente" || rolesQueCargan.has(r)))
    .sort((a, b) => (a.nombre ?? a.email).localeCompare(b.nombre ?? b.email, "es"));
}

const cajaEstilo: React.CSSProperties = { padding: 16, display: "grid", gap: 12 };
const botonesEstilo: React.CSSProperties = { display: "flex", gap: 8, flexWrap: "wrap" };

export function ManualesPanel() {
  const [estado, correr] = useCarga("No se pudo leer el equipo");
  const [agentes, setAgentes] = useState<UsuarioPanel[] | null>(null);

  const cargar = () => correr(async () => { setAgentes(agentesDe(await getEquipo())); });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void cargar(); }, []);

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 980 }}>
      <p style={{ margin: 0, fontSize: 14.5, color: "var(--txt-2)" }}>
        <Ic n="dato" s={16} /> Abrí el manual y tocá <b>Guardar como PDF</b> para mandarlo por WhatsApp.
      </p>

      <section className="panel-card glass" style={cajaEstilo} aria-labelledby="man-agente">
        <h3 id="man-agente" style={{ margin: 0, fontSize: 17 }}>Manual del agente</h3>
        <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-3)" }}>
          Uno por agente, con su nombre, su ciudad y su correo ya puestos.
        </p>

        {estado.cargando && !agentes && <CargandoSeccion texto="Buscando a los agentes del equipo…" />}

        {estado.error && (
          <div role="alert" className="ash-aviso ash-aviso-error" style={{ margin: 0 }}>
            <span className="ash-estado-txt">
              <Ic n="aviso" s={18} /> {estado.error}. No se puede armar la lista de agentes
              (para verla hace falta el permiso de Equipo): mientras tanto está la versión genérica, sin nombre.
            </span>
            <button type="button" className="btn btn-ghost btn-sm ash-btn-grande" onClick={() => void cargar()}>Reintentar</button>
          </div>
        )}

        {agentes && agentes.length === 0 && !estado.error && (
          <p role="status" style={{ margin: 0, fontSize: 14, color: "var(--txt-2)" }}>
            <Ic n="gente" s={16} /> Todavía no hay agentes en Equipo. Cuando agregues uno (rol «Agente») va a aparecer acá.
            Mientras tanto está la versión genérica.
          </p>
        )}

        {agentes && agentes.length > 0 && (
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
            {agentes.map((u) => <FilaAgente key={u.id} u={u} />)}
          </ul>
        )}

        <div style={{ ...botonesEstilo, paddingTop: 4, borderTop: "1px solid var(--stroke)" }}>
          <a className="btn btn-ghost btn-sm ash-btn-grande" href={rutaManualAgente()} target="_blank" rel="noopener noreferrer">
            <Ic n="abrir" s={16} /> Versión genérica (sin nombre)
          </a>
        </div>
      </section>

      <FilaFija tipo="admin" titulo="Manual del admin" bajada="Cómo se usa este panel, sección por sección." />
      <FilaFija tipo="comercio" titulo="Manual del comerciante"
                bajada="Cómo entrar a Mi comercio y publicar. Se le puede mandar el enlace por WhatsApp." />
      <FilaFija tipo="uruku" titulo="Qué es URUKU"
                bajada="Para la gente y los medios: cómo nace, qué ofrece y el WhatsApp con su QR. No figura en el sitio: se comparte el enlace." />
    </div>
  );
}

function FilaAgente({ u }: { u: UsuarioPanel }) {
  const ciudad = u.ciudad_nombre ?? u.ciudad_slug ?? "";
  const ruta = rutaManualAgente({ nombre: u.nombre, ciudad, mail: u.email });
  return (
    <li style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap",
                 padding: "10px 12px", border: "1px solid var(--stroke)", borderRadius: 12, background: "var(--panel)" }}>
      <div style={{ minWidth: 0, flex: "1 1 220px" }}>
        <div style={{ fontWeight: 700, overflowWrap: "anywhere" }}>{u.nombre?.trim() || u.email}</div>
        <div style={{ fontSize: 13, color: "var(--txt-2)", overflowWrap: "anywhere" }}>
          {ciudad ? <>{ciudad} · </> : <span style={{ color: "var(--amber)" }}>Sin ciudad asignada · </span>}{u.email}
        </div>
      </div>
      <a className="btn btn-primary btn-sm ash-btn-grande" href={ruta} target="_blank" rel="noopener noreferrer"
         aria-label={`Abrir el manual de ${u.nombre?.trim() || u.email}`}>
        <Ic n="abrir" s={16} /> Abrir manual
      </a>
    </li>
  );
}

/** Un manual sin personalizar: «Abrir» y «Copiar enlace» (con la dirección completa). */
function FilaFija({ tipo, titulo, bajada }: { tipo: Exclude<TipoManual, "agente">; titulo: string; bajada: string }) {
  // «Qué es URUKU» tiene una dirección corta, para dictarla: uruku.bo/que-es-uruku.
  const ruta = tipo === "uruku" ? "/que-es-uruku" : `/manual/${tipo}`;
  const [copiado, setCopiado] = useState(false);
  const [aMano, setAMano] = useState("");   // si el navegador no deja copiar: la dirección para copiar a mano

  async function copiar() {
    const url = `${window.location.origin}${ruta}`;
    setAMano("");
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      window.setTimeout(() => setCopiado(false), 2500);
    } catch {
      setCopiado(false);
      setAMano(url);
    }
  }

  return (
    <section className="panel-card glass" style={cajaEstilo} aria-label={titulo}>
      <div>
        <h3 style={{ margin: 0, fontSize: 17 }}>{titulo}</h3>
        <p style={{ margin: "4px 0 0", fontSize: 13.5, color: "var(--txt-3)" }}>{bajada}</p>
      </div>
      <div style={botonesEstilo}>
        <a className="btn btn-primary btn-sm ash-btn-grande" href={ruta} target="_blank" rel="noopener noreferrer">
          <Ic n="abrir" s={16} /> Abrir
        </a>
        <button type="button" className="btn btn-ghost btn-sm ash-btn-grande" onClick={() => void copiar()}>
          <Ic n="compartir" s={16} /> Copiar enlace
        </button>
        <span role="status" aria-live="polite" style={{ alignSelf: "center", fontSize: 13.5, color: "var(--neon)", fontWeight: 700 }}>
          {copiado && <><Ic n="listo" s={16} /> Copiado</>}
        </span>
      </div>
      {aMano && (
        <label style={{ display: "grid", gap: 4, fontSize: 13 }}>
          <span style={{ color: "var(--amber)" }}><Ic n="aviso" s={14} /> No se pudo copiar solo. Copialo a mano:</span>
          <input className="adm-input" readOnly value={aMano} onFocus={(e) => e.currentTarget.select()} />
        </label>
      )}
    </section>
  );
}
