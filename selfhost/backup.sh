#!/usr/bin/env bash
# Backup diario de las bases Postgres del VPS (URUKU y, si está, Reservalo).
# Dump comprimido + rotación de 14 días. Sirve para prod y QA (respalda las
# bases que encuentre corriendo).
#
# Instalar (una vez, en el VPS):
#   cp /docker/uruku/selfhost/backup.sh /docker/backup.sh   # (o /docker/buscadonde/... en QA)
#   chmod +x /docker/backup.sh
#   crontab -e   # y agregar:
#   0 3 * * * /docker/backup.sh >> /docker/backups/backup.log 2>&1
#
# Restaurar un backup:
#   gunzip -c /docker/backups/<archivo>.sql.gz | docker exec -i <contenedor-postgres> psql -U postgres -d postgres
set -euo pipefail

DIR=/docker/backups
RETENCION_DIAS=14
mkdir -p "$DIR"
STAMP=$(date +%Y%m%d-%H%M)

for c in buscadonde-postgres reservalo-postgres; do
  if docker ps --format '{{.Names}}' | grep -qx "$c"; then
    out="$DIR/${c}-${STAMP}.sql.gz"
    if docker exec "$c" pg_dump -U postgres -d postgres | gzip > "$out"; then
      echo "$(date '+%F %T') OK  $c -> $out ($(du -h "$out" | cut -f1))"
    else
      echo "$(date '+%F %T') ERR $c (falló pg_dump)"
      rm -f "$out"
    fi
  fi
done

# Rotación: borrar dumps de más de N días
find "$DIR" -name '*.sql.gz' -mtime +"$RETENCION_DIAS" -delete
