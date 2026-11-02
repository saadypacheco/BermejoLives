#!/usr/bin/env bash
# Deploy a producción, desde el VPS (/docker/uruku).
#
#   bash scripts/deploy-prod.sh                       # frontend + backend
#   bash scripts/deploy-prod.sh frontend              # sólo el frontend
#   bash scripts/deploy-prod.sh --sql selfhost/postgres-init/0105_*.sql frontend
#
# Hace lo mismo que se venía haciendo a mano, en el mismo orden: git pull,
# las migraciones que se le pasen con --sql (antes de levantar nada), el
# build con GIT_SHA, y después ESPERA a que el sitio conteste con el commit
# nuevo antes de decir que terminó.
#
# La espera es el motivo de que exista este archivo. `docker compose up`
# vuelve enseguida, pero el contenedor nuevo tarda unos segundos en levantar
# y Traefik otros tantos en registrarlo; un `curl` justo después cae en esa
# ventana y Traefik contesta su "404 page not found", que no es del sitio.
# Se leía como que el deploy había fallado cuando sólo había que esperar.
set -euo pipefail

cd "$(dirname "$0")/.."
ARGS=("$@")
DOMINIO="${DOMINIO:-uruku.bo}"
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file .env)

SQL=()
SERVICIOS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --sql) SQL+=("$2"); shift 2 ;;
    *) SERVICIOS+=("$1"); shift ;;
  esac
done
[ ${#SERVICIOS[@]} -eq 0 ] && SERVICIOS=(frontend backend)

echo "== git pull =="
if [ -z "${DEPLOY_SCRIPT_FRESCO:-}" ]; then
  ANTES="$(sha1sum scripts/deploy-prod.sh)"
  git pull --ff-only
  # bash lee el script a medida que lo ejecuta: si el pull trajo una versión
  # nueva de este mismo archivo, seguía corriendo la vieja (o un pedazo de cada
  # una). Pasó el 2/11: la clave de IndexNow no se publicó porque el bloque que
  # la escribe llegó en ese mismo pull. Se relanza con la versión recién bajada.
  if [ "$ANTES" != "$(sha1sum scripts/deploy-prod.sh)" ]; then
    echo "deploy-prod.sh cambió con el pull: se relanza la versión nueva"
    DEPLOY_SCRIPT_FRESCO=1 exec bash scripts/deploy-prod.sh "${ARGS[@]}"
  fi
fi
SHA="$(git rev-parse --short HEAD)"
echo "commit: $SHA"

for f in "${SQL[@]}"; do
  echo "== migración: $f =="
  "${COMPOSE[@]}" exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f - < "$f"
done
if [ ${#SQL[@]} -gt 0 ]; then
  # PostgREST guarda en memoria qué tablas y funciones existen. Una tabla
  # nueva se puede LEER igual (delega en Postgres), pero para INSERTAR
  # necesita conocer sus columnas, y contesta "404 {}" hasta que recarga.
  # Pasó con asistente_conversaciones: el sitio decía "Error interno" con
  # la tabla ya creada. El NOTIFY recarga sin reiniciar nada.
  echo "== PostgREST: recargar el esquema =="
  "${COMPOSE[@]}" exec -T postgres psql -U postgres -d postgres -c "NOTIFY pgrst, 'reload schema';"
fi

# IndexNow (docs/visibilidad-buscadores-ia.md §3.12): Bing exige la clave en
# https://uruku.bo/<clave>.txt. La clave vive sólo en backend/.env; el archivo
# se escribe acá, antes del build, porque Next sirve `public/` tal cual. Está
# en .gitignore: nunca se commitea.
# `|| true`: sin la clave, el grep no encuentra nada y con `set -e` cortaba el
# deploy en silencio, con las migraciones ya aplicadas y sin build.
INDEXNOW_KEY="$(grep -E '^INDEXNOW_KEY=' backend/.env 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r"' || true)"
if [ -n "$INDEXNOW_KEY" ]; then
  # El mismo formato que acepta el backend (indexnow.py): sin `/` ni `..`, el
  # archivo no puede caer fuera de public/.
  if ! [[ "$INDEXNOW_KEY" =~ ^[A-Za-z0-9-]{8,128}$ ]]; then
    echo "INDEXNOW_KEY inválida en backend/.env (sólo letras, números y guiones, 8 a 128)"; exit 1
  fi
  printf %s "$INDEXNOW_KEY" > "frontend/public/$INDEXNOW_KEY.txt"
  echo "IndexNow: clave publicada en /$INDEXNOW_KEY.txt"
fi

echo "== build: ${SERVICIOS[*]} =="
GIT_SHA="$SHA" APP_ENV=prod "${COMPOSE[@]}" up -d --build "${SERVICIOS[@]}"

# Esperar a que conteste con el commit nuevo. Hasta 2 minutos; en la práctica
# son 10-30 segundos.
esperar() {  # esperar <nombre> <url> <clave json>
  local nombre="$1" url="$2" clave="$3" i
  printf "== esperando %s " "$nombre"
  for i in $(seq 1 60); do
    if curl -sf --max-time 5 "$url" 2>/dev/null | grep -q "\"$clave\": *\"$SHA\""; then
      echo " listo ($((i * 2))s)"
      return 0
    fi
    printf "."
    sleep 2
  done
  echo
  echo "!! $nombre no contestó con $SHA en 2 minutos. Mirá: ${COMPOSE[*]} logs --tail 60 $nombre"
  return 1
}

for s in "${SERVICIOS[@]}"; do
  case "$s" in
    frontend) esperar frontend "https://$DOMINIO/version" commit ;;
    backend)  esperar backend  "https://api.$DOMINIO/health" commit ;;
  esac
done

echo "== contenedores =="
docker ps --format '{{.Names}}\t{{.Status}}' | grep buscadonde
echo "== listo: $SHA =="
