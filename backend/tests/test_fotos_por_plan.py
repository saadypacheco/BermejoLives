"""Fotos del local según el plan (docs/fotos-por-plan.md, parte A).

El tope de la galería dejó de ser 10 fijo: es el `fotos_max` del plan (gratis 50,
publica 100, destacado 300) mientras el pago esté al día, el del gratis si no,
más las fotos extra que el comercio compró a Bs 5.

Lo que se prueba es sobre todo lo que NO puede pasar:
- que un pago vencido borre fotos (sólo deja de poder subir más);
- que reemplazar borre la vieja y después falle la nueva (la vieja se pierde);
- que el agente o el admin comprometan plata del comercio;
- que se cobre una foto extra que no hacía falta, o una que no entró.

Nunca se suben cientos de fotos: el conteo se siembra en el FakeRepo, y el
volumen de fotos es un tmp por test (autouse en conftest).
"""
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.services import cargas, fotos_galeria
from app.services.imagenes import guardar_foto_local
from tests.conftest import comercio_token

BASE = "https://api.test/fotos"
AGENTE = "agente@bermejolive.com"


@pytest.fixture(autouse=True)
def _base_publica(monkeypatch):
    """La URL pública que corresponde al volumen tmp: sin esto no se sabe a qué
    archivo del disco apunta una foto sembrada."""
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _hoy(dias=0):
    return (cargas.hoy_bolivia() + timedelta(days=dias)).isoformat()


def _jpeg():
    buf = BytesIO()
    Image.new("RGB", (10, 10), "green").save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _foto():
    return {"foto": ("f.jpg", _jpeg(), "image/jpeg")}


def _stamp(i):
    # Cada foto un minuto después de la anterior: la 0 es la más vieja.
    return f"2026-01-01T{i // 60:02d}:{i % 60:02d}:00+00:00"


def _sembrar(repo, cid, n, con_archivos=False, slug="local"):
    """n fotos ya cargadas, de la más vieja (f0) a la más nueva. Sin subir nada."""
    for i in range(n):
        url, thumb = f"{BASE}/{slug}/s{i}.jpg", f"{BASE}/{slug}/s{i}_t3.jpg"
        if con_archivos:
            guardar_foto_local(f"{slug}/s{i}.jpg", b"grande")
            guardar_foto_local(f"{slug}/s{i}_t3.jpg", b"chica")
        repo.comercio_fotos.append({"id": f"f{i}", "comercio_id": cid, "url": url,
                                    "thumb_url": thumb, "orden": i, "created_at": _stamp(i)})


def _en_disco(slug, nombre):
    return (Path(settings.fotos_dir) / slug / nombre).exists()


def _comercio(repo, **kw):
    return repo.seed_comercio(id="com-g", slug="local", nombre="Local", whatsapp="59170000001",
                              confiable=True, cargado_por=AGENTE, **kw)


def _fotos_de(repo, cid):
    return [f["id"] for f in repo.list_fotos_comercio(cid)]


# ══════════════════════════════════════════════════ el tope sale del plan

@pytest.mark.parametrize("campos, esperado", [
    ({"plan": "gratis"}, 50),
    ({"plan": "publica", "paga_hasta": _hoy(5)}, 100),
    ({"plan": "publica", "paga_hasta": _hoy(0)}, 100),           # vence hoy: todavía rige
    ({"plan": "destacado", "paga_hasta": _hoy(30)}, 300),
    ({"plan": "pro", "paga_hasta": _hoy(30)}, 300),
    ({"plan": "empleado_ia", "paga_hasta": _hoy(30)}, 300),
    ({"plan": "destacado", "paga_hasta": _hoy(-1)}, 50),          # vencido: vuelve al gratis
    ({"plan": "destacado"}, 50),                                   # nunca pagó
    ({"plan": "destacado", "paga_hasta": _hoy(30), "suspendido": True}, 50),
    ({"plan": "destacado", "plan_cortesia": True}, 300),          # cortesía: el de su plan, sin pagar
    ({"plan": "publica", "plan_cortesia": True, "paga_hasta": _hoy(-90)}, 100),
    ({"plan": "destacado", "plan_cortesia": True, "suspendido": True}, 50),   # suspendido nunca
    ({"plan": "publica", "paga_hasta": _hoy(5), "fotos_extra": 7}, 107),
    ({"plan": "destacado", "paga_hasta": _hoy(-1), "fotos_extra": 3}, 53),   # las extra no vencen
])
def test_tope_por_plan(repo, campos, esperado):
    c = _comercio(repo, **campos)
    assert fotos_galeria.tope_fotos(repo, c) == esperado


def test_el_tope_sigue_lo_que_se_edita_en_el_plan(repo):
    c = _comercio(repo, plan="publica", paga_hasta=_hoy(5))
    repo.upsert_plan("publica", {"fotos_max": 120})
    assert fotos_galeria.tope_fotos(repo, c) == 120
    repo.upsert_plan("gratis", {"fotos_max": 40})
    vencido = _comercio(repo, plan="publica", paga_hasta=_hoy(-1))
    assert fotos_galeria.tope_fotos(repo, vencido) == 40


def test_un_plan_sin_fotos_max_usa_el_del_gratis(repo):
    """Un plan nuevo creado en Admin sin ese dato no queda sin tope ni en cero."""
    repo.upsert_plan("mayorista", {"nombre": "Mayorista", "orden": 7})
    c = _comercio(repo, plan="mayorista", paga_hasta=_hoy(5))
    assert fotos_galeria.tope_fotos(repo, c) == 50


def test_sin_ningun_dato_de_fotos_hay_un_respaldo(repo):
    for p in repo.planes.values():
        p.pop("fotos_max", None)
    assert fotos_galeria.tope_fotos(repo, _comercio(repo)) == 10


# ═════════════════════════════════════════════ subir hasta el tope, y el 409

def test_gratis_sube_hasta_50_y_la_51_da_409(client, repo):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 49)
    h = _h(comercio_token(comercio_id=c["id"]))
    assert client.post("/comercio/fotos", headers=h, files=_foto()).status_code == 200
    assert len(repo.list_fotos_comercio(c["id"])) == 50
    assert client.post("/comercio/fotos", headers=h, files=_foto()).status_code == 409
    assert len(repo.list_fotos_comercio(c["id"])) == 50


def test_publica_al_dia_llega_a_100(client, repo):
    c = _comercio(repo, plan="publica", paga_hasta=_hoy(10))
    _sembrar(repo, c["id"], 99)
    h = _h(comercio_token(comercio_id=c["id"]))
    assert client.post("/comercio/fotos", headers=h, files=_foto()).status_code == 200
    assert client.post("/comercio/fotos", headers=h, files=_foto()).status_code == 409


CUERPO_409 = {
    "mensaje": "Llegaste al tope de 50 fotos de tu plan.",
    "codigo": "tope_fotos",
    "limite": 50,
    "precio_extra": 5,
    "moneda": "BOB",
    "mas_vieja": {"id": "f0", "url": f"{BASE}/local/s0.jpg"},
}


def _post(client, repo, lado, token, cid, **data):
    url = {"comercio": "/comercio/fotos", "agente": f"/campo/mis-comercios/{cid}/fotos",
           "admin": f"/admin/comercio/{cid}/fotos"}[lado]
    return client.post(url, headers=_h(token), files=_foto(), data=data)


@pytest.fixture
def lados(agente_token, admin_token):
    return {"comercio": comercio_token(comercio_id="com-g"), "agente": agente_token, "admin": admin_token}


@pytest.mark.parametrize("lado", ["comercio", "agente", "admin"])
def test_el_409_trae_el_cuerpo_exacto_en_los_tres_lados(client, repo, lados, lado):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    repo.comercio_fotos.reverse()      # la más vieja NO es la primera de la lista
    r = _post(client, repo, lado, lados[lado], c["id"])
    assert r.status_code == 409
    assert r.json() == {"detail": CUERPO_409}


def test_el_precio_del_409_es_el_del_extra_del_plan(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    repo.upsert_plan("gratis", {"precio_publicacion_extra": 8})
    d = _post(client, repo, "comercio", lados["comercio"], c["id"]).json()["detail"]
    assert d["precio_extra"] == 8 and d["moneda"] == "BOB"


def test_con_el_pago_vencido_las_fotos_se_quedan_y_no_se_puede_subir_mas(client, repo, lados):
    """Tenía 120 con destacado; vencido baja el tope a 50. No se borra ninguna."""
    c = _comercio(repo, plan="destacado", paga_hasta=_hoy(-3))
    _sembrar(repo, c["id"], 120)
    r = _post(client, repo, "comercio", lados["comercio"], c["id"])
    assert r.status_code == 409 and r.json()["detail"]["limite"] == 50
    assert len(repo.list_fotos_comercio(c["id"])) == 120


# ══════════════════════════════════════════════════════════════ reemplazar

@pytest.mark.parametrize("lado", ["comercio", "agente", "admin"])
def test_reemplazar_guarda_la_nueva_y_borra_la_vieja_de_base_y_disco(client, repo, lados, lado):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50, con_archivos=True)
    assert _en_disco("local", "s0.jpg") and _en_disco("local", "s0_t3.jpg")

    r = _post(client, repo, lado, lados[lado], c["id"], reemplazar="f0")

    assert r.status_code == 200, r.text
    ids = _fotos_de(repo, c["id"])
    assert "f0" not in ids and r.json()["foto"]["id"] in ids
    assert len(ids) == 50                                  # sigue en el tope, no pasa
    assert not _en_disco("local", "s0.jpg") and not _en_disco("local", "s0_t3.jpg")
    assert _en_disco("local", "s1.jpg")                    # las demás, intactas
    nueva = Path(settings.fotos_dir) / r.json()["foto"]["url"].split("/fotos/", 1)[1]
    assert nueva.exists()


def test_reemplazar_una_foto_ajena_se_rechaza_y_no_toca_nada(client, repo, lados):
    c = _comercio(repo)
    otro = repo.seed_comercio(id="com-otro", slug="otro", nombre="Otro")
    _sembrar(repo, c["id"], 50)
    guardar_foto_local("otro/ajena.jpg", b"x")
    repo.comercio_fotos.append({"id": "ajena", "comercio_id": otro["id"],
                                "url": f"{BASE}/otro/ajena.jpg", "thumb_url": None,
                                "orden": 0, "created_at": _stamp(0)})
    for lado in ("comercio", "agente", "admin"):
        r = _post(client, repo, lado, lados[lado], c["id"], reemplazar="ajena")
        assert r.status_code == 404, lado
    assert "ajena" in _fotos_de(repo, otro["id"])
    assert _en_disco("otro", "ajena.jpg")
    assert len(repo.list_fotos_comercio(c["id"])) == 50


def test_si_falla_guardar_la_nueva_la_vieja_queda(client, repo, lados, monkeypatch):
    """El orden es la regla: primero la nueva, recién después se borra la vieja."""
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50, con_archivos=True)
    for modulo in ("comercio", "campo", "moderacion"):
        monkeypatch.setattr(f"app.api.{modulo}.subir_foto_galeria", lambda slug, data: (None, None))
    for lado in ("comercio", "agente", "admin"):
        r = _post(client, repo, lado, lados[lado], c["id"], reemplazar="f0")
        assert r.status_code == 502, lado
    assert "f0" in _fotos_de(repo, c["id"]) and len(repo.list_fotos_comercio(c["id"])) == 50
    assert _en_disco("local", "s0.jpg") and _en_disco("local", "s0_t3.jpg")


def test_si_falla_insertar_la_nueva_la_vieja_queda_y_no_sobra_archivo(client, repo, lados, monkeypatch):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50, con_archivos=True)
    antes = set((Path(settings.fotos_dir) / "local").iterdir())

    def roto(row):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "add_foto_comercio", roto)
    with pytest.raises(RuntimeError):
        client.post("/comercio/fotos", headers=_h(lados["comercio"]), files=_foto(),
                    data={"reemplazar": "f0"})
    assert "f0" in _fotos_de(repo, c["id"])
    assert _en_disco("local", "s0.jpg")
    assert set((Path(settings.fotos_dir) / "local").iterdir()) == antes   # la nueva no quedó huérfana


def test_reemplazar_sin_estar_en_el_tope_solo_sube(client, repo, lados):
    """Pantalla desactualizada: no hay nada que borrar."""
    c = _comercio(repo)
    _sembrar(repo, c["id"], 3, con_archivos=True)
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], reemplazar="f0")
    assert r.status_code == 200
    assert len(repo.list_fotos_comercio(c["id"])) == 4 and "f0" in _fotos_de(repo, c["id"])
    assert _en_disco("local", "s0.jpg")


def test_reemplazar_no_borra_un_archivo_que_es_la_portada(client, repo, lados):
    c = _comercio(repo, portada_url=f"{BASE}/local/s0.jpg")
    _sembrar(repo, c["id"], 50, con_archivos=True)
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], reemplazar="f0")
    assert r.status_code == 200 and "f0" not in _fotos_de(repo, c["id"])
    assert _en_disco("local", "s0.jpg")          # la portada la sigue mostrando
    assert not _en_disco("local", "s0_t3.jpg")


def test_una_url_rara_no_hace_borrar_archivos_fuera_de_la_galeria(client, repo, lados, tmp_path):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    afuera = tmp_path / "secreto.jpg"
    afuera.write_bytes(b"no me toques")
    repo.comercio_fotos[0]["url"] = f"{BASE}/../secreto.jpg"
    repo.comercio_fotos[0]["thumb_url"] = "https://otro.com/local/x.jpg"
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], reemplazar="f0")
    assert r.status_code == 200
    assert afuera.exists()


# ═════════════════════════════════════════════════════════ pagar la extra

def test_pagar_registra_el_cargo_suma_una_foto_y_la_foto_entra(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar")

    assert r.status_code == 200, r.text
    assert len(repo.list_fotos_comercio(c["id"])) == 51
    assert repo.comercios[c["id"]]["fotos_extra"] == 1
    assert len(repo.cargos_extra) == 1
    cargo = repo.cargos_extra[0]
    assert (cargo["comercio_id"], cargo["monto"], cargo["moneda"]) == (c["id"], 5, "BOB")
    assert cargo["concepto"] == "foto_extra" and cargo["publicacion_id"] is None
    assert cargo["estado"] == "pendiente"
    # El tope sube con lo comprado: la 52 vuelve a dar 409, ahora con límite 51.
    d = _post(client, repo, "comercio", lados["comercio"], c["id"]).json()["detail"]
    assert d["limite"] == 51


def test_el_cargo_aparece_en_los_cargos_pendientes_del_admin(client, repo, lados, admin_token):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar")
    r = client.get("/admin/cargos-extra", headers=_h(admin_token))
    assert r.json()["total"] == 5 and r.json()["items"][0]["concepto"] == "foto_extra"


def test_el_precio_del_cargo_es_el_del_extra_editado_en_el_plan(client, repo, lados):
    c = _comercio(repo, plan="publica", paga_hasta=_hoy(5))
    _sembrar(repo, c["id"], 100)
    repo.upsert_plan("publica", {"precio_publicacion_extra": 8})
    assert _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar").status_code == 200
    assert repo.cargos_extra[0]["monto"] == 8


@pytest.mark.parametrize("lado", ["agente", "admin"])
def test_el_agente_y_el_admin_no_pueden_pagar(client, repo, lados, lado):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    r = _post(client, repo, lado, lados[lado], c["id"], extra="pagar")
    assert r.status_code == 403
    assert r.json()["detail"] == "Sólo el comercio puede pagar una foto extra."
    assert repo.cargos_extra == [] and len(repo.list_fotos_comercio(c["id"])) == 50
    assert not repo.comercios[c["id"]].get("fotos_extra")


@pytest.mark.parametrize("lado", ["agente", "admin"])
def test_el_agente_y_el_admin_no_pagan_ni_estando_bajo_el_tope(client, repo, lados, lado):
    c = _comercio(repo)
    r = _post(client, repo, lado, lados[lado], c["id"], extra="pagar")
    assert r.status_code == 403 and repo.cargos_extra == []


def test_pagar_sin_estar_en_el_tope_no_cobra(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 3)
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar")
    assert r.status_code == 200 and len(repo.list_fotos_comercio(c["id"])) == 4
    assert repo.cargos_extra == [] and not repo.comercios[c["id"]].get("fotos_extra")


def test_extra_con_un_valor_raro_o_junto_con_reemplazar_es_400(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    assert _post(client, repo, "comercio", lados["comercio"], c["id"], extra="gratis").status_code == 400
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar", reemplazar="f0")
    assert r.status_code == 400
    assert repo.cargos_extra == [] and len(repo.list_fotos_comercio(c["id"])) == 50


def test_si_no_se_puede_registrar_el_cargo_no_queda_la_foto(client, repo, lados, monkeypatch):
    """Ni foto gratis ni cobro sin foto."""
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)

    def roto(*a, **k):
        raise RuntimeError("tabla caída")
    monkeypatch.setattr(repo, "registrar_cargo_extra", roto)
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar")
    assert r.status_code == 502
    assert len(repo.list_fotos_comercio(c["id"])) == 50
    assert not repo.comercios[c["id"]].get("fotos_extra")
    assert not any(Path(settings.fotos_dir, "local").glob("*.jpg"))


def test_si_falla_guardar_la_foto_no_se_cobra(client, repo, lados, monkeypatch):
    c = _comercio(repo)
    _sembrar(repo, c["id"], 50)
    monkeypatch.setattr("app.api.comercio.subir_foto_galeria", lambda slug, data: (None, None))
    r = _post(client, repo, "comercio", lados["comercio"], c["id"], extra="pagar")
    assert r.status_code == 502 and repo.cargos_extra == []
    assert not repo.comercios[c["id"]].get("fotos_extra")


# ═════════════════════════════════════════ el límite que lee cada pantalla

def test_los_get_de_la_galeria_devuelven_el_limite(client, repo, lados):
    c = _comercio(repo, plan="destacado", paga_hasta=_hoy(9), fotos_extra=2)
    _sembrar(repo, c["id"], 4)
    cid = c["id"]
    for url, lado in (("/comercio/fotos", "comercio"),
                      (f"/campo/mis-comercios/{cid}/fotos", "agente"),
                      (f"/admin/comercio/{cid}/fotos", "admin")):
        r = client.get(url, headers=_h(lados[lado]))
        assert r.status_code == 200, lado
        assert r.json()["limite"] == 302, lado
        assert len(r.json()["items"]) == 4, lado


def test_el_limite_cae_al_del_gratis_con_el_pago_vencido(client, repo, lados):
    _comercio(repo, plan="destacado", paga_hasta=_hoy(-1))
    assert client.get("/comercio/fotos", headers=_h(lados["comercio"])).json()["limite"] == 50


# ═════════════════════════════════════════════════ Admin › Planes: fotos_max

def test_fotos_max_se_ve_y_se_edita_en_admin_planes(client, repo, admin_token):
    r = client.get("/admin/planes", headers=_h(admin_token))
    por_slug = {p["slug"]: p for p in r.json()["items"]}
    assert por_slug["gratis"]["fotos_max"] == 50
    assert por_slug["publica"]["fotos_max"] == 100
    assert por_slug["destacado"]["fotos_max"] == 300

    r = client.put("/admin/planes/publica", json={"fotos_max": 150}, headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["plan"]["fotos_max"] == 150
    assert repo.get_plan("publica")["fotos_max"] == 150
    # y el tope de un comercio de ese plan lo sigue
    c = _comercio(repo, plan="publica", paga_hasta=_hoy(5))
    assert fotos_galeria.tope_fotos(repo, c) == 150


def test_fotos_max_cero_es_valido_y_los_valores_fuera_de_rango_se_rechazan(client, repo, admin_token):
    h = _h(admin_token)
    assert client.put("/admin/planes/publica", json={"fotos_max": 0}, headers=h).status_code == 200
    assert repo.get_plan("publica")["fotos_max"] == 0
    assert client.put("/admin/planes/publica", json={"fotos_max": 1000}, headers=h).status_code == 200
    for malo in (-1, 1001, 99999, "mucho", 12.5):
        r = client.put("/admin/planes/publica", json={"fotos_max": malo}, headers=h)
        assert r.status_code == 422, malo
    assert repo.get_plan("publica")["fotos_max"] == 1000


# ══════════════════════════════════════════ borrar una foto borra el archivo

@pytest.mark.parametrize("lado", ["comercio", "agente", "admin"])
def test_borrar_una_foto_la_saca_de_la_base_y_del_disco(client, repo, lados, lado):
    """Antes los tres «borrar foto» sólo borraban la fila y el archivo quedaba
    en el disco para siempre."""
    c = _comercio(repo)
    _sembrar(repo, c["id"], 3, con_archivos=True)
    url = {"comercio": "/comercio/fotos/f1", "agente": f"/campo/mis-comercios/{c['id']}/fotos/f1",
           "admin": f"/admin/comercio/{c['id']}/fotos/f1"}[lado]
    r = client.delete(url, headers=_h(lados[lado]))
    assert r.status_code == 200, r.text
    assert "f1" not in _fotos_de(repo, c["id"])
    assert not _en_disco("local", "s1.jpg") and not _en_disco("local", "s1_t3.jpg")
    assert _en_disco("local", "s0.jpg") and _en_disco("local", "s2.jpg")


def test_borrar_una_foto_que_es_la_portada_no_borra_el_archivo(client, repo, lados):
    c = _comercio(repo, portada_url=f"{BASE}/local/s0.jpg")
    _sembrar(repo, c["id"], 2, con_archivos=True)
    r = client.delete("/comercio/fotos/f0", headers=_h(lados["comercio"]))
    assert r.status_code == 200, r.text
    assert "f0" not in _fotos_de(repo, c["id"])
    assert _en_disco("local", "s0.jpg")          # la sigue mostrando la portada


def test_borrar_una_foto_ajena_da_404_y_no_toca_nada(client, repo, lados):
    c = _comercio(repo)
    otro = repo.seed_comercio(id="com-otro", slug="otro", nombre="Otro")
    guardar_foto_local("otro/ajena.jpg", b"x")
    repo.comercio_fotos.append({"id": "ajena", "comercio_id": otro["id"], "url": f"{BASE}/otro/ajena.jpg",
                                "thumb_url": None, "orden": 0, "created_at": _stamp(0)})
    r = client.delete("/comercio/fotos/ajena", headers=_h(lados["comercio"]))
    assert r.status_code == 404
    assert _en_disco("otro", "ajena.jpg")
    assert "ajena" in _fotos_de(repo, otro["id"])
