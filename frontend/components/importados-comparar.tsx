"use client";

/**
 * «Comparar y completar» (docs/turismo-home-y-repetidos.md §1): el panel que abre la ficha de un importado
 * (tarjeta o turismo) que se repite con un comercio ya cargado. Muestra los dos lado a lado —«Ya está en URUKU» y
 * «Lo que trae turismo / la tarjeta»— y deja completar el existente en vez de crear un segundo comercio.
 *
 * Qué se hace con cada campo lo decide `lib/completar-pure.ts`: vacío en el existente → se completa solo; los dos
 * con dato distinto → se conserva el actual salvo «usar el nuevo»; el punto existente nunca se pisa. A 400 px las dos
 * columnas se apilan (grid auto-fit). Estados: cargando, error con reintento y sin conexión, siempre con texto + ícono.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, Insignia, type Tono } from "@/components/content/content-ui";
import { compararImportado, type ComercioImportado } from "@/lib/api";
import {
  TITULO_COLUMNA_ACTUAL, accionCampo, alternarEleccion, armarBodyCompletar, camposVisibles, esElegible, etiquetaCampo,
  mensajeComparador, puedeSumarRubro, resumenAcciones, sumarRubroPorDefecto, textoAccion, textoResumen, textoValor,
  tituloColumnaNuevo, type AccionCampo, type BodyCompletar, type CampoComparado, type Comparacion, type Elecciones,
} from "@/lib/completar-pure";
import type { Rubro } from "@/lib/types";

const TONO_ACCION: Record<AccionCampo, Tono> = {
  completa: "ok", igual: "info", conserva: "info", "punto-fijo": "info", "sin-dato": "info",
};

const CAJA = { border: "1px solid var(--border)", borderRadius: 10, padding: 10, background: "var(--panel)" } as const;
const GRILLA = { display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" } as const;

function Valor({ texto, cambia }: { texto: string | null; cambia?: boolean }) {
  return texto
    ? <span style={{ overflowWrap: "anywhere", fontWeight: cambia ? 700 : 400 }}>{texto}</span>
    : <span style={{ color: "var(--txt-3)" }}>(vacío)</span>;
}

function FilaCampo({ c, usarNuevo, deshabilitado, fuente, onAlternar }: {
  c: CampoComparado; usarNuevo: boolean; deshabilitado: boolean; fuente: string; onAlternar: () => void;
}) {
  const accion = accionCampo(c);
  const elegible = esElegible(c);
  const reemplaza = elegible && usarNuevo;
  const tono = reemplaza ? "aviso" : TONO_ACCION[accion];
  const icono = accion === "completa" ? "listo" : accion === "punto-fijo" ? "ubicacion" : accion === "igual" ? "si" : "dato";
  return (
    <div style={{ ...CAJA, display: "grid", gap: 6 }}>
      <b style={{ fontSize: 13 }}>{etiquetaCampo(c.campo)}</b>
      <div style={{ ...GRILLA, fontSize: 13.5 }}>
        <div>
          <div style={{ fontSize: 11.5, color: "var(--txt-3)" }}>{TITULO_COLUMNA_ACTUAL}</div>
          <Valor texto={textoValor(c.actual)} cambia={accion === "conserva" && !usarNuevo} />
        </div>
        <div>
          <div style={{ fontSize: 11.5, color: "var(--txt-3)" }}>{tituloColumnaNuevo(fuente)}</div>
          <Valor texto={textoValor(c.nuevo)} cambia={accion === "completa" || reemplaza} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <Insignia icono={icono} tono={tono}>{textoAccion(accion, usarNuevo)}</Insignia>
        {elegible && (
          <label style={{ display: "inline-flex", gap: 8, alignItems: "center", fontSize: 13, minHeight: 44, cursor: "pointer" }}>
            <input type="checkbox" role="switch" checked={usarNuevo} disabled={deshabilitado} onChange={onAlternar}
                   style={{ width: 20, height: 20 }} />
            Usar el nuevo
          </label>
        )}
      </div>
    </div>
  );
}

export function CompararCompletar({ item, rubros, busy, online, onCompletar, onNoEsElMismo, onCerrar }: {
  item: ComercioImportado;
  rubros: Rubro[];
  /** Una acción del padre (completar / no es el mismo) está en curso. */
  busy: boolean;
  online: boolean;
  onCompletar: (body: BodyCompletar, nombreExistente: string) => void;
  onNoEsElMismo: () => void;
  onCerrar: () => void;
}) {
  const [cmp, setCmp] = useState<Comparacion | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [intento, setIntento] = useState(0);
  const [elecciones, setElecciones] = useState<Elecciones>({});
  const [sumarRubro, setSumarRubro] = useState(false);

  const comercioId = item.duplicado_de ?? undefined;

  const cargar = useCallback(async () => {
    setCargando(true); setErr("");
    try {
      const r = await compararImportado(item.id, comercioId);
      setCmp(r);
      setElecciones({});
      setSumarRubro(sumarRubroPorDefecto(r.rubro_sugerido, r.rubros_actuales));
    } catch (e) {
      setCmp(null);
      setErr(mensajeComparador(e, "No se pudo traer la comparación"));
    } finally {
      setCargando(false);
    }
  }, [item.id, comercioId]);

  // `intento` fuerza el pedido otra vez desde «Reintentar».
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void cargar(); }, [cargar, intento]);

  const campos = useMemo(() => camposVisibles(cmp?.campos ?? []), [cmp]);
  const deshabilitado = busy || !online;

  if (cargando) return <Cargando texto="Trayendo los dos para compararlos…" />;
  if (err || !cmp) {
    return (
      <Aviso tono="error" accion={
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setIntento((n) => n + 1)}>
          <Ic n="actualizar" s={14} /> Reintentar
        </button>}>
        {err || "No se pudo traer la comparación"}
      </Aviso>
    );
  }

  const { comercio } = cmp;
  const tienePuntoActual = typeof comercio.lat === "number" && typeof comercio.lng === "number";
  const puedeRubro = puedeSumarRubro(cmp.rubro_sugerido, cmp.rubros_actuales);
  const nombreRubro = (slug: string) => rubros.find((r) => r.slug === slug)?.nombre ?? slug;
  const resumen = textoResumen(resumenAcciones(cmp.campos, elecciones), sumarRubro && puedeRubro);
  const nuevoCampo = (c: CampoComparado) => () => setElecciones((e) => alternarEleccion(e, c.campo));

  return (
    <div style={{ display: "grid", gap: 10, padding: 10, border: "1px solid var(--neon)", borderRadius: 12 }}
         role="region" aria-label="Comparar y completar">
      <div style={GRILLA}>
        <div style={CAJA}>
          <b style={{ fontSize: 13 }}>{TITULO_COLUMNA_ACTUAL}</b>
          <div style={{ fontSize: 14, margin: "4px 0 6px", overflowWrap: "anywhere" }}>{comercio.nombre}</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Insignia icono="foto" tono={comercio.tiene_foto ? "ok" : "info"}>{comercio.tiene_foto ? "Tiene foto" : "Sin foto"}</Insignia>
            <Insignia icono="ubicacion" tono={tienePuntoActual ? "ok" : "info"}>{tienePuntoActual ? "Tiene punto en el mapa" : "Sin punto en el mapa"}</Insignia>
          </div>
        </div>
        <div style={CAJA}>
          <b style={{ fontSize: 13 }}>{tituloColumnaNuevo(item.fuente)}</b>
          <div style={{ fontSize: 14, margin: "4px 0 6px", overflowWrap: "anywhere" }}>{item.nombre ?? "(sin nombre)"}</div>
          <div style={{ fontSize: 12, color: "var(--txt-3)" }}>La foto y el punto del comercio actual no se tocan.</div>
        </div>
      </div>

      {campos.length === 0 && (
        <span style={{ fontSize: 13, color: "var(--txt-3)" }}><Ic n="dato" s={14} /> No hay datos para comparar.</span>
      )}
      {campos.map((c) => (
        <FilaCampo key={c.campo} c={c} fuente={item.fuente} usarNuevo={!!elecciones[c.campo]}
                   deshabilitado={deshabilitado} onAlternar={nuevoCampo(c)} />
      ))}

      {puedeRubro && cmp.rubro_sugerido && (
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13.5, minHeight: 44, cursor: "pointer" }}>
          <input type="checkbox" checked={sumarRubro} disabled={deshabilitado}
                 onChange={(e) => setSumarRubro(e.target.checked)} style={{ width: 20, height: 20 }} />
          <span>Sumar el rubro <b>{nombreRubro(cmp.rubro_sugerido)}</b></span>
        </label>
      )}

      <span style={{ fontSize: 12.5, color: "var(--txt-2)" }} role="status"><Ic n="dato" s={14} /> {resumen}</span>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <button type="button" className="btn btn-primary" style={BTN_GRANDE} disabled={deshabilitado}
                onClick={() => onCompletar(armarBodyCompletar(comercio.id, cmp.campos, elecciones, sumarRubro && puedeRubro), comercio.nombre)}>
          <Ic n="si" s={15} /> Completar el existente
        </button>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={deshabilitado} onClick={onNoEsElMismo}>
          <Ic n="volver" s={14} /> No es el mismo
        </button>
        <button type="button" className="link-more" style={{ padding: "0 8px", fontSize: 13.5, minHeight: 44 }} onClick={onCerrar}>
          Cerrar la comparación
        </button>
      </div>
    </div>
  );
}
