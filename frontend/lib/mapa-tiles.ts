/**
 * El mapa base, en un solo lugar.
 *
 * POR QUÉ ESTE ARCHIVO EXISTE
 * ===========================
 *
 * La URL de los tiles estaba copiada en seis componentes. El 2026-08-27 CARTO
 * empezó a exigir API key y estampó "API key required" sobre el mapa de
 * producción: hubo que tocar seis archivos, el preconnect del layout y el
 * service worker para algo que es UNA decisión. Ahora es una constante.
 *
 * QUÉ PROVEEDOR Y POR QUÉ
 * =======================
 *
 * Tiles estándar de OpenStreetMap: no piden clave, no hay cuenta que crear y
 * no hay nadie que pueda cambiar los términos de un día para el otro sin
 * aviso — que es exactamente lo que acaba de pasar.
 *
 * La contrapartida honesta: la política de uso de OSM está pensada para
 * aplicaciones chicas y pide atribución visible. Para un directorio de una
 * ciudad alcanza de sobra, pero **no es una solución para siempre**: si URUKU
 * crece, lo correcto es servir los tiles desde el VPS propio (ya se
 * self-hostean Postgres y PostgREST) o contratar un proveedor con clave.
 *
 * LA ATRIBUCIÓN NO ES OPCIONAL. La licencia de OSM la exige, y además ya hacía
 * falta por los comercios importados con `importar_osm.py`.
 */

export const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export const TILE_ATRIBUCION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

/** El host, para el preconnect del layout y la caché del service worker. */
export const TILE_HOST = "tile.openstreetmap.org";

/**
 * Agrega el mapa base. `oscuro` invierte los colores por CSS.
 *
 * OSM publica un solo estilo, claro. Antes se usaban dos mapas distintos
 * (`light_all` y `dark_all`); ahora el oscuro sale de un filtro sobre el mismo
 * tile — se ve bien, no agrega otra dependencia, y evita quedar atado a que un
 * proveedor mantenga las dos variantes.
 */
export function agregarTiles(
  L: any, map: any,
  opciones: {
    oscuro?: boolean;
    maxZoom?: number;
    /** La ciudad que se está mostrando. Si trae `tiles_url`, manda esa. */
    ciudad?: { tiles_url?: string | null; tiles_atribucion?: string | null } | null;
  } = {},
) {
  // La ciudad manda sobre el valor por defecto. Si no dice nada, sigue el del
  // código — así una ciudad nueva tiene mapa sin que nadie la configure.
  const url = opciones.ciudad?.tiles_url || TILE_URL;
  const atribucion = opciones.ciudad?.tiles_atribucion || TILE_ATRIBUCION;
  const capa = L.tileLayer(url, {
    maxZoom: opciones.maxZoom ?? 19,
    attribution: atribucion,
    className: opciones.oscuro ? "uk-tiles-oscuro" : "",
    updateWhenIdle: true,
    keepBuffer: 2,
  });
  capa.addTo(map);
  return capa;
}
