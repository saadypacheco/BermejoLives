// uruku.bo/agentes: las personas que visitan comercios en nombre de URUKU.
//
// Se lee en el servidor (`GET /public/agents`, revalidate 60). La lista sale ya
// filtrada del backend: sólo agentes activos, con credencial vigente y foto.
// NUNCA se muestra cuántos son (regla del sitio: sin cifras al público).

import type { Metadata } from "next";
import "@/app/styles/agentes.css";
import { Ic } from "@/components/ic";
import { UrukuShell } from "@/components/uruku-shell";
import { WA_URUKU_TEXTO, waUruku } from "@/lib/contacto";
import { getAgentesPublicos, mesAnio, nombreCompleto, type AgentePublico } from "@/lib/agent-credentials";

export const revalidate = 60;

export const metadata: Metadata = {
  title: "Agentes autorizados: quiénes visitan comercios",
  description: "Las únicas personas que visitan comercios en nombre de URUKU. Los agentes de URUKU nunca cobran.",
  alternates: { canonical: "/agentes" },
};

/** Agrupa por ciudad conservando el orden del backend (ciudad, apellido, nombre). */
function porCiudad(items: AgentePublico[]): { ciudad: string; agentes: AgentePublico[] }[] {
  const grupos: { ciudad: string; agentes: AgentePublico[] }[] = [];
  for (const a of items) {
    const ciudad = a.ciudad_nombre ?? "Otras ciudades";
    const g = grupos.find((x) => x.ciudad === ciudad);
    if (g) g.agentes.push(a);
    else grupos.push({ ciudad, agentes: [a] });
  }
  return grupos;
}

export default async function AgentesPage() {
  const items = await getAgentesPublicos();
  const grupos = items ? porCiudad(items) : [];

  return (
    <UrukuShell showCatnav={false}>
      <div className="uk-container ag-lista">
        <h1>Agentes de URUKU</h1>
        <p className="ag-bajada">
          Son las únicas personas que visitan comercios en nombre de URUKU.{" "}
          <b>Los agentes de URUKU nunca cobran</b>: los planes se pagan sólo por QR en uruku.bo/pagar.
        </p>

        {items === null ? (
          <div className="ag-estado" role="alert">
            <Ic n="aviso" s={24} />
            <p>No pudimos cargar la lista ahora. Probá de nuevo en un rato.</p>
          </div>
        ) : items.length === 0 ? (
          <div className="ag-estado" role="status">
            <Ic n="gente" s={24} />
            <p>Pronto vas a ver acá a los agentes de URUKU.</p>
          </div>
        ) : (
          grupos.map((g) => (
            <section key={g.ciudad} aria-label={`Agentes en ${g.ciudad}`}>
              <h2 className="ag-ciudad"><Ic n="ubicacion" s={20} tono="marca" /> {g.ciudad}</h2>
              <ul className="ag-grid">
                {g.agentes.map((a, i) => {
                  const nombre = nombreCompleto(a.nombre, a.apellido);
                  const desde = mesAnio(a.desde);
                  return (
                    <li key={`${nombre}-${i}`} className="ag-tarjeta">
                      {a.photo_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img className="ag-foto" src={a.photo_url} alt={`Foto de ${nombre}`} width={96} height={96} loading="lazy" />
                      ) : (
                        <span className="ag-foto ag-foto-vacia" aria-hidden="true"><Ic n="usuario" s={40} /></span>
                      )}
                      <b>{nombre}</b>
                      <span>{a.ciudad_nombre ?? g.ciudad}</span>
                      {desde && <span>Agente desde {desde}</span>}
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}

        <div className="ag-aviso-wa">
          <p><b>¿Te visitó alguien que no está acá?</b> Avisanos al WhatsApp {WA_URUKU_TEXTO}.</p>
          <div>
            <a className="ag-btn" href={waUruku("Hola URUKU, me visitó alguien que dijo ser agente de URUKU y no figura en la lista")} target="_blank" rel="noopener noreferrer">
              <Ic n="whatsapp" s={20} /> Avisar por WhatsApp
            </a>
          </div>
        </div>
      </div>
    </UrukuShell>
  );
}
