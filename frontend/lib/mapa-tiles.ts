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
 * SERVIRLOS DESDE EL VPS NO CAMBIA LA ATRIBUCIÓN. Los datos siguen siendo de
 * OpenStreetMap: cachearlos no los hace nuestros. Sacar el crédito sería una
 * violación de licencia, no un detalle de diseño.
 *
 * LA ATRIBUCIÓN NO ES OPCIONAL. La licencia de OSM la exige, y además ya hacía
 * falta por los comercios importados con `importar_osm.py`.
 */

/**
 * Por defecto, el caché de tiles propio (ver selfhost/tiles/nginx.conf): un
 * nginx en el mismo VPS que le pide a OSM la primera vez y después sirve él.
 *
 * Es variable de entorno y no una constante porque el dominio cambia entre QA y
 * producción. Y si no está puesta cae a OSM directo: preferible un mapa que
 * anda contra el servidor de otro, a ningún mapa.
 */
export const TILE_URL =
  process.env.NEXT_PUBLIC_TILES_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

export const TILE_ATRIBUCION =
  '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>';

/** El host, para el preconnect del layout y la caché del service worker.
 *  Se deriva de la URL en vez de repetirse: escritos por separado, el día que
 *  cambie uno el otro queda apuntando al proveedor viejo y nadie lo nota —
 *  el preconnect a un host que ya no se usa no rompe nada, sólo deja de
 *  ayudar. */
export const TILE_HOST = (() => {
  try { return new URL(TILE_URL.replace(/\{[zxy]\}/g, "0")).hostname; }
  catch { return "tile.openstreetmap.org"; }
})();

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
    // MAPA SIEMPRE CLARO, aunque el sitio esté en oscuro.
    //
    // El oscuro salía de un filtro CSS sobre las tiles de OSM, y ese filtro
    // destapaba las costuras: entre dos tiles vecinas queda una fracción de
    // píxel sin cubrir por el redondeo del navegador, y sobre un mapa gris ese
    // hueco blanco se ve como una grilla de líneas. En claro el hueco es blanco
    // sobre un mapa casi blanco y no lo ve nadie — por eso nunca apareció en
    // los meses que el mapa fue claro.
    //
    // Es tapar el síntoma, dicho de frente: la costura sigue ahí. Pero el
    // arreglo de verdad es pelearle al subpíxel del navegador, y no vale un
    // mapa con líneas a días de arrancar. `opciones.oscuro` se conserva para
    // el día que se quiera volver a intentar.
    className: "",
    updateWhenIdle: true,
    keepBuffer: 2,
  });
  capa.addTo(map);
  return capa;
}
