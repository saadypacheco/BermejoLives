"""Pedir un video a mano (§17.3): de un negocio o de un rubro. Los 422 y 429 exactos, la ciudad limitada para
agentes, que un pedido no cuenta cuota ni crea tareas ni ocupa un lugar del calendario, y el pilar `rubro` en todo
el camino (textos, consentimiento, baja de un comercio, aprobación, página pública)."""
from datetime import timedelta

import pytest

from app.core import auth
from app.core.config import settings
from app.services import (content_captions as cc, content_consent, content_posts, content_public, content_requests as cr,
                          content_selector as sel, content_video_texts as cvt)
from tests.content_helpers import autorizar, banco, comercio, h, hoy

NOMBRES = ("uno", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho")


@pytest.fixture(autouse=True)
def _sin_gemini(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")


@pytest.fixture
def ana():
    return h(auth.make_token("ana.perez@uruku.bo", rol="admin"))


def solo(*permisos, ciudad=None):
    return h(auth.make_token("agente@uruku.bo", rol="x", roles=["x"], permisos=list(permisos), ciudad_slug=ciudad))


def zapaterias(repo, crepo, n=5, slug="zapatillas", nombre="Zapatillas", ciudad="ciu-1", fotos=1, subs=(), **kw):
    """`n` comercios del rubro, cada uno con autorización y `fotos` fotos del banco. `subs`: índices suscriptores."""
    crepo.sembrar_rubro(slug, nombre)
    for i in range(n):
        cid = f"{slug}-{i}"
        extra = {} if i in subs else {"plan": "gratis", "paga_hasta": None}
        comercio(repo, cid, nombre=f"Zapatería {NOMBRES[i]}", rubro_id=f"rub-{slug}", ciudad_id=ciudad,
                 rubros={"nombre": nombre, "slug": slug}, **extra, **kw)
        autorizar(crepo, cid)
        if fotos:
            banco(crepo, cid, fotos)


def pedir_rubro(client, ana, slug="zapatillas", ciudad="bermejo"):
    return client.post("/admin/content/pieces/request", headers=ana,
                       json={"kind": "rubro", "rubro_slug": slug, "ciudad_slug": ciudad})


def pedir_comercio(client, ana, cid="com-1"):
    return client.post("/admin/content/pieces/request", headers=ana, json={"kind": "comercio", "comercio_id": cid})


# ══════════════════════════════════════════════════════════════ pedir un rubro

def test_un_rubro_con_comercios_crea_la_pieza_de_rubro(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=5)
    r = pedir_rubro(client, ana)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["pillar"] == "rubro" and p["status"] == "queued" and p["origin"] == "pedido"
    assert p["rubro"] == {"nombre": "Zapatillas", "slug": "zapatillas"} and p["comercio"] is None
    assert p["pillar_label"] == "Repaso de rubro" and p["title"] == "Zapatillas en Bermejo" and p["counts_for_quota"] is False
    assert p["scheduled_for"] == hoy().isoformat() and p["template_version"] == 2
    fila = crepo.pieces[p["id"]]
    assert fila["comercio_id"] is None and fila["ciudad_id"] == "ciu-1" and fila["rubro_id"] == "rub-zapatillas"
    assert fila["origin"] == "pedido" and fila["created_by"] == "ana.perez@uruku.bo" and fila["quota_cycle_start"] is None
    assert fila["week_start"] == sel.lunes_de(hoy()).isoformat() and fila["template"] == "rubro"


def test_el_rubro_lleva_una_foto_por_comercio_con_el_nombre_como_frase(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=5, fotos=3)
    p = pedir_rubro(client, ana).json()
    fuentes = crepo.list_sources(p["id"])
    assert len(fuentes) == 5 and len({f["comercio_id"] for f in fuentes}) == 5          # una foto por comercio
    assert {f["chip_text"] for f in fuentes} == {f"Zapatería {NOMBRES[i]}" for i in range(5)}
    assert all(f["photo_flags"] == [] and f["source_type"] == "asset" for f in fuentes)
    assert [s["comercio_nombre"] for s in p["sources"]] == [f["caption_fact"] for f in fuentes]       # el nombre sale de la base


def test_maximo_6_comercios(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=8)
    assert len(crepo.list_sources(pedir_rubro(client, ana).json()["id"])) == 6


def test_suscriptores_primero_y_despues_la_foto_mas_reciente(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=8, subs=(5, 6))                 # los suscriptores son los dos últimos
    p = pedir_rubro(client, ana).json()
    comercios = [f["comercio_id"] for f in crepo.list_sources(p["id"])]
    # los suscriptores primero (el de la foto más reciente, antes) y, entre los demás, también la foto más reciente
    assert comercios == ["zapatillas-6", "zapatillas-5", "zapatillas-7", "zapatillas-4", "zapatillas-3", "zapatillas-2"]


def test_los_textos_fijos_del_video_de_rubro(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=5)
    p = pedir_rubro(client, ana).json()
    vt = p["video_texts"]
    assert vt["kick"] == "EN BERMEJO" and vt["title1"] == "Zapatillas" and vt["title2"] == "en Bermejo"
    assert vt["search_term"] == "zapatillas" and vt["subtitle"] is None
    assert vt["close_title1"] == "Encuéntrelos" and vt["close_title2"] == "en Uruku" and vt["place_chip"] is None
    assert vt["close_line"] == "Vea horario y cómo llegar en Uruku" and vt["lema"] == "Si está en Bolivia, está en Uruku."
    assert p["video_texts_engine"] == "template" and p["video_texts_checks"] == [] and cvt.iconos_de("rubro") == ["tienda", "pin"]


def test_el_caption_fijo_nombra_dos_comercios_y_nunca_cuenta_cuantos_hay(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=6)
    p = pedir_rubro(client, ana).json()
    primeros = [i["nombre"] for i in p["facts"]["items"][:2]]
    texto = f"Dónde comprar zapatillas en Bermejo: {primeros[0]}, {primeros[1]} y más. Búsquelos en uruku.bo"
    assert p["caption_tiktok"] == p["caption_ig"] == p["caption_channel"] == texto
    assert p["caption_engine"] == "template" and p["caption_checks"] == []
    assert not cc._CANTIDAD.search(texto) and "6" not in texto and "comercios" not in texto
    assert 4 <= len(p["hashtags"]) <= 8 and "#Zapatillas" in p["hashtags"]
    f = p["facts"]
    assert f["pillar"] == "rubro" and f["rubro"] == "Zapatillas" and f["rubro_slug"] == "zapatillas"
    assert f["ciudad"] == "Bermejo" and f["departamento"] and f["allowed_numbers"] == []
    assert [i["nombre"] for i in f["items"]] == [x["caption_fact"] for x in crepo.list_sources(p["id"])] and len(f["items"]) == 6


def test_los_comercios_que_no_cumplen_no_entran(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=4)                                       # 4 buenos
    crepo.sembrar_rubro("ropa", "Ropa")
    comercio(repo, "sin-consent", rubro_id="rub-zapatillas", ciudad_id="ciu-1", nombre="Sin consent"); banco(crepo, "sin-consent", 1)
    comercio(repo, "sin-foto", rubro_id="rub-zapatillas", ciudad_id="ciu-1", nombre="Sin foto"); autorizar(crepo, "sin-foto")
    comercio(repo, "otra-ciudad", rubro_id="rub-zapatillas", ciudad_id="ciu-santa-cruz", nombre="Otra"); autorizar(crepo, "otra-ciudad"); banco(crepo, "otra-ciudad", 1)
    comercio(repo, "dado-de-baja", rubro_id="rub-zapatillas", ciudad_id="ciu-1", activo=False, nombre="Baja"); autorizar(crepo, "dado-de-baja"); banco(crepo, "dado-de-baja", 1)
    comercio(repo, "retiro", rubro_id="rub-zapatillas", ciudad_id="ciu-1", nombre="Retiró"); autorizar(crepo, "retiro"); autorizar(crepo, "retiro", granted=False); banco(crepo, "retiro", 1)
    comercio(repo, "otro-rubro", rubro_id="rub-ropa", ciudad_id="ciu-1", nombre="Ropa"); autorizar(crepo, "otro-rubro"); banco(crepo, "otro-rubro", 1)
    p = pedir_rubro(client, ana).json()
    assert {f["comercio_id"] for f in crepo.list_sources(p["id"])} == {f"zapatillas-{i}" for i in range(4)}


def test_el_rubro_secundario_tambien_cuenta(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=3)
    crepo.sembrar_rubro("ropa", "Ropa")
    comercio(repo, "mixto", rubro_id="rub-ropa", ciudad_id="ciu-1", nombre="Mixto"); autorizar(crepo, "mixto"); banco(crepo, "mixto", 1)
    assert pedir_rubro(client, ana).status_code == 422                 # con 3 no alcanza
    crepo.comercio_rubros.append({"comercio_id": "mixto", "rubro_id": "rub-zapatillas"})        # su rubro secundario
    r = pedir_rubro(client, ana)
    assert r.status_code == 201 and "mixto" in {f["comercio_id"] for f in crepo.list_sources(r.json()["id"])}


def test_la_foto_del_rubro_es_el_banco_mas_reciente_y_una_portada_que_no_esta_en_el_disco_no_sirve(repo, crepo):
    zapaterias(repo, crepo, n=1, fotos=0)
    c = crepo.get_comercio_ficha("zapatillas-0")
    c["portada_url"] = "/fotos/no-existe.jpg"
    assert sel.elegir_fotos(crepo, c, 1, hoy(), set(), preferir_banco=True, con_ofertas=False) == []
    banco(crepo, "zapatillas-0", 2)
    mas_reciente = max(crepo.list_assets(["zapatillas-0"]), key=lambda a: a["created_at"])
    elegida = sel.elegir_fotos(crepo, c, 1, hoy(), set(), preferir_banco=True, con_ofertas=False)
    assert [(e["source_type"], e["source_id"]) for e in elegida] == [("asset", mas_reciente["id"])]


def test_menos_de_4_comercios_es_422_con_el_numero_exacto(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=3)
    r = pedir_rubro(client, ana)
    assert r.status_code == 422
    assert r.json()["detail"] == "Hay 3 comercios de ese rubro con autorización y foto; hacen falta 4"
    assert crepo.pieces == {}
    zapaterias(repo, crepo, n=0, slug="vacio", nombre="Vacío")
    assert pedir_rubro(client, ana, "vacio").json()["detail"] == "Hay 0 comercios de ese rubro con autorización y foto; hacen falta 4"


def test_rubro_o_ciudad_que_no_existen_son_404_y_un_rubro_no_comercial_es_422(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=4)
    assert pedir_rubro(client, ana, "no-existe").status_code == 404
    assert pedir_rubro(client, ana, ciudad="no-existe").status_code == 404
    crepo.sembrar_rubro("banos", "Baños", comercial=False)
    assert pedir_rubro(client, ana, "banos").status_code == 422
    crepo.sembrar_rubro("viejo", "Viejo", activo=False)
    assert pedir_rubro(client, ana, "viejo").status_code == 404


def test_el_cuerpo_incompleto_o_mal_formado_es_422_de_validacion(repo, crepo, client, ana):
    url = "/admin/content/pieces/request"
    for cuerpo in ({"kind": "comercio"}, {"kind": "rubro", "rubro_slug": "zapatillas"}, {"kind": "rubro", "ciudad_slug": "bermejo"},
                   {"kind": "otro"}, {}, {"kind": "rubro", "rubro_slug": "../x", "ciudad_slug": "bermejo"}):
        assert client.post(url, headers=ana, json=cuerpo).status_code == 422, cuerpo


# ══════════════════════════════════════════════════════════════ pedir un negocio

def test_un_negocio_con_autorizacion_y_fotos_crea_la_pieza(repo, crepo, client, ana):
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 7)
    r = pedir_comercio(client, ana)
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["pillar"] == "comercio_del_dia" and p["status"] == "queued" and p["origin"] == "pedido" and p["rubro"] is None
    assert p["comercio"]["id"] == "com-1" and p["counts_for_quota"] is False and p["scheduled_for"] == hoy().isoformat()
    fila = crepo.pieces[p["id"]]
    assert fila["created_by"] == "ana.perez@uruku.bo" and fila["quota_cycle_start"] is None and fila["rubro_id"] is None
    assert fila["week_start"] == sel.lunes_de(hoy()).isoformat()
    assert len(crepo.list_sources(p["id"])) == 6                         # tope de 6 del video v2
    assert p["video_texts"]["title1"] == "Vidriería" and p["caption_engine"] == "template"


def test_el_pedido_de_un_negocio_no_cuenta_cuota_ni_crea_tareas_ni_ocupa_el_lugar(repo, crepo, client, ana):
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 12)
    assert pedir_comercio(client, ana).status_code == 201
    hoy_ = hoy()
    s = sel.evaluar_suscriptores(crepo, hoy_)[0]
    assert s["usadas"] == 0 and s["debe"] == s["cuota"] and s["ultima"] is None      # ni cuota ni agenda del selector
    assert crepo.tasks == {}
    # el lugar del calendario de hoy sigue libre para el selector
    p2 = crepo.insert_piece({"week_start": sel.lunes_de(hoy_).isoformat(), "scheduled_for": hoy_.isoformat(), "pillar": "comercio_del_dia",
                             "comercio_id": "com-1", "status": "queued", "facts": {}, "template": "x", "caption_engine": "template",
                             "created_by": "selector"})
    assert p2 is not None


def test_dos_pedidos_del_mismo_dia_no_chocan(repo, crepo, client, ana):
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 12)
    comercio(repo, "com-2", nombre="Otro"); autorizar(crepo, "com-2"); banco(crepo, "com-2", 6)
    assert pedir_comercio(client, ana, "com-1").status_code == 201
    assert pedir_comercio(client, ana, "com-2").status_code == 201
    # Un pedido no mira la regla de 60 días: pedir otra vez el mismo negocio arma otro video.
    assert pedir_comercio(client, ana, "com-2").status_code == 201


def test_un_negocio_sin_autorizacion_es_422_con_el_motivo(repo, crepo, client, ana):
    comercio(repo); banco(crepo, "com-1", 5)
    r = pedir_comercio(client, ana)
    assert r.status_code == 422 and r.json()["detail"] == "El comercio no tiene autorización vigente para aparecer en las redes"
    autorizar(crepo, "com-1"); autorizar(crepo, "com-1", granted=False)
    assert pedir_comercio(client, ana).status_code == 422                # la última fila manda: retiró


def test_un_negocio_con_pocas_fotos_es_422_con_cuantas_sirven(repo, crepo, client, ana):
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 2)
    r = pedir_comercio(client, ana)
    assert r.status_code == 422 and r.json()["detail"] == "Tiene 2 fotos que sirven: subí al menos 4 en Banco de contenido"
    banco(crepo, "com-1", 1, w=400, h=300)                                # una chica no sirve
    assert pedir_comercio(client, ana).json()["detail"].startswith("Tiene 2 fotos")
    assert crepo.pieces == {}


def test_un_negocio_inactivo_es_422_y_uno_que_no_existe_es_404(repo, crepo, client, ana):
    comercio(repo, activo=False); autorizar(crepo, "com-1"); banco(crepo, "com-1", 5)
    r = pedir_comercio(client, ana)
    assert r.status_code == 422 and r.json()["detail"] == "El comercio no está activo"
    assert pedir_comercio(client, ana, "no-existe").status_code == 404


def test_las_fotos_marcadas_de_un_pedido_siguen_las_mismas_reglas_del_selector(repo, crepo, client, ana, monkeypatch):
    from tests.content_helpers import gemini_on
    from tests.test_content_video_texts import BUENOS, _slides
    gemini_on(crepo)
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 6)
    monkeypatch.setattr(cc, "_llamar_gemini", lambda prompt: None)
    monkeypatch.setattr(cvt, "_llamar_gemini", lambda partes: {**BUENOS, "slides": _slides(6, {2: {"price_or_code_visible": True}})})
    p = pedir_comercio(client, ana).json()
    assert p["video_texts_engine"].startswith("gemini:") and len(p["sources"]) == 5      # la marcada se sacó (quedaban 5)


# ══════════════════════════════════════════════════════════════ el tope y los permisos

def _pedidos_armandose(crepo, n, estado="queued"):
    for i in range(n):
        crepo.insert_piece({"week_start": sel.lunes_de(hoy()).isoformat(), "scheduled_for": hoy().isoformat(), "pillar": "rubro",
                            "status": estado, "facts": {"pillar": "rubro"}, "template": "rubro", "caption_engine": "template",
                            "created_by": "x", "origin": "pedido", "ciudad_id": "ciu-1", "rubro_id": "rub-x"})


def test_con_5_pedidos_armandose_es_429_exacto(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=5)
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 5)
    _pedidos_armandose(crepo, 3)
    _pedidos_armandose(crepo, 2, "rendering")
    for r in (pedir_rubro(client, ana), pedir_comercio(client, ana)):
        assert r.status_code == 429 and r.json()["detail"] == "Ya hay 5 videos pedidos armándose; esperá a que terminen"


def test_los_pedidos_ya_armados_o_de_la_semana_no_cuentan_para_el_tope(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=5)
    _pedidos_armandose(crepo, 4)
    _pedidos_armandose(crepo, 3, "ready_for_review")
    _pedidos_armandose(crepo, 3, "failed")
    assert pedir_rubro(client, ana).status_code == 201                    # 4 armándose + este = 5, entra
    assert pedir_rubro(client, ana).status_code in (422, 429)            # el sexto no
    from tests.content_helpers import pieza
    pieza(crepo, "com-1", status="queued", created_by="selector")        # una del selector en cola no cuenta
    assert crepo.count_pending_requests() == 5


def test_el_permiso_es_difusion(repo, crepo, client):
    zapaterias(repo, crepo, n=5)
    cuerpo = {"kind": "rubro", "rubro_slug": "zapatillas", "ciudad_slug": "bermejo"}
    assert client.post("/admin/content/pieces/request", json=cuerpo).status_code == 401
    assert client.post("/admin/content/pieces/request", json=cuerpo, headers=solo("moderar")).status_code == 403
    assert client.get("/admin/content/request-options?ciudad_slug=bermejo", headers=solo("moderar")).status_code == 403
    assert client.get("/admin/content/merchants/zapatillas-0/request-check", headers=solo("moderar")).status_code == 403
    assert client.post("/admin/content/pieces/request", json=cuerpo, headers=solo("difusion")).status_code == 201


def test_un_agente_solo_pide_en_su_ciudad(repo, crepo, client):
    zapaterias(repo, crepo, n=5)
    bermejo, scz = solo("difusion", ciudad="bermejo"), solo("difusion", ciudad="santa-cruz")
    cuerpo_rubro = {"kind": "rubro", "rubro_slug": "zapatillas", "ciudad_slug": "bermejo"}
    cuerpo_comercio = {"kind": "comercio", "comercio_id": "zapatillas-0"}
    assert client.post("/admin/content/pieces/request", json=cuerpo_rubro, headers=scz).status_code == 403
    assert client.post("/admin/content/pieces/request", json=cuerpo_comercio, headers=scz).status_code == 404
    assert client.get("/admin/content/request-options?ciudad_slug=bermejo", headers=scz).status_code == 403
    assert client.get("/admin/content/merchants/zapatillas-0/request-check", headers=scz).status_code == 404
    assert crepo.pieces == {}
    assert client.get("/admin/content/request-options?ciudad_slug=bermejo", headers=bermejo).status_code == 200
    assert client.get("/admin/content/merchants/zapatillas-0/request-check", headers=bermejo).status_code == 200
    assert client.post("/admin/content/pieces/request", json=cuerpo_rubro, headers=bermejo).status_code == 201


# ══════════════════════════════════════════════════════════════ opciones y chequeo para el modal

def test_request_options_lista_los_rubros_con_cuantos_alcanzan(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=5)
    zapaterias(repo, crepo, n=2, slug="ropa", nombre="Ropa")
    crepo.sembrar_rubro("banos", "Baños", comercial=False)
    crepo.sembrar_rubro("vacio", "Vacío")
    comercio(repo, "sin-nada", rubro_id="rub-vacio", ciudad_id="ciu-1", nombre="Sin nada")        # hay un comercio, sin autorización
    zapaterias(repo, crepo, n=4, slug="celulares", nombre="Celulares", ciudad="ciu-santa-cruz")
    r = client.get("/admin/content/request-options?ciudad_slug=bermejo", headers=ana)
    assert r.status_code == 200
    assert r.json() == {"rubros": [
        {"slug": "zapatillas", "nombre": "Zapatillas", "eligible": True, "eligible_count": 5},
        {"slug": "ropa", "nombre": "Ropa", "eligible": False, "eligible_count": 2},
        {"slug": "vacio", "nombre": "Vacío", "eligible": False, "eligible_count": 0}]}
    scz = client.get("/admin/content/request-options?ciudad_slug=santa-cruz", headers=ana).json()["rubros"]
    assert scz == [{"slug": "celulares", "nombre": "Celulares", "eligible": True, "eligible_count": 4}]


def test_request_options_con_ciudad_desconocida_es_404_y_sin_ciudad_422(client, ana):
    assert client.get("/admin/content/request-options?ciudad_slug=nada", headers=ana).status_code == 404
    assert client.get("/admin/content/request-options", headers=ana).status_code == 422
    assert client.get("/admin/content/request-options?ciudad_slug=", headers=ana).status_code == 422


def test_request_options_cuenta_lo_mismo_que_el_pedido(repo, crepo, client, ana):
    zapaterias(repo, crepo, n=4)
    opciones = {r["slug"]: r for r in client.get("/admin/content/request-options?ciudad_slug=bermejo", headers=ana).json()["rubros"]}
    assert opciones["zapatillas"]["eligible_count"] == 4 and opciones["zapatillas"]["eligible"] is True
    assert pedir_rubro(client, ana).status_code == 201
    # Las fotos ya usadas no cuentan para un pedido: el rubro se puede volver a pedir.
    opciones = {r["slug"]: r for r in client.get("/admin/content/request-options?ciudad_slug=bermejo", headers=ana).json()["rubros"]}
    assert opciones["zapatillas"]["eligible_count"] == 4 and opciones["zapatillas"]["eligible"] is True
    assert pedir_rubro(client, ana).status_code == 201


def test_request_check_dice_consent_fotos_ok_y_motivo(repo, crepo, client, ana):
    comercio(repo)
    url = "/admin/content/merchants/com-1/request-check"
    assert client.get(url, headers=ana).json() == {
        "consent": False, "usable_photos": 0, "ok": False, "reason": "El comercio no tiene autorización vigente para aparecer en las redes"}
    autorizar(crepo, "com-1"); banco(crepo, "com-1", 2)
    assert client.get(url, headers=ana).json() == {
        "consent": True, "usable_photos": 2, "ok": False, "reason": "Tiene 2 fotos que sirven: subí al menos 4 en Banco de contenido"}
    banco(crepo, "com-1", 5)
    assert client.get(url, headers=ana).json() == {"consent": True, "usable_photos": 6, "ok": True, "reason": None}
    assert client.get("/admin/content/merchants/no-existe/request-check", headers=ana).status_code == 404
    repo.comercios["com-1"]["activo"] = False
    assert client.get(url, headers=ana).json()["reason"] == "El comercio no está activo"


def test_el_check_y_el_pedido_dan_el_mismo_motivo(repo, crepo, client, ana):
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 3)
    motivo = client.get("/admin/content/merchants/com-1/request-check", headers=ana).json()["reason"]
    assert pedir_comercio(client, ana).json()["detail"] == motivo


# ══════════════════════════════════════════════════════════════ buscar el negocio por código

def test_el_buscador_encuentra_por_codigo_uruku_y_por_nombre(repo, crepo, client, ana):
    comercio(repo, "com-1", nombre="Casa Mesa", codigo="K7M2")
    comercio(repo, "com-2", nombre="Otro Local", codigo="P3Q9")
    comercio(repo, "com-3", nombre="Uruku Casa", codigo="X5X5")
    ids = lambda q: [c["id"] for c in client.get("/admin/content/merchants", headers=ana, params={"q": q}).json()["items"]]
    assert ids("URUKU-K7M2") == ["com-1"] and ids("uruku k7m2") == ["com-1"] and ids("  URUKUK7M2 ") == ["com-1"]
    assert ids("URUKU-P3Q9") == ["com-2"]
    assert ids("casa") == ["com-1", "com-3"]                          # por nombre, como siempre
    assert ids("Mesa") == ["com-1"]                                   # 4 letras del alfabeto, sin prefijo: es un nombre, no un código
    assert ids("K7M2") == []                                          # el código pelado no es "forma URUKU-XXXX"
    assert ids("URUKU-ZZZZ") == []                                    # ningún código así y ningún nombre
    assert ids("URUKU CASA") == ["com-3"]                             # parece código pero no existe: sigue con el nombre


def test_el_codigo_no_se_devuelve_en_el_buscador(repo, crepo, client, ana):
    comercio(repo, "com-1", nombre="Casa", codigo="K7M2")
    r = client.get("/admin/content/merchants", headers=ana, params={"q": "URUKU-K7M2"})
    assert "K7M2" not in r.text and "codigo" not in r.text


# ══════════════════════════════════════════════════════════════ el pilar rubro en el resto del camino

def _rubro_listo(repo, crepo, client, ana, n=5, estado="ready_for_review"):
    zapaterias(repo, crepo, n=n)
    p = pedir_rubro(client, ana).json()
    crepo.update_piece(p["id"], {"status": estado, "video_path": "renders/x/video.mp4", "cover_path": "renders/x/cover.jpg"})
    return crepo.pieces[p["id"]]


def test_origin_y_rubro_vienen_tambien_en_el_resumen_de_la_semana_y_el_paquete_del_dia(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    semana = client.get("/admin/content/week", headers=ana).json()
    res = next(x for d in semana["days"] for x in d["pieces"] if x["id"] == p["id"])
    assert res["origin"] == "pedido" and res["rubro"] == {"nombre": "Zapatillas", "slug": "zapatillas"}
    assert res["pillar"] == "rubro" and res["pillar_label"] == "Repaso de rubro" and res["title"] == "Zapatillas en Bermejo"
    assert res["comercio"] is None and res["ciudad_nombre"] == "Bermejo"
    hoy_ = client.get("/admin/content/today", headers=ana).json()
    pendiente = next(x for x in hoy_["pending_review"] if x["id"] == p["id"])
    assert pendiente["origin"] == "pedido" and pendiente["rubro"]["slug"] == "zapatillas"
    # una pieza del selector: origin selector y rubro null
    from tests.content_helpers import pieza
    comercio(repo); q = pieza(crepo, "com-1", dia=hoy(), status="ready_for_review")
    r = client.get(f"/admin/content/pieces/{q['id']}", headers=ana).json()
    assert r["origin"] == "selector" and r["rubro"] is None


def test_aprobar_un_rubro_con_objeciones_o_fotos_marcadas_es_409(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    crepo.update_piece(p["id"], {"video_texts_checks": ["Kick: pasa de 22 caracteres"]})
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Revise los textos del video"
    crepo.update_piece(p["id"], {"video_texts_checks": []})
    crepo.update_source(crepo.list_sources(p["id"])[0]["id"], {"photo_flags": ["price_or_code_visible"]})
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Hay fotos marcadas: cámbielas o confirme que están bien"
    crepo.update_piece(p["id"], {"photo_flags_ok": True})
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 200 and r.json()["status"] == "approved"
    refs = [x["ref_tag"] for x in r.json()["posts"]]
    assert refs and all(x.startswith(("tt-r-zapatillas-", "ig-r-zapatillas-", "fb-r-zapatillas-", "canal-r-zapatillas-")) for x in refs)


def test_las_marcadas_de_un_rubro_se_quedan_con_la_marca_aunque_sobren_fotos():
    fuentes = [{"source_type": "asset", "source_id": f"a{i}", "file_ref": f"r{i}"} for i in range(6)]
    prop = {"slides": [{"chip": None, "flags": ["price_or_code_visible"] if i == 0 else [], "focus_y": None} for i in range(6)]}
    quedan, n = cvt.aplicar_en_memoria(fuentes, prop, "rubro")
    assert n == 0 and len(quedan) == 6 and quedan[0]["photo_flags"]


def test_el_link_de_facebook_y_del_canal_va_a_la_pagina_del_rubro(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    aprobada = crepo.update_piece(p["id"], {"video_texts_checks": [], "photo_flags_ok": True})
    r = client.post(f"/admin/content/pieces/{aprobada['id']}/approve", headers=ana).json()
    base = settings.sitio_url.rstrip("/")
    fb = next(x for x in r["posts"] if x["network"] == "facebook")
    canal = next(x for x in r["posts"] if x["network"] == "wa_channel")
    assert f"{base}/bermejo/zapatillas?ref={fb['ref_tag']}" in fb["caption_text"]
    assert f"{base}/bermejo/zapatillas?ref={canal['ref_tag']}" in canal["caption_text"]
    tiktok = next(x for x in r["posts"] if x["network"] == "tiktok")
    assert "http" not in tiktok["caption_text"] and "Dónde comprar zapatillas en Bermejo" in tiktok["caption_text"]


def test_patch_de_textos_en_un_rubro_valida_igual_pero_las_frases_no_se_editan(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    antes = [f["chip_text"] for f in crepo.list_sources(p["id"])]
    fuente = crepo.list_sources(p["id"])[0]
    cuerpo = {"kick": "EN BERMEJO", "title1": "Zapatillas", "title2": "en Bermejo", "subtitle": None, "search_term": "zapatillas",
              "chips": [{"source_id": fuente["id"], "text": "Frase que se ignora"}]}
    r = client.patch(f"/admin/content/pieces/{p['id']}/video-texts", headers=ana, json={**cuerpo, "title2": "Buscá acá"})
    assert r.status_code == 400 and "Use usted" in r.json()["detail"]
    r = client.patch(f"/admin/content/pieces/{p['id']}/video-texts", headers=ana, json={**cuerpo, "title2": "en la frontera"})
    assert r.status_code == 200 and r.json()["video_texts"]["title2"] == "en la frontera" and r.json()["status"] == "queued"
    assert [f["chip_text"] for f in crepo.list_sources(p["id"])] == antes
    assert r.json()["video_texts"]["close_title1"] == "Encuéntrelos"


def test_el_validador_no_mira_los_chips_de_un_rubro():
    assert cvt.validate_video_texts(None, ["Zapatería 24 Bs", "x"], "rubro") == []
    assert cvt.validate_video_texts(None, ["Zapatería 24 Bs"], "comercio_del_dia")


def test_el_gemini_de_un_rubro_recibe_rubro_ciudad_y_nombres_sin_contacto():
    pieza = {"pillar": "rubro", "facts": {"pillar": "rubro", "rubro": "Zapatillas", "ciudad": "Bermejo",
                                          "items": [{"nombre": "Zapatería uno", "slug": "z1"}, {"nombre": "Zapatería dos", "slug": "z2"}]}}
    prompt = cvt.construir_prompt(pieza, None, 2)
    assert "Zapatillas" in prompt and "Zapatería uno" in prompt and "mismo rubro" in prompt
    assert "deja `chip` en null" in prompt and "z1" not in prompt


def test_el_titulo_publico_es_rubro_en_ciudad_y_trae_el_rubro(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    v = content_public.video_response(p, [], {"ciu-1": "bermejo"})
    assert v["title"] == "Zapatillas en Bermejo" and v["comercio"] is None
    assert v["rubro"] == {"nombre": "Zapatillas", "slug": "zapatillas"} and v["city_slug"] == "bermejo"
    assert "5" not in v["title"] and set(v) >= {"id", "title", "comercio", "rubro", "city_slug", "cover_url", "video_url"}
    comercio(repo)
    from tests.content_helpers import pieza
    assert content_public.video_response(pieza(crepo, "com-1"), [], {})["rubro"] is None


def test_la_pagina_publica_de_un_rubro_y_el_nombre_de_la_descarga(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    crepo.update_piece(p["id"], {"status": "published", "share_token": "t" * 22, "share_expires_at": "2099-01-01T00:00:00+00:00"})
    r = client.get(f"/public/pieces/{'t' * 22}")
    assert r.status_code == 200 and r.json()["pillar"] == "rubro" and r.json()["comercio_nombre"] is None
    assert r.json()["status_text"].endswith("/bermejo/zapatillas?ref=st-r-zapatillas") and "Zapatillas en Bermejo" in r.json()["status_text"]
    from app.api import content
    assert content._nombre_pieza(crepo.pieces[p["id"]], "mp4").startswith("uruku-zapatillas-bermejo-")


def test_publicar_un_pedido_no_crea_la_tarea_de_entrega(repo, crepo, client, ana):
    comercio(repo); autorizar(crepo, "com-1"); banco(crepo, "com-1", 5)
    p = pedir_comercio(client, ana).json()
    crepo.update_piece(p["id"], {"status": "approved"})
    crepo.insert_posts([{"piece_id": p["id"], "network": "tiktok", "ref_tag": "tt-x-1103"}])
    post = crepo.list_posts([p["id"]])[0]
    crepo.update_post(post["id"], {"status": "posted", "post_url": "https://tiktok.com/x"})
    assert content_posts.cerrar_pieza_si_corresponde(crepo, p["id"])["status"] == "published"
    assert crepo.tasks == {}
    # una pieza del selector del mismo comercio sí la crea
    from tests.content_helpers import pieza
    q = pieza(crepo, "com-1", dia=hoy() + timedelta(days=1), status="approved")
    crepo.insert_posts([{"piece_id": q["id"], "network": "tiktok", "ref_tag": "tt-y-1104"}])
    crepo.update_post(crepo.list_posts([q["id"]])[0]["id"], {"status": "posted"})
    content_posts.cerrar_pieza_si_corresponde(crepo, q["id"])
    assert [t["kind"] for t in crepo.tasks.values()] == ["piece_delivery"]


# ── consentimiento de TODAS las fuentes ──

def test_si_un_comercio_retira_la_autorizacion_sale_del_video_de_rubro(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana, n=6)
    r = content_consent.aplicar(crepo, "zapatillas-0", False, "admin", "ana@uruku.bo")
    assert r["pieces_skipped"] == 0
    nueva = crepo.pieces[p["id"]]
    activas = crepo.list_sources(p["id"])
    assert nueva["status"] == "queued" and len(activas) == 5 and "zapatillas-0" not in {f["comercio_id"] for f in activas}
    assert len(nueva["facts"]["items"]) == 5 and "Zapatería uno" not in nueva["caption_tiktok"]
    assert nueva["facts"]["pillar"] == "rubro" and nueva["facts"]["rubro_slug"] == "zapatillas" and nueva["facts"]["ciudad_slug"] == "bermejo"
    assert nueva["caption_tiktok"].startswith("Dónde comprar zapatillas en Bermejo") and nueva["caption_checks"] == []
    assert nueva["video_path"] is None and nueva["rubro_id"] == "rub-zapatillas"


def test_si_el_video_de_rubro_queda_con_menos_de_4_comercios_se_saltea(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana, n=4)
    r = content_consent.aplicar(crepo, "zapatillas-2", False, "admin", "ana@uruku.bo")
    assert r["pieces_skipped"] == 1 and crepo.pieces[p["id"]]["status"] == "skipped"


def test_un_comercio_dado_de_baja_o_sin_autorizacion_bloquea_la_aprobacion_del_rubro(repo, crepo, client, ana):
    p = _rubro_listo(repo, crepo, client, ana)
    crepo.update_piece(p["id"], {"photo_flags_ok": True})
    repo.comercios["zapatillas-3"]["activo"] = False
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == content_consent.MENSAJE_DE_BLOQUEO["comercio_inactivo"]
    repo.comercios["zapatillas-3"]["activo"] = True
    crepo.consents.append({"id": "x", "comercio_id": "zapatillas-1", "granted": False, "via": "admin", "recorded_by": "z",
                           "recorded_at": "2999-01-01T00:00:00+00:00", "activo": True})
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == content_consent.MENSAJE_DE_BLOQUEO["consent_revoked"]
    assert content_consent.motivo_de_comercios(crepo, crepo.pieces[p["id"]]) == "consent_revoked"


# ── captions y hechos del rubro ──

def test_los_hechos_del_rubro_no_cuentan_comercios_y_pasan_el_validador():
    facts = cc.build_facts_rubro({"nombre": "👟 Zapatillas", "slug": "calzado"}, {"nombre": "Bermejo", "slug": "bermejo", "departamento": "Tarija"},
                                 [{"nombre": "Zapatería Uno", "slug": "z1"}, {"nombre": "Calzados Luz", "slug": "z2"}] * 2)
    assert facts["rubro"] == "Zapatillas" and facts["allowed_numbers"] == [] and "#Calzado" in facts["hashtags_allowed"]
    t = cc.template_captions(facts)
    assert cc.validate_piece(facts, t["caption_tiktok"], t["caption_ig"], t["caption_channel"], t["hashtags"]) == []
    assert t["caption_tiktok"] == "Dónde comprar zapatillas en Bermejo: Zapatería Uno, Calzados Luz y más. Búsquelos en uruku.bo"
    assert 4 <= len(t["hashtags"]) <= 8
    assert any("Cuenta comercios" in o for o in cc.validate_caption("Hay 12 comercios en Bermejo", facts, "tiktok"))


def test_un_nombre_con_numero_no_traba_el_texto_fijo():
    facts = cc.build_facts_rubro({"nombre": "Zapatillas", "slug": "zapatillas"}, {"nombre": "Bermejo", "slug": "bermejo", "departamento": "Tarija"},
                                 [{"nombre": "Zapatería 24 Horas", "slug": "z1"}] * 4)
    assert facts["allowed_numbers"] == ["24"]
    t = cc.template_captions(facts)
    assert cc.validate_piece(facts, t["caption_tiktok"], t["caption_ig"], t["caption_channel"], t["hashtags"]) == []


def test_el_caption_de_rubro_puede_llamarse_tu_casa_sin_ser_tuteo():
    facts = cc.build_facts_rubro({"nombre": "Hogar", "slug": "hogar"}, {"nombre": "Bermejo", "slug": "bermejo", "departamento": "Tarija"},
                                 [{"nombre": "Tu Casa", "slug": "tu-casa"}, {"nombre": "El Hogar", "slug": "hogar-1"}] * 2)
    t = cc.template_captions(facts)
    assert cc.validate_piece(facts, t["caption_tiktok"], t["caption_ig"], t["caption_channel"], t["hashtags"]) == []
    assert cc.tiene_voseo_o_tuteo("Dónde comprar tu casa", cc._nombres_propios(facts)) is False


def test_rubro_largo_o_prohibido_usa_el_titulo_generico():
    t = cvt.textos_fijos("rubro", {"pillar": "rubro", "rubro": "Ferretería y Construcción", "ciudad": "Bermejo"})
    assert t["title1"] == "Dónde comprar" and t["title2"] == "en Bermejo" and t["search_term"] == "ferretería"
    t = cvt.textos_fijos("rubro", {"pillar": "rubro", "rubro": "Envíos", "ciudad": "Santa Cruz de la Sierra"})
    assert t["title1"] == "Dónde comprar" and t["title2"] == "está en Uruku" and t["search_term"] == "comercios" and t["kick"] is None
    assert cvt.validate_video_texts(t, None, "rubro") == []


# ── render ──

def test_el_motor_pillow_arma_los_tramos_de_un_video_de_rubro(tmp_path):
    from app.services import content_render_job as job
    from tests.content_helpers import jpg
    assert job.MAX_FOTOS["rubro"] == 6
    slides = []
    for i in range(4):
        (tmp_path / f"f{i}.jpg").write_bytes(jpg(900, 900, seed=i))
        slides.append({"path": str(tmp_path / f"f{i}.jpg"), "caption_fact": f"Zapatería {NOMBRES[i]}"})
    facts = {"pillar": "rubro", "rubro": "Zapatillas", "ciudad": "Bermejo",
             "items": [{"nombre": f"Zapatería {NOMBRES[i]}", "slug": f"z{i}"} for i in range(4)]}
    tramos = job.armar_tramos(facts, slides)
    assert len(tramos) == 6                                           # tapa + 4 fotos + cierre
    with pytest.raises(job.RenderError, match="Faltan fotos"):
        job.armar_tramos(facts, slides[:3])
