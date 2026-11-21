"""Correcciones de la revisión y de QA de las fotos con estilo URUKU (docs/fotos-estilo-uruku.md).

Cada test nombra el hallazgo que cubre: la propuesta privada que se filtraba, la carrera entre aprobar y re-proponer, el tope que
fallaba abierto, Gemini sin tope de tiempo total, la lectura remota en producción, el conteo de usos, etc.
"""
import base64
import json
import time
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.services import cost_switches, fotos_estilo as fe, fotos_estilo_gemini as ge, fotos_galeria, fotos_origen as fo
from app.services import portada_diseno as pd
from app.services.imagenes import guardar_foto_local
from tests.conftest import comercio_token
# (los fixtures y ayudas de los tests de endpoints: el mismo comercio con portada y dos fotos, Gemini falso, etc.)
from tests.test_fotos_estilo_endpoints import (ADMIN, BASE, CLAVE, COSTO, COVER, ESTADO, GAL, MODELO, Gemini, _base,  # noqa: F401
                                               _con_respuesta, _en_disco, _h, _jpeg, _png, conf, gemini, mundo)  # noqa: F401


def _cuerpo_imagen(datos: bytes | None = None) -> dict:
    datos = datos or _jpeg(1536, 1024, "orange")
    return {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/jpeg",
                                                                  "data": base64.b64encode(datos).decode()}}]}}]}


# ══════════════════════════════════════════ 1. la propuesta privada no sale del panel

def test_el_comerciante_no_recibe_la_propuesta_en_su_galeria(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    assert repo.comercio_fotos[0]["diseno_propuesta_url"]
    r = client.get("/comercio/fotos", headers=_h(comercio_token(comercio_id="com-d")))
    assert r.status_code == 200, r.text
    assert "diseno_propuesta_url" not in json.dumps(r.json())
    assert all("diseno_propuesta_url" not in f for f in r.json()["items"])
    # lo público de la fila sí sigue yendo
    assert {"id", "url", "thumb_url"} <= set(r.json()["items"][0])


def test_el_agente_de_campo_no_recibe_la_propuesta(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    repo.comercios["com-d"]["cargado_por"] = "agente@bermejolive.com"
    r = client.get("/campo/mis-comercios/com-d/fotos", headers=_h(auth.make_agente_token("agente@bermejolive.com")))
    assert r.status_code == 200, r.text
    assert "diseno_propuesta_url" not in json.dumps(r.json())


def test_cambiar_la_portada_desde_la_cuenta_o_el_campo_tampoco_filtra_la_propuesta(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    r = client.put("/comercio/portada", headers=_h(comercio_token(comercio_id="com-d")), json={"foto_id": "f2"})
    assert r.status_code == 200, r.text
    assert "diseno_propuesta_url" not in json.dumps(r.json())
    repo.comercios["com-d"]["cargado_por"] = "agente@bermejolive.com"
    r = client.put("/campo/mis-comercios/com-d/portada", headers=_h(auth.make_agente_token("agente@bermejolive.com")),
                   json={"foto_id": "f1"})
    assert r.status_code == 200, r.text
    assert "diseno_propuesta_url" not in json.dumps(r.json())


def test_el_panel_del_admin_si_ve_las_columnas_de_diseno_de_la_galeria(client, repo, mundo, admin_token):
    p = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    r = client.get("/admin/comercio/com-d/fotos", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["items"][0]["diseno_propuesta_url"] == p
    assert r.json()["items"][0]["diseno_propuesta_url"] and fotos_galeria.PRIVADAS == ("diseno_propuesta_url",)


def test_sin_privadas_devuelve_una_copia_y_no_toca_la_fila():
    fila = {"id": "f", "url": "u", "diseno_url": "d", "diseno_propuesta_url": "p"}
    limpia = fotos_galeria.sin_privadas(fila)
    assert limpia == {"id": "f", "url": "u", "diseno_url": "d"} and fila["diseno_propuesta_url"] == "p"
    assert fotos_galeria.sin_privadas(None) is None


def test_la_lista_de_columnas_de_diseno_es_una_sola():
    from app.db.repository import COLUMNAS_DISENO_FOTO
    assert fotos_galeria.COLUMNAS_DISENO is COLUMNAS_DISENO_FOTO


# ══════════════════════════════════════════ 2. la carrera entre aprobar y re-proponer

def test_usar_una_propuesta_que_otro_pedido_acaba_de_reemplazar_es_409_y_no_publica(client, repo, mundo, admin_token, monkeypatch):
    p1 = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    original = fe._foto_o_404

    def foto_vieja_y_reemplazo(repo_, cid, foto_id):
        fila = dict(original(repo_, cid, foto_id))              # lo que el pedido LEYÓ: la propuesta p1
        repo_.update_foto_comercio(foto_id, cid, {"diseno_propuesta_url": "https://api.test/fotos/local-d/diseno-nueva.jpg"})
        return fila                                              # y en el medio otro pedido la reemplazó

    monkeypatch.setattr(fe, "_foto_o_404", foto_vieja_y_reemplazo)
    r = client.put(GAL, headers=_h(admin_token))
    assert r.status_code == 409 and r.json()["detail"] == "La propuesta cambió, revisá de nuevo"
    fila = repo.comercio_fotos[0]
    assert not fila.get("diseno_url") and fila["diseno_propuesta_url"].endswith("diseno-nueva.jpg")
    assert p1 != fila["diseno_propuesta_url"]


def test_descartar_una_propuesta_que_ya_es_otra_es_409_y_no_descarta_la_nueva(client, repo, mundo, admin_token, monkeypatch):
    client.post(GAL, headers=_h(admin_token))
    original = fe._foto_o_404

    def reemplaza(repo_, cid, foto_id):
        fila = dict(original(repo_, cid, foto_id))
        repo_.update_foto_comercio(foto_id, cid, {"diseno_propuesta_url": "https://api.test/fotos/local-d/diseno-otra.jpg"})
        return fila

    monkeypatch.setattr(fe, "_foto_o_404", reemplaza)
    r = client.delete(f"{GAL}/propuesta", headers=_h(admin_token))
    assert r.status_code == 409
    assert repo.comercio_fotos[0]["diseno_propuesta_url"].endswith("diseno-otra.jpg")


def test_volver_a_la_original_con_un_diseno_que_cambio_es_409(client, repo, mundo, admin_token, monkeypatch):
    client.post(GAL, headers=_h(admin_token))
    client.put(GAL, headers=_h(admin_token))
    original = fe._foto_o_404

    def cambia(repo_, cid, foto_id):
        fila = dict(original(repo_, cid, foto_id))
        repo_.update_foto_comercio(foto_id, cid, {"diseno_url": "https://api.test/fotos/local-d/diseno-z.jpg"})
        return fila

    monkeypatch.setattr(fe, "_foto_o_404", cambia)
    assert client.delete(GAL, headers=_h(admin_token)).status_code == 409
    assert repo.comercio_fotos[0]["diseno_url"].endswith("diseno-z.jpg")


@pytest.mark.parametrize("metodo,ruta", [("put", COVER), ("delete", COVER + "/propuesta")])
def test_la_portada_tambien_es_condicional(client, repo, mundo, admin_token, monkeypatch, metodo, ruta):
    client.post(COVER, headers=_h(admin_token))
    original = repo.actualizar_comercio_si

    def reemplaza_antes(cid, patch, si):
        repo.comercios[cid]["portada_diseno_propuesta_url"] = "https://api.test/fotos/local-d/diseno-nueva.jpg"
        return original(cid, patch, si)

    monkeypatch.setattr(repo, "actualizar_comercio_si", reemplaza_antes)
    r = getattr(client, metodo)(ruta, headers=_h(admin_token))
    assert r.status_code == 409 and r.json()["detail"] == "La propuesta cambió, revisá de nuevo"
    assert repo.comercios["com-d"]["portada_diseno_propuesta_url"].endswith("diseno-nueva.jpg")
    assert not repo.comercios["com-d"].get("portada_diseno_url")


def test_quitar_la_portada_de_diseno_que_cambio_es_409(client, repo, mundo, admin_token, monkeypatch):
    client.post(COVER, headers=_h(admin_token))
    client.put(COVER, headers=_h(admin_token))
    original = repo.actualizar_comercio_si
    monkeypatch.setattr(repo, "actualizar_comercio_si", lambda cid, patch, si: (
        repo.comercios[cid].update(portada_diseno_url="https://api.test/fotos/local-d/diseno-q.jpg"), original(cid, patch, si))[1])
    assert client.delete(COVER, headers=_h(admin_token)).status_code == 409


def test_el_repo_real_arma_el_update_condicional():
    from app.db.repository import SupabaseRepo
    pasos = []

    class Q:
        def __getattr__(self, nombre):
            def llamar(*a, **kw):
                pasos.append((nombre, a))
                return self
            return llamar

        def execute(self):
            return type("R", (), {"data": []})()

    class Db:
        def table(self, nombre):
            pasos.append(("table", (nombre,)))
            return Q()

    repo = SupabaseRepo.__new__(SupabaseRepo)
    repo._db = Db()
    assert repo.update_foto_comercio("f1", "c1", {"diseno_propuesta_url": None}, si={"diseno_propuesta_url": "P", "diseno_url": None}) is None
    assert ("eq", ("diseno_propuesta_url", "P")) in pasos and ("is_", ("diseno_url", "null")) in pasos
    pasos.clear()
    assert repo.actualizar_comercio_si("c1", {"a": 1}, {"portada_diseno_url": "V"}) is None
    assert pasos[0] == ("table", ("comercios",)) and ("eq", ("id", "c1")) in pasos and ("eq", ("portada_diseno_url", "V")) in pasos


def test_las_acciones_de_la_galeria_no_leen_toda_la_galeria(client, repo, mundo, admin_token, monkeypatch):
    """Una foto por acción: `get_foto_comercio`, no `list_fotos_comercio` (hasta 300 filas) 3 o 4 veces por clic."""
    client.post(GAL, headers=_h(admin_token))
    llamadas = []
    original = repo.list_fotos_comercio
    monkeypatch.setattr(repo, "list_fotos_comercio", lambda cid: llamadas.append(cid) or original(cid))
    assert client.put(GAL, headers=_h(admin_token)).status_code == 200
    assert client.post(GAL, headers=_h(admin_token)).status_code == 200
    assert client.delete(f"{GAL}/propuesta", headers=_h(admin_token)).status_code == 200
    assert client.delete(GAL, headers=_h(admin_token)).status_code == 200
    assert llamadas == []


# ══════════════════════════════════════════ 4. BUG-2: la miniatura de la propuesta también se suelta

def test_urls_de_diseno_incluye_la_miniatura_de_la_propuesta():
    fila = {"diseno_url": "https://x/a/diseno-1.jpg", "diseno_thumb_url": "https://x/a/diseno-1-t.jpg",
            "diseno_propuesta_url": "https://x/a/diseno-2.jpg"}
    assert fotos_galeria.urls_de_diseno(fila) == ["https://x/a/diseno-1.jpg", "https://x/a/diseno-1-t.jpg",
                                                  "https://x/a/diseno-2.jpg", "https://x/a/diseno-2-t.jpg"]
    assert fotos_galeria.urls_de_diseno(None) == [None, None, None, None]
    assert fotos_galeria.miniatura_de(None) is None and fotos_galeria.miniatura_de("https://x/a.png") is None
    assert fe.miniatura_de is fotos_galeria.miniatura_de


# ══════════════════════════════════════════ 5. tope diario en 0: el GET lo dice, el POST da 429

def test_con_tope_cero_el_estado_dice_que_no_esta_disponible_y_el_post_da_429(client, repo, mundo, admin_token, conf, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", 0)
    g = client.get(ESTADO, headers=_h(admin_token)).json()["gemini"]
    assert g["available"] is False and g["reason"] == "El tope diario de fotos con IA está en 0" and g["daily_cap"] == 0
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 429 and "0" in r.json()["detail"]


def test_disponibilidad_con_tope_cero_solo_cuando_se_pide(crepo, conf, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", 0)
    assert fe.disponibilidad(crepo) == (False, "el tope diario de fotos con IA está en 0")
    assert fe.disponibilidad(crepo, con_tope=False) == (True, None)


# ══════════════════════════════════════════ 6. el comentario del JPEG no llega a la portada (por los endpoints)

def _jpeg_con_comentario(w=1200, h=800) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), "gray").save(buf, format="JPEG", comment=b"SECRETO-del-celular")
    return buf.getvalue()


def test_la_portada_guardada_no_trae_el_comentario_de_la_foto_ni_por_free_ni_por_externa(client, repo, mundo, admin_token):
    guardar_foto_local("local-d/orig.jpg", _jpeg_con_comentario())
    guardados = []
    free = client.post(COVER, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    guardados.append((Path(settings.fotos_dir) / free[len(BASE) + 1:]).read_bytes())      # (la siguiente propuesta suelta este archivo)
    ext = client.post(f"{COVER}/externa", headers=_h(admin_token),
                      files={"foto": ("a.jpg", _jpeg_con_comentario(), "image/jpeg")}).json()["portada_diseno_propuesta_url"]
    guardados.append((Path(settings.fotos_dir) / ext[len(BASE) + 1:]).read_bytes())
    for datos in guardados:
        assert b"SECRETO" not in datos and not Image.open(BytesIO(datos)).info.get("comment")


# ══════════════════════════════════════════ 7. Gemini: tiempo total, ConnectTimeout, tamaños, forma de la respuesta

def test_un_connect_timeout_es_fallo_sin_cobrar_no_timeout(client, repo, mundo, admin_token, conf, monkeypatch):
    def no_conecta(req):
        raise httpx.ConnectTimeout("no conecta", request=req)
    _con_respuesta(monkeypatch, no_conecta)
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502, r.text
    [uso] = repo.photo_style_uses
    assert (uso["result"], uso["cost_usd"]) == ("error", 0)


def test_el_pool_agotado_tampoco_se_cobra(client, repo, mundo, admin_token, conf, monkeypatch):
    def pool(req):
        raise httpx.PoolTimeout("sin conexiones", request=req)
    _con_respuesta(monkeypatch, pool)
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502
    assert repo.photo_style_uses[0]["cost_usd"] == 0


def test_el_tiempo_total_se_corta_aunque_cada_trozo_llegue_a_tiempo(client, repo, mundo, admin_token, conf, monkeypatch):
    """`httpx.Timeout` vale por fase: un servidor que gotea bytes cada 0,3 s no dispara ningún timeout de lectura."""
    monkeypatch.setattr(settings, "gemini_image_timeout_seg", 1)

    def goteo():
        for _ in range(20):
            time.sleep(0.3)
            yield b" "

    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, content=goteo()))
    inicio = time.monotonic()
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 504, r.text
    assert time.monotonic() - inicio < 3.5                       # ~1 s + un trozo, no los 6 s que tardaría entera
    assert repo.photo_style_uses[0]["result"] == "timeout" and repo.photo_style_uses[0]["cost_usd"] == COSTO


def test_una_imagen_que_pasa_el_maximo_se_cobra(client, repo, mundo, admin_token, conf, monkeypatch):
    monkeypatch.setattr(ge, "MAX_BYTES_RESPUESTA", 1000)
    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, json=_cuerpo_imagen()))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502 and "demasiado grande" in r.json()["detail"]
    assert (repo.photo_style_uses[0]["result"], repo.photo_style_uses[0]["cost_usd"]) == ("error", COSTO)


def test_la_respuesta_http_enorme_se_corta_con_un_tope(client, repo, mundo, admin_token, conf, monkeypatch):
    monkeypatch.setattr(ge, "MAX_BYTES_HTTP", 5000)
    leidos = []

    def trozos():
        for _ in range(1000):
            leidos.append(1)
            yield b"x" * 1000

    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, content=trozos()))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502 and "demasiado grande" in r.json()["detail"]
    assert len(leidos) < 20                                       # dejó de leer: no bajó el mega entero


@pytest.mark.parametrize("cuerpo", [
    [1, 2, 3], "texto", 7, None, {"candidates": "x"}, {"candidates": [1, None, "a"]}, {"candidates": [{"content": [1]}]},
    {"candidates": [{"content": {"parts": "no"}}]}, {"candidates": [{"content": {"parts": [1, None, [], "x"]}}]},
    {"candidates": [{"content": {"parts": [{"inlineData": "no"}]}}]}, {"candidates": [{"content": {"parts": [{"inlineData": {"data": 5}}]}}]},
    {"promptFeedback": "bloqueado"}, {"promptFeedback": {"blockReason": 3}}, {"error": "boom"},
])
def test_una_respuesta_con_otra_forma_es_502_nunca_500(client, repo, mundo, admin_token, conf, monkeypatch, cuerpo):
    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, json=cuerpo))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502, (cuerpo, r.text)
    _con_respuesta(monkeypatch, lambda req: httpx.Response(500, json=cuerpo))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502


def test_una_respuesta_que_no_es_json_es_502(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, content=b"<html>gateway</html>"))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502


def test_cualquier_excepcion_adentro_de_reestilizar_sale_como_gemini_fallo(conf, monkeypatch):
    monkeypatch.setattr(ge, "armar_pedido", lambda *a: (_ for _ in ()).throw(RuntimeError(f"explotó con {CLAVE}")))
    with pytest.raises(ge.GeminiFallo) as e:
        ge.reestilizar(_jpeg(), "cover")
    assert CLAVE not in str(e.value) and e.value.cobrada is False
    with pytest.raises(ge.GeminiNoDisponible):
        monkeypatch.setattr(settings, "gemini_api_key", "")
        ge.reestilizar(_jpeg(), "cover")


def test_un_error_raro_adentro_no_es_un_500_en_el_endpoint(client, repo, mundo, admin_token, conf, monkeypatch):
    monkeypatch.setattr(ge, "armar_pedido", lambda *a: (_ for _ in ()).throw(MemoryError("sin memoria")))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502, r.text
    assert len(repo.photo_style_uses) == 1 and repo.photo_style_uses[0]["cost_usd"] == 0


# ══════════════════════════════════════════ 8. el tope no falla abierto

def test_si_falla_el_registro_la_ia_queda_no_disponible_por_el_dia(client, repo, mundo, admin_token, gemini, crepo):
    repo.falla_registro_uso = True
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200      # la foto ya estaba pagada
    assert fe.registro_roto_hoy()
    r = client.post(GAL, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 503 and "registrar" in r.json()["detail"], r.text
    assert len(gemini.pedidos) == 1                                            # NO se llamó otra vez a ciegas
    g = client.get(ESTADO, headers=_h(admin_token)).json()["gemini"]
    assert g["available"] is False and "registrar" in g["reason"] and "queda apagada por hoy" in g["reason"]
    # lo gratis y lo de afuera no dependen del registro de Gemini
    assert client.post(GAL, headers=_h(admin_token)).status_code == 200


def test_el_flag_del_registro_roto_se_olvida_al_dia_siguiente_y_se_puede_reiniciar(client, repo, mundo, admin_token, gemini, monkeypatch):
    from datetime import date, timedelta
    from app.services import cargas
    repo.falla_registro_uso = True
    client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    repo.falla_registro_uso = False
    assert fe.registro_roto_hoy()
    manana = cargas.hoy_bolivia() + timedelta(days=1)
    with monkeypatch.context() as m:
        m.setattr(fe.cargas, "hoy_bolivia", lambda *a, **k: manana)
        assert not fe.registro_roto_hoy()                                      # cambió el día de Bolivia
    assert isinstance(cargas.hoy_bolivia(), date) and fe.registro_roto_hoy()   # y volviendo a hoy, sigue roto
    fe.reiniciar_registro_roto()
    assert not fe.registro_roto_hoy()


def test_un_pedido_que_esperaba_el_lock_no_llama_a_gemini_si_el_anterior_rompio_el_registro(client, repo, mundo, admin_token, gemini, monkeypatch):
    """El control de disponibilidad se repite adentro del lock: el pedido B pasó el primero antes de que A rompiera el registro."""
    fe.marcar_registro_roto()
    with pytest.raises(fe.EstiloError) as e:
        fe.producir(repo, None, comercio=repo.comercios["com-d"], target="cover", metodo="gemini", origen=_jpeg(),
                    externa=None, pos=None, foto_id=None, actor="t@t")
    assert e.value.status == 503 and gemini.pedidos == []


def test_si_el_registro_anda_el_flag_no_se_prende(client, repo, mundo, admin_token, gemini):
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    assert not fe.registro_roto_hoy() and len(repo.photo_style_uses) == 1


# ══════════════════════════════════════════ 10. los archivos diseno-*

def test_el_token_del_archivo_de_diseno_tiene_128_bits(client, repo, mundo, admin_token):
    cover = client.post(COVER, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    gal = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    for url in (cover, gal):
        nombre = url.rsplit("/", 1)[1]
        token = nombre[len("diseno-"):-len(".jpg")]
        assert len(token) == 32 and int(token, 16) >= 0
    assert gal[:-4] + "-t.jpg" and _en_disco(gal[:-4] + "-t.jpg")


def test_los_disenos_se_sirven_con_cache_corto_y_noindex_y_lo_demas_igual():
    from app.main import app
    from fastapi.testclient import TestClient
    montaje = next(r for r in app.routes if getattr(r, "name", None) == "fotos")
    raiz = Path(montaje.app.directory)
    carpeta = raiz / "revision-diseno"
    carpeta.mkdir(parents=True, exist_ok=True)
    try:
        (carpeta / "diseno-abc.jpg").write_bytes(_jpeg())
        (carpeta / "diseno-abc-t.jpg").write_bytes(_jpeg())
        (carpeta / "foto-normal.jpg").write_bytes(_jpeg())
        with TestClient(app) as c:
            for ruta in ("diseno-abc.jpg", "diseno-abc-t.jpg"):
                h = c.get(f"/fotos/revision-diseno/{ruta}").headers
                assert h["cache-control"] == "public, max-age=3600" and "immutable" not in h["cache-control"]
                assert h["x-robots-tag"] == "noindex" and h["x-content-type-options"] == "nosniff"
            h = c.get("/fotos/revision-diseno/foto-normal.jpg").headers
            assert h["cache-control"] == "public, max-age=31536000, immutable" and "x-robots-tag" not in h
            assert "cache-control" not in c.get("/fotos/revision-diseno/diseno-no-existe.jpg").headers or \
                "immutable" not in c.get("/fotos/revision-diseno/diseno-no-existe.jpg").headers["cache-control"]
    finally:
        for f in carpeta.glob("*"):
            f.unlink()
        carpeta.rmdir()


# ══════════════════════════════════════════ 11. lectura remota

PROD = "https://api.uruku.bo/fotos"


class Red:
    def __init__(self):
        self.pedidos = []

    def __call__(self, req):
        self.pedidos.append(req)
        return httpx.Response(200, content=_jpeg())


def test_en_produccion_la_variable_se_ignora_y_se_avisa_sin_tirar_el_arranque(monkeypatch):
    red = Red()
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(red))
    monkeypatch.setattr(settings, "fotos_public_base_url", "https://api.encontralo.store/fotos")
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)
    monkeypatch.setattr(settings, "app_env", "prod")
    avisos = []
    monkeypatch.setattr(fo.logger, "warning", lambda evento, **kw: avisos.append(evento))
    assert fo.es_produccion() and fo.bases_remotas() == []
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None and red.pedidos == []
    fo.registrar_arranque()                                      # no lanza
    assert avisos == ["fotos.lectura_remota_ignorada_en_prod"]
    monkeypatch.setattr(settings, "app_env", "qa")
    assert fo.bases_remotas() == [PROD + "/"] and fo.leer_foto_origen(f"{PROD}/local/a.jpg") == _jpeg()


def test_el_lifespan_arranca_en_produccion_con_la_variable_puesta(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_la_lectura_remota_pide_sin_compresion(monkeypatch):
    visto = []
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(lambda req: visto.append(req.headers.get("accept-encoding")) or
                                                               httpx.Response(200, content=_jpeg())))
    monkeypatch.setattr(settings, "fotos_public_base_url", "https://api.encontralo.store/fotos")
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") == _jpeg()
    assert visto == ["identity"]


@pytest.mark.parametrize("malo", [f"{PROD}/lo\ncal/a.jpg", f"{PROD}/local/a\t.jpg", f"{PROD}/local/\x7fa.jpg",
                                  f"{PROD}/lo​cal/a.jpg", f"{PROD}/local/a\x1b.jpg", f"{PROD}/local/a .jpg"])
def test_la_ruta_canonica_exige_caracteres_imprimibles(malo):
    assert fo.ruta_relativa_canonica(malo, PROD) is None
    assert fo.ruta_relativa_canonica(f"{PROD}/local/a-ñ.jpg", PROD) == "local/a-ñ.jpg"       # un nombre normal con tilde sí


def test_la_tarjeta_de_la_portada_no_lee_por_la_red(repo, monkeypatch):
    from app.services import fotos_tarjeta
    red = Red()
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(red))
    monkeypatch.setattr(settings, "fotos_public_base_url", "https://api.encontralo.store/fotos")
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)
    comercio = {"id": "c", "slug": "local", "portada_url": f"{PROD}/local/a.jpg"}
    assert pd.leer_portada(comercio, remoto=False) is None and red.pedidos == []
    assert pd.leer_portada(comercio) == _jpeg() and len(red.pedidos) == 1         # la portada de diseño sí
    assert fotos_tarjeta._armar(repo, comercio) == (None, fotos_tarjeta.SIN_FOTO)
    assert len(red.pedidos) == 1                                                  # la tarjeta no sumó ninguna llamada
    assert fo.leer_foto_origen(comercio["portada_url"], remoto=False) is None


def test_la_galeria_y_la_portada_de_diseno_si_leen_remoto(client, repo, admin_token, monkeypatch):
    red = Red()
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(red))
    monkeypatch.setattr(settings, "fotos_public_base_url", "https://api.encontralo.store/fotos")
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)
    repo.seed_comercio(id="com-r", slug="local-r", nombre="R", whatsapp="59170000555", ciudad_id="ciu-1",
                       portada_url=f"{PROD}/local-r/o.jpg")
    repo.comercio_fotos.append({"id": "fr", "comercio_id": "com-r", "url": f"{PROD}/local-r/g.jpg", "thumb_url": None,
                                "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    assert client.post("/admin/comercio/com-r/portada-diseno", headers=_h(admin_token)).status_code == 200
    assert client.post("/admin/comercio/com-r/fotos/fr/diseno", headers=_h(admin_token)).status_code == 200
    assert len(red.pedidos) == 2


# ══════════════════════════════════════════ 12. los usos se cuentan igual en el GET y en /usos

def test_merchant_uses_y_usos_cuentan_lo_mismo_solo_gemini_cobrado(client, repo, mundo, admin_token):
    from app.services import cargas
    for method, costo, res in (("free", 0, "ok"), ("external", 0, "ok"), ("free", 0, "ok"), ("gemini", COSTO, "ok"),
                               ("gemini", COSTO, "timeout"), ("gemini", 0, "error")):
        repo.registrar_uso_foto_estilo({"comercio_id": "com-d", "target": "cover", "method": method, "result": res,
                                        "actor": "a@b", "cost_usd": costo})
    g = client.get(ESTADO, headers=_h(admin_token)).json()["gemini"]
    hoy = cargas.hoy_bolivia().isoformat()
    u = client.get(f"/admin/fotos-estilo/usos?desde={hoy}&hasta={hoy}", headers=_h(admin_token)).json()
    assert g["merchant_uses"] == u["images"] == 2
    assert g["merchant_cost_usd"] == pytest.approx(u["cost_usd"], abs=1e-4) == pytest.approx(2 * COSTO, abs=1e-4)
    assert g["used_today"] == 3                                    # el tope SÍ cuenta la llamada que falló sin cobrar


def test_el_repo_real_filtra_los_gastos_en_la_consulta_y_no_se_corta_en_mil():
    """`gastos_gemini_comercio` y `resumen_usos_foto_estilo` piden sólo gemini con costo > 0 y pagina de a 1000;
    `usos_foto_estilo` pide sólo lo que dejó un archivo (no mezcla errores)."""
    from app.db.repository import SupabaseRepo

    class Q:
        def __init__(self, db):
            self.db, self.filtros = db, []

        def __getattr__(self, nombre):
            if nombre == "not_":
                return self

            def llamar(*a, **kw):
                self.filtros.append((nombre, a))
                return self
            return llamar

        def execute(self):
            self.db.consultas.append(self.filtros)
            rango = next((a for n, a in self.filtros if n == "range"), None)
            inicio, fin = rango if rango else (0, 999)
            return type("R", (), {"data": [{"cost_usd": 0.0336, "comercio_id": "c", "result": "ok"}
                                           for _ in range(max(0, min(fin, 2499) - inicio + 1))]})()

    class Db:
        def __init__(self):
            self.consultas = []

        def table(self, nombre):
            assert nombre == "photo_style_uses"
            return Q(self)

    db = Db()
    repo = SupabaseRepo.__new__(SupabaseRepo)
    repo._db = db
    assert len(repo.gastos_gemini_comercio("c1")) == 2500 and len(db.consultas) == 3        # 1000 + 1000 + 500
    assert ("eq", ("method", "gemini")) in db.consultas[0] and ("gt", ("cost_usd", 0)) in db.consultas[0]
    db.consultas.clear()
    assert len(repo.resumen_usos_foto_estilo("2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z")) == 2500
    assert ("gt", ("cost_usd", 0)) in db.consultas[0]
    db.consultas.clear()
    repo.usos_foto_estilo("c1")
    assert ("eq", ("result", "ok")) in db.consultas[0] and ("is_", ("result_url", "null")) in db.consultas[0]


# ══════════════════════════════════════════ 9. la imagen de afuera pesa poco en memoria

def test_una_externa_de_mas_de_16_megapixeles_es_400(client, repo, mundo, admin_token):
    for ruta in (f"{COVER}/externa", f"{GAL}/externa"):
        r = client.post(ruta, headers=_h(admin_token), files={"foto": ("a.png", _png(4100, 4100, "gray"), "image/png")})
        assert r.status_code == 400 and "16 megapíxeles" in r.json()["detail"], r.text
    assert repo.photo_style_uses == []


def test_una_externa_grande_con_alfa_sale_bien_y_achicada(client, repo, mundo, admin_token):
    buf = BytesIO()
    Image.new("RGBA", (4000, 3500), (0, 0, 0, 0)).save(buf, format="PNG")
    r = client.post(f"{COVER}/externa", headers=_h(admin_token), files={"foto": ("a.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text


# ══════════════════════════════════════════ 14. limpieza

def test_leer_subida_vive_en_los_servicios_y_no_en_la_api():
    import app.api.fotos_estilo as api
    assert hasattr(fe, "leer_subida") and not hasattr(api, "leer_subida")
    for muerto in ("armar_plantilla", "_diseno", "_cubrir"):
        assert not hasattr(pd, muerto), muerto
    for muerto in ("caja_logo_galeria", "recortar"):
        assert not hasattr(fe, muerto), muerto


def test_cubrir_y_el_recorte_de_gemini_comparten_la_misma_caja(monkeypatch):
    usadas = []
    original = pd.caja_cubrir
    monkeypatch.setattr(pd, "caja_cubrir", lambda *a, **k: usadas.append(a) or original(*a, **k))
    fe.jpeg_para_gemini(Image.new("RGB", (1000, 1000), "gray"), "cover", 10)
    pd.cubrir(Image.new("RGB", (1000, 1000), "gray"), 300, 200, 10)
    assert len(usadas) == 2
