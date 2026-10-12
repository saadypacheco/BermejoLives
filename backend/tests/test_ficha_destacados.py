"""«Lo que suma» en la ficha del comercio (docs/ficha-destacados.md).

Cubre los 6 datos nuevos (por el comerciante y por el agente), el catálogo como
archivo PDF (subir, reemplazar, quitar, rechazar) y que el borrado de archivos
sólo toque lo que es nuestro. El `fotos_dir` es un tmp por test (autouse en
conftest), así que nada de esto escribe en el disco real.
"""
from pathlib import Path

import pytest

from app.core import auth
from app.core.config import settings
from app.services import ficha_catalogo as catalogo_svc
from tests.conftest import comercio_token

MB = 1024 * 1024


def _pdf(tam: int = 2048) -> bytes:
    return b"%PDF-1.4\n" + b"0" * (tam - 9)


def _subir(client, url, headers, data=None, nombre="catalogo.pdf"):
    data = _pdf() if data is None else data
    return client.post(url, headers=headers, files={"archivo": (nombre, data, "application/pdf")})


def _carpeta(slug: str) -> Path:
    return Path(settings.fotos_dir) / "catalogos" / slug


def _archivos(slug: str) -> list[str]:
    c = _carpeta(slug)
    return sorted(p.name for p in c.glob("*")) if c.exists() else []


def _archivo_de(url: str) -> Path:
    return Path(settings.fotos_dir) / url.split("/fotos/", 1)[1]


def _cabeceras_comercio(cid="com-f"):
    return {"Authorization": f"Bearer {comercio_token(comercio_id=cid)}"}


def _cabeceras_agente(email="agente@bermejolive.com", ciudad="bermejo"):
    return {"Authorization": f"Bearer {auth.make_agente_token(email, ciudad)}"}


@pytest.fixture(autouse=True)
def _sin_limite_de_subidas():
    """El contador de subidas por hora es del proceso: cada test arranca limpio."""
    catalogo_svc.reiniciar_limites()
    yield
    catalogo_svc.reiniciar_limites()


@pytest.fixture
def comercio(repo):
    return repo.seed_comercio(id="com-f", slug="tienda-f", nombre="Tienda F", whatsapp="59170001111",
                              ciudad_id="ciu-1", cargado_por="agente@bermejolive.com")


# ── Los 6 datos por el comerciante ───────────────────────────────────────────
def test_comerciante_guarda_los_seis_datos(client, repo, comercio):
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={
        "canal_wa_url": "https://whatsapp.com/channel/abc123",
        "catalogo_url": "https://drive.google.com/file/d/xyz",
        "tiene_pasero": True, "envios_internacionales": True, "tiene_factura": True,
        "pedido_minimo": "  3 unidades  ",
    })
    assert r.status_code == 200, r.text
    fila = repo.comercios["com-f"]
    assert fila["canal_wa_url"] == "https://whatsapp.com/channel/abc123"
    assert fila["catalogo_url"] == "https://drive.google.com/file/d/xyz"
    assert fila["tiene_pasero"] is True
    assert fila["envios_internacionales"] is True
    assert fila["tiene_factura"] is True
    assert fila["pedido_minimo"] == "3 unidades"
    # y el GET que usa Mi comercio los devuelve
    perfil = client.get("/comercio/perfil", headers=_cabeceras_comercio()).json()
    for campo in ("canal_wa_url", "catalogo_url", "tiene_pasero", "envios_internacionales",
                  "tiene_factura", "pedido_minimo"):
        assert perfil[campo] == fila[campo], campo


def test_comerciante_texto_vacio_borra(client, repo, comercio):
    comercio.update(canal_wa_url="https://x.com/c", catalogo_url="https://x.com/k", pedido_minimo="5")
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(),
                   json={"canal_wa_url": "", "catalogo_url": "   ", "pedido_minimo": ""})
    assert r.status_code == 200, r.text
    fila = repo.comercios["com-f"]
    assert fila["canal_wa_url"] is None
    assert fila["catalogo_url"] is None
    assert fila["pedido_minimo"] is None


def test_comerciante_los_booleanos_se_pueden_apagar(client, repo, comercio):
    comercio.update(tiene_pasero=True)
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={"tiene_pasero": False})
    assert r.status_code == 200, r.text
    assert repo.comercios["com-f"]["tiene_pasero"] is False


@pytest.mark.parametrize("campo", ["canal_wa_url", "catalogo_url"])
@pytest.mark.parametrize("valor", ["ftp://x.com/a", "javascript:alert(1)", "wa.me/59170001111", "https://", "http://a b.com"])
def test_comerciante_enlace_no_http_400(client, repo, comercio, campo, valor):
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={campo: valor})
    assert r.status_code == 400
    assert "http" in r.json()["detail"]
    assert campo not in repo.comercios["com-f"]


def test_comerciante_pedido_minimo_largo_400(client, repo, comercio):
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={"pedido_minimo": "x" * 121})
    assert r.status_code == 400
    ok = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={"pedido_minimo": "x" * 120})
    assert ok.status_code == 200


# ── Los 6 datos por el agente ────────────────────────────────────────────────
def test_agente_guarda_los_seis_datos(client, repo, comercio):
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(), json={
        "canal_wa_url": "https://whatsapp.com/channel/abc123",
        "catalogo_url": "https://tienda.example.com/catalogo",
        "tiene_pasero": True, "envios_internacionales": True, "tiene_factura": False,
        "pedido_minimo": "Compra mínima Bs 100",
    })
    assert r.status_code == 200, r.text
    fila = repo.comercios["com-f"]
    assert fila["canal_wa_url"] == "https://whatsapp.com/channel/abc123"
    assert fila["catalogo_url"] == "https://tienda.example.com/catalogo"
    assert fila["tiene_pasero"] is True
    assert fila["envios_internacionales"] is True
    assert fila["tiene_factura"] is False
    assert fila["pedido_minimo"] == "Compra mínima Bs 100"


def test_agente_texto_vacio_borra(client, repo, comercio):
    comercio.update(canal_wa_url="https://x.com/c", catalogo_url="https://x.com/k", pedido_minimo="5")
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(),
                     json={"canal_wa_url": "", "pedido_minimo": " "})
    assert r.status_code == 200, r.text
    fila = repo.comercios["com-f"]
    assert fila["canal_wa_url"] is None and fila["pedido_minimo"] is None
    assert fila["catalogo_url"] == "https://x.com/k"            # el catálogo no lo toca


def test_agente_no_vacia_el_catalogo_ni_con_un_enlace(client, repo, comercio):
    """El agente sólo sube (ronda 2): vaciar `catalogo_url` es quitarlo, y es del admin."""
    comercio.update(catalogo_url="https://x.com/k")
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(), json={"catalogo_url": ""})
    assert r.status_code == 403, r.text
    assert repo.comercios["com-f"]["catalogo_url"] == "https://x.com/k"


@pytest.mark.parametrize("campo", ["canal_wa_url", "catalogo_url"])
def test_agente_enlace_no_http_400(client, repo, comercio, campo):
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(), json={campo: "ftp://x.com/a"})
    assert r.status_code == 400
    assert "http" in r.json()["detail"]


def test_agente_pedido_minimo_largo_400(client, repo, comercio):
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(),
                     json={"pedido_minimo": "x" * 121})
    assert r.status_code == 400


def test_la_consulta_del_agente_trae_los_cuatro_campos_nuevos():
    from app.db.repository import _COLS_COMERCIO_CAMPO
    columnas = {c.strip() for c in _COLS_COMERCIO_CAMPO.split(",")}
    for campo in ("tiene_pasero", "envios_internacionales", "tiene_factura", "pedido_minimo",
                  "canal_wa_url", "catalogo_url"):
        assert campo in columnas, campo


# ── Subir el catálogo ────────────────────────────────────────────────────────
def test_comerciante_sube_pdf(client, repo, comercio):
    r = _subir(client, "/comercio/catalogo", _cabeceras_comercio())
    assert r.status_code == 200, r.text
    url = r.json()["catalogo_url"]
    assert repo.comercios["com-f"]["catalogo_url"] == url
    assert url.startswith(settings.fotos_public_base_url.rstrip("/") + "/catalogos/com-f/")
    assert url.endswith(".pdf")
    assert _archivo_de(url).read_bytes() == _pdf()


def test_agente_sube_pdf(client, repo, comercio):
    r = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente())
    assert r.status_code == 200, r.text
    url = r.json()["catalogo_url"]
    assert repo.comercios["com-f"]["catalogo_url"] == url
    assert _archivo_de(url).exists()


def test_el_pdf_se_sirve_como_application_pdf(client, repo, comercio):
    """/fotos es un StaticFiles (main.py): el tipo sale de la extensión. Se monta
    uno igual sobre el fotos_dir del test y se pide el PDF recién subido."""
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles
    from fastapi.testclient import TestClient

    url = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    estatico = FastAPI()
    estatico.mount("/fotos", StaticFiles(directory=settings.fotos_dir))
    r = TestClient(estatico).get("/fotos/" + url.split("/fotos/", 1)[1])
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content == _pdf()


def test_pdf_de_exactamente_8mb_pasa(client, repo, comercio):
    r = _subir(client, "/comercio/catalogo", _cabeceras_comercio(), data=_pdf(8 * MB))
    assert r.status_code == 200, r.text


def test_un_byte_de_mas_se_corta_en_la_lectura_por_trozos(client, repo, comercio):
    # Entra en la holgura del Content-Length: lo para el conteo de bytes leídos.
    r = _subir(client, "/comercio/catalogo", _cabeceras_comercio(), data=_pdf(8 * MB + 1))
    assert r.status_code == 413
    assert _archivos("com-f") == []


def test_pdf_de_9mb_se_rechaza_y_el_anterior_queda(client, repo, comercio):
    primero = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    r = _subir(client, "/comercio/catalogo", _cabeceras_comercio(), data=_pdf(9 * MB))
    assert r.status_code == 413
    assert r.json()["detail"] == "El catálogo puede pesar hasta 8 MB."
    assert repo.comercios["com-f"]["catalogo_url"] == primero
    assert _archivo_de(primero).exists()
    assert len(_archivos("com-f")) == 1


def test_agente_pdf_de_9mb_se_rechaza(client, repo, comercio):
    r = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente(), data=_pdf(9 * MB))
    assert r.status_code == 413
    assert _archivos("com-f") == []


def test_no_pdf_se_rechaza_aunque_se_llame_pdf(client, repo, comercio):
    primero = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    r = _subir(client, "/comercio/catalogo", _cabeceras_comercio(), data=b"MZ\x90\x00 no soy un pdf", nombre="catalogo.pdf")
    assert r.status_code == 400
    assert r.json()["detail"] == "El catálogo tiene que ser un PDF."
    assert repo.comercios["com-f"]["catalogo_url"] == primero
    assert _archivo_de(primero).exists()
    assert len(_archivos("com-f")) == 1


def test_una_imagen_no_es_un_catalogo(client, repo, comercio):
    r = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente(),
               data=b"\xff\xd8\xff\xe0" + b"0" * 100, nombre="foto.jpg")
    assert r.status_code == 400


def test_archivo_vacio_o_ausente_400(client, repo, comercio):
    assert _subir(client, "/comercio/catalogo", _cabeceras_comercio(), data=b"").status_code == 400
    r = client.post("/comercio/catalogo", headers=_cabeceras_comercio(), files={"otro": ("a.pdf", _pdf())})
    assert r.status_code == 400
    r = client.post("/comercio/catalogo", headers=_cabeceras_comercio())
    assert r.status_code == 400
    assert _archivos("com-f") == []


def test_el_tope_se_corta_antes_de_parsear_si_el_content_length_lo_delata(client, repo, comercio):
    # Un cuerpo declarado de 500 MB se rechaza sin leerlo.
    h = {**_cabeceras_comercio(), "Content-Length": str(500 * MB), "Content-Type": "multipart/form-data; boundary=x"}
    r = client.post("/comercio/catalogo", headers=h, content=b"--x--")
    assert r.status_code == 413


# ── Reemplazar ───────────────────────────────────────────────────────────────
def test_subir_otro_borra_el_archivo_anterior(client, repo, comercio):
    uno = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    dos = _subir(client, "/comercio/catalogo", _cabeceras_comercio(), data=_pdf(4096)).json()["catalogo_url"]
    assert uno != dos
    assert not _archivo_de(uno).exists()
    assert _archivo_de(dos).exists()
    assert _archivos("com-f") == [dos.rsplit("/", 1)[1]]
    assert repo.comercios["com-f"]["catalogo_url"] == dos


def test_el_agente_tambien_reemplaza_y_borra(client, repo, comercio):
    uno = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente()).json()["catalogo_url"]
    dos = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente()).json()["catalogo_url"]
    assert not _archivo_de(uno).exists() and _archivo_de(dos).exists()


def test_reemplazar_un_enlace_externo_no_borra_nada(client, repo, comercio, tmp_path):
    # Un archivo de otro lado, con nombre parecido, no se toca.
    ajeno = Path(settings.fotos_dir) / "catalogos" / "com-otro" / "aaaaaaaa.pdf"
    ajeno.parent.mkdir(parents=True)
    ajeno.write_bytes(_pdf())
    comercio["catalogo_url"] = "https://drive.google.com/file/d/xyz"
    r = _subir(client, "/comercio/catalogo", _cabeceras_comercio())
    assert r.status_code == 200, r.text
    assert ajeno.exists()
    assert len(_archivos("com-f")) == 1


def test_si_falla_la_base_no_queda_archivo_huerfano_ni_se_borra_el_viejo(client, repo, comercio, monkeypatch):
    viejo = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]

    def falla(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "update_comercio", falla)
    with pytest.raises(RuntimeError):
        _subir(client, "/comercio/catalogo", _cabeceras_comercio())
    assert _archivo_de(viejo).exists()
    assert len(_archivos("com-f")) == 1


def test_cambiar_el_catalogo_a_un_enlace_borra_el_pdf_nuestro(client, repo, comercio):
    pdf = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(),
                   json={"catalogo_url": "https://drive.google.com/file/d/nuevo"})
    assert r.status_code == 200, r.text
    assert not _archivo_de(pdf).exists()
    assert repo.comercios["com-f"]["catalogo_url"] == "https://drive.google.com/file/d/nuevo"


def test_el_agente_no_vacia_el_catalogo_por_patch_y_el_pdf_nuestro_queda(client, repo, comercio):
    pdf = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente()).json()["catalogo_url"]
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(), json={"catalogo_url": ""})
    assert r.status_code == 403, r.text
    assert _archivo_de(pdf).exists()
    assert repo.comercios["com-f"]["catalogo_url"] == pdf


def test_reenviar_el_mismo_catalogo_en_el_perfil_no_borra_el_pdf(client, repo, comercio):
    pdf = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(),
                   json={"catalogo_url": pdf, "pedido_minimo": "2"})
    assert r.status_code == 200, r.text
    assert _archivo_de(pdf).exists()


# ── Quitar ───────────────────────────────────────────────────────────────────
def test_comerciante_quita_el_catalogo(client, repo, comercio):
    url = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    r = client.delete("/comercio/catalogo", headers=_cabeceras_comercio())
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert repo.comercios["com-f"]["catalogo_url"] is None
    assert not _archivo_de(url).exists()


def test_agente_no_quita_el_catalogo(client, repo, comercio):
    """El agente sólo sube (ronda 2): quitar el catálogo borra el PDF, y eso es del admin."""
    url = _subir(client, "/campo/mis-comercios/com-f/catalogo", _cabeceras_agente()).json()["catalogo_url"]
    r = client.delete("/campo/mis-comercios/com-f/catalogo", headers=_cabeceras_agente())
    assert r.status_code == 403, r.text
    assert repo.comercios["com-f"]["catalogo_url"] == url
    assert _archivo_de(url).exists()


def test_quitar_con_enlace_externo_deja_null_y_barre_los_huerfanos(client, repo, comercio):
    """Si la columna ya apuntaba a un enlace, el PDF que quedara en la carpeta
    del comercio es un huérfano: la carpeta es sólo nuestra y se limpia."""
    huerfano = _subir(client, "/comercio/catalogo", _cabeceras_comercio()).json()["catalogo_url"]
    comercio["catalogo_url"] = "https://drive.google.com/file/d/xyz"
    r = client.delete("/comercio/catalogo", headers=_cabeceras_comercio())
    assert r.status_code == 200
    assert repo.comercios["com-f"]["catalogo_url"] is None
    assert not _archivo_de(huerfano).exists()


def test_quitar_sin_catalogo_es_ok(client, repo, comercio):
    assert client.delete("/comercio/catalogo", headers=_cabeceras_comercio()).status_code == 200


# ── Qué se puede borrar ──────────────────────────────────────────────────────
def _url(rel: str) -> str:
    return settings.fotos_public_base_url.rstrip("/") + "/" + rel


def test_archivo_propio_solo_acepta_la_carpeta_del_comercio(comercio):
    Path(settings.fotos_dir, "catalogos", "com-f").mkdir(parents=True)
    assert catalogo_svc.archivo_propio(_url("catalogos/com-f/abcdef0123456789.pdf"), "com-f") is not None
    malos = [
        _url("catalogos/com-otro/abcdef0123456789.pdf"),         # catálogo de otro comercio
        _url("catalogos/com-f/../com-otro/abcdef0123456789.pdf"),
        _url("catalogos/com-f/..%2Fx.pdf"),
        _url("catalogos/com-f/abc.pdf"),                         # nombre no generado por nosotros
        _url("catalogos/com-f/abcdef0123456789.jpg"),
        _url("com-f/abcdef0123456789.jpg"),                      # foto del comercio
        _url("catalogos/com-f/sub/abcdef0123456789.pdf"),
        _url("catalogos/com-f/abcdef0123456789.pdf?x=1"),
        "https://drive.google.com/catalogos/com-f/abcdef0123456789.pdf",
        "/etc/passwd",
        None,
        "",
    ]
    for u in malos:
        assert catalogo_svc.archivo_propio(u, "com-f") is None, u


def test_un_id_con_path_traversal_no_borra_nada(tmp_path):
    fuera = tmp_path / "fotos" / "secreto.pdf"
    fuera.parent.mkdir(parents=True, exist_ok=True)
    fuera.write_bytes(_pdf())
    for slug in ("..", "../x", "a/b", ".", ""):
        assert catalogo_svc.archivo_propio(_url(f"catalogos/{slug}/abcdef0123456789.pdf"), slug) is None
    assert fuera.exists()


def test_el_comercio_no_puede_hacer_borrar_el_catalogo_de_otro(client, repo, comercio):
    """Pega la URL del PDF de otro local como su catálogo y después sube uno
    propio: el archivo ajeno tiene que seguir ahí."""
    repo.seed_comercio(id="com-g", slug="tienda-g", nombre="Tienda G", whatsapp="59170002222")
    ajeno = _subir(client, "/comercio/catalogo", _cabeceras_comercio("com-g")).json()["catalogo_url"]
    client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={"catalogo_url": ajeno})
    _subir(client, "/comercio/catalogo", _cabeceras_comercio())
    assert _archivo_de(ajeno).exists()
    client.delete("/comercio/catalogo", headers=_cabeceras_comercio())
    assert _archivo_de(ajeno).exists()


# ── Permisos ─────────────────────────────────────────────────────────────────
def test_agente_de_otra_ciudad_404(client, repo, comercio):
    h = _cabeceras_agente(email="otro@bermejolive.com", ciudad="atlantida")
    assert _subir(client, "/campo/mis-comercios/com-f/catalogo", h).status_code == 404
    assert client.delete("/campo/mis-comercios/com-f/catalogo", headers=h).status_code == 404
    assert client.patch("/campo/mis-comercios/com-f", headers=h, json={"tiene_pasero": True}).status_code == 404
    assert _archivos("com-f") == []
    assert "tiene_pasero" not in repo.comercios["com-f"]


def test_agente_de_otra_ciudad_con_ciudad_valida_404(client, repo, comercio):
    h = _cabeceras_agente(email="otro@bermejolive.com", ciudad="santa-cruz")
    assert _subir(client, "/campo/mis-comercios/com-f/catalogo", h).status_code == 404


def test_comercio_inexistente_404(client, repo):
    assert _subir(client, "/campo/mis-comercios/no-hay/catalogo", _cabeceras_agente()).status_code == 404


def test_sin_token_401(client, repo, comercio):
    pdf = {"archivo": ("c.pdf", _pdf(), "application/pdf")}
    assert client.post("/comercio/catalogo", files=pdf).status_code == 401
    assert client.delete("/comercio/catalogo").status_code == 401
    assert client.post("/campo/mis-comercios/com-f/catalogo", files=pdf).status_code == 401
    assert client.delete("/campo/mis-comercios/com-f/catalogo").status_code == 401
    assert client.put("/comercio/perfil", json={"tiene_pasero": True}).status_code == 401
    assert _archivos("com-f") == []


def test_un_token_de_agente_no_sirve_en_los_endpoints_del_comercio(client, repo, comercio):
    assert _subir(client, "/comercio/catalogo", _cabeceras_agente()).status_code in (401, 403)


# ── Migración 0141 ───────────────────────────────────────────────────────────
def _migracion(carpeta: str) -> bytes:
    raiz = Path(__file__).resolve().parents[2]
    return (raiz / carpeta / "0141_comercio_pasero.sql").read_bytes()


def test_la_migracion_0141_esta_igual_en_supabase_y_en_selfhost():
    assert _migracion("supabase/migrations") == _migracion("selfhost/postgres-init")


def test_la_migracion_0141_es_idempotente_y_recarga_el_esquema():
    sql = " ".join(_migracion("supabase/migrations").decode("utf-8").lower().split())
    assert "add column if not exists tiene_pasero boolean not null default false" in sql
    assert "comment on column comercios.tiene_pasero" in sql
    assert "notify pgrst, 'reload schema'" in sql


# ── Talles especiales (0142) ─────────────────────────────────────────────────
def test_comerciante_marca_talles_especiales_y_el_perfil_lo_devuelve(client, repo, comercio):
    r = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={"talles_especiales": True})
    assert r.status_code == 200, r.text
    assert repo.comercios["com-f"]["talles_especiales"] is True
    perfil = client.get("/comercio/perfil", headers=_cabeceras_comercio()).json()
    assert perfil["talles_especiales"] is True
    apagado = client.put("/comercio/perfil", headers=_cabeceras_comercio(), json={"talles_especiales": False})
    assert apagado.status_code == 200
    assert repo.comercios["com-f"]["talles_especiales"] is False


def test_agente_marca_talles_especiales(client, repo, comercio):
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(), json={"talles_especiales": True})
    assert r.status_code == 200, r.text
    assert repo.comercios["com-f"]["talles_especiales"] is True


def test_talles_especiales_en_null_no_se_toca(client, repo, comercio):
    comercio.update(talles_especiales=True)
    r = client.patch("/campo/mis-comercios/com-f", headers=_cabeceras_agente(),
                     json={"talles_especiales": None, "pedido_minimo": "2 unidades"})
    assert r.status_code == 200, r.text
    assert repo.comercios["com-f"]["talles_especiales"] is True


def test_la_lista_del_agente_trae_talles_especiales():
    from app.db.repository import _COLS_COMERCIO_CAMPO
    assert "talles_especiales" in _COLS_COMERCIO_CAMPO


def test_la_migracion_0142_esta_igual_en_supabase_y_en_selfhost():
    raiz = Path(__file__).resolve().parents[2]
    a = (raiz / "supabase/migrations/0142_talles_especiales.sql").read_bytes()
    b = (raiz / "selfhost/postgres-init/0142_talles_especiales.sql").read_bytes()
    assert a == b
    texto = a.decode("utf-8")
    assert "add column if not exists talles_especiales boolean not null default false" in texto
    assert "notify pgrst, 'reload schema'" in texto
