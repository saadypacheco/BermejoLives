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
git pull --ff-only
SHA="$(git rev-parse --short HEAD)"
echo "commit: $SHA"

for f in "${SQL[@]}"; do
  echo "== migración: $f =="
  "${COMPOSE[@]}" exec -T postgres psql -U postgres -d postgres -v ON_ERROR_STOP=1 -f - < "$f"
done

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
