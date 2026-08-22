#!/usr/bin/env python3
"""Rehace las miniaturas existentes al tamaño nuevo, desde la foto grande.

Por qué: las miniaturas se generaban a 400px pero se muestran a 22px en el pin
del mapa, 34px en la lista y 84px en la tarjeta. El mapa de Bermejo abre ~160 de
una sola vez, así que eran unos 5 MB para dibujar pines diminutos — lo que se
siente como "el buscador va lento" en una conexión mala.

A 200px cubre el doble del tamaño de pantalla más grande (pantallas retina) y
pesa alrededor de un tercio.

Uso, dentro del contenedor del backend:
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/regenerar_miniaturas.py --aplicar

Sin --aplicar sólo informa cuánto se ahorraría. No toca la base: los nombres de
archivo no cambian, así que las URLs guardadas siguen sirviendo.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.core.config import settings          # noqa: E402
from app.services.imagenes import procesar_imagen  # noqa: E402

LADO = 200
CALIDAD = 72


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--aplicar", action="store_true", help="escribir; sin esto sólo informa")
    ap.add_argument("--lado", type=int, default=LADO)
    ap.add_argument("--calidad", type=int, default=CALIDAD)
    args = ap.parse_args()

    raiz = Path(settings.fotos_dir)
    if not raiz.is_dir():
        print(f"No existe {raiz}")
        return 1

    thumbs = sorted(raiz.rglob("*_t.jpg"))
    if not thumbs:
        print("No hay miniaturas para procesar.")
        return 0

    antes = despues = 0
    saltadas = errores = 0

    for thumb in thumbs:
        # La grande es el mismo nombre sin el sufijo _t.
        grande = thumb.with_name(thumb.name[:-6] + ".jpg")
        if not grande.is_file():
            saltadas += 1
            continue
        try:
            nueva = procesar_imagen(grande.read_bytes(), args.lado, args.calidad)
        except Exception as exc:  # noqa: BLE001
            print(f"  error en {thumb.name}: {exc}")
            errores += 1
            continue

        peso_viejo = thumb.stat().st_size
        antes += peso_viejo
        despues += len(nueva)
        if args.aplicar:
            thumb.write_bytes(nueva)

    n = len(thumbs) - saltadas - errores
    print(f"Miniaturas procesadas: {n}"
          + (f" · sin foto grande: {saltadas}" if saltadas else "")
          + (f" · con error: {errores}" if errores else ""))
    if n:
        print(f"  antes:   {antes/1024/1024:.1f} MB  ({antes/n/1024:.0f} KB promedio)")
        print(f"  después: {despues/1024/1024:.1f} MB  ({despues/n/1024:.0f} KB promedio)")
        ahorro = 100 * (1 - despues / antes) if antes else 0
        print(f"  ahorro:  {ahorro:.0f}%")
    print("APLICADO" if args.aplicar else "\nSimulación. Volvé a correrlo con --aplicar para escribir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
