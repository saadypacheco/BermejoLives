"""QR de cobro: archivo del servidor, endpoints públicos de sólo lectura."""
import io
import os

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import settings
from app.main import app
from app.services import pago_qr

client = TestClient(app)


def _imagen(ruta, formato="PNG", exif=False, tam=(40, 40)):
    im = Image.new("RGB", tam, (10, 20, 30))
    kw = {}
    if exif:
        e = Image.Exif()
        e[0x010F] = "CamaraSecreta"
        kw["exif"] = e
    im.save(ruta, format=formato, **kw)


@pytest.fixture(autouse=True)
def _limpio(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "pago_qr_path", "")
    monkeypatch.setattr(settings, "pago_titular", "")
    monkeypatch.setattr(settings, "pago_banco", "")
    monkeypatch.setattr(settings, "pago_nota", "")
    monkeypatch.setattr(settings, "fotos_dir", str(tmp_path / "fotos"))
    pago_qr._cache.clear()
    monkeypatch.setattr(pago_qr, "_huella_base", None)
    pago_qr._cambio_avisado.clear()
    yield


def test_info_sin_archivo_no_disponible():
    r = client.get("/pago/qr/info")
    assert r.status_code == 200
    assert r.json() == {
        "disponible": False, "titular": None, "banco": None, "nota": None,
        "actualizado": None, "huella": None, "whatsapp_comprobante": "59167671888",
    }


def test_info_ruta_inexistente(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "pago_qr_path", str(tmp_path / "no_esta.png"))
    assert client.get("/pago/qr/info").json()["disponible"] is False


def test_info_con_archivo(monkeypatch, tmp_path):
    qr = tmp_path / "pago" / "qr.png"
    qr.parent.mkdir()
    _imagen(qr)
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    monkeypatch.setattr(settings, "pago_titular", "URUKU SRL")
    monkeypatch.setattr(settings, "pago_banco", "Banco X")
    monkeypatch.setattr(settings, "pago_nota", "Monto abierto")
    d = client.get("/pago/qr/info").json()
    assert d["disponible"] is True
    assert (d["titular"], d["banco"], d["nota"]) == ("URUKU SRL", "Banco X", "Monto abierto")
    assert len(d["huella"]) == 12 and d["actualizado"]
    assert d["whatsapp_comprobante"] == settings.wa_contacto_publico


def test_imagen_404_sin_archivo():
    assert client.get("/pago/qr/imagen").status_code == 404


def test_imagen_png_sin_exif_con_cache_y_etag(monkeypatch, tmp_path):
    qr = tmp_path / "qr.jpg"
    _imagen(qr, formato="JPEG", exif=True)
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    r = client.get("/pago/qr/imagen")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=300"
    huella = client.get("/pago/qr/info").json()["huella"]
    assert r.headers["etag"] == f'"{huella}"'
    im = Image.open(io.BytesIO(r.content))
    assert im.format == "PNG" and len(im.getexif()) == 0
    assert b"CamaraSecreta" not in r.content
    r2 = client.get("/pago/qr/imagen", headers={"If-None-Match": f'"{huella}"'})
    assert r2.status_code == 304


def test_traversal_rechazado(monkeypatch, tmp_path):
    secreto = tmp_path / "secreto.png"
    _imagen(secreto)
    (tmp_path / "pago").mkdir()
    monkeypatch.setattr(settings, "pago_qr_path", str(tmp_path / "pago" / ".." / "secreto.png"))
    assert client.get("/pago/qr/info").json()["disponible"] is False
    assert client.get("/pago/qr/imagen").status_code == 404


def test_symlink_hacia_afuera_rechazado(monkeypatch, tmp_path):
    secreto = tmp_path / "secreto.png"
    _imagen(secreto)
    carpeta = tmp_path / "pago"
    carpeta.mkdir()
    try:
        os.symlink(secreto, carpeta / "qr.png")
    except (OSError, NotImplementedError):
        pytest.skip("sin permiso para symlinks en este sistema")
    monkeypatch.setattr(settings, "pago_qr_path", str(carpeta / "qr.png"))
    assert client.get("/pago/qr/info").json()["disponible"] is False


def test_ruta_bajo_fotos_rechazada(monkeypatch, tmp_path):
    fotos = tmp_path / "fotos"
    fotos.mkdir()
    qr = fotos / "qr.png"
    _imagen(qr)
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    assert client.get("/pago/qr/info").json()["disponible"] is False


def test_imagen_invalida_no_disponible(monkeypatch, tmp_path):
    qr = tmp_path / "qr.png"
    qr.write_bytes(b"esto no es una imagen")
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    assert client.get("/pago/qr/info").json()["disponible"] is False
    assert client.get("/pago/qr/imagen").status_code == 404


def test_extension_no_imagen_rechazada(monkeypatch, tmp_path):
    qr = tmp_path / "qr.txt"
    _imagen(qr)
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    assert client.get("/pago/qr/info").json()["disponible"] is False


def test_archivo_demasiado_grande(monkeypatch, tmp_path):
    qr = tmp_path / "qr.png"
    _imagen(qr)
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    monkeypatch.setattr(pago_qr, "MAX_BYTES", 10)
    assert client.get("/pago/qr/info").json()["disponible"] is False


def test_cambio_de_huella_avisa(monkeypatch, tmp_path):
    qr = tmp_path / "qr.png"
    _imagen(qr, tam=(40, 40))
    monkeypatch.setattr(settings, "pago_qr_path", str(qr))
    avisos = []
    monkeypatch.setattr(pago_qr.logger, "warning", lambda ev, **kw: avisos.append(ev))
    pago_qr.registrar_arranque()
    assert client.get("/pago/qr/info").json()["disponible"] is True
    assert "pago.qr_cambio" not in avisos
    _imagen(qr, tam=(60, 60))
    assert client.get("/pago/qr/info").json()["disponible"] is True
    assert avisos.count("pago.qr_cambio") == 1
