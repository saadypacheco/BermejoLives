// uruku.bo/agentes/<token>: la página que abre el QR de la credencial.
//
// Contesta UNA pregunta: ¿esta persona es agente de URUKU hoy? Se comprueba en
// cada visita (force-dynamic + no-store) y trae un reloj que corre, para que una
// captura vieja no sirva. Si la credencial se dio de baja, la pantalla se pone
// roja y dice que NO es agente. Sin cifras, sin datos de contacto del agente.

import type { Metadata } from "next";
import "@/app/styles/agentes.css";
import { Ic } from "@/components/ic";
import { RelojCredencial } from "@/components/reloj-credencial";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";
import { nombreCompleto, verificarCredencial } from "@/lib/agent-credentials";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Credencial de agente de URUKU",
  robots: { index: false, follow: false },
};

function Logo() {
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="ag-logo" src="/logouruku-wordmark.png" alt="URUKU" />;
}

function Foto({ url, nombre }: { url: string | null; nombre: string }) {
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img className="ag-foto-grande" src={url} alt={nombre ? `Foto de ${nombre}` : "Foto del titular de la credencial"} width={190} height={190} />
  ) : (
    <span className="ag-foto-grande ag-sin" aria-hidden="true"><Ic n="usuario" s={72} /></span>
  );
}

export default async function CredencialPage({ params }: { params: { token: string } }) {
  const r = await verificarCredencial(params.token);

  // 404 del backend: el token no existe. Siempre el mismo mensaje.
  if (r.tipo === "no_existe") {
    return (
      <main className="ag-root">
        <Logo />
        <section className="ag-vacio" role="alert">
          <Ic n="aviso" s={40} />
          <h1>Esta credencial no es de URUKU.</h1>
          <p>No le pagues nada a quien te la mostró. Fijate que arriba diga <b>uruku.bo</b>.</p>
          <a className="ag-link" href="/agentes"><Ic n="gente" s={18} /> Ver todos los agentes</a>
        </section>
        <Ayuda />
      </main>
    );
  }

  // El backend no contestó: no se afirma nada ni para un lado ni para el otro.
  if (r.tipo === "error") {
    return (
      <main className="ag-root">
        <Logo />
        <section className="ag-vacio" role="alert">
          <Ic n="aviso" s={40} />
          <h1>No pudimos comprobar la credencial.</h1>
          <p>Probá de nuevo en un momento. Mientras tanto, no le pagues nada a nadie en mano.</p>
          <a className="ag-btn" href={`/agentes/${encodeURIComponent(params.token)}`}><Ic n="actualizar" s={20} /> Reintentar</a>
        </section>
        <Ayuda />
      </main>
    );
  }

  const d = r.datos;
  const nombre = nombreCompleto(d.nombre, d.apellido);

  if (d.status !== "valid") {
    // revoked | inactive: para el público es lo mismo, «NO ES AGENTE DE URUKU».
    return (
      <main className="ag-root ag-rojo">
        <Logo />
        <section className="ag-baja" role="alert">
          <Ic n="aviso" s={48} />
          <h1>NO ES AGENTE DE URUKU</h1>
          <p>Esta credencial se dio de baja. No le pagues nada.</p>
        </section>
        <section className="ag-id" aria-label="Datos de la credencial dada de baja">
          <Foto url={d.photo_url} nombre={nombre} />
          {nombre && <h2 className="ag-nom">{nombre}</h2>}
          <p className="ag-rol">Credencial dada de baja</p>
        </section>
        <Ayuda />
      </main>
    );
  }

  return (
    <main className="ag-root">
      <Logo />
      <section className="ag-id" aria-label="Credencial de agente">
        <Foto url={d.photo_url} nombre={nombre} />
        <p className="ag-comparar" role="note"><Ic n="usuario" s={22} /> Compará la foto con la persona que tenés enfrente. Si no es la misma, no es agente.</p>
        {nombre && <h1 className="ag-nom">{nombre}</h1>}
        <p className="ag-rol">Agente de URUKU{d.ciudad ? ` · ${d.ciudad}` : ""}</p>
        <p className="ag-sello ag-sello-ok"><Ic n="listo" s={26} /> VIGENTE</p>
        <RelojCredencial checkedAt={d.checked_at} />
      </section>

      <section className="ag-nocobran" role="note" aria-label="Aviso de seguridad">
        <Ic n="aviso" s={26} />
        <div>
          <p><b>LOS AGENTES DE URUKU NUNCA COBRAN.</b></p>
          <p>Pagá sólo por QR a URUKU: <b>uruku.bo/pagar</b></p>
        </div>
      </section>
      <Ayuda />
    </main>
  );
}

/** Lo que va siempre abajo: a quién avisar, cómo reconocer el sitio y el enlace a la lista. */
function Ayuda() {
  return (
    <section className="ag-ayuda">
      <p><b>¿Te pidieron plata?</b> Avisanos al WhatsApp {WA_URUKU_TEXTO}.</p>
      <a className="ag-btn" href={waUruku("Hola URUKU, un agente me pidió plata")} target="_blank" rel="noopener noreferrer">
        <Ic n="whatsapp" s={20} /> Avisar por WhatsApp
      </a>
      <p>Fijate que arriba, en la barra del navegador, diga <b>uruku.bo</b>.</p>
      <a className="ag-link" href="/agentes"><Ic n="gente" s={18} /> Ver todos los agentes</a>
    </section>
  );
}
