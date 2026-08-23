"use client";

// Qué hay cargado y, sobre todo, QUÉ FALTA.
//
// El resto del panel muestra bien lo que existe y es ciego a lo que no: con 203
// comercios la pantalla se siente llena aunque falte medio pueblo. Esta vista
// invierte eso — los rubros vacíos van resaltados y arriba de todo, y al lado
// del vocabulario cargado va lo que la gente buscó y no encontró.
//
// Los dos huecos NO son lo mismo y por eso están separados:
//
//   Un rubro vacío puede ser un negocio que en Bermejo no existe —y entonces la
//   categoría sobra— o uno que existe y no se relevó. Sólo lo sabe quien camina
//   la ciudad, así que se muestra sin opinar.
//
//   Un término buscado sin resultado es otra cosa: alguien lo escribió. Eso es
//   demanda medida, y ya dice a qué salir a buscar.
import { useEffect, useState } from "react";
import { adminCatalogo, type Catalogo } from "@/lib/api";

export function CatalogoPanel() {
  const [data, setData] = useState<Catalogo | null>(null);
  const [err, setErr] = useState("");
  const [verVacios, setVerVacios] = useState(false);

  useEffect(() => {
    adminCatalogo().then(setData).catch((e) => setErr(String(e?.message || e)));
  }, []);

  if (err) return <p className="uk-error">{err}</p>;
  if (!data) return <p className="uk-hint">Cargando…</p>;

  const rubros = verVacios ? data.rubros.filter((r) => r.comercios === 0 && !r.descarte) : data.rubros;

  return (
    <div className="cat-panel">
      <div className="cat-resumen">
        <div><b>{data.comercios}</b><span>comercios activos</span></div>
        <div><b>{data.rubros.length}</b><span>rubros</span></div>
        <div className={data.rubros_vacios ? "alerta" : ""}>
          <b>{data.rubros_vacios}</b><span>rubros sin comercios</span>
        </div>
        <div><b>{data.productos_distintos}</b><span>productos distintos</span></div>
        <div><b>{data.buscado_sin_resultado.length}</b><span>búsquedas sin resultado</span></div>
      </div>

      {/* Lo primero de la pantalla es lo que falta, no lo que hay: es la única
          lista de este panel que sale de gente real. */}
      <section className="cat-bloque cat-demanda">
        <h3>Lo buscaron y no lo encontraron</h3>
        <p className="uk-hint">
          Alguien escribió esto en el buscador y se fue con las manos vacías.
          Es demanda medida — la mejor lista de a qué comercios salir a buscar.
        </p>
        {data.buscado_sin_resultado.length === 0 ? (
          <p className="cat-vacio">
            Nada por ahora. Con pocas búsquedas registradas esto queda vacío
            aunque falten comercios: no significa que el catálogo esté completo.
          </p>
        ) : (
          <ul className="cat-chips">
            {data.buscado_sin_resultado.map((b) => (
              <li key={b.query}><b>{b.query}</b><i>{b.n}</i></li>
            ))}
          </ul>
        )}
      </section>

      <section className="cat-bloque">
        <div className="cat-head">
          <h3>Rubros</h3>
          <button className={verVacios ? "active" : ""} onClick={() => setVerVacios((v) => !v)}>
            {verVacios ? "Ver todos" : `Ver sólo los vacíos (${data.rubros_vacios})`}
          </button>
        </div>
        <p className="uk-hint">
          Un rubro sin comercios puede ser una categoría que sobra o un
          relevamiento que falta. El sistema no puede distinguirlos: lo sabés vos.
        </p>
        <table className="cat-tabla">
          <thead><tr><th>Rubro</th><th>Comercios</th></tr></thead>
          <tbody>
            {rubros.map((r) => (
              <tr key={r.slug} className={r.comercios === 0 && !r.descarte ? "vacio" : ""}>
                <td>{r.nombre}{r.descarte && <em> · descarte</em>}</td>
                <td>{r.comercios === 0 ? <span className="cat-cero">sin comercios</span> : r.comercios}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="cat-bloque">
        <h3>Productos</h3>
        <p className="uk-hint">
          Lo que la IA vio en las vidrieras, y en cuántos locales aparece cada
          cosa. De {data.productos_distintos} productos distintos,{" "}
          <b>{data.productos_unicos}</b> aparecen en un solo comercio: eso es
          cola larga, no catálogo — sirve para que la búsqueda encuentre, no para
          armar un filtro.
        </p>
        <ul className="cat-chips">
          {data.productos.map((p) => (
            <li key={p.termino}><b>{p.termino}</b><i>{p.comercios}</i></li>
          ))}
        </ul>
      </section>
    </div>
  );
}
