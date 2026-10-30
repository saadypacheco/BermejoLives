"use client";

// /admin/credencial/<usuarioId>: la credencial del agente, lista para imprimir.
//
// Usa el JWT del admin (el mismo de /admin) y lee `GET /admin/agents/<id>/credential`.
// Sin credencial vigente no hay nada que imprimir: avisa y vuelve a Equipo.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { AgentCredentialCard } from "@/components/agent-credential-card";
import { Carga, useCarga } from "@/components/admin/estado-seccion";
import { Ic } from "@/components/ic";
import { getToken } from "@/lib/api";
import { getCredencialAdmin, nombreCompleto, type CredencialAdmin } from "@/lib/agent-credentials";
import "@/app/styles/credencial-agente.css";

export default function CredencialAdminPage({ params }: { params: { id: string } }) {
  const [estado, correr] = useCarga("No se pudo cargar la credencial");
  const [datos, setDatos] = useState<CredencialAdmin | null>(null);
  // `null` hasta montar: el token vive en localStorage y el servidor no lo ve.
  const [conSesion, setConSesion] = useState<boolean | null>(null);

  const cargar = useCallback(() => correr(async () => { setDatos(await getCredencialAdmin(params.id)); }), [correr, params.id]);

  useEffect(() => {
    const hay = !!getToken();
    setConSesion(hay);
    if (hay) void cargar();
  }, [cargar]);

  return (
    <div className="acc-fondo">
      <div className="acc-pagina">
        <div className="acc-oculta-al-imprimir" style={{ display: "grid", gap: 12 }}>
          <h1>Credencial del agente</h1>
          <div className="acc-barra">
            <Link className="acc-btn acc-btn-claro" href="/admin?s=equipo"><Ic n="volver" s={20} /> Volver a Equipo</Link>
          </div>
        </div>

        {conSesion === false && (
          <div className="acc-estado acc-estado-error acc-oculta-al-imprimir" role="alert">
            <Ic n="aviso" s={22} />
            <p>Tenés que entrar al panel para ver esta credencial. <Link href="/admin">Entrar al panel</Link></p>
          </div>
        )}

        {conSesion && (
          <Carga estado={estado} onReintentar={cargar} que="la credencial">
            {datos && <Contenido datos={datos} />}
          </Carga>
        )}
      </div>
    </div>
  );
}

function Contenido({ datos }: { datos: CredencialAdmin }) {
  const cred = datos.credential;
  const completo = nombreCompleto(datos.nombre, datos.apellido);

  if (!cred) {
    return (
      <div className="acc-estado acc-oculta-al-imprimir" role="status">
        <Ic n="dato" s={22} />
        <p>
          {completo || "Esta persona"} no tiene una credencial vigente. Emitila desde <b>Equipo</b> (hace falta la foto,
          el nombre y el apellido) y volvé acá para imprimirla.
        </p>
      </div>
    );
  }

  return (
    <>
      {!datos.activo && (
        <div className="acc-estado acc-estado-error acc-oculta-al-imprimir" role="alert">
          <Ic n="aviso" s={22} />
          <p>Esta persona está dada de baja en el panel: el QR de la tarjeta va a decir «NO ES AGENTE DE URUKU».</p>
        </div>
      )}
      <div className="acc-oculta-al-imprimir" style={{ display: "grid", gap: 10 }}>
        <p>
          <b>{completo}</b>. Se imprime en tamaño tarjeta (54 × 85,6 mm): frente y reverso, dos copias por hoja A4.
          Recortá por la línea punteada.
        </p>
        <div className="acc-barra">
          <button type="button" className="acc-btn" onClick={() => window.print()}><Ic n="imprimir" s={20} /> Imprimir</button>
        </div>
      </div>

      <AgentCredentialCard nombre={datos.nombre} apellido={datos.apellido} ciudad={datos.ciudad_nombre} photoUrl={datos.photo_url} token={cred.token} />
      <div className="acc-copia" aria-hidden="true">
        <AgentCredentialCard nombre={datos.nombre} apellido={datos.apellido} ciudad={datos.ciudad_nombre} photoUrl={datos.photo_url} token={cred.token} />
      </div>
    </>
  );
}
