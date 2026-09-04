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
            return {"candidates": [{"content": {"parts": [{"text": j.dumps(payload)}]}}],
                    "usageMetadata": {"promptTokenCount": 1800,
                                      "candidatesTokenCount": 120,
                                      "totalTokenCount": 1920}}
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


def test_la_descripcion_se_regenera_siempre(client, repo, admin_token, monkeypatch):
    """`descripcion` es de la IA: se rehace en cada análisis sin mirar lo que
    había. Lo que escribió una persona vive en `prod_obs_human`, que no se toca."""
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", portada_url="http://x/p.jpg",
                           descripcion="Descripción vieja de la IA",
                           prod_obs_human="medias", activo=True)
    payload = {"productos": "zapatillas", "descripcion": "Zapatería del centro",
               "subcategoria": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        client.post(f"/admin/comercio/{c['id']}/analizar?aplicar=true", headers=_h(admin_token))

    guardado = repo.comercios[c["id"]]
    assert guardado["descripcion"] == "Zapatería del centro"   # regenerada
    assert guardado["prod_obs_human"] == "medias"              # de la persona: intacta


def test_los_rubros_descartados_quedan_registrados(client, repo, admin_token, monkeypatch):
    """Es la evidencia para decidir qué categorías crear."""
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Peluchería", portada_url="http://x/p.jpg", activo=True)
    payload = {"productos": "peluches", "descripcion": "d", "subcategoria": "peluches",
               "rubro_slugs": ["peluches y muñecos"], "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))

    assert any(x["texto"] == "peluches y muñecos" for x in repo.rubros_propuestos)


def test_los_descartados_se_registran_aunque_no_se_aplique(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="X", portada_url="http://x/p.jpg", activo=True)
    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": ["categoria inventada"], "confianza": 0.2}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        r = client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))

    assert r.json()["aplicado"] is False
    assert len(repo.rubros_propuestos) == 1


def test_reporte_agrupa_variantes_y_ordena_por_frecuencia(client, repo, admin_token):
    """'Juguetería', 'jugueterias' y '🧸 Juguetería' son la misma necesidad."""
    repo.registrar_rubros_propuestos(["Juguetería", "jugueterias", "🧸 Juguetería"], "c1")
    repo.registrar_rubros_propuestos(["Floristería"], "c2")

    # El campo es `propuestas`, que es el que lee el panel. Este test pedía
    # `items` y pasaba: había DOS rutas con este path, y la primera —muerta para
    # el panel— devolvía esa forma. El test verde tapaba el /admin caído.
    cuerpo = client.get("/admin/rubros/propuestos", headers=_h(admin_token)).json()
    items = cuerpo["propuestas"]
    assert cuerpo["rubros"], "el panel también necesita la lista de rubros para resolver una propuesta"
    assert items[0]["normalizado"] == "jugueteria"
    assert items[0]["veces"] == 3
    assert len(items[0]["variantes"]) == 3
    assert items[1]["normalizado"] == "floristeria"


def test_reporte_de_propuestos_requiere_admin(client, repo):
    assert client.get("/admin/rubros/propuestos").status_code in (401, 403)


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


def test_se_reporta_el_consumo_de_tokens(monkeypatch):
    """Permite ver el costo por comercio en vez de estimarlo o mirarlo agregado
    en el panel de Google."""
    _con_key(monkeypatch)
    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": [], "confianza": 0.5}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert out["tokens"]["entrada"] == 1800
    assert out["tokens"]["salida"] == 120
    assert out["tokens"]["total"] == 1920


def test_sin_usageMetadata_no_rompe(monkeypatch):
    """Si la API deja de mandarlo, el análisis tiene que seguir funcionando."""
    _con_key(monkeypatch)

    class SinUso:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"confianza": 0.5}'}]}}]}

    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=SinUso()):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert out["tokens"]["total"] is None
    assert out["confianza"] == 0.5


# ───────────────────── errores transitorios de Gemini
def _respuesta_error(status: int, retry_after: str | None = None, cuerpo: dict | None = None):
    class R:
        status_code = status
        headers = {"retry-after": retry_after} if retry_after else {}
        def raise_for_status(self):
            import httpx as h
            raise h.HTTPStatusError(f"Server error '{status}'", request=None, response=None)
        def json(self):
            return cuerpo if cuerpo is not None else {"error": {"code": status}}
    return R()


# El 429 real de Gemini cuando se agota la cuota gratuita: el tiempo de espera
# viene en el CUERPO, no en la cabecera Retry-After.
_CUOTA_AGOTADA = {"error": {
    "code": 429, "status": "RESOURCE_EXHAUSTED",
    "message": ("You exceeded your current quota. * Quota exceeded for metric: "
                "generativelanguage.googleapis.com/generate_content_free_tier_requests, "
                "limit: 20, model: gemini-3.6-flash Please retry in 34.288884339s."),
}}


def test_reintenta_ante_un_503_y_sale_bien(monkeypatch):
    """Gemini devuelve 503 cuando está saturado; la misma llamada anda segundos
    después. Sin reintento el admin ve un error por algo que se resuelve solo."""
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 0)   # sin esperas en test
    payload = {"productos": "zapatillas", "descripcion": "", "subcategoria": "",
               "rubro_slugs": ["calzado"], "confianza": 0.9}
    respuestas = [_respuesta_error(503), _respuesta_error(503), _respuesta(payload)]

    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", side_effect=respuestas) as post:
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert post.call_count == 3
    assert out["confianza"] == 0.9
    assert out["productos"] == "zapatillas"


def test_no_reintenta_un_error_del_cliente(monkeypatch):
    """Un 404 (modelo inexistente) o un 401 no se arreglan reintentando: sólo
    gastan tiempo y hacen esperar al admin."""
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 0)

    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta_error(404)) as post:
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert post.call_count == 1
    assert "error" in out


def test_si_falla_en_todos_los_intentos_lo_reporta(monkeypatch):
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 0)

    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta_error(503)) as post:
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert post.call_count == 3
    assert out["confianza"] == 0.0
    assert "error" in out


def test_el_429_espera_mas_que_un_503(monkeypatch):
    """Un 429 es límite de frecuencia: reintentar enseguida quema los tres
    intentos dentro de la misma ventana bloqueada."""
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 1)
    esperas = []
    monkeypatch.setattr("app.services.vision.time.sleep", lambda s: esperas.append(s))

    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": [], "confianza": 0.5}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post",
               side_effect=[_respuesta_error(429), _respuesta(payload)]):
        analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert esperas[0] >= 4, "el 429 tiene que esperar bastante más que la base"


def test_se_respeta_el_retry_after_del_servidor(monkeypatch):
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 1)
    esperas = []
    monkeypatch.setattr("app.services.vision.time.sleep", lambda s: esperas.append(s))

    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": [], "confianza": 0.5}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post",
               side_effect=[_respuesta_error(429, retry_after="30"), _respuesta(payload)]):
        analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert esperas[0] == 30, "si el servidor dice cuánto esperar, se le hace caso"


def test_no_insiste_cuando_la_cuota_esta_agotada(monkeypatch):
    """Reintentar no repone la cuota, y cada intento gasta otra request de la
    misma cuota agotada — o sea que empeora el problema que intenta resolver."""
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 0)
    esperas = []
    monkeypatch.setattr("app.services.vision.time.sleep", lambda s: esperas.append(s))

    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post",
               return_value=_respuesta_error(429, cuerpo=_CUOTA_AGOTADA)) as post:
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert post.call_count == 1, "no tiene que gastar más requests de una cuota agotada"
    assert esperas == []
    assert "error" in out


def test_lee_el_tiempo_de_espera_del_cuerpo(monkeypatch):
    """Gemini no manda Retry-After en estos casos: el número está en el mensaje."""
    from app.services.vision import _retry_after
    assert _retry_after(_respuesta_error(429, cuerpo=_CUOTA_AGOTADA)) == 34.288884339


def test_la_cabecera_tiene_prioridad_sobre_el_cuerpo(monkeypatch):
    from app.services.vision import _retry_after
    r = _respuesta_error(429, retry_after="5", cuerpo=_CUOTA_AGOTADA)
    assert _retry_after(r) == 5


def test_se_devuelve_la_categoria_sugerida(monkeypatch):
    """El prompt obliga a elegir de la lista de 42, así que un modelo obediente
    nunca "descarta" nada y el reporte de faltantes queda vacío aunque falten
    categorías. Este campo es el que le da voz para pedir una nueva."""
    _con_key(monkeypatch)
    payload = {"productos": "peluches", "descripcion": "", "subcategoria": "peluches",
               "rubro_slugs": ["jugueteria"], "categoria_sugerida": "peluchería",
               "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)

    assert out["categoria_sugerida"] == "peluchería"
    assert out["rubro_slugs"] == ["jugueteria"], "sugerir no reemplaza al rubro elegido"


def test_sin_sugerencia_el_campo_queda_vacio(monkeypatch):
    _con_key(monkeypatch)
    payload = {"productos": "x", "descripcion": "", "subcategoria": "",
               "rubro_slugs": ["calzado"], "confianza": 0.8}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)
    assert out["categoria_sugerida"] == ""


def test_la_categoria_sugerida_se_registra(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    c = repo.seed_comercio(slug="x", nombre="Peluchería Luli",
                           portada_url="http://x/p.jpg", activo=True)
    payload = {"productos": "peluches", "descripcion": "d", "subcategoria": "peluches",
               "rubro_slugs": ["jugueteria"], "categoria_sugerida": "peluchería",
               "confianza": 0.9}
    with patch("app.services.vision._descargar", return_value=b"jpg"),          patch("app.services.vision.httpx.post", return_value=_respuesta(payload)):
        client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))

    assert any(x["texto"] == "peluchería" for x in repo.rubros_propuestos)
