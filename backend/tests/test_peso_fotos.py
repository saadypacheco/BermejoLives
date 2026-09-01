"""Peso de las fotos: medir, y recomprimir sin romper nada."""
from io import BytesIO
from pathlib import Path

import pytest

from app.services.peso_fotos import medir, optimizar


def _jpeg(tmp: Path, nombre: str, lado: int = 700) -> Path:
    """Una foto grande y ruidosa: lisa comprime tanto que no sirve de caso."""
    from PIL import Image

    import random
    random.seed(lado)
    img = Image.new("RGB", (lado, lado))
    img.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
                 for _ in range(lado * lado)])
    ruta = tmp / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=95)
    ruta.write_bytes(buf.getvalue())
    return ruta


def test_medir_separa_imagenes_de_videos(tmp_path):
    _jpeg(tmp_path, "local-a/portada.jpg", 400)
    (tmp_path / "local-a/videos").mkdir(parents=True)
    (tmp_path / "local-a/videos/x.mp4").write_bytes(b"0" * 5_000_000)

    r = medir(str(tmp_path))

    assert r["imagenes"]["n"] == 1
    assert r["videos"]["n"] == 1
    assert r["videos"]["bytes"] == 5_000_000


def test_medir_dir_inexistente_no_revienta(tmp_path):
    assert medir(str(tmp_path / "no-existe"))["existe"] is False


def test_optimizar_achica_y_conserva_el_nombre(tmp_path):
    """El nombre no puede cambiar: las URLs están guardadas en la base."""
    ruta = _jpeg(tmp_path, "local-a/portada.jpg")
    antes = ruta.stat().st_size

    r = optimizar(str(tmp_path), max_kb=50, limite=10)

    assert r["optimizados"] == 1
    assert ruta.exists()                      # mismo archivo, misma URL
    assert ruta.stat().st_size < antes
    assert r["ahorro_bytes"] == antes - ruta.stat().st_size


def test_optimizar_no_toca_los_videos(tmp_path):
    """Un video pasado por el procesador de imágenes se destruye, y son
    justamente los archivos más pesados."""
    (tmp_path / "local-a/videos").mkdir(parents=True)
    video = tmp_path / "local-a/videos/x.mp4"
    crudo = b"\x00\x00\x00\x18ftypmp42" + b"0" * 9_000_000
    video.write_bytes(crudo)

    r = optimizar(str(tmp_path), max_kb=50, limite=10)

    assert r["optimizados"] == 0
    assert video.read_bytes() == crudo


def test_optimizar_no_agranda_al_correrlo_dos_veces(tmp_path):
    """Recomprimir un JPEG ya comprimido a veces lo agranda. Sin la guarda,
    apretar el botón dos veces dejaba todo más pesado que al principio."""
    ruta = _jpeg(tmp_path, "local-a/portada.jpg")

    optimizar(str(tmp_path), max_kb=50, limite=10)
    tras_una = ruta.stat().st_size
    optimizar(str(tmp_path), max_kb=50, limite=10)

    assert ruta.stat().st_size <= tras_una


def test_optimizar_respeta_el_umbral(tmp_path):
    _jpeg(tmp_path, "local-a/chica.jpg", 120)
    r = optimizar(str(tmp_path), max_kb=500, limite=10)
    assert r["revisados"] == 0 and r["optimizados"] == 0


def test_optimizar_avisa_cuantas_quedaron_afuera(tmp_path):
    """"optimizadas 1" se lee como "listo" cuando faltan tres."""
    for i in range(4):
        _jpeg(tmp_path, f"local-{i}/portada.jpg", 700 + i)

    r = optimizar(str(tmp_path), max_kb=50, limite=1)

    assert r["optimizados"] == 1
    assert r["restantes"] == 3
