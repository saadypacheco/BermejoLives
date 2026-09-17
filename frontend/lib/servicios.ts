// Los servicios de la ciudad que NO son negocios: baños públicos,
// estacionamientos, cajeros, wifi. Son RUBROS no comerciales (`banos` desde la
// 0083; los otros tres desde la 0113) y se cargan como cualquier comercio,
// desde campo o desde Admin › Comercios. Una sola forma de cargar: la que ya
// se usa. (La 0110 había abierto otra —la tabla `lugares` con un tipo— y el
// buscador miraba ésa, vacía, mientras los nueve baños reales estaban acá.)
//
// Cuando alguien escribe "baño público" en el buscador, lo que quiere no es
// la casa de sanitarios: quiere un baño. Por eso el buscador detecta el
// servicio y busca por SU rubro en vez de por texto, que es lo que hace que
// "estacionamiento" no devuelva estaciones de servicio.
export type TipoServicio = "baño" | "estacionamiento" | "cajero" | "wifi";

export const SERVICIOS: Record<TipoServicio, { rubro: string; nombre: string; plural: string; icono: string; patron: RegExp }> = {
  "baño":          { rubro: "banos", nombre: "Baño público", plural: "Baños públicos", icono: "🚻", patron: /\bba[ñn]os?\b|sanitarios? p[uú]blicos?|inodoro|\bwc\b/ },
  estacionamiento: { rubro: "estacionamiento", nombre: "Estacionamiento", plural: "Estacionamientos", icono: "🅿️", patron: /estacionamiento|estacionar|cochera|parking|playa de estacionamiento|d[oó]nde dejo el auto/ },
  cajero:          { rubro: "cajeros", nombre: "Cajero automático", plural: "Cajeros y bancos", icono: "🏧", patron: /cajeros?( autom[aá]ticos?)?|\batm\b|\bbancos?\b|sacar plata|retirar (plata|dinero|efectivo)/ },
  wifi:            { rubro: "wifi", nombre: "Wifi", plural: "Wifi gratis", icono: "📶", patron: /\bwi-?fi\b|internet gratis/ },
};

function norm(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, (m) => (m === "̃" ? m : "")).normalize("NFC");
}

/** El servicio que la persona está buscando, si la búsqueda es eso. */
export function detectarServicio(q: string): TipoServicio | null {
  const t = norm(q || "").trim();
  if (!t) return null;
  for (const [tipo, s] of Object.entries(SERVICIOS) as [TipoServicio, (typeof SERVICIOS)[TipoServicio]][]) {
    if (s.patron.test(t)) return tipo;
  }
  return null;
}

/** El servicio cuyo rubro es éste, para titular "🚻 Baños públicos" al entrar por el chip. */
export function servicioDeRubro(slug: string): TipoServicio | null {
  for (const [tipo, s] of Object.entries(SERVICIOS) as [TipoServicio, (typeof SERVICIOS)[TipoServicio]][]) {
    if (s.rubro === slug) return tipo;
  }
  return null;
}
