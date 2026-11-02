"""El selector semanal: calendario, cuota por ciclo, filtros, compilado de ofertas y fotos sin repetir."""
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import cargas, content_selector as sel, content_storage
from tests.content_helpers import autorizar, banco, comercio, jpg, pieza

#: Domingo 1/11/2026, 20:30 en Bolivia (00:30 UTC del lunes). La semana a planificar arranca el 2/11.
AHORA = datetime(2026, 11, 2, 0, 30, tzinfo=timezone.utc)
HOY = date(2026, 11, 1)
SEMANA = date(2026, 11, 2)


@pytest.fixture(autouse=True)
def _sin_gemini(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")


def suscriptor(repo, crepo, cid, fotos=5, autorizado=True, **kw):
    kw.setdefault("paga_hasta", (HOY + timedelta(days=20)).isoformat())
    c = comercio(repo, cid, **kw)
    if autorizado:
        autorizar(crepo, cid)
    if fotos:
        banco(crepo, cid, fotos)
    return c


def plan(repo, crepo, semana=SEMANA, ahora=AHORA):
    return sel.plan_week(repo, crepo, semana, "selector", ahora)


def vivas(crepo):
    return sorted((p["scheduled_for"], p["pillar"], p["comercio_id"]) for p in crepo.pieces.values()
                  if p["status"] not in ("skipped", "failed"))


# ── calendario ───────────────────────────────────────────────────────────────

def test_lugares_de_la_semana_y_el_sabado_y_lunes_segun_la_deuda():
    dias = lambda deuda: [d.isoformat() for d, _ in sel._slots_de_la_semana(SEMANA, HOY, deuda)]
    base = ["2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"]
    assert dias(0) == dias(3) == base
    assert dias(4) == base + ["2026-11-07"]
    assert dias(5) == ["2026-11-02"] + base + ["2026-11-07"]
    assert [p for _, p in sel._slots_de_la_semana(SEMANA, HOY, 0)] == ["comercio_del_dia", "comercio_del_dia", "ofertas", "comercio_del_dia"]
    # nunca el domingo ni días que ya pasaron
    assert [d.isoformat() for d, _ in sel._slots_de_la_semana(SEMANA, date(2026, 11, 5), 9)] == ["2026-11-05", "2026-11-06", "2026-11-07"]


def test_arma_una_pieza_por_lugar_con_tres_suscriptores(repo, crepo):
    for i in (1, 2, 3):
        suscriptor(repo, crepo, f"com-{i}")
    r = plan(repo, crepo)
    assert r["created"] == 3 and r["week_start"] == "2026-11-02"
    assert [(d, p) for d, p, _ in vivas(crepo)] == [("2026-11-03", "comercio_del_dia"), ("2026-11-04", "comercio_del_dia"),
                                                    ("2026-11-06", "comercio_del_dia")]
    assert {c for _, _, c in vivas(crepo)} == {"com-1", "com-2", "com-3"}          # uno distinto por lugar
    assert r["slots_left_empty"] == [{"date": "2026-11-05", "pillar": "ofertas", "reason": "not_enough_offers"}]
    p = next(iter(crepo.pieces.values()))
    assert p["status"] == "queued" and p["counts_for_quota"] and p["week_start"] == "2026-11-02"
    assert p["quota_cycle_start"] and p["created_by"] == "selector" and p["caption_engine"] == "template"
    assert p["facts"]["pillar"] == "comercio_del_dia" and len(crepo.list_sources(p["id"])) == 5


def test_es_idempotente_la_segunda_corrida_no_crea_nada(repo, crepo):
    for i in (1, 2, 3):
        suscriptor(repo, crepo, f"com-{i}")
    plan(repo, crepo)
    antes = vivas(crepo)
    assert plan(repo, crepo)["created"] == 0 and vivas(crepo) == antes


def test_no_planifica_lugares_que_ya_pasaron(repo, crepo):
    for i in (1, 2, 3):
        suscriptor(repo, crepo, f"com-{i}")
    miercoles = datetime(2026, 11, 4, 14, 0, tzinfo=timezone.utc)
    r = plan(repo, crepo, ahora=miercoles)
    assert {d for d, _, _ in vivas(crepo)} <= {"2026-11-04", "2026-11-06"} and r["created"] == 2


# ── cuota y filtros ──────────────────────────────────────────────────────────

def test_la_cuota_se_cuenta_por_ciclo_y_una_pieza_saltada_no_consume(repo, crepo):
    c = suscriptor(repo, crepo, "com-1")
    inicio, _ = sel.ciclo_de(c, HOY)
    for status in ("published", "approved"):
        pieza(crepo, "com-1", dia=HOY - timedelta(days=20 + (status == "approved")), status=status,
              counts_for_quota=True, quota_cycle_start=inicio.isoformat())
    assert plan(repo, crepo)["created"] == 0                        # cuota 2: ya la usó
    pieza(crepo, "com-1", dia=HOY - timedelta(days=30), status="skipped", counts_for_quota=True,
          quota_cycle_start=inicio.isoformat())
    assert sel.evaluar_suscriptores(crepo, HOY)[0]["debe"] == 0
    crepo.pieces = {k: v for k, v in crepo.pieces.items() if v["status"] != "approved"}
    assert sel.evaluar_suscriptores(crepo, HOY)[0]["debe"] == 1     # la saltada no cuenta


def test_la_cuota_de_otro_ciclo_no_cuenta(repo, crepo):
    c = suscriptor(repo, crepo, "com-1")
    inicio, _ = sel.ciclo_de(c, HOY)
    pieza(crepo, "com-1", dia=HOY - timedelta(days=60), status="published", counts_for_quota=True,
          quota_cycle_start=(inicio - timedelta(days=30)).isoformat())
    assert sel.evaluar_suscriptores(crepo, HOY)[0]["usadas"] == 0


def test_el_ciclo_de_una_cortesia_sin_paga_hasta_no_se_mueve_cada_dia(repo, crepo):
    c = suscriptor(repo, crepo, "com-1", paga_hasta=None, plan_cortesia=True)
    assert sel.ciclo_de(c, HOY) == sel.ciclo_de(c, HOY + timedelta(days=5)) == (date(2026, 11, 1), date(2026, 12, 1))
    assert sel.evaluar_suscriptores(crepo, HOY)[0]["cuota"] == 2


@pytest.mark.parametrize("nombre, kw, autorizado, entra", [
    ("al día y autorizado", {}, True, True),
    ("sin autorización", {}, False, False),
    ("vencido dentro de la gracia", {"paga_hasta": (HOY - timedelta(days=3)).isoformat()}, True, True),
    ("vencido fuera de la gracia", {"paga_hasta": (HOY - timedelta(days=10)).isoformat()}, True, False),
    ("suspendido", {"suspendido": True}, True, False),
    ("dado de baja", {"activo": False}, True, False),
    ("plan sin piezas", {"plan": "gratis"}, True, False),
    ("cortesía", {"plan_cortesia": True, "paga_hasta": None}, True, True),
])
def test_quien_entra_y_quien_no(repo, crepo, nombre, kw, autorizado, entra):
    suscriptor(repo, crepo, "com-1", autorizado=autorizado, **kw)
    assert (plan(repo, crepo)["created"] == 1) is entra, nombre


def test_con_menos_de_4_fotos_pide_fotos_una_sola_vez_por_ciclo(repo, crepo):
    suscriptor(repo, crepo, "com-1", fotos=3)
    r = plan(repo, crepo)
    assert r["created"] == 0 and r["tasks_created"] == 1
    t = next(iter(crepo.tasks.values()))
    assert t["kind"] == "photo_refresh" and t["comercio_id"] == "com-1" and t["due_on"] == HOY.isoformat()
    assert plan(repo, crepo, ahora=AHORA + timedelta(days=1))["tasks_created"] == 0      # una por ciclo
    assert len(crepo.tasks) == 1


def test_las_fotos_chicas_o_con_personas_sin_confirmar_no_cuentan(repo, crepo):
    suscriptor(repo, crepo, "com-1", fotos=0)
    banco(crepo, "com-1", 3)
    banco(crepo, "com-1", 2, w=600, h=400)                              # < 720 de lado menor
    banco(crepo, "com-1", 1, has_people=True, people_ok=None)
    banco(crepo, "com-1", 1, usable_for_social=False)
    assert plan(repo, crepo)["created"] == 0
    banco(crepo, "com-1", 1, has_people=True, people_ok=True)
    assert plan(repo, crepo)["created"] == 1


def test_separacion_de_14_dias_o_5_si_al_ciclo_le_quedan_10_o_menos(repo, crepo):
    c = suscriptor(repo, crepo, "com-1")
    pieza(crepo, "com-1", dia=date(2026, 10, 29), status="published")          # 5 días antes del martes 3/11
    assert plan(repo, crepo)["created"] == 0                                    # le quedan 20 días: espera 14
    repo.comercios["com-1"]["paga_hasta"] = (HOY + timedelta(days=8)).isoformat()
    assert plan(repo, crepo)["created"] == 1                                    # le quedan ≤ 10: alcanza con 5


def test_ordena_primero_al_que_mas_urge(repo, crepo):
    suscriptor(repo, crepo, "tranquilo", paga_hasta=(HOY + timedelta(days=25)).isoformat())
    suscriptor(repo, crepo, "urgente", paga_hasta=(HOY + timedelta(days=3)).isoformat())
    plan(repo, crepo)
    assert [c for _, _, c in vivas(crepo)][0] == "urgente"


def test_una_pieza_saltada_libera_el_lugar_y_se_vuelve_a_ofrecer(repo, crepo):
    suscriptor(repo, crepo, "com-1")
    plan(repo, crepo)
    p = next(iter(crepo.pieces.values()))
    crepo.update_piece(p["id"], {"status": "skipped", "skip_reason": "bad_photos"})
    assert plan(repo, crepo)["created"] == 1                                    # no consumió cuota ni ocupa el lugar
    assert sum(1 for x in crepo.pieces.values() if x["status"] == "queued") == 1


# ── fotos ────────────────────────────────────────────────────────────────────

def _publica(slug, nombre, w=1280, h=960, seed=1):
    ruta = Path(settings.fotos_dir) / slug / nombre
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(jpg(w, h, seed))
    return f"{settings.fotos_public_base_url.rstrip('/')}/{slug}/{nombre}"


def test_orden_portada_banco_nuevo_primero_galeria_sin_copias_y_chicas_fuera(repo, crepo):
    c = suscriptor(repo, crepo, "com-1", fotos=0, portada_url=_publica("local-com-1", "portada.jpg"))
    nuevos = banco(crepo, "com-1", 2)
    repo.comercio_fotos += [
        {"id": "g1", "comercio_id": "com-1", "url": _publica("local-com-1", "g1.jpg", seed=2), "created_at": "2026-01-01"},
        {"id": "g2", "comercio_id": "com-1", "url": _publica("local-com-1", "g2.jpg", 500, 400), "created_at": "2026-02-01"},   # chica
        {"id": "g3", "comercio_id": "com-1", "url": _publica("local-com-1", "g3.jpg", seed=3), "created_at": "2026-03-01"},
    ]
    crepo.assets[nuevos[0]["id"]]["gallery_photo_id"] = "g3"                      # g3 es copia de una del banco
    fotos = sel.elegir_fotos(crepo, c, 7, HOY, set())
    assert [(f["source_type"], f.get("source_id")) for f in fotos] == [
        ("cover", None), ("asset", nuevos[1]["id"]), ("asset", nuevos[0]["id"]), ("gallery", "g1")]


def test_no_repite_fotos_usadas_en_los_ultimos_60_dias(repo, crepo):
    c = suscriptor(repo, crepo, "com-1", fotos=6)
    assets = sorted(crepo.assets.values(), key=lambda a: a["created_at"], reverse=True)
    p = pieza(crepo, "com-1", dia=HOY - timedelta(days=20), status="published")
    crepo.insert_sources([{"piece_id": p["id"], "position": i, "source_type": "asset", "source_id": a["id"],
                           "comercio_id": "com-1", "file_ref": a["file_path"]} for i, a in enumerate(assets[:2])])
    usadas = sel.claves_usadas(crepo, HOY)
    elegidas = sel.elegir_fotos(crepo, c, 7, HOY, usadas)
    assert {f["source_id"] for f in elegidas} == {a["id"] for a in assets[2:]}
    # hace más de 60 días ya vuelven a estar disponibles
    crepo.pieces[p["id"]]["scheduled_for"] = (HOY - timedelta(days=61)).isoformat()
    assert len(sel.elegir_fotos(crepo, c, 7, HOY, sel.claves_usadas(crepo, HOY))) == 6


def test_una_foto_que_no_esta_en_el_disco_no_sirve(repo, crepo):
    c = suscriptor(repo, crepo, "com-1", fotos=4)
    content_storage.borrar(next(iter(crepo.assets.values()))["file_path"])
    assert len(sel.elegir_fotos(crepo, c, 7, HOY, set())) == 3


# ── compilado de ofertas ─────────────────────────────────────────────────────

def _oferta(repo, cid, i, dias=2, ciudad_slug=None, precio=100):
    c = repo.comercios[cid]
    repo.publicaciones.append({
        "id": f"of-{cid}-{i}", "comercio_id": cid, "tipo": "oferta", "estado": "aprobado", "activo": True,
        "titulo": f"Zapatillas URUKU-K7M2 {i}", "precio": precio, "moneda": "BOB",
        "imagen_url": _publica(c["slug"], f"o{i}.jpg", seed=i + len(cid)),
        "approved_at": (AHORA - timedelta(days=dias)).isoformat()})


def _comercios_con_oferta(repo, crepo, subs, otros, **kw):
    for i in range(subs):
        suscriptor(repo, crepo, f"s{i}", fotos=0)
        _oferta(repo, f"s{i}", 1, **kw)
    for i in range(otros):
        comercio(repo, f"n{i}", plan="gratis", paga_hasta=None)
        autorizar(crepo, f"n{i}")
        _oferta(repo, f"n{i}", 1, **kw)


def _compilado(crepo):
    return next((p for p in crepo.pieces.values() if p["pillar"] == "ofertas"), None)


def test_compilado_con_4_suscriptores_y_el_tope_de_un_tercio_de_los_demas(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=4, otros=4)
    r = plan(repo, crepo)
    p = _compilado(crepo)
    assert p and p["scheduled_for"] == "2026-11-05" and p["comercio_id"] is None and not p["counts_for_quota"]
    fuentes = crepo.list_sources(p["id"])
    assert len(fuentes) == 6 and all(f["source_type"] == "offer" for f in fuentes)
    assert [f["comercio_id"] for f in fuentes][:4] == ["s0", "s1", "s2", "s3"]          # suscriptores primero
    assert sum(1 for f in fuentes if f["comercio_id"].startswith("n")) == 2             # ≤ piso(6 / 3)
    assert p["facts"]["ciudad"] == "Bermejo" and len(p["facts"]["items"]) == 6
    assert p["facts"]["items"][0]["precio"] == "Bs 100" and p["facts"]["items"][0]["titulo_corto"] == "Zapatillas 1"
    assert fuentes[0]["caption_fact"] == "Local s0 · Bs 100"
    assert "ofertas" not in [e["pillar"] for e in r["slots_left_empty"]]


def test_compilado_con_menos_de_4_queda_vacio_con_su_motivo(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=3, otros=0)
    r = plan(repo, crepo)
    assert _compilado(crepo) is None
    assert {"date": "2026-11-05", "pillar": "ofertas", "reason": "not_enough_offers"} in r["slots_left_empty"]


def test_compilado_sin_suscriptores_no_arma_con_puros_extranos(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=0, otros=6)
    plan(repo, crepo)
    assert _compilado(crepo) is None


def test_compilado_es_de_una_sola_ciudad_la_que_tiene_mas(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=4, otros=0)
    for i in range(2):
        suscriptor(repo, crepo, f"sc{i}", fotos=0, ciudad_id="ciu-santa-cruz")
        _oferta(repo, f"sc{i}", 1)
    plan(repo, crepo)
    ids = {f["comercio_id"] for f in crepo.list_sources(_compilado(crepo)["id"])}
    assert ids == {"s0", "s1", "s2", "s3"}


def test_compilado_una_oferta_por_comercio_la_mas_nueva_y_solo_de_10_dias(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=4, otros=0)
    _oferta(repo, "s0", 2, dias=1)                       # más nueva que la 1
    _oferta(repo, "s1", 9, dias=30)                      # muy vieja
    plan(repo, crepo)
    fuentes = {f["comercio_id"]: f["source_id"] for f in crepo.list_sources(_compilado(crepo)["id"])}
    assert fuentes["s0"] == "of-s0-2" and fuentes["s1"] == "of-s1-1" and len(fuentes) == 4


def test_compilado_no_repite_una_oferta_que_ya_salio_en_otro_en_60_dias(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=4, otros=0)
    previa = pieza(crepo, None, dia=date(2026, 10, 15), pilar="ofertas", status="published")
    crepo.insert_sources([{"piece_id": previa["id"], "position": 0, "source_type": "offer", "source_id": "of-s0-1",
                           "comercio_id": "s0", "file_ref": "x"}])
    plan(repo, crepo)
    assert _compilado(crepo)["id"] == previa["id"] or all(
        f["source_id"] != "of-s0-1" for f in crepo.list_sources(_compilado(crepo)["id"]))
    assert sum(1 for p in crepo.pieces.values() if p["pillar"] == "ofertas" and p["status"] == "queued") == 0


def test_compilado_solo_con_comercios_autorizados(repo, crepo):
    _comercios_con_oferta(repo, crepo, subs=4, otros=0)
    crepo.consents.clear()
    plan(repo, crepo)
    assert _compilado(crepo) is None


# ── cuándo planificar ────────────────────────────────────────────────────────

def bo(dia, hora, minuto=0):
    """Un instante dado en hora de Bolivia."""
    return datetime(2026, 11, dia, hora, minuto, tzinfo=cargas.BOLIVIA)


def test_is_planning_due_domingo_19_59_no_20_00_si():
    assert sel.week_to_plan(bo(1, 19, 59), set()) is None and not sel.is_planning_due(bo(1, 19, 59), set())
    assert sel.week_to_plan(bo(1, 20, 0), set()) == date(2026, 11, 2) and sel.is_planning_due(bo(1, 20, 0), set())
    assert sel.week_to_plan(bo(1, 23, 59), {"2026-11-02"}) is None            # ya planificada


def test_recuperacion_el_lunes_planifica_lo_que_falte_de_la_semana_actual():
    assert sel.week_to_plan(bo(2, 9), set()) == date(2026, 11, 2)
    assert sel.week_to_plan(bo(4, 9), {"2026-10-26"}) == date(2026, 11, 2)
    assert sel.week_to_plan(bo(2, 9), {"2026-11-02"}) is None


def test_planner_tick_corre_una_vez_y_no_repite_enseguida(repo, crepo):
    for i in (1, 2, 3):
        suscriptor(repo, crepo, f"com-{i}")
    r = sel.planner_tick(repo, crepo, AHORA)
    assert r and r["created"] == 3
    assert sel.planner_tick(repo, crepo, AHORA) is None                       # ya está planificada (y espera una hora)
    assert sel.planner_tick(repo, crepo, bo(1, 19, 0)) is None                # domingo antes de las 20


def test_plan_manual_por_la_api(client, repo, crepo):
    from app.core import auth
    for i in (1, 2, 3):
        suscriptor(repo, crepo, f"com-{i}")
    t = auth.make_token("ana@uruku.bo", rol="admin")
    r = client.post("/admin/content/week/plan", headers={"Authorization": f"Bearer {t}"}, json={"week_start": "2020-01-06"})
    assert r.status_code == 400 and r.json()["detail"] == "Esa semana ya pasó"
    r = client.post("/admin/content/week/plan", headers={"Authorization": f"Bearer {t}"}, json={"week_start": "2026-11-03"})
    assert r.status_code == 400 and "lunes" in r.json()["detail"]
    r = client.post("/admin/content/week/plan", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 200 and set(r.json()) == {"week_start", "created", "slots_left_empty", "tasks_created"}


# ── cambiar fotos ────────────────────────────────────────────────────────────

def test_cambiar_fotos_quita_busca_reemplazo_y_si_no_hay_da_409(repo, crepo):
    from fastapi import HTTPException
    suscriptor(repo, crepo, "com-1", fotos=7)
    plan(repo, crepo)
    p = next(iter(crepo.pieces.values()))
    activas = crepo.list_sources(p["id"])
    assert len(activas) == 7
    r = sel.cambiar_fotos(crepo, p, [activas[0]["position"], activas[1]["position"]], HOY)
    assert r == {"quitadas": 2, "agregadas": 0}                  # no hay más fotos que sirvan
    assert len(crepo.list_sources(p["id"])) == 5
    with pytest.raises(HTTPException) as e:
        sel.cambiar_fotos(crepo, p, [crepo.list_sources(p["id"])[0]["position"], crepo.list_sources(p["id"])[1]["position"]], HOY)
    assert e.value.status_code == 409 and e.value.detail["codigo"] == "no_more_photos"
    assert any(t["kind"] == "photo_refresh" for t in crepo.tasks.values())
    assert len(crepo.list_sources(p["id"])) == 5                 # no se quitó nada
