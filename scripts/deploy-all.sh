#!/usr/bin/env bash
# Deploy conjunto Encontralo + Reservalo (correr en el VPS).
# Repos separados, un solo comando. Ajustá los paths si difieren.
set -euo pipefail

ENC_DIR="/docker/buscadonde"   # Encontralo (este repo)
RES_DIR="/docker/reservalo"    # Reservalo (confirmar path real)

echo "== Encontralo =="
cd "$ENC_DIR"
git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

echo "== Reservalo =="
cd "$RES_DIR"
git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build

echo "== Listo. Containers: =="
docker ps --format '{{.Names}}\t{{.Status}}'
