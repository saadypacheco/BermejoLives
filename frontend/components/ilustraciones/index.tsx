import { useId } from "react";
import type { IlustracionId } from "@/lib/planes-ciudad-pure";

/**
 * El catálogo fijo de ilustraciones de «Qué podés hacer en {ciudad}» y de la página de sabores
 * (docs/home-ciudades.md §12 y §15). Son dibujos propios, planos y con los colores de la marca: sin fotos de
 * terceros ni IA. Cada una trae su propio fondo, así que se ven igual en los dos temas, y es decorativa
 * (`aria-hidden`): el título va escrito al lado.
 *
 * Las de 170×110 van en las tarjetas chicas; la de la ruta del vino (358×440) es la tarjeta grande. Los degradés
 * llevan un id único por dibujo (`useId`): la misma ilustración puede estar dos veces en la página.
 */

/** Las del catálogo y las tres de la página de sabores (el plato reusa la olla de «Sabores»). */
export type IdIlustracion = IlustracionId | "plato" | "reposteria" | "bebida";

type Propiedades = { className?: string };

/** El `id` de `useId` trae «:», que dentro de `url(#…)` es incómodo: se le sacan. */
function useIdSvg(): string {
  return useId().replace(/[^a-zA-Z0-9_-]/g, "");
}

function Marco({ ancho, alto, className, children, slice = false }: {
  ancho: number; alto: number; className?: string; children: React.ReactNode; slice?: boolean;
}) {
  return (
    <svg viewBox={`0 0 ${ancho} ${alto}`} className={className} aria-hidden="true" focusable="false"
         preserveAspectRatio={slice ? "xMidYMid slice" : "xMidYMid meet"}>
      {children}
    </svg>
  );
}

/** La ruta del vino y el singani: colinas con viñedos al atardecer y el recorrido dibujado (no es un mapa real). */
function IlusVino({ className }: Propiedades) {
  const k = useIdSvg();
  return (
    <Marco ancho={358} alto={440} className={className} slice>
      <defs>
        <linearGradient id={`${k}cielo`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3B1D45" /><stop offset=".55" stopColor="#B4495E" /><stop offset="1" stopColor="#F2A65A" /></linearGradient>
        <linearGradient id={`${k}col1`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3E7A4A" /><stop offset="1" stopColor="#244B33" /></linearGradient>
        <linearGradient id={`${k}col2`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#2F6440" /><stop offset="1" stopColor="#173525" /></linearGradient>
        <linearGradient id={`${k}sombra`} x1="0" y1="0" x2="0" y2="1"><stop offset=".55" stopColor="#140B18" stopOpacity="0" /><stop offset="1" stopColor="#140B18" stopOpacity=".9" /></linearGradient>
      </defs>
      <rect width="358" height="440" fill={`url(#${k}cielo)`} />
      <circle cx="268" cy="96" r="34" fill="#F6D38A" opacity=".95" />
      <circle cx="268" cy="96" r="52" fill="#F6D38A" opacity=".15" />
      <path d="M0 132 L40 104 L70 118 L110 84 L150 112 L190 92 L230 116 L270 98 L310 120 L358 100 V170 H0Z" fill="#6E3557" opacity=".75" />
      <path d="M0 160 C60 128 120 150 180 136 C240 122 300 150 358 132 V440 H0Z" fill={`url(#${k}col1)`} />
      <g stroke="#7FB069" strokeWidth="2.4" strokeLinecap="round" fill="none" opacity=".85">
        <path d="M20 176 C80 156 140 170 200 160" /><path d="M14 190 C80 170 150 184 214 174" /><path d="M10 204 C80 186 160 198 228 188" />
        <path d="M206 158 C260 146 310 160 352 150" /><path d="M220 172 C270 160 320 172 356 164" />
      </g>
      <path d="M0 214 C70 192 150 220 220 204 C280 190 320 206 358 196 V440 H0Z" fill={`url(#${k}col2)`} />
      <g fill="#4C9A5E"><circle cx="40" cy="214" r="6" /><circle cx="52" cy="211" r="5" /><circle cx="300" cy="200" r="6" /><circle cx="312" cy="198" r="5" /></g>
      <g fill="#7A1F3D"><circle cx="46" cy="219" r="2.2" /><circle cx="50" cy="222" r="2.2" /><circle cx="306" cy="205" r="2.2" /></g>
      <path d="M36 248 C80 230 110 250 150 226 C190 202 230 222 262 196 C290 174 316 178 330 160" fill="none" stroke="#F6D38A" strokeWidth="3" strokeDasharray="2 9" strokeLinecap="round" />
      <rect width="358" height="440" fill={`url(#${k}sombra)`} />
      <g fontFamily="Poppins, sans-serif" fontSize="10.5" fontWeight="700">
        <g transform="translate(36 248)"><circle r="9" fill="#fff" /><circle r="4" fill="#8E2F52" /></g>
        <g transform="translate(150 226)"><circle r="9" fill="#fff" /><circle r="4" fill="#8E2F52" /><rect x="-46" y="-34" width="92" height="20" rx="10" fill="#fff" /><text y="-20" textAnchor="middle" fill="#3B1D45">Viñedos</text></g>
        <g transform="translate(262 196)"><circle r="9" fill="#fff" /><circle r="4" fill="#8E2F52" /><rect x="-40" y="-34" width="80" height="20" rx="10" fill="#fff" /><text y="-20" textAnchor="middle" fill="#3B1D45">Bodegas</text></g>
        <g transform="translate(330 160)"><circle r="9" fill="#F6D38A" /><circle r="4" fill="#8E2F52" /><rect x="-74" y="-36" width="64" height="20" rx="10" fill="#fff" /><text x="-42" y="-22" textAnchor="middle" fill="#3B1D45">Singani</text></g>
      </g>
      <g transform="translate(300 40)" fill="none" stroke="#fff" strokeWidth="2" opacity=".9"><path d="M-4 0 h14 l-2 14 a5 5 0 0 1 -10 0 z" /><path d="M3 19 v9 M-3 28 h12" /></g>
    </Marco>
  );
}

/** Centro histórico: plaza con iglesia, torre y casonas de adobe. */
function IlusCentro({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#F3E3C3" /><circle cx="135" cy="28" r="14" fill="#F6B44A" />
      <rect x="40" y="38" width="90" height="56" fill="#E8C98E" /><path d="M36 40 L85 16 L134 40Z" fill="#C98E38" />
      <rect x="74" y="12" width="22" height="30" fill="#F8EBD0" /><path d="M72 14 L85 2 L98 14Z" fill="#B0702A" /><rect x="81" y="20" width="8" height="10" rx="4" fill="#7A4A1A" />
      <rect x="76" y="64" width="18" height="30" rx="9" fill="#7A4A1A" /><rect x="50" y="52" width="12" height="16" rx="6" fill="#7A4A1A" /><rect x="108" y="52" width="12" height="16" rx="6" fill="#7A4A1A" />
      <rect y="94" width="170" height="16" fill="#9FBF7A" /><path d="M18 94 v-30" stroke="#5E7A3A" strokeWidth="3" /><circle cx="18" cy="60" r="12" fill="#6FA35A" /><circle cx="154" cy="70" r="10" fill="#6FA35A" /><path d="M154 94 v-20" stroke="#5E7A3A" strokeWidth="3" />
    </Marco>
  );
}

/** Miradores: la montaña de noche con la ciudad iluminada abajo. */
function IlusMiradores({ className }: Propiedades) {
  const k = useIdSvg();
  return (
    <Marco ancho={170} alto={110} className={className}>
      <defs><linearGradient id={`${k}noche`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1B2A4A" /><stop offset="1" stopColor="#3E4F7A" /></linearGradient></defs>
      <rect width="170" height="110" fill={`url(#${k}noche)`} />
      <path d="M0 110 V70 L40 46 L70 62 L110 30 L170 66 V110Z" fill="#2E6B4A" /><path d="M110 30 L118 30 L114 20Z" fill="#fff" />
      <path d="M114 20 v-8 M110 15 h8" stroke="#fff" strokeWidth="2" />
      <g fill="#F6D38A"><circle cx="20" cy="96" r="1.6" /><circle cx="34" cy="92" r="1.6" /><circle cx="50" cy="98" r="1.6" /><circle cx="64" cy="90" r="1.6" /><circle cx="80" cy="96" r="1.6" /><circle cx="96" cy="88" r="1.6" /><circle cx="120" cy="94" r="1.6" /><circle cx="140" cy="90" r="1.6" /><circle cx="156" cy="98" r="1.6" /></g>
      <g fill="#fff" opacity=".8"><circle cx="30" cy="18" r="1.2" /><circle cx="60" cy="10" r="1" /><circle cx="150" cy="16" r="1.2" /><circle cx="84" cy="22" r="1" /></g>
    </Marco>
  );
}

/** Cascadas y ríos: una caída de agua entre cerros, con su poza. */
function IlusCascadas({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#CFE8E4" /><path d="M0 110 V40 C30 30 50 20 62 10 H108 C120 20 140 30 170 40 V110Z" fill="#5E8F5A" />
      <path d="M70 10 H100 V78 H70Z" fill="#8FD0E8" /><g stroke="#fff" strokeWidth="2.5" opacity=".9"><path d="M76 12 V76" /><path d="M85 12 V76" /><path d="M94 12 V76" /></g>
      <ellipse cx="85" cy="88" rx="56" ry="14" fill="#5BB7D9" /><ellipse cx="85" cy="84" rx="30" ry="6" fill="#fff" opacity=".7" /><circle cx="30" cy="62" r="12" fill="#3F7A44" /><circle cx="142" cy="60" r="13" fill="#3F7A44" />
    </Marco>
  );
}

/** Noche: luna, copa de cóctel y guitarras de peña, sobre un cielo morado. */
function IlusNoche({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#2A1638" /><circle cx="132" cy="28" r="14" fill="#F6D38A" /><circle cx="138" cy="24" r="12" fill="#2A1638" />
      <g fill="#fff"><circle cx="30" cy="20" r="1.4" /><circle cx="64" cy="12" r="1.2" /><circle cx="96" cy="26" r="1.4" /></g>
      <path d="M56 40 h34 l-17 24 z" fill="none" stroke="#F6D38A" strokeWidth="3" /><path d="M73 64 v22 M62 86 h22" stroke="#F6D38A" strokeWidth="3" /><circle cx="84" cy="44" r="4" fill="#E0567A" />
      <g fill="#4CC985"><path d="M112 56 v26" stroke="#4CC985" strokeWidth="3" /><ellipse cx="108" cy="82" rx="6" ry="4.5" /><path d="M112 56 l14 -4 v8 l-14 4z" /><path d="M126 52 v24" stroke="#4CC985" strokeWidth="3" /><ellipse cx="122" cy="76" rx="6" ry="4.5" /></g>
      <rect y="96" width="170" height="14" fill="#3D2152" />
    </Marco>
  );
}

/** Sabores: una olla humeante con el guiso (el plato de la página de sabores usa la misma). */
function IlusSabores({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#F7D9B5" /><ellipse cx="85" cy="82" rx="58" ry="16" fill="#C46A3A" /><ellipse cx="85" cy="76" rx="58" ry="16" fill="#E9894F" /><ellipse cx="85" cy="74" rx="46" ry="11" fill="#9E3B1F" />
      <circle cx="70" cy="72" r="6" fill="#F6D38A" /><circle cx="96" cy="70" r="5" fill="#6FA35A" /><circle cx="84" cy="76" r="4" fill="#F6D38A" />
      <g fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="round" opacity=".85"><path d="M66 50 c-6 -8 6 -12 0 -22" /><path d="M85 48 c-6 -8 6 -12 0 -22" /><path d="M104 50 c-6 -8 6 -12 0 -22" /></g>
    </Marco>
  );
}

/** Lagunas y montaña: cordillera nevada y una laguna al pie. */
function IlusLagunas({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#BFD7EA" /><path d="M0 76 L36 30 L58 52 L88 14 L120 50 L140 34 L170 66 V110 H0Z" fill="#7C8FA6" /><path d="M88 14 L98 26 L90 24 L82 28Z" fill="#fff" />
      <ellipse cx="85" cy="92" rx="70" ry="13" fill="#4F8FC0" /><path d="M0 86 C40 78 60 84 85 80 C110 76 140 82 170 78 V110 H0Z" fill="#7FA36A" opacity=".9" /><ellipse cx="85" cy="94" rx="50" ry="8" fill="#5FA3D3" />
    </Marco>
  );
}

/** Parques: césped, un camino, árboles redondos y un banco. */
function IlusParques({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#D6EEDC" /><circle cx="138" cy="24" r="13" fill="#F6D38A" />
      <path d="M0 74 C36 62 78 72 118 64 C140 60 158 64 170 62 V110 H0Z" fill="#9CCB7E" />
      <path d="M0 88 C50 80 110 86 170 82 V110 H0Z" fill="#6FA35A" />
      <path d="M62 110 C70 98 88 92 104 84 L118 84 C108 94 98 100 96 110Z" fill="#F3E3C3" />
      <path d="M32 84 v-26" stroke="#7A4A1A" strokeWidth="4" /><circle cx="32" cy="50" r="15" fill="#3F7A44" /><circle cx="42" cy="58" r="10" fill="#4C9A5E" />
      <path d="M142 80 v-22" stroke="#7A4A1A" strokeWidth="4" /><circle cx="142" cy="50" r="13" fill="#3F7A44" /><circle cx="132" cy="58" r="9" fill="#4C9A5E" />
      <g fill="#7A4A1A"><rect x="76" y="76" width="26" height="4" rx="2" /><rect x="78" y="80" width="3" height="8" /><rect x="97" y="80" width="3" height="8" /></g>
      <g fill="#E0567A"><circle cx="18" cy="96" r="2" /><circle cx="52" cy="100" r="2" /><circle cx="150" cy="98" r="2" /></g>
    </Marco>
  );
}

/** Museos: un edificio de columnas y frontón, con su escalinata. */
function IlusMuseos({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#E4DDF2" /><circle cx="28" cy="26" r="12" fill="#F6D38A" opacity=".9" />
      <path d="M30 46 L85 16 L140 46Z" fill="#B79A6A" /><path d="M42 44 L85 22 L128 44Z" fill="#F1E6D0" />
      <rect x="30" y="46" width="110" height="7" fill="#C9B07E" />
      <g fill="#F1E6D0"><rect x="38" y="53" width="10" height="34" /><rect x="58" y="53" width="10" height="34" /><rect x="78" y="53" width="10" height="34" /><rect x="98" y="53" width="10" height="34" /><rect x="118" y="53" width="10" height="34" /></g>
      <g fill="#C9B07E"><rect x="36" y="53" width="14" height="3" /><rect x="56" y="53" width="14" height="3" /><rect x="76" y="53" width="14" height="3" /><rect x="96" y="53" width="14" height="3" /><rect x="116" y="53" width="14" height="3" /></g>
      <rect x="26" y="87" width="118" height="6" fill="#C9B07E" /><rect x="20" y="93" width="130" height="6" fill="#B79A6A" /><rect y="99" width="170" height="11" fill="#9FBF7A" />
      <circle cx="85" cy="34" r="4" fill="#8E2F52" />
    </Marco>
  );
}

/** Mercados: puesto con toldo a rayas y cajones de fruta. */
function IlusMercados({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#FBE3C4" />
      <path d="M26 30 H144 L152 52 H18Z" fill="#fff" />
      <g fill="#E0567A"><path d="M26 30 H46 L44 52 H18Z" /><path d="M66 30 H86 L86 52 H64Z" /><path d="M106 30 H126 L128 52 H106Z" /></g>
      <g fill="#7A4A1A"><rect x="26" y="52" width="4" height="40" /><rect x="140" y="52" width="4" height="40" /></g>
      <rect x="20" y="76" width="130" height="8" rx="2" fill="#A8672B" /><rect x="26" y="84" width="118" height="14" fill="#7A4A1A" />
      <g fill="#F6B44A"><circle cx="42" cy="70" r="6" /><circle cx="54" cy="70" r="6" /><circle cx="48" cy="63" r="6" /></g>
      <g fill="#6FA35A"><circle cx="82" cy="70" r="6" /><circle cx="94" cy="70" r="6" /><circle cx="88" cy="63" r="6" /></g>
      <g fill="#D5384B"><circle cx="122" cy="70" r="6" /><circle cx="134" cy="70" r="6" /><circle cx="128" cy="63" r="6" /></g>
      <rect y="98" width="170" height="12" fill="#E8C98E" />
    </Marco>
  );
}

/** Repostería: una torta de capas con velita. */
function IlusReposteria({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#F9DDE6" />
      <ellipse cx="85" cy="92" rx="60" ry="9" fill="#E7B9C7" />
      <rect x="40" y="66" width="90" height="26" rx="5" fill="#C98E38" /><rect x="46" y="44" width="78" height="24" rx="5" fill="#F3E3C3" /><rect x="40" y="62" width="90" height="6" fill="#8E2F52" />
      <path d="M46 44 q6 10 12 0 q6 10 12 0 q6 10 12 0 q6 10 12 0 q6 10 12 0 q6 10 12 0" fill="#fff" />
      <rect x="83" y="26" width="4" height="18" rx="2" fill="#E0567A" /><path d="M85 14 c5 6 3 10 0 11 c-3 -1 -5 -5 0 -11z" fill="#F6B44A" />
      <g fill="#E0567A"><circle cx="58" cy="78" r="3" /><circle cx="84" cy="80" r="3" /><circle cx="110" cy="78" r="3" /></g>
    </Marco>
  );
}

/** Bebidas típicas: una copa de singani y una botella de vino. */
function IlusBebida({ className }: Propiedades) {
  return (
    <Marco ancho={170} alto={110} className={className}>
      <rect width="170" height="110" fill="#E9D4F0" />
      <rect y="94" width="170" height="16" fill="#C9A9D6" />
      <path d="M44 42 h40 l-8 28 a12 12 0 0 1 -24 0z" fill="#fff" opacity=".85" /><path d="M48 52 h32 l-5 18 a11 11 0 0 1 -22 0z" fill="#F6B44A" />
      <path d="M64 80 v12 M52 94 h24" stroke="#8E2F52" strokeWidth="3" strokeLinecap="round" />
      <rect x="110" y="30" width="16" height="64" rx="4" fill="#5A1E3A" /><rect x="114" y="14" width="8" height="20" rx="2" fill="#5A1E3A" /><rect x="110" y="56" width="16" height="22" fill="#F3E3C3" />
      <circle cx="118" cy="67" r="4" fill="#8E2F52" />
      <g fill="#fff" opacity=".8"><circle cx="30" cy="20" r="1.4" /><circle cx="96" cy="16" r="1.2" /><circle cx="150" cy="40" r="1.4" /></g>
    </Marco>
  );
}

const DIBUJOS: Record<IdIlustracion, (p: Propiedades) => React.JSX.Element> = {
  vino: IlusVino, centro: IlusCentro, miradores: IlusMiradores, cascadas: IlusCascadas, noche: IlusNoche, sabores: IlusSabores,
  lagunas: IlusLagunas, parques: IlusParques, museos: IlusMuseos, mercados: IlusMercados,
  plato: IlusSabores, reposteria: IlusReposteria, bebida: IlusBebida,
};

/** Los ids del catálogo, para recorrerlos (los tests y la galería). */
export const ILUSTRACIONES: readonly IdIlustracion[] = Object.keys(DIBUJOS) as IdIlustracion[];

/** Una ilustración del catálogo. Siempre decorativa: el título va escrito al lado. */
export function Ilustracion({ id, className }: { id: IdIlustracion; className?: string }) {
  const Dibujo = DIBUJOS[id];
  return <Dibujo className={className} />;
}
