import { Ic } from "@/components/ic";
import { Ilustracion } from "@/components/ilustraciones";
import { EnlaceFiltrado } from "./enlace-filtrado";
import { hayPlanes, type Plan, type PlanesCiudad } from "@/lib/planes-ciudad-pure";

/**
 * «Qué podés hacer en {ciudad}» (docs/home-ciudades.md §12): planes ilustrados que llevan al mapa. Una tarjeta
 * grande (la ruta del vino, el centro histórico o la noche, la primera que la ciudad tenga) y una grilla de dos
 * columnas con el resto. Cada plan sale sólo si hay datos para su destino; sin ninguno, el bloque no aparece.
 * Las ilustraciones son del catálogo propio (`components/ilustraciones`): no hay fotos acá.
 */
export function QueHacer({ planes, ciudad }: { planes: PlanesCiudad; ciudad: string }) {
  if (!hayPlanes(planes)) return null;
  const { grande, grilla, verTodos } = planes;
  return (
    <section className="uk-container uk-home-sec uk-hc-sec" aria-labelledby="home-que-hacer">
      <div className="uk-hc-hacer">
        <div className="uk-hc-hacer-cab">
          <h2 id="home-que-hacer">Qué podés hacer en <em>{ciudad}</em></h2>
          <p>Elegí un plan y te lo mostramos en el mapa.</p>
        </div>
        <div className="uk-hc-planes">
          {grande && <PlanGrande plan={grande} />}
          {grilla.length > 0 && (
            <ul className="uk-hc-plan-grid">
              {grilla.map((p) => (
                <li key={p.id}><PlanChico plan={p} /></li>
              ))}
            </ul>
          )}
        </div>
        {verTodos && (
          <div className="uk-hc-planes-pie">
            <EnlaceFiltrado href={verTodos} className="uk-hc-mapa-link">
              <Ic n="mapa" s={18} /> Ver todos los planes en el mapa ›
            </EnlaceFiltrado>
          </div>
        )}
      </div>
    </section>
  );
}

function PlanGrande({ plan }: { plan: Plan }) {
  return (
    <EnlaceFiltrado href={plan.href} className={`uk-hc-plan-grande plan-${plan.id}`}>
      <Ilustracion id={plan.ilustracion} className="uk-hc-plan-dib" />
      <span className="uk-hc-plan-txt">
        <span className="uk-hc-plan-tag">{plan.etiqueta}</span>
        <b>{plan.titulo}</b>
        <span className="uk-hc-plan-btn">{plan.cta}</span>
      </span>
    </EnlaceFiltrado>
  );
}

function PlanChico({ plan }: { plan: Plan }) {
  return (
    <EnlaceFiltrado href={plan.href} className="uk-hc-plan">
      <Ilustracion id={plan.ilustracion} className="uk-hc-plan-dib" />
      <span className="uk-hc-plan-txt">
        <b>{plan.titulo}</b>
        <small>{plan.bajada}</small>
      </span>
    </EnlaceFiltrado>
  );
}
