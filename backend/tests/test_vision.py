"""Clasificación por fotos: lo que importa es que NUNCA invente ni pise datos."""
from unittest.mock import patch

import pytest

from app.services.vision import VisionNoConfigurada, _parsear, analizar_fotos

RUBROS = [{"slug": "calzado", "nombre": "Calzado"}, {"slug": "ropa", "nombre": "Moda y ropa"},
          {"slug": "jugueteria", "nombre": "🧸 Juguetería, librería y escolar"}]


def _con_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")


# ------------------------------------------------------------------ parseo
@pytest.mark.parametrize("crudo", [
    '{"productos": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.8}',
    '```json\n{"productos": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.8}\n```',
    'Claro:\n{"productos": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.8}',
])
def test_parsea_lo_que_el_modelo_suele_devolver(crudo):
    """Los modelos envuelven el JSON en markdown o lo preceden de texto."""
    assert _parsear(crudo)["productos"] == "zapatillas"


# --------------------------------------------------------- sin configurar
def test_sin_key_avisa_en_vez_de_fallar_raro(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(VisionNoConfigurada):
        analizar_fotos(["http://x/foto.jpg"], RUBROS)


# ------------------------------------------------------ robustez de red
def test_sin_fotos_descargables_no_inventa(monkeypatch):
    _con_key(monkeypatch)
    with patch("app.services.vision._descargar", return_value=None):
        out = analizar_fotos(["http://x/rota.jpg"], RUBROS)
    assert out["confianza"] == 0.0
    assert out["rubro_slugs"] == []
    assert out["fotos_analizadas"] == 0


def test_si_el_modelo_falla_devuelve_vacio_no_basura(monkeypatch):
    """Ante un error preferimos "no sé" a un dato inventado: esto se escribe en
    la ficha que ve el comprador."""
    _con_key(monkeypatch)
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", side_effect=RuntimeError("503")):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)
    assert out["confianza"] == 0.0
    assert out["productos"] == ""
    assert "error" in out


# ------------------------------------------------------- validación de salida
def _respuesta(payload: dict):
    class R:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            import json as j
            return {"candidates": [{"content": {"parts": [{"text": j.dumps(payload)}]}}]}
    return R()


def test_descarta_rubros_que_no_existen(monkeypatch):
    """El modelo inventa slugs. Si se aceptaran, el comercio quedaría en una
    categoría fantasma que ninguna búsqueda encuentra."""
    _con_key(monkeypatch)
    payload = {"productos": "zapatillas", "descripcion": "d", "subcategoria": "s",
               "rubro_slugs": ["calzado", "zapateria_inventada"], "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)
    assert out["rubro_slugs"] == ["calzado"]
    assert out["slugs_descartados"] == ["zapateria_inventada"]


def test_analiza_como_maximo_tres_fotos(monkeypatch):
    """Más fotos no aportan y multiplican el costo por comercio."""
    _con_key(monkeypatch)
    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": [], "confianza": 0.5}
    urls = [f"http://x/{i}.jpg" for i in range(10)]
    with patch("app.services.vision._descargar", return_value=b"jpg") as desc, \
         patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(urls, RUBROS)
    assert desc.call_count == 3
    assert out["fotos_analizadas"] == 3


# ------------------------------------------------------------- endpoint
def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_endpoint_sin_fotos_lo_dice(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Sin fotos", activo=True)
    r = client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))
    assert r.status_code == 400
    assert "fotos" in r.json()["detail"]


def test_endpoint_no_escribe_si_no_se_pide(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", portada_url="http://x/p.jpg",
                           prod_obs_human="medias", activo=True)
    payload = {"productos": "zapatillas", "descripcion": "Zapatería", "subcategoria": "zapatillas",
               "rubro_slugs": ["calzado"], "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        r = client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))

    assert r.status_code == 200, r.text
    assert r.json()["aplicado"] is False
    assert repo.comercios[c["id"]].get("prod_det_ia") is None


def test_al_aplicar_no_toca_el_dato_humano(client, repo, admin_token, monkeypatch):
    """La regla que ordena todo el diseño."""
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", portada_url="http://x/p.jpg",
                           prod_obs_human="medias", descripcion="", activo=True)
    payload = {"productos": "zapatillas, chinelas", "descripcion": "Zapatería del centro",
               "subcategoria": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        r = client.post(f"/admin/comercio/{c['id']}/analizar?aplicar=true", headers=_h(admin_token))

    assert r.status_code == 200, r.text
    guardado = repo.comercios[c["id"]]
    assert guardado["prod_obs_human"] == "medias"          # intacto
    assert guardado["prod_det_ia"] == "zapatillas, chinelas"
    assert guardado["subcategoria"] == "zapatillas"
    assert guardado["descripcion"] == "Zapatería del centro"   # estaba vacía


def test_no_pisa_una_descripcion_escrita_por_una_persona(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", portada_url="http://x/p.jpg",
                           descripcion="Atiende de 8 a 12", activo=True)
    payload = {"productos": "zapatillas", "descripcion": "Zapatería del centro",
               "subcategoria": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        client.post(f"/admin/comercio/{c['id']}/analizar?aplicar=true", headers=_h(admin_token))

    assert repo.comercios[c["id"]]["descripcion"] == "Atiende de 8 a 12"


def test_confianza_cero_no_escribe_nada(client, repo, admin_token, monkeypatch):
    """Persiana cerrada o foto ilegible: no se guarda una clasificación inventada."""
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", portada_url="http://x/p.jpg", activo=True)
    payload = {"productos": "", "descripcion": "", "subcategoria": "",
               "rubro_slugs": [], "confianza": 0}
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        r = client.post(f"/admin/comercio/{c['id']}/analizar?aplicar=true", headers=_h(admin_token))

    assert r.json()["aplicado"] is False
    assert repo.comercios[c["id"]].get("prod_det_ia") is None


# ─────────────────────────── la API key no puede salir en pantalla
def test_el_error_no_expone_la_api_key(monkeypatch):
    """httpx mete la URL completa en sus mensajes, y la URL de Gemini lleva
    ?key=... — así un 404 mostraba la clave entera en el panel del admin."""
    from app.core.config import settings
    from app.services.vision import _sin_secretos

    monkeypatch.setattr(settings, "gemini_api_key", "AQ.Ab8RN6secretisimo")
    mensaje = ("Client error '404 Not Found' for url 'https://generativelanguage."
               "googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
               "?key=AQ.Ab8RN6secretisimo'")

    limpio = _sin_secretos(mensaje)
    assert "AQ.Ab8RN6secretisimo" not in limpio
    assert "<oculta>" in limpio
    assert "404" in limpio, "el diagnóstico útil tiene que sobrevivir"


def test_se_tapa_la_key_aunque_venga_sin_el_parametro(monkeypatch):
    from app.core.config import settings
    from app.services.vision import _sin_secretos

    monkeypatch.setattr(settings, "gemini_api_key", "AIzaSuperSecreta")
    assert "AIzaSuperSecreta" not in _sin_secretos("falló con la clave AIzaSuperSecreta")


def test_el_error_del_endpoint_llega_sin_la_key(monkeypatch):
    """De punta a punta: lo que ve el panel no puede tener la clave."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_api_key", "AQ.Ab8RN6secretisimo")

    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post",
               side_effect=RuntimeError("404 for url 'https://x?key=AQ.Ab8RN6secretisimo'")):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert "AQ.Ab8RN6secretisimo" not in out["error"]
    assert "AQ.Ab8RN6secretisimo" not in out.get("crudo", "")


# ────────────── el modelo devuelve nombres, no siempre slugs
@pytest.mark.parametrize("devuelto,esperado", [
    (["calzado"],                              ["calzado"]),
    (["Calzado"],                              ["calzado"]),
    (["CALZADO"],                              ["calzado"]),
    (["Juguetería"],                           ["jugueteria"]),
    (["jugueteria"],                           ["jugueteria"]),
    (["🧸 Juguetería, librería y escolar"],     ["jugueteria"]),
    (["Moda y ropa"],                          ["ropa"]),
    (["calzado", "Calzado"],                   ["calzado"]),   # sin duplicar
])
def test_acepta_el_nombre_del_rubro_ademas_del_slug(monkeypatch, devuelto, esperado):
    """Exigir el slug exacto descartaba todo y el comercio quedaba sin categorías,
    sin que se viera por qué."""
    _con_key(monkeypatch)
    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": devuelto, "confianza": 0.8}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)
    assert out["rubro_slugs"] == esperado


def test_lo_que_no_matchea_con_nada_se_reporta(monkeypatch):
    _con_key(monkeypatch)
    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": ["calzado", "peluqueria canina"], "confianza": 0.8}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)
    assert out["rubro_slugs"] == ["calzado"]
    assert out["slugs_descartados"] == ["peluqueria canina"]
