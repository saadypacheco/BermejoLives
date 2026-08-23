"use client";

// Pedir el número de WhatsApp también DESPUÉS de registrar el local.
//
// El campo sigue estando en el formulario de alta, y esto no lo reemplaza: son
// dos momentos distintos de la misma visita. A veces el dueño está ahí y lo
// dicta enseguida —ese es el camino corto, el formulario—; otras veces el
// agente releva el local primero —foto, ubicación, lo que ve en la vidriera— y
// recién después se pone a hablar, y el número aparece al final de esa charla,
// cuando el formulario ya quedó atrás.
//
// Si vino cargado desde el alta, esto lo muestra guardado con opción de
// corregirlo: el agente pudo tipearlo mal, o la persona puede dar otro número
// cuando ve para qué se lo están pidiendo.
//
// EL PROBLEMA DE CONFIANZA
//
// Cuando alguien dicta su número mira la pantalla donde lo estás anotando. Un
// campo de texto suelto no dice nada: no se ve para qué es ni quién lo va a
// usar, y ahí es donde la persona duda.
//
// La respuesta NO es disfrazar esto de WhatsApp. Si el comerciante nota que
// parece WhatsApp y no lo es, la desconfianza que genera es peor que la que
// evita. Lo que sí tranquiliza sin fingir nada es MOSTRARLE QUÉ VA A PASAR: el
// mensaje que le va a llegar de un comprador, con su número escrito arriba tal
// como quedará guardado. Verde de WhatsApp e ícono, sí — pero como destino
// declarado, que es lo que son, no como imitación.
//
// Y la letra chica dice la verdad: los compradores le escriben directo y URUKU
// no ve esas conversaciones. No decimos "tu número no se publica", porque no
// sería cierto — el botón de WhatsApp de la ficha lleva a ese número.
import { useState } from "react";
import { editarComercioAgente } from "@/lib/campo";

const PREFIJOS: [string, string, string][] = [
  ["591", "🇧🇴", "Bolivia"],
  ["549", "🇦🇷", "Argentina"],
];

/** Cómo se ve el número una vez guardado, para que la persona lo verifique de
 *  un vistazo. Agrupado como se dicta, no como se almacena. */
function formatear(prefijo: string, cel: string): string {
  const d = cel.replace(/\D/g, "");
  if (!d) return "";
  const grupos = d.length > 4 ? `${d.slice(0, d.length - 4)} ${d.slice(-4)}` : d;
  return `+${prefijo} ${grupos}`;
}

/** Parte un número guardado en prefijo + resto. Se guarda pegado (5917xxxxxxx),
 *  pero para mostrarlo y para poder corregirlo hay que volver a separarlo. */
function separar(numero: string, porDefecto: string): [string, string] {
  const d = (numero || "").replace(/\D/g, "");
  for (const [p] of PREFIJOS) {
    if (d.startsWith(p)) return [p, d.slice(p.length)];
  }
  return [porDefecto, d];
}

export function CapturaWhatsapp({
  comercioId, nombre, prefijoInicial = "591", valorInicial, onGuardado,
}: {
  comercioId: string;
  nombre?: string | null;
  prefijoInicial?: string;
  /** Número ya cargado en el formulario de alta. Arranca mostrándolo guardado,
   *  con la opción de corregirlo: el agente puede haberlo tipeado mal o la
   *  persona puede dar otro cuando ve para qué es. */
  valorInicial?: string | null;
  onGuardado?: (whatsapp: string) => void;
}) {
  const [pref0, cel0] = separar(valorInicial || "", prefijoInicial);
  const [prefijo, setPrefijo] = useState(pref0);
  const [cel, setCel] = useState(cel0);
  const [guardado, setGuardado] = useState<string | null>(valorInicial || null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const digitos = cel.replace(/\D/g, "");
  // Los celulares de la zona tienen 8 dígitos en Bolivia y 10 en Argentina. Con
  // menos de 7 no se habilita: es un número a medio dictar, no uno corto.
  const completo = digitos.length >= 7;
  const bonito = formatear(prefijo, cel);

  async function guardar() {
    if (!completo || busy) return;
    setErr(""); setBusy(true);
    try {
      const numero = prefijo + digitos;
      await editarComercioAgente(comercioId, { whatsapp: numero });
      setGuardado(numero);
      onGuardado?.(numero);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo guardar");
    } finally { setBusy(false); }
  }

  if (guardado) {
    return (
      <div className="wa-card wa-card--ok">
        <div className="wa-ok-ic">✓</div>
        <div>
          <b>Número guardado</b>
          <div className="wa-ok-num">{formatear(prefijo, digitos)}</div>
        </div>
        <button className="wa-editar" onClick={() => { setGuardado(null); }}>
          Cambiar
        </button>
      </div>
    );
  }

  return (
    <div className="wa-card">
      <div className="wa-head">
        <span className="wa-ic" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M17.5 14.4c-.3-.2-1.8-.9-2-1s-.5-.2-.7.1-.8 1-1 1.2-.4.2-.7 0a8 8 0 0 1-2.4-1.5 9 9 0 0 1-1.6-2c-.2-.4 0-.5.1-.7l.5-.6.3-.5v-.5l-1-2.3c-.2-.6-.5-.5-.7-.5h-.6c-.2 0-.5.1-.8.4-.3.3-1 1-1 2.5s1 2.9 1.2 3.1a11.4 11.4 0 0 0 4.4 3.9c1.6.6 2.2.7 3 .6.5 0 1.6-.7 1.9-1.3s.3-1.2.2-1.3l-.5-.3z"/>
            <path d="M12 2a10 10 0 0 0-8.6 15L2 22l5.2-1.4A10 10 0 1 0 12 2zm0 18.2c-1.6 0-3.1-.4-4.4-1.2l-.3-.2-3.1.8.8-3-.2-.3A8.2 8.2 0 1 1 12 20.2z"/>
          </svg>
        </span>
        <div>
          <b>¿Tiene WhatsApp el local?</b>
          <p>Así los compradores le escriben directo desde URUKU.</p>
        </div>
      </div>

      <div className="wa-input-row">
        <select className="wa-prefijo" value={prefijo}
                onChange={(e) => setPrefijo(e.target.value)} aria-label="País">
          {PREFIJOS.map(([p, bandera, pais]) => (
            <option key={p} value={p}>{bandera} +{p} · {pais}</option>
          ))}
        </select>
        <input
          className="wa-numero"
          // Teclado numérico en el celular: se dicta un número y se tipea rápido.
          type="tel" inputMode="numeric" autoComplete="off"
          value={cel}
          onChange={(e) => setCel(e.target.value)}
          placeholder="Número de celular"
          aria-label="Número de celular"
        />
      </div>

      {/* La previsualización: qué le va a llegar. Es lo que responde la pregunta
          que la persona no siempre hace en voz alta. */}
      <div className="wa-preview" aria-hidden={!completo}>
        <div className="wa-preview-top">
          <span className="wa-preview-avatar">🛍️</span>
          <div>
            <b>{nombre && !/^comercio/i.test(nombre) ? nombre : "Tu local"}</b>
            <span>{completo ? bonito : "—"}</span>
          </div>
        </div>
        <div className="wa-burbuja">
          Hola! Vi tu local en URUKU y quería consultar por un producto 👋
          <i className="wa-hora">ahora</i>
        </div>
        <p className="wa-nota">
          Así le va a llegar el mensaje de un comprador. La conversación es
          entre ustedes dos: URUKU no la ve ni participa.
        </p>
      </div>

      {err && <p className="wa-err">{err}</p>}

      <button className="wa-guardar" onClick={guardar} disabled={!completo || busy}>
        {busy ? "Guardando…" : completo ? `Guardar ${bonito}` : "Escribí el número"}
      </button>

      <p className="wa-saltar">
        Si no te lo quiere dar, dejalo así: el local igual queda en el mapa y el
        número se puede sumar después.
      </p>
    </div>
  );
}
