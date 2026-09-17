// La ubicación: el mensaje de error de navigator.geolocation y los pasos para
// destrabarla, según el aparato en el que está la persona. Cada uno guarda el
// "no" en un lugar distinto y ninguno vuelve a preguntar solo: decirle a
// alguien en Chrome de Windows que vaya a Ajustes del iPhone es mandarlo a
// buscar un menú que no existe.
export type Aparato = "iphone" | "android" | "escritorio";

export function aparato(): Aparato {
  if (typeof navigator === "undefined") return "escritorio";
  const ua = navigator.userAgent || "";
  // iPadOS se presenta como Mac; lo delata la pantalla táctil.
  if (/iPhone|iPad|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "iphone";
  if (/Android/.test(ua)) return "android";
  return "escritorio";
}

/** Los pasos para volver a dar el permiso cuando el navegador lo tiene
 *  bloqueado. Ninguna página puede abrir ese ajuste por la persona: lo único
 *  honesto es decirle dónde está, en tres renglones. */
export function pasosPermisoUbicacion(donde: Aparato = aparato()): { pasos: string[]; recargar: boolean } {
  if (donde === "iphone") {
    return {
      pasos: [
        "Abrí Ajustes del iPhone → Privacidad y seguridad → Localización.",
        "Activá el interruptor general y, en Safari (o en URUKU si la agregaste a la pantalla de inicio), elegí «Mientras se usa la app».",
        "Volvé acá y tocá «Probar de nuevo».",
      ],
      recargar: false,
    };
  }
  if (donde === "android") {
    return {
      pasos: [
        "Tocá el candado 🔒 (o el ícono de ajustes) a la izquierda de la dirección.",
        "Entrá a Permisos → Ubicación y elegí «Permitir».",
        "Si el celular tiene la ubicación apagada, encendela desde la barra de arriba. Después, «Probar de nuevo».",
      ],
      recargar: false,
    };
  }
  return {
    pasos: [
      "Hacé clic en el ícono a la izquierda de la dirección (el candado 🔒 o el de ajustes).",
      "Buscá «Ubicación» y elegí «Permitir».",
      "Recargá la página. En una computadora sin GPS la ubicación es aproximada: sale de la red.",
    ],
    recargar: true,
  };
}

export function geoErrorMsg(e: GeolocationPositionError): string {
  if (e.code === e.PERMISSION_DENIED) {
    return "Permiso de ubicación denegado. " + pasosPermisoUbicacion().pasos.join(" ");
  }
  if (e.code === e.TIMEOUT) return "Se demoró demasiado en obtener la ubicación. Probá de nuevo.";
  return "No se pudo obtener la ubicación. Revisá que la localización esté activada.";
}
