#!/usr/bin/env bash
# Copia las migraciones reales (schema + RLS) a selfhost/postgres-init/, para
# que Postgres las corra solas la primera vez que arranca con el volumen
# vacío (docker-entrypoint-initdb.d corre *.sql en orden alfabético).
#
# Se EXCLUYEN a propósito:
#   0003_seed.sql            -> datos de ejemplo/prueba (comercios ficticios,
#                                picsum.photos, whatsapp 5917000000X) — el
#                                agente de campo va a cargar negocios reales.
#   0007_storage_comercios.sql -> crea un bucket de Supabase Storage; el
#                                self-host no corre storage-api (las fotos
#                                se guardan en disco, ver services/imagenes.py).
#
# Re-correr este script cada vez que se agregue una migración nueva en
# supabase/migrations/, ANTES del primer arranque de un Postgres nuevo.
# Si el volumen de Postgres ya tiene datos, docker-entrypoint-initdb.d NO
# vuelve a correr nada — las migraciones nuevas hay que aplicarlas a mano.
set -euo pipefail
cd "$(dirname "$0")"

rm -f postgres-init/00[0-9][0-9]_*.sql
for f in ../supabase/migrations/*.sql; do
  base="$(basename "$f")"
  case "$base" in
    0003_seed.sql|0007_storage_comercios.sql)
      echo "omitido: $base"
      ;;
    *)
      cp "$f" "postgres-init/$base"
      ;;
  esac
done
echo "listo — $(ls postgres-init/*.sql | wc -l) archivos en postgres-init/"
