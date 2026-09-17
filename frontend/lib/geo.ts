// Mensaje de error consistente para navigator.geolocation.getCurrentPosition,
// con instrucciones para el aparato en el que está la persona. Cada uno
// guarda el "no" en un lugar distinto y ninguno vuelve a preguntar solo:
// decirle a alguien en Chrome de Windows que vaya a Ajustes del iPhone es
// mandarlo a buscar un menú que no existe.
function aparato(): "iphone" | "android" | "escritorio" {
  if (typeof navigator === "undefined") return "escritorio";
  const ua = navigator.userAgent || "";
  // iPadOS se presenta como Mac; lo delata la pantalla táctil.
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "iphone";
  if (/Android/.test(ua)) return "android";
  return "escritorio";
}

export function geoErrorMsg(e: GeolocationPositionError): string {
  if (e.code === e.PERMISSION_DENIED) {
    const donde = aparato();
    if (donde === "iphone") {
      return (
        "Permiso de ubicación denegado. En iPhone: Ajustes → Privacidad y Seguridad → " +
        "Localización, activá el interruptor general y elegí \"Mientras se usa la app\" " +
        "para Safari (o para esta app si la agregaste a la pantalla de inicio). Si ya " +
        "habías elegido \"No permitir\" antes, Safari no vuelve a preguntar solo — hay " +
        "que cambiarlo ahí manualmente."
      );
    }
    if (donde === "android") {
      return (
        "Permiso de ubicación denegado. Tocá el candado (o el ícono de ajustes) a la " +
        "izquierda de la dirección, entrá a Permisos → Ubicación y elegí \"Permitir\". " +
        "Si el celular tiene la ubicación apagada, encendela desde la barra de arriba."
      );
    }
    return (
      "Permiso de ubicación denegado. Hacé clic en el ícono a la izquierda de la " +
      "dirección (el candado o el de ajustes), buscá \"Ubicación\" y elegí \"Permitir\"; " +
      "después recargá la página. En una computadora sin GPS la ubicación es " +
      "aproximada (sale de la red)."
    );
  }
  if (e.code === e.TIMEOUT) return "Se demoró demasiado en obtener la ubicación. Probá de nuevo.";
  return "No se pudo obtener la ubicación. Revisá que la localización esté activada.";
}
