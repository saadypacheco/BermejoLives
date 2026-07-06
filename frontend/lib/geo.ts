// Mensaje de error consistente para navigator.geolocation.getCurrentPosition,
// con instrucciones específicas para iOS: una vez que Safari registra un "No
// permitir", no vuelve a preguntar — hay que resetearlo a mano en Ajustes.
export function geoErrorMsg(e: GeolocationPositionError): string {
  if (e.code === e.PERMISSION_DENIED) {
    return (
      "Permiso de ubicación denegado. En iPhone: Ajustes → Privacidad y Seguridad → " +
      "Localización, activá el interruptor general y elegí \"Mientras se usa la app\" " +
      "para Safari (o para esta app si la agregaste a la pantalla de inicio). Si ya " +
      "habías elegido \"No permitir\" antes, Safari no vuelve a preguntar solo — hay " +
      "que cambiarlo ahí manualmente."
    );
  }
  if (e.code === e.TIMEOUT) return "Se demoró demasiado en obtener la ubicación. Probá de nuevo.";
  return "No se pudo obtener la ubicación. Revisá que la localización esté activada.";
}
