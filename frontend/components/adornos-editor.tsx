"use client";

// Ubicar las chalanas y los lapachos del mapa: clic para poner, arrastrar para
// mover, y los comercios de fondo para no pisarlos.
//
// Dónde va cada adorno no es una decisión técnica: hay que conocer Bermejo. Una
// chalana sobre tierra firme se lee como un error, y un lapacho encima de una
// cuadra llena de locales tapa justo lo que el mapa existe para mostrar. Por eso
// se marcan a mano acá y no quedan fijos en el código: se corrigen sin deploy.
//
// El mapa muestra los comercios en gris mientras editás. Es la única forma de
// ver si el lugar que elegiste está libre — que era el criterio pedido: poner
// los lapachos donde NO hay negocios.
import { useEffect, useRef, useState } from "react";
import { loadLeaflet } from "@/lib/mapa-visual";
import { adornoHTML, MEDIDAS, type Adorno } from "@/lib/adornos";
import { getComerciosMapa } from "@/lib/data";
import {
  adminListAdornos, adminCrearAdorno, adminUpdateAdorno, adminDeleteAdorno,
  type AdornoAdmin,
} from "@/lib/api";
import { BANDERAS, LAPACHOS } from "@/lib/adornos";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
const TIPOS: [Adorno["tipo"], string][] = [
  ["chalana", "⛵ Chalana"], ["lapacho", "🌳 Lapacho"], ["bandera", "🏳 Bandera"],
];

export function AdornosEditor() {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const LRef = useRef<any>(null);
  const capaRef = useRef<any>(null);
  const fondoRef = useRef<any>(null);
  const tipoRef = useRef<Adorno["tipo"]>("chalana");
  // Qué bandera se pone al hacer clic. Vive en un ref por lo mismo que el tipo:
  // el handler del mapa se registra una sola vez y no ve el estado nuevo.
  const varianteRef = useRef<string>("bo");

  const [items, setItems] = useState<AdornoAdmin[]>([]);
  const [tipo, setTipo] = useState<Adorno["tipo"]>("chalana");
  const [variante, setVariante] = useState<string>("bo");
  const [selId, setSelId] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  tipoRef.current = tipo;
  varianteRef.current = variante;

  const sel = items.find((a) => a.id === selId) || null;

  async function cargar() {
    setItems(await adminListAdornos().catch((e) => { setErr(String(e)); return []; }));
  }
  useEffect(() => { cargar(); }, []);

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      LRef.current = L;
      const map = L.map(elRef.current, { attributionControl: false }).setView(BERMEJO, 15);
      mapRef.current = map;
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2 }).addTo(map);

      fondoRef.current = L.layerGroup().addTo(map);
      capaRef.current = L.layerGroup().addTo(map);

      // Un clic en el mapa vacío crea uno del tipo elegido, ahí mismo.
      map.on("click", (e: any) => crear(e.latlng.lat, e.latlng.lng));

      // Los comercios de fondo, apagados: están para decidir dónde NO poner un
      // adorno, no para trabajar con ellos.
      getComerciosMapa().then((cs: any[]) => {
        if (cancelled) return;
        cs.forEach((c) => {
          if (c.lat == null || c.lng == null) return;
          L.circleMarker([c.lat, c.lng], {
            radius: 4, color: "#94a3b8", weight: 1, fillColor: "#94a3b8",
            fillOpacity: .5, interactive: false,
          }).addTo(fondoRef.current);
        });
      }).catch(() => {});

      setTimeout(() => map.invalidateSize(), 60);
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { pintar(); /* eslint-disable-next-line */ }, [items, selId]);

  function pintar() {
    const L = LRef.current, capa = capaRef.current;
    if (!L || !capa) return;
    capa.clearLayers();

    items.forEach((a, i) => {
      const m = MEDIDAS[a.tipo] ?? MEDIDAS.lapacho;
      const marca = L.marker([a.lat, a.lng], {
        icon: L.divIcon({
          className: a.id === selId ? "uk-adorno-sel" : "",
          html: adornoHTML(a as Adorno, i),
          iconSize: [m.w, m.h],
          iconAnchor: [m.w / 2, m.anclaY],
        }),
        draggable: true,        // arrastrar = mover, sin formularios de por medio
      });
      marca.on("click", (e: any) => {
        e.originalEvent?.stopPropagation();   // no crear otro encima
        setSelId(a.id);
      });
      marca.on("dragend", async (e: any) => {
        const p = e.target.getLatLng();
        setSelId(a.id);
        await guardar(a.id, { lat: p.lat, lng: p.lng });
      });
      capa.addLayer(marca);
    });
  }

  async function crear(lat: number, lng: number) {
    setErr(""); setBusy(true);
    try {
      const nuevo = await adminCrearAdorno({
        tipo: tipoRef.current, lat, lng,
        // Sólo las banderas la usan; en los demás va null y la base la ignora.
        // Las chalanas no tienen variedad. En lapacho, vacío significa "al
        // azar" y se guarda como null para que el color salga del id.
        variante: tipoRef.current === "chalana" ? null : (varianteRef.current || null),
      });
      setItems((xs) => [...xs, nuevo]);
      setSelId(nuevo.id);
    } catch (e: any) { setErr(String(e?.message || e)); }
    finally { setBusy(false); }
  }

  async function guardar(id: string, patch: Partial<AdornoAdmin>) {
    setErr("");
    // Se pinta el cambio antes de que responda el servidor: arrastrar tiene que
    // sentirse inmediato. Si falla, se recarga desde la base y el mapa vuelve a
    // decir la verdad.
    setItems((xs) => xs.map((a) => (a.id === id ? { ...a, ...patch } : a)));
    try { await adminUpdateAdorno(id, patch as any); }
    catch (e: any) { setErr(String(e?.message || e)); cargar(); }
  }

  async function borrar(id: string) {
    setErr("");
    setItems((xs) => xs.filter((a) => a.id !== id));
    if (selId === id) setSelId(null);
    try { await adminDeleteAdorno(id); }
    catch (e: any) { setErr(String(e?.message || e)); cargar(); }
  }

  // Chalanas no tienen variedad; banderas y lapachos sí, y usan el mismo campo.
  const opciones = (t: Adorno["tipo"]): [string, string][] =>
    t === "bandera" ? Object.entries(BANDERAS).map(([k, b]) => [k, b.nombre])
    : t === "lapacho" ? Object.entries(LAPACHOS).map(([k, l]) => [k, l.nombre])
    : [];

  const nChalanas = items.filter((a) => a.tipo === "chalana").length;
  const nLapachos = items.filter((a) => a.tipo === "lapacho").length;
  const nBanderas = items.filter((a) => a.tipo === "bandera").length;

  return (
    <div className="uk-adornos-editor">
      <p className="uk-hint">
        Elegí qué querés poner y tocá el mapa. Arrastrá para mover, tocá un
        adorno para seleccionarlo. Los puntos grises son los comercios: sirven
        para ver qué zonas están libres.
      </p>

      <div className="uk-adornos-barra">
        {TIPOS.map(([t, etiqueta]) => (
          <button key={t} className={tipo === t ? "active" : ""}
                  onClick={() => {
                    setTipo(t);
                    // La variante es de OTRO tipo: si no se resetea, el combo
                    // muestra una clave que su lista no tiene y el navegador
                    // elige la primera opción por su cuenta, sin avisar — se
                    // pondría una bandera de Bolivia creyendo elegir otra cosa.
                    setVariante(t === "bandera" ? "bo" : "");
                  }}>
            {etiqueta}
          </button>
        ))}
        {/* CUÁL bandera, antes de ponerla. Sin este control la variante existía
            en el estado pero no había forma de elegirla: todas salían Bolivia y
            había que corregirlas de a una después de puestas. */}
        {opciones(tipo).length > 0 && (
          <select value={variante} onChange={(e) => setVariante(e.target.value)}
                  className="uk-adornos-variante" aria-label="Cuál poner">
            {tipo === "lapacho" && <option value="">Al azar</option>}
            {opciones(tipo).map(([k, nombre]) => (
              <option key={k} value={k}>{nombre}</option>
            ))}
          </select>
        )}
        <span className="uk-adornos-conteo">
          {nChalanas} chalana{nChalanas === 1 ? "" : "s"} · {nLapachos} lapacho{nLapachos === 1 ? "" : "s"}
          {nBanderas > 0 && ` · ${nBanderas} bandera${nBanderas === 1 ? "" : "s"}`}
        </span>
      </div>

      {err && <p className="uk-error">{err}</p>}

      <div ref={elRef} className="uk-adornos-mapa" />

      {sel && (
        <div className="uk-adornos-sel">
          <b>
            {sel.tipo === "chalana" ? "⛵ Chalana"
             : sel.tipo === "bandera" ? `🏳 ${BANDERAS[sel.variante || "bo"]?.nombre ?? "Bandera"}`
             : sel.tipo === "lapacho" ? `🌳 Lapacho${sel.variante ? ` ${LAPACHOS[sel.variante]?.nombre ?? ""}` : ""}`
             : "🌳 Lapacho"}
          </b>
          <span className="uk-adornos-coords">
            {sel.lat.toFixed(5)}, {sel.lng.toFixed(5)}
          </span>

          <label>
            Tamaño
            <input type="range" min={0.4} max={3} step={0.05}
                   value={sel.escala ?? 1}
                   onChange={(e) => guardar(sel.id, { escala: Number(e.target.value) })} />
          </label>

          {opciones(sel.tipo).length > 0 && (
            <label>
              Cuál
              <select value={sel.variante ?? ""} className="uk-adornos-variante"
                      onChange={(e) => guardar(sel.id, { variante: e.target.value || null })}>
                {sel.tipo === "lapacho" && <option value="">Al azar</option>}
                {opciones(sel.tipo).map(([k, nombre]) => (
                  <option key={k} value={k}>{nombre}</option>
                ))}
              </select>
            </label>
          )}

          {sel.tipo === "chalana" && (
            <label>
              Giro
              <input type="range" min={-30} max={30} step={1}
                     value={sel.giro ?? 0}
                     onChange={(e) => guardar(sel.id, { giro: Number(e.target.value) })} />
            </label>
          )}

          <button className="uk-adornos-borrar" onClick={() => borrar(sel.id)} disabled={busy}>
            Borrar
          </button>
        </div>
      )}

      <p className="uk-hint">
        En el mapa público se dibujan por debajo de los pines y no reciben
        clics, así que nunca tapan un comercio. De lejos no se muestran.
      </p>
    </div>
  );
}
