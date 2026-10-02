/**
 * Los íconos de URUKU: Phosphor, estilo duotono.
 *
 * El manual de identidad los fija en Phosphor duotono, verde #1D8D52.
 * Reemplazan a los emojis, que tenían un problema de fondo: los dibuja el
 * sistema operativo. El local de un Windows no es el de un Android ni el de un
 * iPhone — con emojis es imposible que la marca se vea igual en dos
 * teléfonos, por más que todo lo demás esté bien.
 *
 * TRES DECISIONES QUE CONVIENE CONOCER
 * ====================================
 *
 * 1. ACÁ NO SE IMPORTA `@phosphor-icons/react`. Cada ícono de ese paquete
 *    arrastra sus SEIS pesos (fino, liviano, normal, negrita, relleno,
 *    duotono) en un solo módulo, y el paquete no se puede podar por peso.
 *    Importar los ciento sesenta de este catálogo metía 106 kB comprimidos en
 *    TODAS las páginas del sitio —medido: el build los ponía en el layout—
 *    para usar uno de cada seis dibujos. Así que los dibujos se sacan una vez
 *    en tiempo de desarrollo (`scripts/generar-iconos.mjs`) y quedan como
 *    texto en `lib/iconos-dibujos.ts`: duotono y relleno, nada más. El
 *    paquete de Phosphor es una dependencia de DESARROLLO, no de producción.
 *
 * 2. Todos los íconos se nombran ACÁ, en un solo archivo. Phosphor trae más
 *    de mil quinientos: elegirlos sueltos en cada pantalla termina metiendo de
 *    a poco los mil quinientos. Con una sola puerta, lo que entra está a la
 *    vista y se puede contar. La clave es lo que el ícono SIGNIFICA en URUKU,
 *    no cómo se llama en Phosphor: cambiar el dibujo de «ofertas» no debería
 *    obligar a tocar diez pantallas.
 *
 * 3. El color por defecto es `currentColor`, no el verde fijo. Un ícono
 *    adentro de un botón verde tiene que ser blanco, y uno sobre una tarjeta
 *    tiene que seguir al texto. El verde de marca se pone donde el ícono va
 *    solo, con `tono="marca"`.
 *
 * Si se agrega o se cambia una clave de acá, hay que volver a correr
 * `node scripts/generar-iconos.mjs` para que exista el dibujo.
 */
import { DUOTONO, RELLENO, POR_CLAVE, POR_CLAVE_RELLENO } from "@/lib/iconos-dibujos";

/** El verde del manual. Acá y no suelto: el ícono se dibuja en el servidor,
 *  donde no hay variables CSS que leer. */
export const VERDE = "#1D8D52";

export type NombreIcono = keyof typeof ICONOS;

/** El catálogo: qué dibujo de Phosphor usa cada cosa de URUKU. El valor es el
 *  NOMBRE del ícono en Phosphor, en texto, porque este archivo no importa el
 *  paquete (ver arriba): lo lee el generador, que es quien saca el dibujo. */
export const ICONOS = {
  // ── Navegación y acciones ────────────────────────────────────────────────
  buscar: "MagnifyingGlass", mapa: "MapTrifold", ubicacion: "MapPin", comercios: "Storefront",
  ofertas: "Tag", novedades: "Megaphone", cambio: "ArrowsLeftRight", guia: "BookOpen",
  whatsapp: "WhatsappLogo", compartir: "ShareNetwork", favorito: "Heart", verificado: "SealCheck",
  volver: "ArrowLeft", seguir: "ArrowRight", abrir: "ArrowSquareOut", cerrar: "X",
  si: "Check", listo: "CheckCircle", mas: "Plus", aviso: "Warning", ayuda: "Question",
  dato: "Info", reloj: "Clock", calendario: "CalendarBlank", usuario: "User", gente: "Users",
  foto: "Camera", video: "VideoCamera", descargar: "DownloadSimple", estrella: "Star",
  destacado: "Sparkle", mas_opciones: "DotsThree", dax: "ChatCircleDots", clima: "CloudSun",
  sol: "Sun", luna: "MoonStars", seguridad: "ShieldCheck", ruta: "Path", llama: "Flame",
  explorar: "Compass", telefono: "Phone", video_play: "PlayCircle", videos: "FilmSlate",
  cartel: "Signpost", comunidad: "ChatsCircle", util: "ThumbsUp", inutil: "ThumbsDown",
  imprimir: "Printer", ciudad: "City", emergencia: "Lifebuoy",
  inicio: "House", guardado: "BookmarkSimple", documento: "FileText",
  desplegar: "CaretDown", enviar: "PaperPlaneTilt", web: "GlobeSimple",
  editar: "PencilSimple",
  // Logos de marcas ajenas. Van acá porque el sitio los usa como íconos
  // (las redes de un comercio en su ficha); los TILES de las redes de URUKU
  // siguen con el dibujo oficial de cada marca, en components/uruku-ui.tsx.
  instagram: "InstagramLogo", facebook: "FacebookLogo",
  tiktok: "TiktokLogo", youtube: "YoutubeLogo",

  // ── La frontera y el clima ───────────────────────────────────────────────
  frontera: "Bridge", chalanas: "Boat", rio: "Waves", aduana: "Stamp",
  documentos: "IdentificationCard", transporte: "Bus", comprar: "ShoppingBag",
  salir: "Mountains", pagos: "CreditCard", policia: "Siren",
  clima_despejado: "Sun", clima_parcial: "CloudSun", clima_nublado: "Cloud",
  clima_niebla: "CloudFog", clima_lluvia: "CloudRain", clima_nieve: "Snowflake",
  clima_tormenta: "CloudLightning", clima_otro: "ThermometerSimple",

  // ── Rubros ───────────────────────────────────────────────────────────────
  ropa: "TShirt", calzado: "Sneaker", bolsos: "Handbag", joyeria: "Watch", belleza: "Palette",
  optica: "Eyeglasses", celulares: "DeviceMobile", computacion: "Laptop",
  electronica: "Television", electrodomesticos: "PlugCharging", bazar: "ForkKnife",
  hogar: "Bed", muebles: "Armchair", ferreteria: "Wrench", "repuestos-autos": "CarProfile",
  neumaticos: "Tire", motos: "Motorcycle", bicicletas: "Bicycle", alimentos: "ShoppingCart",
  bebidas: "BeerBottle", farmacia: "Pill", mascotas: "Dog", restaurantes: "ForkKnife",
  "comida-rapida": "Hamburger", cafeteria: "Coffee", panaderia: "Bread",
  cambio_rubro: "CurrencyCircleDollar", envios: "Package", peluqueria: "Scissors",
  lavadero: "Broom", "gomeria-servicio": "Tire", cerrajeria: "Key", hospedaje: "Bed",
  jugueteria: "Gift", bebes: "Baby", deportes: "SoccerBall", regaleria: "Confetti",
  "ropa-americana": "TShirt", "calzado-usado": "Sneaker", usados: "Recycle",
  alquiler: "House", "servicio-tecnico": "Toolbox", taxis: "Taxi",
  "estacion-servicio": "GasPump", "taller-mecanico": "Wrench", coca: "Leaf",
  nocturna: "Martini", carpinteria: "Tree", herreria: "Hammer", limpieza: "Broom",
  telas: "Needle", gimnasios: "Barbell", funeraria: "Flower", carniceria: "ForkKnife",
  salones: "Confetti", agro: "Tractor", kiosco: "Cookie", lenceria: "Pants",
  blanqueria: "Bed", marroquineria: "Suitcase", floreria: "Flower", otros: "Package",
  mercado: "ShoppingBagOpen", tecnologia: "Laptop", servicios: "Toolbox",
  galeria: "Buildings", pintura: "PaintBrush", musica: "MusicNotes", luz: "Lamp",
  planta: "PottedPlant", diente: "Tooth", salud: "FirstAidKit", camion: "Truck",
  combi: "Van", pared: "Wall", banco: "Bank", plata: "HandCoins", energia: "Lightning",
  // Slugs viejos, de los comercios cargados antes de la taxonomía v2. Están
  // acá y no en una tabla de alias aparte porque el mapa los recibe tal cual
  // vienen de la base: un alias suelto sería un pin genérico sin aviso.
  zapatillas: "Sneaker", moda: "TShirt", gastronomia: "ForkKnife",
  mercados: "ShoppingCart", gomeria: "Tire", tablets: "DeviceMobile",

  // ── Servicios de la ciudad ───────────────────────────────────────────────
  banos: "Toilet", cajeros: "CreditCard", estacionamiento: "Garage",
  wifi: "WifiHigh", emergencias: "ShieldCheck",
} as const;

type Props = {
  n: NombreIcono;
  /** Píxeles. 20 por defecto, que es el tamaño de un ícono al lado de texto. */
  s?: number;
  /** `marca` lo pinta del verde oficial; por defecto sigue al texto. */
  tono?: "marca" | "texto";
  /** Duotono es el del manual. `fill` es para lo que se dibuja CHICO —una
   *  estrella de 12 px, un pin del mapa—: a ese tamaño el duotono, que es
   *  trazo fino más relleno al 20%, se deshace en una manchita. */
  peso?: "duotone" | "fill";
  className?: string;
  style?: React.CSSProperties;
};

/** El dibujo de una clave, con respaldo en el paquete genérico. Si se pide
 *  relleno de algo que no lo tiene generado, cae en duotono: el relleno sólo
 *  existe para lo que se dibuja chico (ver el generador). */
function dibujo(n: string, peso: "duotone" | "fill"): string {
  if (peso === "fill") {
    const r = POR_CLAVE_RELLENO[n];
    if (r !== undefined) return RELLENO[r];
  }
  return DUOTONO[POR_CLAVE[n] ?? POR_CLAVE.otros];
}

/**
 * Un ícono. `<Ic n="ofertas" />`
 *
 * Duotono por defecto, como manda el manual: es el peso que le da el aire de
 * marca —relleno suave más trazo— y el que distingue a URUKU de cualquier
 * sitio con íconos de línea.
 *
 * El SVG se inyecta como texto porque eso es lo que es: dibujo fijo que salió
 * del generador, sin nada que venga de la base ni de la persona. No hay dónde
 * inyectar.
 */
export function Ic({ n, s = 20, tono = "texto", peso = "duotone", className, style }: Props) {
  return (
    <svg width={s} height={s} viewBox="0 0 256 256" aria-hidden
         fill={tono === "marca" ? VERDE : "currentColor"}
         className={className} style={{ flexShrink: 0, ...style }}
         dangerouslySetInnerHTML={{ __html: dibujo(n, peso) }} />
  );
}

/** El ícono de un rubro por su slug, con respaldo. Los rubros vienen de la
 *  base y pueden aparecer slugs que este archivo todavía no conoce: antes que
 *  romper la pantalla, cae en el paquete genérico. */
export function IcRubro({ slug, ...r }: Omit<Props, "n"> & { slug?: string | null }) {
  const clave = (slug ?? "") as NombreIcono;
  return <Ic n={clave in ICONOS ? clave : "otros"} {...r} />;
}

/** El ícono del clima a partir de la descripción que manda el backend
 *  («Despejado», «Lluvia»…). El backend guarda además un emoji, pero es el
 *  mismo dato dicho dos veces: la descripción alcanza y así el dibujo lo
 *  elige el sitio, no el sistema operativo del visitante. */
export function climaIcono(descripcion?: string | null): NombreIcono {
  const d = (descripcion ?? "").toLowerCase();
  if (d.startsWith("despejado")) return "clima_despejado";
  if (d.startsWith("parcial")) return "clima_parcial";
  if (d.startsWith("nublado")) return "clima_nublado";
  if (d.startsWith("niebla")) return "clima_niebla";
  if (d.startsWith("lluvia")) return "clima_lluvia";
  if (d.startsWith("nieve")) return "clima_nieve";
  if (d.startsWith("tormenta")) return "clima_tormenta";
  return "clima_otro";
}
