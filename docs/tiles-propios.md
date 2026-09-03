# El mapa base servido desde el VPS (2026-09-02)

## De dónde salían los tiles hasta hoy

De `tile.openstreetmap.org`, los servidores públicos de OpenStreetMap. Sin
cuenta, sin clave, y sin nada nuestro en el medio. Comprobado el 2/9: las 22
ciudades tenían `tiles_url` en NULL.

Eso funcionó y fue la decisión correcta cuando CARTO cortó de un día para el
otro. Pero la política de uso de OSM está escrita para aplicaciones chicas, y un
directorio con 22 ciudades y usuarios reales deja de serlo. **La forma en que
eso se rompe es el mapa entero dejando de cargar, sin aviso** — exactamente lo
que pasó el 27 de agosto con CARTO.

## Qué se hizo

Un **caché propio** delante de OSM: un nginx en el mismo VPS, en
`tiles.<dominio>`. El primer pedido de cada tile va a OSM; después lo sirve él.

Lo que cambia de verdad:

- **Mil personas mirando el centro de Bermejo son UN pedido a OSM**, no mil. Se
  pasa de estar en el borde de su política a estar sobradamente adentro.
- **El mapa carga más rápido acá**: la tile sale del mismo servidor que el sitio,
  no de Europa.
- **Si OSM se cae o corta, lo cacheado sigue andando 30 días.** Deja de ser una
  caída y pasa a ser un mes para reaccionar.

## Qué NO es

No es una copia del mapa del mundo, y **no reemplaza la atribución**: los datos
siguen siendo de OpenStreetMap. Cachearlos no los hace nuestros.

No es tampoco la solución final. La final es **PMTiles**: un archivo propio que
el navegador dibuja, con estilo propio — ahí sí desaparece la dependencia y se
puede tener un mapa oscuro de verdad en vez del filtro CSS que destapa las
costuras entre tiles. Se dejó para después a propósito: cambia el motor de
dibujo del mapa, suma una dependencia de JavaScript y obliga a generar y
mantener el archivo. Eso no se hace a días de arrancar.

**Y el cambio de uno a otro no va a requerir un deploy**: `ciudades.tiles_url`
(migración 0068) permite mover una ciudad por vez y comparar. Para eso existe
esa columna.

## Cómo se despliega

```bash
cd /docker/uruku && git pull

# 1. El subdominio tiene que resolver ANTES de levantar: Traefik pide el
#    certificado a Let's Encrypt en el arranque y si el DNS no está, falla.
#    En el panel del DNS: A  tiles.uruku.bo  ->  <IP del VPS>   (igual que api.)
dig +short tiles.uruku.bo        # tiene que devolver la IP del VPS

# 2. Levantar el caché
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml up -d tiles

# 3. Probar que sirve una tile ANTES de apuntar el sitio.
#    X-Tile-Cache: MISS la primera vez, HIT la segunda.
curl -sI https://tiles.uruku.bo/15/11000/19000.png | grep -i "HTTP/\|x-tile-cache\|content-type"
curl -sI https://tiles.uruku.bo/15/11000/19000.png | grep -i x-tile-cache

# 4. Recién ahí, reconstruir el frontend (que ya apunta a tiles.<dominio>)
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml up -d --build frontend
```

El paso 3 no es ceremonia: si el certificado no salió o el resolver no funciona,
el mapa queda en blanco para todos y el síntoma no dice por qué.

## Si algo sale mal

**Volver atrás no necesita deploy.** Apuntá las ciudades de nuevo a OSM:

```sql
update ciudades set tiles_url = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
```

Es inmediato y no reconstruye nada. Para volver al caché, `set tiles_url = null`
y vuelve a mandar el valor del build.

## Lo que hay que vigilar

- **El disco.** El caché está topeado en 4 GB y se limpia solo lo que no se
  pidió en 60 días. Bermejo entera hasta zoom 19 son unos cientos de MB.
  `docker exec uruku-tiles du -sh /var/cache/tiles`
- **El User-Agent.** La política de OSM exige uno que identifique la aplicación
  y permita contactarla. Está en el nginx.conf con el mail de contacto: si ese
  mail deja de existir, hay que cambiarlo. Un agente genérico es motivo de
  bloqueo.
- **Nunca precargar el caché bajando el mapa entero.** La descarga masiva está
  prohibida y es lo que haría que nos bloqueen — este caché es legítimo
  justamente porque se llena con lo que la gente mira de verdad.
