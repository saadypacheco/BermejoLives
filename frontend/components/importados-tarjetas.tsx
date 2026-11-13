"use client";

/**
 * Carga de comercios desde fotos de tarjetas (docs/carga-tarjetas.md, sección «Pantalla»).
 * Vive dentro de Comercios › Importados:
 *
 *  · `CargarTarjetasModal`: elegir ciudad y fotos, subir con progreso, ver el resumen.
 *  · `FichaTarjeta`: la revisión de una tarjeta (foto, campos editables, repetido, punto en
 *    el mapa, promover / descartar).
 *
 * La foto de la tarjeta es privada: se pide con el Bearer y se muestra como blob (se revoca
 * al salir); el token nunca va en una URL. Estados en todo: cargando, vacío, error y sin
 * conexión, siempre con texto + ícono. Si el servidor todavía no tiene las rutas (404) se
 * dice «Esta versión del servidor todavía no tiene la carga de tarjetas».
 */
import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { Ic } from "@/components/ic";
import { nombreCiudad, useAdminCiudad } from "@/components/admin-ciudad";
import { Aviso, BTN_GRANDE, Insignia, SinConexion, useOnline } from "@/components/content/content-ui";
import {
  descartarImportado, editarImportado, getFotoImportado, promoverImportado, subirTarjetas, ubicarImportado,
  type ComercioImportado,
} from "@/lib/api";
import { agregarTiles } from "@/lib/mapa-tiles";
import { loadLeaflet } from "@/lib/mapa-visual";
import type { Ciudad, Rubro } from "@/lib/types";
import {
  ACCEPT_FOTOS, ENLACE_NEGOCIOS, MAX_ARCHIVOS, chipUbicacion, diffPatch, erroresDeRespuesta, formDeItem, hayCambios,
  mensajeError, puedePromover, resumenCarga, textoUbicar, tienePunto, urlDeOrigen, validarArchivos,
  type ErrorArchivo, type FormTarjeta,
} from "@/lib/tarjetas-pure";

const CAMPO: CSSProperties = {
  width: "100%", padding: "8px 10px", borderRadius: 8, border: "1px solid var(--border)",
  background: "var(--panel)", color: "var(--txt-1)", fontSize: 14, minHeight: 40, boxSizing: "border-box",
};

// ───────────────────────────── Modal «Cargar tarjetas» ─────────────────────────────

type Fase = "elegir" | "subiendo" | "listo";

export function CargarTarjetasModal({ ciudadInicial, onCerrar, onTerminado }: {
  ciudadInicial: Ciudad | null;
  onCerrar: () => void;
  /** Se llama al cerrar si se subió algo: la lista se vuelve a pedir. */
  onTerminado: () => void;
}) {
  const { ciudades } = useAdminCiudad();
  const online = useOnline();
  const [ciudadId, setCiudadId] = useState(ciudadInicial?.id ?? "");
  const [fotos, setFotos] = useState<File[]>([]);
  const [rechazadas, setRechazadas] = useState<ErrorArchivo[]>([]);
  const [fase, setFase] = useState<Fase>("elegir");
  const [pct, setPct] = useState(0);
  const [err, setErr] = useState("");
  const [resultado, setResultado] = useState<{ texto: string; errores: ErrorArchivo[] } | null>(null);
  const [subio, setSubio] = useState(false);
  const caja = useRef<HTMLDivElement>(null);
  const entrada = useRef<HTMLInputElement>(null);

  const cerrar = useCallback(() => {
    if (fase === "subiendo") return;           // a mitad de subida no se cierra: se perdería el resumen
    if (subio) onTerminado();
    onCerrar();
  }, [fase, subio, onTerminado, onCerrar]);

  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") cerrar(); };
    document.addEventListener("keydown", alTeclear);
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    caja.current?.focus();
    return () => { document.removeEventListener("keydown", alTeclear); document.body.style.overflow = previo; };
  }, [cerrar]);

  function elegirArchivos(lista: FileList | null) {
    if (!lista || lista.length === 0) return;
    const { validos, errores } = validarArchivos(Array.from(lista), fotos.length);
    setFotos((f) => [...f, ...validos]);
    setRechazadas(errores);
    if (entrada.current) entrada.current.value = "";   // poder elegir el mismo archivo otra vez
  }

  async function subir() {
    if (!ciudadId || fotos.length === 0 || !online) return;
    setFase("subiendo"); setPct(0); setErr("");
    try {
      const r = await subirTarjetas(ciudadId, fotos, setPct);
      const errores = erroresDeRespuesta(r);
      setResultado({ texto: resumenCarga(r.items, errores).texto, errores });
      setSubio(true);
      setFotos([]); setRechazadas([]);
      setFase("listo");
    } catch (e) {
      const sinRed = typeof navigator !== "undefined" && navigator.onLine === false;
      setErr(sinRed ? "Sin conexión: no se pudo subir. Cuando vuelva la señal, probá de nuevo." : mensajeError(e, "No se pudo subir las fotos"));
      setFase("elegir");
    }
  }

  const sinCiudad = !ciudadId;
  const bloqueado = fase === "subiendo";

  return (
    <div onClick={cerrar}
         style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.6)", display: "flex",
                  alignItems: "flex-end", justifyContent: "center" }}>
      <div ref={caja} role="dialog" aria-modal="true" aria-label="Cargar tarjetas" tabIndex={-1}
           onClick={(e) => e.stopPropagation()}
           style={{ background: "var(--bg)", color: "var(--txt)", width: "100%", maxWidth: 560, maxHeight: "92dvh", overflowY: "auto",
                    borderRadius: "18px 18px 0 0", border: "1px solid var(--stroke-2)",
                    padding: "16px 16px calc(20px + env(safe-area-inset-bottom, 0px))",
                    display: "grid", gap: 14, alignContent: "start", outline: "none" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <h3 style={{ margin: 0, fontSize: 18 }}><Ic n="documentos" s={18} /> Cargar tarjetas</h3>
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={cerrar} disabled={bloqueado}>
            <Ic n="cerrar" s={15} /> Cerrar
          </button>
        </div>

        <SinConexion />

        {fase === "listo" && resultado ? (
          <div style={{ display: "grid", gap: 12 }} role="status">
            <Aviso tono={resultado.errores.length === 0 ? "ok" : "aviso"}>
              <b>{resultado.texto}</b>
              <br />Quedan en Importados, sin revisar: nada aparece en el sitio hasta que las promovás.
            </Aviso>
            {resultado.errores.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18, display: "grid", gap: 4, fontSize: 13.5 }}>
                {resultado.errores.map((e, k) => (
                  <li key={`${e.archivo}-${k}`}><b>{e.archivo}</b>: {e.motivo}</li>
                ))}
              </ul>
            )}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={cerrar}>Ver las tarjetas</button>
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE}
                      onClick={() => { setResultado(null); setFase("elegir"); }}>
                <Ic n="mas" s={15} /> Subir más
              </button>
            </div>
          </div>
        ) : (
          <>
            <label style={{ display: "grid", gap: 6, fontSize: 13.5 }}>
              <span style={{ fontWeight: 600 }}>Ciudad de las tarjetas</span>
              <select value={ciudadId} onChange={(e) => setCiudadId(e.target.value)} disabled={bloqueado} style={CAMPO}>
                <option value="">Elegí la ciudad…</option>
                {ciudades.map((c) => <option key={c.id} value={c.id}>{nombreCiudad(c)}</option>)}
              </select>
              <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>La dirección se busca dentro de esta ciudad.</span>
            </label>

            <div style={{ display: "grid", gap: 6 }}>
              <input ref={entrada} type="file" multiple accept={ACCEPT_FOTOS} disabled={bloqueado} style={{ display: "none" }}
                     onChange={(e) => elegirArchivos(e.target.files)} aria-label="Fotos de tarjetas" />
              <button type="button" className="btn btn-ghost" style={{ ...BTN_GRANDE, justifySelf: "start" }}
                      disabled={bloqueado || fotos.length >= MAX_ARCHIVOS} onClick={() => entrada.current?.click()}>
                <Ic n="subir" s={16} /> Elegir fotos
              </button>
              <span style={{ color: "var(--txt-3)", fontSize: 12.5 }}>
                JPEG, PNG o WebP · hasta {MAX_ARCHIVOS} fotos · 10 MB cada una.
              </span>
            </div>

            {fotos.length === 0 && rechazadas.length === 0 && (
              <p style={{ margin: 0, color: "var(--txt-3)", fontSize: 13.5 }}>
                <Ic n="foto" s={15} /> Todavía no elegiste fotos.
              </p>
            )}

            {fotos.length > 0 && (
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: 4 }}>
                {fotos.map((f, k) => (
                  <li key={`${f.name}-${f.size}-${k}`}
                      style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13.5, padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</span>
                    <span style={{ color: "var(--txt-3)", fontSize: 12 }}>{(f.size / (1024 * 1024)).toFixed(1)} MB</span>
                    <button type="button" className="link-more" disabled={bloqueado} aria-label={`Quitar ${f.name}`}
                            style={{ padding: 4 }} onClick={() => setFotos((xs) => xs.filter((_, i) => i !== k))}>
                      <Ic n="cerrar" s={14} />
                    </button>
                  </li>
                ))}
              </ul>
            )}

            {rechazadas.length > 0 && (
              <Aviso tono="aviso">
                <b>No se sumaron {rechazadas.length === 1 ? "1 archivo" : `${rechazadas.length} archivos`}:</b>
                <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                  {rechazadas.map((e, k) => <li key={`${e.archivo}-${k}`}><b>{e.archivo}</b>: {e.motivo}</li>)}
                </ul>
              </Aviso>
            )}

            {err && <Aviso tono="error">{err}</Aviso>}

            {fase === "subiendo" && (
              <div role="status" aria-live="polite" style={{ display: "grid", gap: 6, fontSize: 13.5 }}>
                <progress value={pct} max={100} style={{ width: "100%" }} aria-label="Avance de la subida" />
                <span>
                  <Ic n="actualizar" s={14} />{" "}
                  {pct < 100 ? `Subiendo… ${pct}%` : "Leyendo las tarjetas… puede tardar un rato, no cierres esta ventana."}
                </span>
              </div>
            )}

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button type="button" className="btn btn-primary" style={BTN_GRANDE}
                      disabled={bloqueado || sinCiudad || fotos.length === 0 || !online} onClick={subir}>
                <Ic n="subir" s={16} /> {fotos.length > 0 ? `Subir ${fotos.length} ${fotos.length === 1 ? "foto" : "fotos"}` : "Subir"}
              </button>
              {!bloqueado && (sinCiudad || fotos.length === 0) && (
                <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
                  {sinCiudad ? "Elegí la ciudad para subir." : "Elegí al menos una foto."}
                </span>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ───────────────────────────── Foto privada ─────────────────────────────

function FotoTarjeta({ id }: { id: string }) {
  const [url, setUrl] = useState("");
  const [estado, setEstado] = useState<"cargando" | "ok" | "sin" | "error">("cargando");
  const [intento, setIntento] = useState(0);
  const [grande, setGrande] = useState(false);

  useEffect(() => {
    let vivo = true;
    let creada = "";
    setEstado("cargando");
    getFotoImportado(id)
      .then((b) => {
        if (!vivo) return;
        if (!b) { setEstado("sin"); return; }
        creada = URL.createObjectURL(b);
        setUrl(creada);
        setEstado("ok");
      })
      .catch(() => { if (vivo) setEstado("error"); });
    return () => {
      vivo = false;
      if (creada) URL.revokeObjectURL(creada);
      setUrl("");
    };
  }, [id, intento]);

  useEffect(() => {
    if (!grande) return;
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") setGrande(false); };
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [grande]);

  const marco: CSSProperties = {
    width: 120, height: 120, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    gap: 4, background: "var(--panel)", borderRadius: 8, color: "var(--txt-3)", fontSize: 12, textAlign: "center", flexShrink: 0,
  };

  if (estado === "cargando") return <div style={marco} role="status"><Ic n="reloj" s={16} /> cargando foto…</div>;
  if (estado === "sin") return <div style={marco}><Ic n="foto" s={16} /> sin foto</div>;
  if (estado === "error") {
    return (
      <div style={marco} role="alert">
        <span><Ic n="aviso" s={14} /> no se pudo cargar</span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIntento((n) => n + 1)}>
          <Ic n="actualizar" s={13} /> Reintentar
        </button>
      </div>
    );
  }
  return (
    <>
      <button type="button" onClick={() => setGrande(true)} aria-label="Ver la tarjeta en grande"
              style={{ padding: 0, border: 0, background: "none", cursor: "zoom-in", display: "block", flexShrink: 0 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt="Foto de la tarjeta" width={120} height={120} style={{ borderRadius: 8, objectFit: "cover", display: "block" }} />
      </button>
      {grande && (
        <div role="dialog" aria-modal="true" aria-label="Foto de la tarjeta" onClick={() => setGrande(false)}
             style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.85)",
                      display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setGrande(false)}
                  style={{ position: "absolute", top: 12, right: 12, minHeight: 44 }}>
            <Ic n="cerrar" s={14} /> Cerrar
          </button>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={url} alt="Foto de la tarjeta" style={{ maxWidth: "100%", maxHeight: "100%", borderRadius: 8 }} />
        </div>
      )}
    </>
  );
}

// ───────────────────────────── Mapa con punto arrastrable ─────────────────────────────

// Leaflet se carga por CDN y no trae tipos: los objetos del mapa van como `any`, sólo acá adentro.
function MapaPunto({ lat, lng, ciudad, onMover, bloqueado }: {
  lat: number | null; lng: number | null; ciudad: Ciudad | null;
  onMover: (lat: number, lng: number) => void; bloqueado: boolean;
}) {
  const el = useRef<HTMLDivElement>(null);
  const mapa = useRef<any>(null);
  const marca = useRef<any>(null);
  const L = useRef<any>(null);
  const [fallo, setFallo] = useState(false);
  const [intento, setIntento] = useState(0);
  // Los manejadores viven dentro del mapa: leen siempre la versión última.
  const alMover = useRef(onMover);
  alMover.current = onMover;
  const trabado = useRef(bloqueado);
  trabado.current = bloqueado;

  const poner = useCallback((la: number, ln: number) => {
    if (!L.current || !mapa.current) return;
    if (!marca.current) {
      marca.current = L.current.marker([la, ln], { draggable: true }).addTo(mapa.current);
      marca.current.on("dragend", (e: any) => {
        const p = e.target.getLatLng();
        if (!trabado.current) alMover.current(p.lat, p.lng);
      });
    } else {
      marca.current.setLatLng([la, ln]);
    }
  }, []);

  useEffect(() => {
    let cancelado = false;
    setFallo(false);
    loadLeaflet().then((Lf) => {
      if (cancelado || !el.current || mapa.current) return;
      L.current = Lf;
      const centro: [number, number] | null = tienePunto({ lat, lng }) ? [lat as number, lng as number]
        : ciudad && ciudad.lat != null && ciudad.lng != null ? [ciudad.lat, ciudad.lng] : null;
      const m = Lf.map(el.current, { attributionControl: true }).setView(centro ?? [-17.0, -64.5], centro ? 16 : 5);
      mapa.current = m;
      agregarTiles(Lf, m, { ciudad });
      // Un toque en el mapa marca (o corre) el punto: en el celular arrastrar es incómodo.
      m.on("click", (e: any) => {
        if (trabado.current) return;
        poner(e.latlng.lat, e.latlng.lng);
        alMover.current(e.latlng.lat, e.latlng.lng);
      });
      if (tienePunto({ lat, lng })) poner(lat as number, lng as number);
      setTimeout(() => m.invalidateSize(), 60);
    }).catch(() => { if (!cancelado) setFallo(true); });
    return () => {
      cancelado = true;
      if (mapa.current) { mapa.current.remove(); mapa.current = null; marca.current = null; }
    };
    // El mapa se arma una vez por ficha (o al reintentar); el punto se sigue en el efecto de abajo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intento]);

  useEffect(() => {
    if (tienePunto({ lat, lng })) {
      poner(lat as number, lng as number);
      mapa.current?.panTo([lat, lng]);
    }
  }, [lat, lng, poner]);

  if (fallo) {
    return (
      <div role="alert" style={{ padding: 12, fontSize: 13, color: "var(--txt-3)", border: "1px solid var(--border)", borderRadius: 8 }}>
        <Ic n="aviso" s={14} /> No se pudo cargar el mapa.{" "}
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => setIntento((n) => n + 1)}>
          <Ic n="actualizar" s={13} /> Reintentar
        </button>
      </div>
    );
  }
  return <div ref={el} role="application" aria-label="Mapa: arrastrá el punto o tocá para marcarlo"
              style={{ height: 220, width: "100%", borderRadius: 8, border: "1px solid var(--border)", background: "var(--panel)" }} />;
}

// ───────────────────────────── Ficha de revisión ─────────────────────────────

const ETIQUETAS: { c: keyof FormTarjeta; t: string; tipo?: string; auto?: string }[] = [
  { c: "nombre", t: "Nombre", auto: "off" },
  { c: "direccion", t: "Dirección", auto: "off" },
  { c: "telefono", t: "Teléfono", tipo: "tel" },
  { c: "whatsapp", t: "WhatsApp", tipo: "tel" },
  { c: "website", t: "Web", tipo: "url" },
  { c: "email", t: "Email", tipo: "email" },
];

export function FichaTarjeta({ item, rubros, ciudad, onCambio }: {
  item: ComercioImportado; rubros: Rubro[]; ciudad: Ciudad | null; onCambio: () => void;
}) {
  const { ciudades } = useAdminCiudad();
  const online = useOnline();
  const [it, setIt] = useState(item);
  const [form, setForm] = useState<FormTarjeta>(() => formDeItem(item));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [info, setInfo] = useState("");
  const [texto, setTexto] = useState(false);

  // Si la lista se vuelve a pedir, la fila nueva manda; lo que se estaba escribiendo se pierde
  // sólo cuando el servidor trae otra versión de la fila.
  const ultima = useRef(item);
  useEffect(() => {
    if (ultima.current === item) return;
    ultima.current = item;
    setIt(item); setForm(formDeItem(item));
  }, [item]);

  const revisable = it.estado === "nuevo";
  const parche = diffPatch(it, form);
  const sinGuardar = hayCambios(parche);
  const chip = chipUbicacion(it.ubicacion);
  const regla = puedePromover(it, form, sinGuardar);
  const ciudadDeLaFila = (it.ciudad_id ? ciudades.find((c) => c.id === it.ciudad_id) : null) ?? ciudad;

  function actualizar(nueva: ComercioImportado) {
    setIt(nueva); setForm(formDeItem(nueva));

  }

  async function correr(accion: () => Promise<void>) {
    setBusy(true); setErr(""); setInfo("");
    try { await accion(); }
    catch (e) { setErr(mensajeError(e, "No se pudo")); }
    finally { setBusy(false); }
  }

  const guardar = () => correr(async () => { actualizar(await editarImportado(it.id, parche)); setInfo("Cambios guardados."); });

  const moverPunto = (lat: number, lng: number) => correr(async () => {
    // Lo que está a medio escribir no se guarda con el punto: el punto va solo.
    const nueva = await editarImportado(it.id, { lat, lng });
    setIt((anterior) => ({ ...anterior, lat: nueva.lat, lng: nueva.lng, ubicacion: nueva.ubicacion ?? "confirmada" }));
    setInfo("Punto confirmado.");
  });

  const buscar = () => correr(async () => {
    const dir = form.direccion.trim();
    if (!dir) { setErr("Escribí la dirección para buscarla."); return; }
    const r = await ubicarImportado(it.id, dir);
    if (!r.encontrado) { setInfo(textoUbicar(r)); return; }
    setIt((a) => ({ ...a, lat: r.lat, lng: r.lng, ubicacion: "aproximada" }));
    setInfo(textoUbicar(r));
  });

  const promover = () => correr(async () => {
    await promoverImportado(it.id, { nombre: form.nombre.trim() || undefined, rubro_slug: form.rubro_slug || undefined, whatsapp: form.whatsapp.trim() || undefined });
    onCambio();
  });

  const descartar = () => {
    // Cancelar el cuadro devuelve null: no se descarta nada.
    const motivo = window.prompt("¿Por qué se descarta? (repetido, no es un comercio, datos ilegibles…)");
    if (motivo === null) return;
    void correr(async () => { await descartarImportado(it.id, motivo); onCambio(); });
  };

  const esTurismo = it.fuente === "turismo";
  const origen = esTurismo ? urlDeOrigen(it.texto_leido) : null;
  const colorChip = chip.tono === "ok" ? "ok" : chip.tono === "error" ? "error" : "aviso";

  return (
    <div style={{ padding: "14px 0", borderBottom: "1px solid var(--border)", opacity: busy ? 0.6 : 1 }} aria-busy={busy}>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-start" }}>
        {it.tiene_foto === true && <FotoTarjeta id={it.id} />}

        <div style={{ flex: "1 1 280px", minWidth: 0, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <Insignia icono={esTurismo ? "mapa" : "documentos"} tono="info">{esTurismo ? "Turismo" : "Tarjeta"}</Insignia>
            {it.lector && <span style={{ fontSize: 11.5, color: "var(--txt-3)" }}>leída con {it.lector === "gemini" ? "Gemini" : "Tesseract"}</span>}
            <Insignia icono={chip.icono} tono={colorChip}>{chip.texto}</Insignia>
          </div>

          {esTurismo && (
            <div style={{ fontSize: 12.5, color: "var(--txt-3)", overflowWrap: "anywhere" }}>
              <Ic n="mapa" s={14} /> De la página de turismo
              {origen && <>{" · "}<a href={origen} target="_blank" rel="noopener noreferrer" style={{ color: "var(--txt-2)" }}>Ver la página <Ic n="abrir" s={13} /></a></>}
            </div>
          )}

          {it.duplicado_de && (
            <Aviso tono="aviso"
                   accion={<a href={ENLACE_NEGOCIOS} target="_blank" rel="noopener" className="btn btn-ghost btn-sm" style={{ minHeight: 40 }}>
                     <Ic n="abrir" s={14} /> Ver en Negocios
                   </a>}>
              <b>Repetido:</b> {esTurismo ? "este negocio parece ser" : "un teléfono de esta tarjeta ya es"} del comercio <code style={{ fontSize: 12 }}>{it.duplicado_de}</code>.
            </Aviso>
          )}

          {revisable ? (
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
              {ETIQUETAS.map(({ c, t, tipo, auto }) => (
                <label key={c} style={{ display: "grid", gap: 3, fontSize: 12.5, color: "var(--txt-3)" }}>
                  {t}
                  <input type={tipo ?? "text"} value={form[c]} autoComplete={auto} disabled={busy}
                         onChange={(e) => setForm((f) => ({ ...f, [c]: e.target.value }))} style={CAMPO} />
                </label>
              ))}
              <label style={{ display: "grid", gap: 3, fontSize: 12.5, color: "var(--txt-3)" }}>
                Rubro
                <select value={form.rubro_slug} disabled={busy} style={CAMPO}
                        onChange={(e) => setForm((f) => ({ ...f, rubro_slug: e.target.value }))}>
                  <option value="">(otros)</option>
                  {rubros.map((r) => <option key={r.slug} value={r.slug}>{r.nombre}</option>)}
                </select>
              </label>
            </div>
          ) : (
            <div style={{ fontSize: 13.5 }}>
              <b>{it.nombre}</b>{it.direccion && ` · ${it.direccion}`}{it.telefono && ` · ${it.telefono}`}
              {it.motivo && <div style={{ fontSize: 12, color: "var(--txt-3)" }}>{it.motivo}</div>}
            </div>
          )}
        </div>
      </div>

      {revisable && (
        <div style={{ display: "grid", gap: 8, marginTop: 10 }}>
          <MapaPunto lat={it.lat} lng={it.lng} ciudad={ciudadDeLaFila} onMover={moverPunto} bloqueado={busy || !online} />
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={busy || !online} onClick={buscar}>
              <Ic n="buscar" s={15} /> Buscar la dirección
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={busy || !online || !sinGuardar} onClick={guardar}>
              <Ic n="si" s={15} /> Guardar cambios
            </button>
            <button type="button" className="btn btn-primary" style={BTN_GRANDE} disabled={busy || !online || !regla.ok}
                    aria-describedby={regla.ok ? undefined : `why-${it.id}`} onClick={promover}>
              <Ic n="mapa" s={15} /> Promover
            </button>
            <button type="button" className="link-more" disabled={busy || !online}
                    style={{ color: "var(--pink)", padding: "0 8px", fontSize: 13.5, minHeight: 44 }} onClick={descartar}>
              Descartar
            </button>
          </div>
          {!regla.ok && (
            <span id={`why-${it.id}`} style={{ fontSize: 12.5, color: "var(--txt-3)" }}><Ic n="dato" s={14} /> {regla.motivo}</span>
          )}
          {!online && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}><Ic n="aviso" s={14} /> Sin conexión: las acciones esperan a que vuelva la señal.</span>}
          {info && <span role="status" style={{ fontSize: 12.5, color: "var(--txt-2)" }}><Ic n="dato" s={14} /> {info}</span>}
          {err && <span role="alert" style={{ fontSize: 12.5, color: "salmon" }}><Ic n="aviso" s={14} /> {err}</span>}
        </div>
      )}

      {it.texto_leido && (
        <div style={{ marginTop: 8 }}>
          <button type="button" className="link-more" aria-expanded={texto} onClick={() => setTexto((v) => !v)}
                  style={{ padding: 0, fontSize: 12.5 }}>
            <Ic n={texto ? "arriba" : "abajo"} s={13} /> Texto leído
          </button>
          {texto && (
            <pre style={{ margin: "6px 0 0", padding: 10, background: "var(--panel)", borderRadius: 8, fontSize: 12,
                          whiteSpace: "pre-wrap", wordBreak: "break-word", color: "var(--txt-2)", maxHeight: 200, overflowY: "auto" }}>
              {it.texto_leido}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
