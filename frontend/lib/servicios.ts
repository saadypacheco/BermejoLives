// Los servicios del mapa que NO son comercios: baños públicos, estacionamientos,
// cajeros, wifi, la terminal, migraciones. Viven en `lugares` con un tipo
// (migración 0110) y se cargan desde Admin › Lugares.
//
// Cuando alguien escribe "baño público" en el buscador, lo que quiere no es
// la casa de sanitarios del rubro "Baños": quiere un baño. Por eso el
// buscador detecta el servicio y muestra los lugares, no los comercios.
export type TipoServicio = "baño" | "estacionamiento" | "cajero" | "wifi" | "terminal" | "migraciones";

export const SERVICIOS: Record<TipoServicio, { nombre: string; plural: string; icono: string; patron: RegExp }> = {
  "baño":          { nombre: "Baño público", plural: "Baños públicos", icono: "🚻", patron: /\bba[ñn]os?\b|sanitarios? p[uú]blicos?|inodoro|\bwc\b/ },
  estacionamiento: { nombre: "Estacionamiento", plural: "Estacionamientos", icono: "🅿️", patron: /estacionamiento|estacionar|parking|playa de estacionamiento|d[oó]nde dejo el auto/ },
  cajero:          { nombre: "Cajero automático", plural: "Cajeros automáticos", icono: "🏧", patron: /cajeros?( autom[aá]ticos?)?|\batm\b|sacar plata|retirar (plata|dinero|efectivo)/ },
  wifi:            { nombre: "Wifi", plural: "Wifi gratis", icono: "📶", patron: /\bwi-?fi\b|internet gratis/ },
  terminal:        { nombre: "Terminal de buses", plural: "Terminal de buses", icono: "🚌", patron: /terminal( de (buses|micros|colectivos|omnibus))?|d[oó]nde salen los (buses|micros|colectivos)/ },
  migraciones:     { nombre: "Migraciones", plural: "Migraciones y aduana", icono: "🛂", patron: /migraci[oó]n(es)?|aduana|control fronterizo/ },
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
