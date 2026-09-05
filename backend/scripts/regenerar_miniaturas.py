#!/usr/bin/env python3
"""Rehace las miniaturas de portada que quedaron en 200px.

POR QUÉ
=======
La miniatura se generaba a 200px de lado, con un comentario que decía "84px en
la tarjeta". Era cierto cuando la tarjeta de resultados tenía la foto chica al
costado; el diseño pasó a portada ancha —la foto ocupa el ancho de la tarjeta,
unos 300px— y en una pantalla retina eso son 600px pedidos a una imagen de 200.
Se agranda tres veces y se ve borrosa. Nadie volvió a mirar ese número cuando
cambió el diseño.

`subir_foto_galeria` ya genera 600px, pero eso alcanza sólo a las fotos NUEVAS.
Este script rehace las que ya están, a partir de la grande (1280px) que sigue
guardada al lado.

GUARDA UN ARCHIVO NUEVO, NO PISA EL VIEJO
=========================================
La miniatura nueva va a `<token>_t2.jpg` y se actualiza `portada_thumb_url`.
Pisar el archivo con el mismo nombre habría sido más corto, pero la URL no
cambia y el navegador —y el nginx de adelante— siguen sirviendo la versión
cacheada. La foto seguiría viéndose borrosa y el informe diría que se arregló:
otra vez el resultado plausible.

USO
===
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python - < backend/scripts/regenerar_miniaturas.py

    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend \\
        python - < backend/scripts/regenerar_miniaturas.py

Sin APLICAR=1 sólo cuenta y muestra los primeros casos. Es idempotente: los que
ya tienen `_t2` se saltean, así que se puede cortar y volver a correr.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app")

from app.core.config import settings  # noqa: E402
from app.db.repository import get_repo  # noqa: E402
from app.services.imagenes import guardar_foto_local, procesar_imagen  # noqa: E402

LADO = 600
CALIDAD = 76


def ruta_local(url: str | None) -> Path | None:
    """De la URL pública al archivo en el volumen.

    Se corta por `/fotos/` en vez de armar la ruta desde el dominio: la URL
    pública cambió de host al mudarse a uruku.bo, y las guardadas antes tienen
    el host viejo. Lo que no cambió nunca es lo que va después de /fotos/.
    """
    if not url or "/fotos/" not in url:
        return None
    return Path(settings.fotos_dir) / url.split("/fotos/", 1)[1]


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    repo = get_repo()

    comercios = repo.list_todos_comercios(None, 5000)
    hechos, sin_archivo, ya_estaban, sin_foto = 0, 0, 0, 0
    ejemplos: list[str] = []

    for c in comercios:
        grande, thumb = c.get("portada_url"), c.get("portada_thumb_url")
        if not grande:
            sin_foto += 1
            continue
        if thumb and "_t2.jpg" in thumb:
            ya_estaban += 1
            continue

        origen = ruta_local(grande)
        if not origen or not origen.exists():
            sin_archivo += 1
            continue

        if len(ejemplos) < 5:
            ejemplos.append(f"{c.get('codigo')} {c.get('nombre')}")
        if not aplicar:
            hechos += 1
            continue

        try:
            chica = procesar_imagen(origen.read_bytes(), LADO, CALIDAD)
        except Exception as exc:  # noqa: BLE001 — una foto corrupta no corta la corrida
            print(f"  ! {c.get('codigo')}: {exc}")
            sin_archivo += 1
            continue

        sub = str(origen.relative_to(Path(settings.fotos_dir))).replace("\\", "/")
        nueva = sub.rsplit(".", 1)[0] + "_t2.jpg"
        url = guardar_foto_local(nueva, chica)
        if not url:
            sin_archivo += 1
            continue
        repo.update_comercio(c["id"], {"portada_thumb_url": url}, None)
        hechos += 1

    print(f"\n{'APLICADO' if aplicar else 'SIMULACIÓN'}")
    print(f"  miniaturas rehechas : {hechos}")
    print(f"  ya estaban al día   : {ya_estaban}")
    print(f"  sin archivo en disco: {sin_archivo}")
    print(f"  sin foto            : {sin_foto}")
    if ejemplos:
        print("  primeros:", " · ".join(ejemplos))
    if not aplicar:
        print("\n  Para escribir: APLICAR=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
