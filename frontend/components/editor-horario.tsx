"use client";

import { abiertoAhora } from "@/lib/horario";

/**
 * El editor de horario compartido: lo usan el panel del admin y la pantalla
 * «Completar comercio» del agente de campo.
 *
 * HORARIO: el campo más caro del proyecto.
 * Son cientos de comercios sin él, y es el dato que decide si alguien camina
 * hasta el local o no. Escribirlo a mano cientos de veces no lo hace nadie, así
 * que acá se toca en vez de escribirse. «Igual que el anterior» es el que más
 * rinde: en una cuadra los locales abren casi todos a la misma hora, y yendo de
 * a uno el anterior suele ser el vecino.
 */

const ULTIMO_HORARIO = "uruku_ultimo_horario";

export function ultimoHorario(): string {
  if (typeof window === "undefined") return "";
  try { return localStorage.getItem(ULTIMO_HORARIO) ?? ""; } catch { return ""; }
}

/** Se llama al guardar un horario, para el «igual que el anterior» de la ficha
 *  siguiente. En localStorage y no en estado: la pantalla se remonta en cada
 *  comercio, así que cualquier estado propio se pierde justo cuando hace falta. */
export function recordarUltimoHorario(horario: string): void {
  const h = horario.trim();
  if (!h) return;
  try { localStorage.setItem(ULTIMO_HORARIO, h); } catch { /* modo privado */ }
}

/** Los horarios que de verdad se repiten en Bermejo.
 *
 *  El texto va en el formato que `abiertoAhora` entiende: los días de un lado y
 *  los dos turnos en el mismo segmento, para que la tarde no se aplique también
 *  al domingo. Un horario que el parser no entiende es peor que ninguno —el
 *  comprador no ve "Abierto ahora" y nadie se entera de por qué. */
export const HORARIOS_FRECUENTES: { label: string; texto: string }[] = [
  { label: "8-12 · 14:30-20 (L-S)", texto: "Lun-Sáb 8:00-12:00 y 14:30-20:00" },
  { label: "8-12 · 14:30-20 + Dom AM", texto: "Lun-Sáb 8:00-12:00 y 14:30-20:00 · Dom 8:00-12:00" },
  { label: "Corrido 8-20 (L-S)", texto: "Lun-Sáb 8:00-20:00" },
  { label: "Corrido 9-21 (todos)", texto: "Todos los días 9:00-21:00" },
  { label: "9-13 · 15-19 (L-V)", texto: "Lun-Vie 9:00-13:00 y 15:00-19:00" },
  { label: "24 horas", texto: "Todos los días 0:00-24:00" },
  // Los de la noche. Cruzan la medianoche, que el parser recién entiende desde
  // que existen bares y boliches en la taxonomía.
  { label: "Noche 21-4 (V y S)", texto: "Vie-Sáb 21:00-4:00" },
  { label: "Noche 20-2 (Mié-Dom)", texto: "Mié-Dom 20:00-2:00" },
];

/** El campo de texto, los atajos de un toque y lo que el sitio va a entender de
 *  lo que quedó escrito. El rótulo («Horario») lo pone quien lo usa. */
export function EditorHorario({ value, onChange, inputId }: {
  value: string;
  onChange: (v: string) => void;
  inputId?: string;
}) {
  const ultimo = ultimoHorario();
  return (
    <>
      <input id={inputId} className="adm-input" style={{ marginTop: 4 }} value={value}
        onChange={(e) => onChange(e.target.value)} placeholder="Lun-Sáb 9-20 · Dom 10-14" />
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>
        {ultimo && ultimo !== value && (
          <button type="button" className="mchip" style={{ cursor: "pointer", borderColor: "var(--neon)", color: "var(--neon)" }}
            onClick={() => onChange(ultimo)}
            title={ultimo}>
            Igual que el anterior
          </button>
        )}
        {HORARIOS_FRECUENTES.map((h) => (
          <button type="button" key={h.texto} className={`mchip ${value === h.texto ? "active" : ""}`}
            style={{ cursor: "pointer" }} title={h.texto}
            onClick={() => onChange(value === h.texto ? "" : h.texto)}>
            {h.label}
          </button>
        ))}
        {value && (
          <button type="button" className="mchip" style={{ cursor: "pointer" }} onClick={() => onChange("")}>
            Limpiar
          </button>
        )}
      </div>
      {/* Lo que el sitio va a entender de lo que quedó escrito. Si dice
          "no se entiende", el comprador no va a ver "Abierto ahora" —
          y eso hay que saberlo ACÁ, no descubrirlo en la ficha. */}
      {value.trim() && (
        <div style={{ marginTop: 6, fontSize: 11.5,
                      color: abiertoAhora(value).estado === "desconocido" ? "var(--amber)" : "var(--txt-3)" }}>
          {abiertoAhora(value).estado === "desconocido"
            ? "No se entiende: el sitio no va a poder decir si está abierto"
            : `Ahora mismo: ${abiertoAhora(value).estado}`}
        </div>
      )}
    </>
  );
}
