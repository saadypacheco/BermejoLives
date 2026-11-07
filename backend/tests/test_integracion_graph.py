"""Graph API para la integración: estado `incierto`, Instagram con contenedor y lecturas.

La versión configurable (`GRAPH_API_VERSION`, `settings.graph_base()`) se prueba en `test_graph_version.py`.
"""
from __future__ import annotations

import re
from pathlib import Path

import httpx
import pytest

from app.core.config import settings
from app.services import difusion

APP = Path(__file__).resolve().parents[1] / "app"


class Resp:
    def __init__(self, status=200, cuerpo=None, texto=""):
        self.status_code, self._c, self.text = status, cuerpo, texto or str(cuerpo)

    def json(self):
        if self._c is None:
            raise ValueError('no es json')
        return self._c

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("x", request=None, response=self)


@pytest.fixture
def meta(monkeypatch):
    """httpx.post/get capturados. `meta.respuestas` es una cola por (método, fragmento de URL)."""
    class Meta:
        llamadas: list[dict] = []
        respuestas: dict = {}

        @classmethod
        def _atender(cls, metodo, url, **kw):
            cls.llamadas.append({"metodo": metodo, "url": url, **kw})
            for (m, frag), cola in cls.respuestas.items():
                if m == metodo and url.endswith(frag):
                    item = cola.pop(0) if len(cola) > 1 else cola[0]
                    if isinstance(item, Exception):
                        raise item
                    return item
            return Resp(200, {"id": "ok"})

    Meta.llamadas, Meta.respuestas = [], {}
    monkeypatch.setattr(httpx, "post", lambda url, **kw: Meta._atender("POST", url, **kw))
    monkeypatch.setattr(httpx, "get", lambda url, **kw: Meta._atender("GET", url, **kw))
    monkeypatch.setattr(settings, "facebook_page_id", "111")
    monkeypatch.setattr(settings, "facebook_page_token", "tok")
    monkeypatch.setattr(settings, "instagram_user_id", "222")
    return Meta


# ═════════════════════════════════════════════════════ lo que Meta apaga el 27/10
def test_nada_usa_lo_que_meta_apaga_el_27_de_octubre():
    """`date_format`, `GET /?ids=` y el ETag de Graph dejan de funcionar el 2026-10-27 en todas las versiones."""
    for f in APP.rglob("*.py"):
        texto = f.read_text(encoding="utf-8")
        assert "date_format" not in texto, f
        assert not re.search(r"graph[^\n]*\?ids=|[\"']ids[\"']\s*:", texto), f


def test_las_lecturas_llevan_el_token_en_el_header_y_piden_solo_los_campos_que_usan(meta):
    meta.respuestas[("GET", "/111_9")] = [Resp(200, {"id": "111_9", "permalink_url": "https://fb/x"})]
    difusion._a_meta("GET", "111_9", campos="id,permalink_url")
    c = meta.llamadas[0]
    assert c["headers"] == {"Authorization": "Bearer tok"} and c["params"] == {"fields": "id,permalink_url"}
    assert "access_token" not in c["url"] and "ids" not in (c.get("params") or {})


# ═════════════════════════════════════════════════════ qué es definitivo y qué es incierto
@pytest.mark.parametrize("respuesta,clase", [
    (httpx.ReadTimeout("t"), difusion.DifusionIncierta),
    (httpx.RemoteProtocolError("cortó"), difusion.DifusionIncierta),
    (Resp(502, {}, "bad gateway"), difusion.DifusionIncierta),
    (Resp(200, None), difusion.DifusionIncierta),
    (httpx.ConnectError("no conecta"), difusion.DifusionError),
    (Resp(400, {}, "token vencido"), difusion.DifusionError),
    (Resp(403, {}, "sin permiso"), difusion.DifusionError),
])
def test_clasifica_el_fallo_para_no_duplicar_posteos(meta, respuesta, clase):
    meta.respuestas[("POST", "/photos")] = [respuesta]
    with pytest.raises(clase) as exc:
        difusion._enviar_facebook("t", "https://x/y.jpg")
    assert (type(exc.value) is clase) or (clase is difusion.DifusionError and not isinstance(exc.value, difusion.DifusionIncierta))


def test_un_timeout_deja_la_fila_incierta_con_los_ids_y_no_en_error(repo, meta, monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X", plan="destacado")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado", "imagen_url": "https://x/y.jpg"})
    repo.encolar_difusion(pub["id"], ["instagram"])
    meta.respuestas[("POST", "/media_publish")] = [httpx.ReadTimeout("t")]
    meta.respuestas[("POST", "/222/media")] = [Resp(200, {"id": "cont7"})]
    r = difusion.procesar(repo, repo.difusion[0])
    fila = repo.difusion[0]
    assert r["estado"] == "incierto" and fila["estado"] == "incierto" and fila["ig_container_id"] == "cont7"


def test_instagram_reusa_el_contenedor_finished_en_vez_de_crear_otro(repo, meta):
    meta.respuestas[("GET", "/cont7")] = [Resp(200, {"status_code": "FINISHED"})]
    meta.respuestas[("POST", "/media_publish")] = [Resp(200, {"id": "ig_77"})]
    r = difusion._enviar_instagram("texto", "https://x/y.jpg", contenedor="cont7")
    assert r.external_post_id == "ig_77" and r.ig_container_id == "cont7"
    assert [c["url"].rsplit("/", 1)[1] for c in meta.llamadas if c["metodo"] == "POST"] == ["media_publish"]    # NO hubo /media


def test_instagram_con_contenedor_in_progress_no_publica_ni_crea(meta):
    meta.respuestas[("GET", "/cont7")] = [Resp(200, {"status_code": "IN_PROGRESS"})]
    with pytest.raises(difusion.DifusionIncierta):
        difusion._enviar_instagram("texto", "https://x/y.jpg", contenedor="cont7")
    assert not [c for c in meta.llamadas if c["metodo"] == "POST"]


def test_instagram_con_contenedor_published_busca_el_posteo_y_no_republica(meta):
    meta.respuestas[("GET", "/cont7")] = [Resp(200, {"status_code": "PUBLISHED"})]
    meta.respuestas[("GET", "/222/media")] = [Resp(200, {"data": [
        {"id": "otro", "caption": "otra cosa", "permalink": "https://ig/otro"},
        {"id": "ig_5", "caption": "texto de la oferta\n\nVidriería", "permalink": "https://ig/p/ig_5"}]})]
    r = difusion._enviar_instagram("texto de la oferta\n\nVidriería", "https://x/y.jpg", contenedor="cont7")
    assert r.external_post_id == "ig_5" and r.permalink == "https://ig/p/ig_5"
    assert not [c for c in meta.llamadas if c["metodo"] == "POST"]


def test_instagram_con_contenedor_vencido_crea_uno_nuevo(meta):
    meta.respuestas[("GET", "/cont7")] = [Resp(200, {"status_code": "EXPIRED"})]
    meta.respuestas[("POST", "/222/media")] = [Resp(200, {"id": "cont8"})]
    meta.respuestas[("POST", "/media_publish")] = [Resp(200, {"id": "ig_8"})]
    r = difusion._enviar_instagram("t", "https://x/y.jpg", contenedor="cont7")
    assert r.ig_container_id == "cont8" and r.external_post_id == "ig_8"


def test_si_publicar_falla_con_4xx_el_contenedor_se_guarda_para_consultarlo(meta):
    meta.respuestas[("POST", "/222/media")] = [Resp(200, {"id": "cont9"})]
    meta.respuestas[("POST", "/media_publish")] = [Resp(400, {}, "no se puede")]
    with pytest.raises(difusion.DifusionError) as exc:
        difusion._enviar_instagram("t", "https://x/y.jpg")
    assert exc.value.ig_container_id == "cont9" and not isinstance(exc.value, difusion.DifusionIncierta)


def test_el_panel_reintenta_una_incierta_consultando_a_meta_primero(client, repo, admin_token, meta, monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X", plan="destacado")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado", "titulo": "Zapatillas"})
    repo.encolar_difusion(pub["id"], ["facebook"])
    fila = repo.difusion[0]
    fila["estado"] = "incierto"
    texto = difusion.texto_de(pub, c, "facebook")
    meta.respuestas[("GET", "/111/posts")] = [Resp(200, {"data": [{"id": "111_3", "message": texto, "permalink_url": "https://fb/3"}]})]
    r = client.post(f"/admin/difusion/{fila['id']}/reintentar", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200 and r.json()["estado"] == "enviado"
    assert not [x for x in meta.llamadas if x["metodo"] == "POST"]          # NO se volvió a publicar
    assert repo.difusion[0]["external_post_id"] == "111_3"


def test_resolver_sin_rastro_en_meta_deja_la_fila_pendiente_para_reintentar(repo, meta, monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X", plan="destacado")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado", "titulo": "Zapatillas"})
    repo.encolar_difusion(pub["id"], ["facebook"])
    repo.difusion[0]["estado"] = "incierto"
    meta.respuestas[("GET", "/111/posts")] = [Resp(200, {"data": []})]
    assert difusion.resolver_incierto(repo, repo.difusion[0])["estado"] == "pendiente"
    assert repo.difusion[0]["estado"] == "pendiente"


def test_resolver_si_meta_no_contesta_sigue_incierta(repo, meta, monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X", plan="destacado")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado", "titulo": "Zapatillas"})
    repo.encolar_difusion(pub["id"], ["facebook"])
    repo.difusion[0]["estado"] = "incierto"
    meta.respuestas[("GET", "/111/posts")] = [httpx.ReadTimeout("t")]
    assert difusion.resolver_incierto(repo, repo.difusion[0])["estado"] == "incierto"
    assert repo.difusion[0]["estado"] == "incierto"


# ═════════════════════════════════════════════════════ el texto con el pie estándar (compatible con el de siempre)
def test_texto_con_pie_equivale_a_texto_de_cuando_el_cuerpo_es_el_mismo():
    com = {"nombre": "Calzados Top", "slug": "calzados-top"}
    pub = {"titulo": "Zapatillas"}
    assert difusion.texto_con_pie("Zapatillas", com, "facebook") == difusion.texto_de(pub, com, "facebook")


def test_la_difusion_de_siempre_no_cambia_y_guarda_el_id_del_posteo(repo, meta, monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X", plan="destacado")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado", "titulo": "Zapatillas", "precio": 250,
                                           "moneda": "BOB", "imagen_url": "https://x/y.jpg"})
    repo.encolar_difusion(pub["id"], ["facebook"])
    meta.respuestas[("POST", "/photos")] = [Resp(200, {"id": "f1", "post_id": "111_8"})]
    r = difusion.procesar(repo, repo.difusion[0])
    fila = repo.difusion[0]
    assert r["estado"] == "enviado" and fila["url_publicada"] == "https://www.facebook.com/111_8" and fila["external_post_id"] == "111_8"
    datos = meta.llamadas[0]["data"]
    assert datos["caption"].startswith("Zapatillas\n\nBs 250") and datos["url"] == "https://x/y.jpg"
