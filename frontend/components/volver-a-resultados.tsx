"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Arrow } from "@/components/icons";

/** Dónde guarda el buscador la última búsqueda. Exportado para que el que
 *  escribe y el que lee usen la misma clave y no se separen. */
export const CLAVE_ULTIMA_BUSQUEDA = "uruku:ultima-busqueda";

/**
 * "Volver a resultados", pero a LOS resultados.
 *
 * El enlace iba a `/buscar` pelado, así que volver borraba la búsqueda: quien
 * buscaba "bicicleta", abría el tercer local y volvía, se encontraba el
 * buscador vacío y tenía que escribir todo otra vez. Con tres locales para
 * comparar —que es exactamente lo que hace alguien antes de comprar— eso son
 * tres búsquedas repetidas.
 *
 * La búsqueda se guarda en `sessionStorage` y no en la URL de la ficha. Por la
 * URL habría sido más simple, pero la dirección de un negocio se comparte por
 * WhatsApp, y ahí viajaría pegada la búsqueda de otra persona: el que abre el
 * enlace vería "volver a resultados" y caería en una búsqueda que nunca hizo.
 *
 * `sessionStorage` y no `localStorage`: dura lo que dura la pestaña. Volver
 * mañana a un enlace guardado no tiene por qué devolver la búsqueda del martes.
 */
export function VolverAResultados() {
  // Arranca en el fallback y se corrige al montar. Leer `sessionStorage` en el
  // primer render no se puede: en el servidor no existe, y si el HTML del
  // servidor difiere del primero del navegador, React descarta el árbol.
  const [href, setHref] = useState("/buscar");
  const [hubo, setHubo] = useState(false);

  useEffect(() => {
    try {
      const qs = sessionStorage.getItem(CLAVE_ULTIMA_BUSQUEDA);
      if (qs) { setHref(`/buscar?${qs}`); setHubo(true); }
    } catch {
      // Modo privado o cookies bloqueadas: queda el fallback. Perder el filtro
      // es molesto; romper el botón de volver, mucho peor.
    }
  }, []);

  return (
    <Link className="uk-back" href={href}>
      <Arrow style={{ transform: "rotate(180deg)" }} />
      {hubo ? " Volver a resultados" : " Ir al buscador"}
    </Link>
  );
}
