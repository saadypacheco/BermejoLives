"""«Lo que suma» en el editor del admin (docs/ficha-destacados.md, P4 de
docs/analisis-edicion-comercio.md).

- PUT /admin/comercio/{id}: canal_wa_url, catalogo_url, tiene_pasero, talles_especiales
  (y pedido_minimo, tiene_factura, envios_internacionales) con la MISMA validación
  que el agente y el comerciante.
- POST/DELETE /admin/comercio/{id}/catalogo: el PDF, con borrado del archivo viejo.
- El permiso `comercios.editar` y el tope de 8 MB.
- Las columnas de la lista que llena el modal «Editar negocio».
"""
from pathlib import Path

import pytest

from app.core import auth
from app.core.config import settings
from app.core.limite_cuerpo import HOLGURA, tope_para
from app.services import ficha_catalogo as catalogo_svc

MB = 1024 * 1024
CID = "com-a"


def _pdf(tam: int = 2048) -> bytes:
    return b"%PDF-1.4\n" + b"0" * (tam - 9)


def _h(permisos=("comercios.editar",)):
    return {"Authorization": f"Bearer {auth.make_token('pub@bermejolive.com', rol='x', permisos=list(permisos))}"}


def _subir(client, cid=CID, headers=None, data=None):
    data = _pdf() if data is None else data
    return client.post(f"/admin/comercio/{cid}/catalogo", headers=headers or _h(),
                       files={"archivo": ("c.pdf", data, "application/pdf")})


def _archivos(cid: str) -> list[str]:
    c = Path(settings.fotos_dir) / "catalogos" / cid
    return sorted(p.name for p in c.glob("*")) if c.exists() else []


def _archivo_de(url: str) -> Path:
    return Path(settings.fotos_dir) / url.split("/fotos/", 1)[1]


@pytest.fixture(autouse=True)
def _sin_limite_de_subidas():
    catalogo_svc.reiniciar_limites()
    yield
    catalogo_svc.reiniciar_limites()


@pytest.fixture
def comercio(repo):
    return repo.seed_comercio(id=CID, slug="tienda-a", nombre="Tienda A", whatsapp="59170001111", ciudad_id="ciu-1")


def _put(client, body, headers=None, cid=CID):
    return client.put(f"/admin/comercio/{cid}", headers=headers or _h(), json=body)


# ── Guardar cada campo ───────────────────────────────────────────────────────
@pytest.mark.parametrize("campo,valor,guardado", [
    ("canal_wa_url", "https://whatsapp.com/channel/0029Va", "https://whatsapp.com/channel/0029Va"),
    ("canal_wa_url", "https://wa.me/59170001111", "https://wa.me/59170001111"),
    ("catalogo_url", "https://drive.google.com/file/d/abc", "https://drive.google.com/file/d/abc"),
    ("tiene_pasero", True, True),
    ("tiene_pasero", False, False),
    ("talles_especiales", True, True),
    ("talles_especiales", False, False),
    ("tiene_factura", True, True),
    ("envios_internacionales", True, True),
    ("pedido_minimo", "  3 docenas  ", "3 docenas"),
])
def test_el_admin_guarda_cada_campo_de_lo_que_suma(client, repo, comercio, campo, valor, guardado):
    r = _put(client, {campo: valor})
    assert r.status_code == 200, r.text
    assert repo.comercios[CID][campo] == guardado
    assert r.json()["comercio"][campo] == guardado


def test_el_admin_guarda_todo_junto(client, repo, comercio):
    r = _put(client, {"canal_wa_url": "https://wa.me/59170001111", "catalogo_url": "https://tienda.com/cat",
                      "tiene_pasero": True, "talles_especiales": True, "tiene_factura": True,
                      "envios_internacionales": True, "pedido_minimo": "5 unidades"})
    assert r.status_code == 200, r.text
    c = repo.comercios[CID]
    assert (c["canal_wa_url"], c["catalogo_url"], c["pedido_minimo"]) == (
        "https://wa.me/59170001111", "https://tienda.com/cat", "5 unidades")
    assert all(c[k] is True for k in ("tiene_pasero", "talles_especiales", "tiene_factura", "envios_internacionales"))


@pytest.mark.parametrize("campo", ["canal_wa_url", "catalogo_url", "pedido_minimo"])
def test_un_texto_vacio_borra_el_dato(client, repo, comercio, campo):
    repo.comercios[CID][campo] = "https://wa.me/1" if campo != "pedido_minimo" else "algo"
    r = _put(client, {campo: "   "})
    assert r.status_code == 200, r.text
    assert repo.comercios[CID][campo] is None


def test_un_booleano_en_false_se_guarda_y_en_null_no_se_toca(client, repo, comercio):
    repo.comercios[CID]["tiene_pasero"] = True
    assert _put(client, {"tiene_pasero": None, "nombre": "Otro"}).status_code == 200
    assert repo.comercios[CID]["tiene_pasero"] is True
    assert _put(client, {"tiene_pasero": False}).status_code == 200
    assert repo.comercios[CID]["tiene_pasero"] is False


# ── Validaciones: el mismo texto que el agente y el comerciante ──────────────
@pytest.mark.parametrize("valor", ["https://t.me/canal", "https://evil.com/whatsapp.com", "https://whatsapp.com.evil.com/c"])
def test_canal_que_no_es_de_whatsapp_400(client, repo, comercio, valor):
    r = _put(client, {"canal_wa_url": valor})
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "El canal tiene que ser un enlace de WhatsApp."
    assert "canal_wa_url" not in repo.comercios[CID]


@pytest.mark.parametrize("campo", ["canal_wa_url", "catalogo_url"])
@pytest.mark.parametrize("valor", ["javascript:alert(1)", "ftp://x.com/a", "https://a.com@evil.com/x",
                                   "http://127.0.0.1/c", "http://[::1", "data:text/html;base64,PHNjcmlwdD4="])
def test_enlace_no_http_o_peligroso_400_en_espanol(client, repo, comercio, campo, valor):
    r = _put(client, {campo: valor})
    assert r.status_code == 400, (valor, r.text)
    assert "Invalid" not in r.json()["detail"]
    assert r.json()["detail"].startswith("El enlace") or r.json()["detail"].startswith("El canal")
    assert campo not in repo.comercios[CID]


def test_las_mismas_respuestas_que_el_comerciante_y_el_agente(client, repo, comercio):
    """Mismo texto de error por las tres vías (la regla vive en ficha_catalogo)."""
    from tests.conftest import comercio_token
    hc = {"Authorization": f"Bearer {comercio_token(comercio_id=CID)}"}
    ha = {"Authorization": f"Bearer {auth.make_agente_token('agente@bermejolive.com', 'bermejo')}"}
    repo.comercios[CID]["cargado_por"] = "agente@bermejolive.com"
    for body in ({"canal_wa_url": "https://t.me/x"}, {"catalogo_url": "javascript:alert(1)"},
                 {"pedido_minimo": "x" * 121}):
        a = _put(client, body)
        b = client.put("/comercio/perfil", headers=hc, json=body)
        c = client.patch(f"/campo/mis-comercios/{CID}", headers=ha, json=body)
        assert a.status_code == b.status_code == c.status_code == 400, (body, a.text, b.text, c.text)
        assert a.json()["detail"] == b.json()["detail"] == c.json()["detail"]


def test_pedido_minimo_de_mas_de_120_caracteres_400(client, repo, comercio):
    assert _put(client, {"pedido_minimo": "x" * 120}).status_code == 200
    assert _put(client, {"pedido_minimo": "x" * 121}).status_code == 400


def test_un_error_de_validacion_no_guarda_nada(client, repo, comercio):
    r = _put(client, {"tiene_pasero": True, "canal_wa_url": "https://t.me/x"})
    assert r.status_code == 400
    assert "tiene_pasero" not in repo.comercios[CID]


# ── Subir / reemplazar / quitar el PDF ───────────────────────────────────────
def test_subir_el_pdf_lo_guarda_y_devuelve_la_url(client, repo, comercio):
    r = _subir(client)
    assert r.status_code == 200, r.text
    url = r.json()["catalogo_url"]
    assert f"/catalogos/{CID}/" in url and url.endswith(".pdf")
    assert repo.comercios[CID]["catalogo_url"] == url
    assert _archivo_de(url).read_bytes().startswith(b"%PDF-")


def test_subir_otro_pdf_borra_el_viejo_del_disco(client, repo, comercio):
    viejo = _subir(client, data=_pdf(2048)).json()["catalogo_url"]
    nuevo = _subir(client, data=_pdf(4096)).json()["catalogo_url"]
    assert viejo != nuevo
    assert not _archivo_de(viejo).exists()
    assert _archivos(CID) == [nuevo.rsplit("/", 1)[1]]


def test_quitar_el_pdf_lo_borra_y_deja_null(client, repo, comercio):
    url = _subir(client).json()["catalogo_url"]
    r = client.delete(f"/admin/comercio/{CID}/catalogo", headers=_h())
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert repo.comercios[CID]["catalogo_url"] is None
    assert not _archivo_de(url).exists() and _archivos(CID) == []


def test_quitar_cuando_era_un_enlace_solo_limpia_la_columna(client, repo, comercio):
    repo.comercios[CID]["catalogo_url"] = "https://drive.google.com/x"
    r = client.delete(f"/admin/comercio/{CID}/catalogo", headers=_h())
    assert r.status_code == 200
    assert repo.comercios[CID]["catalogo_url"] is None


@pytest.mark.parametrize("nuevo", ["https://drive.google.com/file/d/nuevo", "", "   "])
def test_mandar_un_enlace_o_vacio_borra_el_pdf_viejo(client, repo, comercio, nuevo):
    url = _subir(client).json()["catalogo_url"]
    assert _archivo_de(url).exists()
    r = _put(client, {"catalogo_url": nuevo})
    assert r.status_code == 200, r.text
    assert repo.comercios[CID]["catalogo_url"] == (nuevo.strip() or None)
    assert not _archivo_de(url).exists()


def test_mandar_de_vuelta_la_misma_url_no_borra_el_pdf(client, repo, comercio):
    """El modal reenvía lo que recibió: no puede costar el archivo."""
    url = _subir(client).json()["catalogo_url"]
    r = _put(client, {"catalogo_url": url, "tiene_pasero": True})
    assert r.status_code == 200, r.text
    assert repo.comercios[CID]["catalogo_url"] == url
    assert _archivo_de(url).exists()


def test_el_pdf_de_otro_comercio_no_se_borra(client, repo, comercio):
    repo.seed_comercio(id="com-b", slug="tienda-b", nombre="B", whatsapp="59170002222")
    ajeno = _subir(client, cid="com-b").json()["catalogo_url"]
    repo.comercios[CID]["catalogo_url"] = ajeno           # apunta al PDF de otro
    assert _put(client, {"catalogo_url": "https://drive.google.com/x"}).status_code == 200
    assert _archivo_de(ajeno).exists()


def test_subir_a_un_comercio_inexistente_404(client, repo):
    assert _subir(client, cid="no-existe").status_code == 404
    assert client.delete("/admin/comercio/no-existe/catalogo", headers=_h()).status_code == 404
    assert _archivos("no-existe") == []


def test_el_archivo_tiene_que_ser_un_pdf_y_falta_el_archivo_400(client, repo, comercio):
    assert _subir(client, data=b"no soy un pdf").status_code == 400
    r = client.post(f"/admin/comercio/{CID}/catalogo", headers=_h(), files={"otro": ("c.pdf", _pdf(), "application/pdf")})
    assert r.status_code == 400
    assert _archivos(CID) == []


# ── Permisos ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("permisos", [(), ("moderar",), ("moderar", "panel", "contenido")])
def test_sin_comercios_editar_403_en_las_tres_rutas(client, repo, comercio, permisos):
    h = _h(permisos)
    assert _put(client, {"tiene_pasero": True}, headers=h).status_code == 403
    assert _subir(client, headers=h).status_code == 403
    assert client.delete(f"/admin/comercio/{CID}/catalogo", headers=h).status_code == 403
    assert "tiene_pasero" not in repo.comercios[CID]
    assert _archivos(CID) == []


def test_sin_token_401_y_con_token_de_comercio_o_agente_403_o_401(client, repo, comercio):
    assert client.delete(f"/admin/comercio/{CID}/catalogo").status_code == 401
    assert client.post(f"/admin/comercio/{CID}/catalogo",
                       files={"archivo": ("c.pdf", _pdf(), "application/pdf")}).status_code == 401
    from tests.conftest import comercio_token
    hc = {"Authorization": f"Bearer {comercio_token(comercio_id=CID)}"}
    assert _subir(client, headers=hc).status_code in (401, 403)
    assert _archivos(CID) == []


def test_el_admin_puro_tambien_puede(client, repo, comercio, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    assert _subir(client, headers=h).status_code == 200
    assert client.delete(f"/admin/comercio/{CID}/catalogo", headers=h).status_code == 200


# ── Tope de 8 MB ─────────────────────────────────────────────────────────────
def test_la_ruta_tiene_tope_de_8mb():
    for ruta in (f"/admin/comercio/{CID}/catalogo", f"/admin/comercio/{CID}/catalogo/"):
        assert tope_para(ruta) == 8 * MB + HOLGURA


def test_un_pdf_de_7mb_pasa_y_uno_de_mas_de_8mb_es_413(client, repo, comercio):
    ok = _subir(client, data=_pdf(7 * MB))
    assert ok.status_code == 200, ok.text
    mal = _subir(client, data=_pdf(8 * MB + 1))
    assert mal.status_code == 413
    assert mal.json()["detail"] == "El catálogo puede pesar hasta 8 MB."
    # el rechazo no toca el PDF vigente ni deja temporales
    assert _archivos(CID) == [repo.comercios[CID]["catalogo_url"].rsplit("/", 1)[1]]


def test_un_cuerpo_enorme_se_corta_antes_de_leerlo(client, repo, comercio):
    mal = _subir(client, data=_pdf(12 * MB))
    assert mal.status_code == 413
    assert _archivos(CID) == []


# ── Lo que lee el modal «Editar negocio» ─────────────────────────────────────
def test_la_lista_que_llena_el_modal_pide_los_siete_campos():
    from app.db.repository import _COLS_COMERCIO_ADMIN
    columnas = {c.strip() for c in _COLS_COMERCIO_ADMIN.split(",")}
    for campo in ("canal_wa_url", "catalogo_url", "tiene_pasero", "talles_especiales",
                  "pedido_minimo", "tiene_factura", "envios_internacionales"):
        assert campo in columnas, campo



def test_la_lista_que_llena_el_modal_trae_las_redes_y_el_email():
    """Sin estas columnas el modal mostraba vacías las redes que el comercio sí tenía."""
    from app.db.repository import _COLS_COMERCIO_ADMIN
    columnas = {c.strip() for c in _COLS_COMERCIO_ADMIN.split(",")}
    for campo in ("email", "facebook_url", "instagram_url", "tiktok_url", "sitio_web"):
        assert campo in columnas, campo
