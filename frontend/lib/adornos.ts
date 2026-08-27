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
  tipo: "chalana" | "lapacho" | "bandera";
  /** Sólo para `bandera`: cuál. La clave de BANDERAS ('ar', 'bo', …). */
  variante?: string | null;
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

/**
 * Las chalanas se dibujan a un CUARTO del tamaño con el que nacieron (64×40 →
 * 16×10). Eran demasiado grandes al lado de un pin de comercio, y eso rompía la
 * regla que gobierna los adornos: el mapa existe para mostrar comercios, así
 * que un adorno que compite por la atención es un adorno que sobra.
 *
 * El viewBox NO cambia — el dibujo es el mismo, sólo se muestra más chico. Y el
 * ancla de MEDIDAS baja en la misma proporción, si no la chalana quedaría
 * flotando lejos del punto donde la pusieron.
 */
const CHALANA_W = 16, CHALANA_H = 10;

/** Chalana vista de costado: casco, toldo a rayas y su reflejo en el agua. */
function chalanaSVG(i: number): string {
  const toldo = TOLDOS[i % TOLDOS.length];
  return `<svg viewBox="0 0 64 40" width="${CHALANA_W}" height="${CHALANA_H}" fill="none" aria-hidden="true">
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
 * Lapacho en flor, dibujado mirando fotos y no de memoria.
 *
 * El dibujo anterior era un tronco con cinco círculos encima: leía como
 * chupetín. Un lapacho de verdad tiene tres rasgos que lo hacen reconocible de
 * lejos, y son los que se dibujan acá:
 *
 *   1. La copa es MÁS ANCHA QUE ALTA y en domo. Casi ningún otro árbol de la
 *      calle tiene esa proporción; es lo primero que lo delata.
 *   2. El tronco es oscuro y se abre en ramas gruesas que se ven ENTRE las
 *      flores. Una copa maciza parece un arbusto.
 *   3. Los pétalos caídos alfombran el piso alrededor. En la foto es la mitad
 *      del efecto: el suelo se tiñe del mismo color que el árbol.
 *
 * Por eso el viewBox pasó de 44×52 (más alto que ancho) a 48×40.
 */

/**
 * Las variedades de lapacho, con su color y —si existe— su FOTO.
 *
 * FOTO O DIBUJO
 * =============
 *
 * Si la variedad tiene `foto`, el mapa muestra la foto. Si no, cae al dibujo.
 * No es un plan B teórico: mientras no estén las cuatro imágenes, el mapa tiene
 * que seguir funcionando con lo que hay, y una foto que falta no puede dejar un
 * ícono roto sobre el mapa.
 *
 * Las fotos viven en `public/adornos/` como archivos estáticos del repo: son
 * cuatro, no cambian nunca, y así el service worker las cachea con el resto del
 * sitio en vez de pedirlas por red cada vez.
 *
 * EL COLOR ES ESTABLE, NO POR ORDEN
 * =================================
 *
 * Antes la variedad salía de la POSICIÓN del adorno en la lista, así que borrar
 * un lapacho le cambiaba el color a todos los que venían después. Ahora se elige
 * en el editor (`variante`) y, si no se eligió, sale del id — que no cambia.
 */
export type Lapacho = { nombre: string; flor: string; borde?: string; foto?: string };

export const LAPACHOS: Record<string, Lapacho> = {
  rosa:     { nombre: "Rosa",        flor: "#e8559b" },
  amarillo: { nombre: "Amarillo",    flor: "#f2b705" },
  magenta:  { nombre: "Rosa fuerte", flor: "#c92f7c" },
  // El blanco lleva un borde apenas visible: sin él desaparece sobre el fondo
  // claro del mapa — puesto y no visible, como pasó con el combo de banderas.
  blanco:   { nombre: "Blanco",      flor: "#fbeff3", borde: "#e9c9d6" },
};

const CLAVES_LAPACHO = Object.keys(LAPACHOS);

/** La variedad de ESTE lapacho: la elegida, o una estable derivada del id. */
function variedadLapacho(a: Adorno): Lapacho {
  if (a.variante && LAPACHOS[a.variante]) return LAPACHOS[a.variante];
  let h = 0;
  for (const c of a.id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return LAPACHOS[CLAVES_LAPACHO[h % CLAVES_LAPACHO.length]];
}

function lapachoSVG(a: Adorno): string {
  const v = variedadLapacho(a);
  // La foto manda cuando está. Se dibuja con el mismo alto que el SVG para que
  // el ancla siga cayendo en la base del tronco y el árbol no quede flotando.
  if (v.foto) {
    return `<img src="${v.foto}" width="48" height="40" alt="" aria-hidden="true"
                 style="display:block;object-fit:contain;object-position:bottom">`;
  }
  const { flor, borde } = v;
  const trazo = borde ? ` stroke="${borde}" stroke-width=".6"` : "";
  return `<svg viewBox="0 0 48 40" width="48" height="40" fill="none" aria-hidden="true">
    <g fill="${flor}" opacity=".45">
      <ellipse cx="14" cy="37.5" rx="4.5" ry="1.1"/>
      <ellipse cx="24" cy="38.6" rx="7" ry="1.3"/>
      <ellipse cx="35" cy="37.2" rx="4" ry="1"/>
    </g>
    <path d="M24 40V27" stroke="#4a3324" stroke-width="2.8" stroke-linecap="round"/>
    <path d="M24 28c-4-2-7-4-9.5-6.5M24 28c4-2 7-4 9.5-6M24 29V19"
          stroke="#4a3324" stroke-width="1.9" stroke-linecap="round"/>
    <path d="M17 23c-2.5-1.5-4-3-5-4.5M31 23c2.5-1.5 4-3 5-4.5"
          stroke="#4a3324" stroke-width="1.2" stroke-linecap="round" opacity=".8"/>
    <g fill="${flor}"${trazo}>
      <ellipse cx="24" cy="14" rx="11.5" ry="9"/>
      <circle cx="11" cy="18" r="7"/>
      <circle cx="37" cy="17.5" r="7.5"/>
      <circle cx="16" cy="8" r="6"/>
      <circle cx="32" cy="8.5" r="5.5"/>
      <circle cx="24" cy="5.5" r="5"/>
      <circle cx="6" cy="22" r="4.5"/>
      <circle cx="42" cy="21.5" r="4.5"/>
    </g>
    <g fill="#000" opacity=".07">
      <circle cx="13" cy="22" r="5"/>
      <circle cx="35" cy="21.5" r="5"/>
    </g>
  </svg>`;
}

/* ─────────────────────────── Banderas ───────────────────────────
 *
 * Bermejo es frontera: el puente cruza a Aguas Blancas y media ciudad compra
 * de los dos lados. Una bandera en el paso dice eso mejor que un cartel.
 *
 * Se declaran como DATO —franjas de color y un emblema opcional— y no como SVG
 * escrito a mano. Dos razones: una bandera mal dibujada es peor que ninguna
 * (queda como si fuera cierta y nadie la revisa, igual que un nombre inventado
 * en la ficha de un comercio), y así corregir un color es cambiar una línea en
 * vez de reescribir un dibujo.
 */
export type Bandera = { nombre: string; franjas: string[]; emblema?: "sol" | "escudo" };

export const BANDERAS: Record<string, Bandera> = {
  bo: { nombre: "Bolivia", franjas: ["#D52B1E", "#F9E300", "#007934"] },
  ar: { nombre: "Argentina", franjas: ["#75AADB", "#FFFFFF", "#75AADB"], emblema: "sol" },

  // Departamentales y municipales, sacadas de las fotos que pasó el equipo.
  // Si alguna está mal, se corrige acá y en ningún otro lado.
  bermejo: { nombre: "Bermejo", franjas: ["#009739", "#FFFFFF", "#009739"] },
  tarija: { nombre: "Tarija", franjas: ["#DA121A", "#FFFFFF"] },
  "santa-cruz": { nombre: "Santa Cruz", franjas: ["#009739", "#FFFFFF", "#009739"] },
  "la-paz": { nombre: "La Paz", franjas: ["#D52B1E", "#007934"], emblema: "escudo" },
};

const BANDERA_W = 26, BANDERA_H = 17;

function banderaSVG(variante: string | null | undefined): string {
  const b = BANDERAS[variante || "bo"] ?? BANDERAS.bo;
  const alto = BANDERA_H / b.franjas.length;
  const franjas = b.franjas
    .map((c, i) => `<rect x="3" y="${(i * alto).toFixed(2)}" width="${BANDERA_W - 3}" height="${alto.toFixed(2)}" fill="${c}"/>`)
    .join("");
  // El sol de mayo, simplificado: a 26 px de ancho los treinta y dos rayos son
  // una mancha. Un disco con ocho puntas se lee como sol y no como error.
  // El escudo de La Paz, a 26 px de ancho, es una mancha de cuatro píxeles: se
  // dibuja un blasón dorado que se LEE como escudo. Fingir el detalle real sería
  // dibujar mal algo que nadie después revisa.
  const escudo = b.emblema === "escudo"
    ? `<g transform="translate(${(3 + (BANDERA_W - 3) / 2).toFixed(1)},${(BANDERA_H / 2).toFixed(1)})">
         <path d="M-3-3.4h6v3.2c0 2.2-1.4 3.6-3 4.4-1.6-.8-3-2.2-3-4.4z"
               fill="#E8B33A" stroke="#8a6a12" stroke-width=".5"/>
       </g>`
    : "";
  const sol = b.emblema === "sol"
    ? `<g transform="translate(${(3 + (BANDERA_W - 3) / 2).toFixed(1)},${(BANDERA_H / 2).toFixed(1)})">
         <circle r="2.6" fill="#F6B40E"/>
         <path d="M0-4.6 0.9-2.6 3.3-3.3 2.6-0.9 4.6 0 2.6 0.9 3.3 3.3 0.9 2.6 0 4.6 -0.9 2.6 -3.3 3.3 -2.6 0.9 -4.6 0 -2.6-0.9 -3.3-3.3 -0.9-2.6z"
               fill="#F6B40E" opacity=".85"/>
       </g>`
    : "";
  return `<svg viewBox="0 0 ${BANDERA_W} ${BANDERA_H + 6}" width="${BANDERA_W}" height="${BANDERA_H + 6}" fill="none" aria-hidden="true">
    <rect x="0" y="0" width="2.2" height="${BANDERA_H + 6}" rx="1.1" fill="#7a6a55"/>
    ${franjas}
    <rect x="3" y="0" width="${BANDERA_W - 3}" height="${BANDERA_H}" fill="none" stroke="#0f172a" stroke-width=".6" opacity=".25"/>
    ${sol}${escudo}
  </svg>`;
}

export function adornoHTML(a: Adorno, i: number): string {
  const svg = a.tipo === "chalana" ? chalanaSVG(i)
            : a.tipo === "bandera" ? banderaSVG(a.variante)
            : lapachoSVG(a);
  const t = [`scale(${a.escala ?? 1})`, a.giro ? `rotate(${a.giro}deg)` : ""]
    .filter(Boolean).join(" ");
  return `<div class="uk-adorno" style="transform:${t}">${svg}</div>`;
}

/** Tamaño del ícono en pantalla, para anclarlo bien. Las chalanas se apoyan
 *  sobre el agua y los lapachos sobre su tronco, así que ninguno se centra. */
export const MEDIDAS = {
  chalana: { w: CHALANA_W, h: CHALANA_H, anclaY: 7.5 },   // era 64×40 / ancla 30
  lapacho: { w: 48, h: 40, anclaY: 39 },   // era 44×52: la copa real es más ancha que alta
  bandera: { w: BANDERA_W, h: BANDERA_H + 6, anclaY: BANDERA_H + 6 },
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
