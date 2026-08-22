/**
 * Adornos de identidad para el mapa y el sitio: chalanas, lapachos y el uruku.
 *
 * Bermejo tiene tres cosas que no tiene ninguna otra ciudad del directorio: las
 * chalanas que cruzan el río hacia Argentina, los lapachos floreciendo en las
 * calles, y el uruku que le da el nombre a la marca. Dibujarlas hace que el mapa
 * se reconozca como Bermejo y no como cualquier grilla de calles.
 *
 * UNA REGLA MANDA SOBRE TODAS: el mapa existe para mostrar comercios. Los
 * adornos van en un panel PROPIO, por debajo de los pines, sin capturar clics y
 * apagados de lejos. Si alguna vez compiten con un local por la atención, el
 * adorno es lo que sobra — no al revés.
 *
 * Por eso también son pocos y están quietos: nada de animaciones ni de repetir
 * el mismo ícono veinte veces. Un adorno que se nota es un adorno que estorba.
 */

/** Un adorno ubicado. Vive en la tabla `mapa_adornos`, no acá: dónde va cada
 * uno no es una decisión técnica, hay que conocer la ciudad. Una chalana sobre
 * tierra firme se lee como un error, y un lapacho encima de una cuadra llena de
 * locales tapa justo lo que el mapa existe para mostrar. Se marcan haciendo
 * clic en el mapa desde el admin y se corrigen sin deploy. */
export type Adorno = {
  id: string;
  tipo: "chalana" | "lapacho";
  lat: number;
  lng: number;
  /** Grados. Las chalanas quedan mejor si no están todas alineadas. */
  giro?: number | null;
  /** 1 = tamaño base. Variarlo evita el efecto de estampilla repetida. */
  escala?: number | null;
};

/**
 * Debajo de este zoom no se dibuja ninguno. De lejos el mapa tiene que ser
 * comercios y nada más: es el momento en que el comprador está buscando, no
 * mirando.
 */
export const ZOOM_MIN_ADORNOS = 15;

/**
 * Las chalanas del río llevan toldos a rayas de colores fuertes. Cada una toma
 * un color distinto de esta lista para que el grupo se vea como en la foto y no
 * como tres copias del mismo bote.
 */
const TOLDOS = ["#e11d48", "#2563eb", "#f59e0b"];

/** Chalana vista de costado: casco, toldo a rayas y su reflejo en el agua. */
function chalanaSVG(i: number): string {
  const toldo = TOLDOS[i % TOLDOS.length];
  return `<svg viewBox="0 0 64 40" width="64" height="40" fill="none" aria-hidden="true">
    <path d="M6 26c6 5 14 7 26 7s20-2 26-7l-4 8c-5 3-13 4-22 4s-17-1-22-4z" fill="#0f172a" opacity=".18"/>
    <path d="M8 20h48l-5 9c-4 2-11 3-19 3s-15-1-19-3z" fill="#8b5e34"/>
    <path d="M8 20h48l-1.5 2.6H9.5z" fill="#a4703f"/>
    <rect x="16" y="9" width="32" height="3" rx="1.5" fill="${toldo}"/>
    <path d="M18 12h28v6H18z" fill="${toldo}" opacity=".55"/>
    <path d="M22 12v6M28 12v6M34 12v6M40 12v6" stroke="#fff" stroke-width="1.6" opacity=".7"/>
    <path d="M17 12v8M47 12v8" stroke="#7c4a21" stroke-width="1.6"/>
  </svg>`;
}

/**
 * Lapacho en flor. El color varía porque en Bermejo florecen rosados, amarillos
 * y blancos, y verlos todos iguales sería menos cierto que verlos distintos.
 */
const FLORES = ["#ec4899", "#f59e0b", "#e879f9", "#f472b6"];

function lapachoSVG(i: number): string {
  const flor = FLORES[i % FLORES.length];
  return `<svg viewBox="0 0 44 52" width="44" height="52" fill="none" aria-hidden="true">
    <path d="M21 50v-16" stroke="#6b4423" stroke-width="3.2" stroke-linecap="round"/>
    <path d="M21 38l-6-6M21 40l7-7" stroke="#6b4423" stroke-width="2.4" stroke-linecap="round"/>
    <circle cx="22" cy="16" r="11" fill="${flor}" opacity=".9"/>
    <circle cx="12" cy="22" r="7" fill="${flor}" opacity=".8"/>
    <circle cx="32" cy="22" r="7.5" fill="${flor}" opacity=".8"/>
    <circle cx="17" cy="9" r="5.5" fill="${flor}" opacity=".95"/>
    <circle cx="29" cy="11" r="5" fill="${flor}" opacity=".95"/>
  </svg>`;
}

export function adornoHTML(a: Adorno, i: number): string {
  const svg = a.tipo === "chalana" ? chalanaSVG(i) : lapachoSVG(i);
  const t = [`scale(${a.escala ?? 1})`, a.giro ? `rotate(${a.giro}deg)` : ""]
    .filter(Boolean).join(" ");
  return `<div class="uk-adorno" style="transform:${t}">${svg}</div>`;
}

/** Tamaño del ícono en pantalla, para anclarlo bien. Las chalanas se apoyan
 *  sobre el agua y los lapachos sobre su tronco, así que ninguno se centra. */
export const MEDIDAS = {
  chalana: { w: 64, h: 40, anclaY: 30 },
  lapacho: { w: 44, h: 52, anclaY: 50 },
} as const;

/**
 * El uruku: la vaina del achiote abriéndose y soltando sus semillas, que es el
 * logo de la marca. Se usa como marca de agua —en el pie de página, en vacíos—
 * así que se dibuja en una sola tinta y hereda el color de donde esté con
 * `currentColor`: sirve igual en tema claro y oscuro sin mantener dos versiones.
 */
export const URUKU_SVG = `<svg viewBox="0 0 48 64" fill="none" aria-hidden="true">
  <circle cx="24" cy="4" r="2.6" fill="currentColor"/>
  <circle cx="16" cy="9" r="2.6" fill="currentColor"/>
  <circle cx="24" cy="11" r="2.6" fill="currentColor"/>
  <circle cx="32" cy="9" r="2.6" fill="currentColor"/>
  <circle cx="20" cy="16" r="2.4" fill="currentColor"/>
  <circle cx="28" cy="16" r="2.4" fill="currentColor"/>
  <circle cx="12" cy="15" r="2.4" fill="currentColor"/>
  <circle cx="36" cy="15" r="2.4" fill="currentColor"/>
  <circle cx="24" cy="21" r="2.4" fill="currentColor"/>
  <circle cx="16" cy="22" r="2.2" fill="currentColor"/>
  <circle cx="32" cy="22" r="2.2" fill="currentColor"/>
  <circle cx="10" cy="23" r="2.2" fill="currentColor"/>
  <circle cx="38" cy="23" r="2.2" fill="currentColor"/>
  <path d="M24 26c7 7 11 14 11 20 0 6.5-5 11-11 11s-11-4.5-11-11c0-6 4-13 11-20z" fill="currentColor"/>
  <path d="M24 58v5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" opacity=".7"/>
</svg>`;
