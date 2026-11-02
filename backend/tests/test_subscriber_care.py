"""Cuidado de suscriptores: el job diario, la bienvenida, el reporte, la renovación y la API de tareas."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core import auth
from app.core.config import settings
from app.services import cargas, content_storage, subscriber_care as care
from tests.content_helpers import autorizar, banco, comercio, h, hoy, pieza


def d(n=0):
    return (hoy() + timedelta(days=n)).isoformat()


def ahora():
    return datetime.now(timezone.utc)


def pago(repo, pid, cid, hace_dias=0):
    repo.pagos[pid] = {"id": pid, "comercio_id": cid, "estado": "confirmado",
                       "created_at": (ahora() - timedelta(days=hace_dias)).isoformat()}


def tareas(crepo, cid="com-1", kind=None):
    return sorted((t["kind"], t["due_on"], t["status"]) for t in crepo.tasks.values()
                  if t["comercio_id"] == cid and (kind is None or t["kind"] == kind))


def job(repo, crepo):
    return care.daily_job(repo, crepo)


# ── bienvenida ───────────────────────────────────────────────────────────────

def test_la_bienvenida_arranca_solo_con_el_primer_pago(repo, crepo):
    comercio(repo, "nuevo")
    pago(repo, "p1", "nuevo", hace_dias=1)
    comercio(repo, "renueva")
    pago(repo, "p0", "renueva", hace_dias=31)
    pago(repo, "p2", "renueva", hace_dias=1)                       # una renovación no dispara nada
    comercio(repo, "viejo")
    pago(repo, "p3", "viejo", hace_dias=10)                        # fuera de los 3 días
    r = job(repo, crepo)
    assert r["welcomes"] == 1
    assert tareas(crepo, "nuevo") == sorted([("welcome", d(0), "open"), ("profile_check", d(0), "open"),
                                              ("first_offer", d(1), "open"), ("photo_session", d(2), "open"),
                                              ("first_piece", d(5), "open"), ("week1_checkin", d(7), "open")])
    assert not tareas(crepo, "renueva", "welcome") and not tareas(crepo, "viejo", "welcome")
    assert crepo.profiles["nuevo"]["onboarding_started_by"] == "auto:pago:p1" and crepo.profiles["nuevo"]["onboarding_started_at"]


def test_el_job_es_idempotente(repo, crepo):
    comercio(repo)
    pago(repo, "p1", "com-1")
    job(repo, crepo)
    antes = tareas(crepo)
    segundo = job(repo, crepo)
    assert tareas(crepo) == antes and segundo["welcomes"] == 0


def test_un_pago_pendiente_no_arranca_nada(repo, crepo):
    comercio(repo)
    pago(repo, "p1", "com-1")
    repo.pagos["p1"]["estado"] = "pendiente"
    assert job(repo, crepo)["welcomes"] == 0 and not crepo.tasks


@pytest.fixture
def token():
    return h(auth.make_token("ana@uruku.bo", roles=["x"], permisos=["pagos"]))


def test_arranque_manual_y_force(client, repo, crepo, token):
    comercio(repo, plan_cortesia=True, paga_hasta=None)
    r = client.post("/admin/subscribers/com-1/onboarding", headers=token)
    assert r.status_code == 200 and r.json()["created"] == 6 and r.json()["started_at"]
    assert crepo.profiles["com-1"]["onboarding_started_by"] == "ana@uruku.bo"
    dos = client.post("/admin/subscribers/com-1/onboarding", headers=token)
    assert dos.status_code == 409 and dos.json()["detail"].startswith("La bienvenida ya arrancó el ")
    forzado = client.post("/admin/subscribers/com-1/onboarding", headers=token, json={"force": True})
    assert forzado.status_code == 200 and forzado.json()["created"] == 0          # las tareas de hoy ya estaban
    assert len(tareas(crepo)) == 6


def test_arrancar_la_bienvenida_de_quien_no_es_suscriptor_es_404(client, repo, token):
    comercio(repo, plan="gratis")
    assert client.post("/admin/subscribers/com-1/onboarding", headers=token).json()["detail"] == "No es un suscriptor"
    assert client.get("/admin/subscribers/com-1", headers=token).status_code == 404
    assert client.post("/admin/subscribers/nada/onboarding", headers=token).status_code == 404


# ── cierres automáticos ──────────────────────────────────────────────────────

def test_las_tareas_automaticas_se_cierran_solas(repo, crepo):
    comercio(repo, portada_url="x", instagram_url="https://instagram.com/x", rubros={"nombre": "Vidriería", "slug": "vidrios"})
    autorizar(crepo, "com-1")
    for i in range(6):
        repo.comercio_fotos.append({"id": f"g{i}", "comercio_id": "com-1", "url": "x", "thumb_url": "x"})
    repo.usuarios["u"] = {"id": "u", "comercio_id": "com-1", "activo": True}
    repo.wa_grupos["g@g.us"] = {"comercio_id": "com-1"}
    care.iniciar_bienvenida(crepo, "com-1", "ana", hoy())
    banco(crepo, "com-1", 8)
    repo.publicaciones.append({"comercio_id": "com-1", "estado": "aprobado", "created_at": (ahora() + timedelta(minutes=1)).isoformat()})
    p = pieza(crepo, status="published")
    r = job(repo, crepo)
    assert r["closed"] == 4
    estados = {t["kind"]: t for t in crepo.tasks.values()}
    for k in ("profile_check", "first_offer", "photo_session", "first_piece"):
        assert estados[k]["status"] == "done" and estados[k]["auto_closed"] is True and estados[k]["done_by"] == "sistema", k
    assert estados["welcome"]["status"] == "open" and estados["week1_checkin"]["status"] == "open"
    assert p


def test_si_falta_algo_no_se_cierra(repo, crepo):
    comercio(repo)                                                   # sin portada, sin redes, sin autorización
    care.iniciar_bienvenida(crepo, "com-1", "ana", hoy())
    assert job(repo, crepo)["closed"] == 0


def test_el_checklist_marca_lo_que_falta_y_lo_que_no_se_pudo_leer(repo, crepo):
    comercio(repo, portada_url="x", horario=None, lat=None)
    autorizar(crepo, "com-1")
    ok = {i["key"]: i for i in care.checklist(repo, crepo, crepo.get_comercio_ficha("com-1"), crepo.current_consents()["com-1"])}
    assert [k for k, i in ok.items() if i["ok"]] == ["portada", "whatsapp", "rubro", "autorizacion"]
    assert all(i["auto"] for i in ok.values()) and len(ok) == 10
    repo.get_cuenta_comercio = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sin base"))
    roto = {i["key"]: i for i in care.checklist(repo, crepo, crepo.get_comercio_ficha("com-1"), None)}
    assert roto["cuenta"] == {"key": "cuenta", "label": "Cuenta de Mi comercio", "ok": False, "auto": False}
    assert roto["autorizacion"]["ok"] is False


# ── reporte, renovación, llamada ─────────────────────────────────────────────

def _vence_en(repo, dias):
    comercio(repo, paga_hasta=d(dias))


def test_el_reporte_sale_5_dias_antes_de_vencer_una_sola_vez(repo, crepo):
    _vence_en(repo, 6)
    assert job(repo, crepo)["tasks"] == 0 and not crepo.reports
    repo.comercios["com-1"]["paga_hasta"] = d(5)
    job(repo, crepo)
    job(repo, crepo)
    assert len(crepo.reports) == 1 and tareas(crepo, kind="monthly_report") == [("monthly_report", d(0), "open")]
    rep = next(iter(crepo.reports.values()))
    assert rep["period_end"] == d(0) and set(rep["data"]) == {"visits", "whatsapp", "directions", "calls", "from_social",
                                                              "terms", "pieces_published", "offers_approved"}
    t = next(iter(crepo.tasks.values()))
    assert t["report_id"] == rep["id"]


def test_los_datos_del_reporte_salen_de_los_leads_y_solo_de_ese_comercio(repo, crepo):
    c = comercio(repo)
    comercio(repo, "otro")
    hace = (ahora() - timedelta(days=2)).isoformat()
    for tipo, n in (("vista", 7), ("whatsapp", 3), ("mapa", 2), ("telefono", 1)):
        repo.leads += [{"comercio_id": "com-1", "tipo": tipo, "created_at": hace}] * n
    repo.leads += [{"comercio_id": "com-1", "tipo": "vista", "created_at": hace, "origen": o} for o in ("tt-x", "ig-x", "fb-x", "canal-x", "st-x", "otro-x")]
    repo.leads += [{"comercio_id": "otro", "tipo": "vista", "created_at": hace}] * 50
    repo.leads.append({"comercio_id": "com-1", "tipo": "vista", "created_at": (ahora() - timedelta(days=90)).isoformat()})   # fuera del ciclo
    repo.busqueda_comercios += [{"comercio_id": "com-1", "query": q} for q in ("vidrios", "vidrios", "espejos", "marcos")]
    repo.publicaciones.append({"comercio_id": "com-1", "estado": "aprobado", "created_at": ahora().isoformat()})
    p = pieza(crepo, status="published", published_at=ahora().isoformat())
    datos = care.datos_del_reporte(repo, crepo, crepo.get_comercio_ficha("com-1"), hoy() - timedelta(days=10), hoy())
    assert datos == {"visits": 13, "whatsapp": 3, "directions": 2, "calls": 1, "from_social": 5, "terms": ["vidrios", "espejos"],
                     "pieces_published": 1, "offers_approved": 1}
    assert c and p


def test_renovacion_vencido_y_llamada_en_su_dia(repo, crepo):
    _vence_en(repo, 2)
    job(repo, crepo)
    assert not tareas(crepo, kind="renewal_before")
    repo.comercios["com-1"]["paga_hasta"] = d(1)
    job(repo, crepo)
    assert tareas(crepo, kind="renewal_before") == [("renewal_before", d(0), "open")]
    for dias, esperado in ((-2, []), (-3, ["renewal_overdue"]), (-6, ["renewal_overdue"]), (-7, ["churn_call", "renewal_overdue"])):
        repo.comercios["com-1"]["paga_hasta"] = d(dias)
        crepo.tasks.clear()
        job(repo, crepo)
        ahora_ = sorted(k for k, _, _ in tareas(crepo) if k in ("renewal_overdue", "churn_call"))
        assert ahora_ == esperado, (dias, ahora_)
    assert ("renewal_overdue", d(-4), "open") in tareas(crepo) and ("churn_call", d(0), "open") in tareas(crepo)


def test_la_cortesia_no_renueva_ni_recibe_reporte(repo, crepo):
    comercio(repo, plan_cortesia=True, paga_hasta=d(1))
    job(repo, crepo)
    assert not crepo.tasks and not crepo.reports


def test_un_comercio_que_ya_pago_de_nuevo_no_recibe_el_aviso_de_atraso(repo, crepo):
    comercio(repo, paga_hasta=d(-4))
    job(repo, crepo)
    repo.comercios["com-1"]["paga_hasta"] = d(26)                    # pagó
    crepo.tasks.clear()
    job(repo, crepo)
    assert not crepo.tasks


def test_a_los_8_dias_sin_pago_saltea_las_piezas_que_no_salieron(repo, crepo):
    comercio(repo, paga_hasta=d(-8))
    autorizar(crepo, "com-1")
    en_cola = pieza(crepo, status="queued", dia=hoy() + timedelta(days=1))
    aprobada = pieza(crepo, status="approved", dia=hoy() + timedelta(days=2))
    crepo.insert_posts([{"piece_id": aprobada["id"], "network": n, "ref_tag": "x"} for n in ("tiktok", "instagram")])
    publicada = pieza(crepo, status="published", dia=hoy() - timedelta(days=3))
    r = job(repo, crepo)
    assert r["unpaid_skipped"] == 2
    for p in (en_cola, aprobada):
        assert crepo.pieces[p["id"]]["status"] == "skipped" and crepo.pieces[p["id"]]["skip_reason"] == "unpaid"
    assert {x["status"] for x in crepo.posts.values()} == {"skipped"}
    assert crepo.pieces[publicada["id"]]["status"] == "published"


def test_antes_de_los_8_dias_o_con_cortesia_no_saltea(repo, crepo):
    comercio(repo, paga_hasta=d(-7))
    p = pieza(crepo, status="queued")
    assert job(repo, crepo)["unpaid_skipped"] == 0 and crepo.pieces[p["id"]]["status"] == "queued"
    repo.comercios["com-1"].update({"paga_hasta": d(-30), "plan_cortesia": True})
    assert job(repo, crepo)["unpaid_skipped"] == 0


def test_libera_reclamos_vencidos_y_purga_archivos(repo, crepo):
    comercio(repo)
    a = banco(crepo, "com-1", 1)[0]
    crepo.update_asset(a["id"], {"activo": False, "deactivated_at": (ahora() - timedelta(days=31)).isoformat()})
    reciente = banco(crepo, "com-1", 1)[0]
    crepo.update_asset(reciente["id"], {"activo": False, "deactivated_at": (ahora() - timedelta(days=5)).isoformat()})
    content_storage.guardar("renders/2026-07/v/video.mp4", b"x")
    content_storage.guardar("renders/2026-07/v/cover.jpg", b"x")
    vieja = pieza(crepo, status="published", video_path="renders/2026-07/v/video.mp4", cover_path="renders/2026-07/v/cover.jpg",
                  published_at=(ahora() - timedelta(days=91)).isoformat())
    content_storage.guardar("renders/2026-10/w/video.mp4", b"x")
    fresca = pieza(crepo, dia=hoy() + timedelta(days=3), status="published", video_path="renders/2026-10/w/video.mp4",
                   published_at=(ahora() - timedelta(days=20)).isoformat())
    r = job(repo, crepo)
    assert r["purged"] == {"pieces": 1, "assets": 1}
    assert not content_storage.esta_en_disco(a["file_path"]) and crepo.assets[a["id"]]["file_purged_at"]
    assert content_storage.esta_en_disco(reciente["file_path"]) and not crepo.assets[reciente["id"]]["file_purged_at"]
    assert not content_storage.esta_en_disco("renders/2026-07/v/video.mp4") and crepo.pieces[vieja["id"]]["files_purged_at"]
    assert crepo.pieces[vieja["id"]]["status"] == "published"                    # la fila queda
    assert content_storage.esta_en_disco("renders/2026-10/w/video.mp4") and not crepo.pieces[fresca["id"]].get("files_purged_at")


def test_un_paso_que_falla_no_frena_a_los_otros(repo, crepo, monkeypatch):
    comercio(repo)
    pago(repo, "p1", "com-1")
    monkeypatch.setattr(care, "bienvenidas_automaticas", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    pieza(crepo, status="queued")
    repo.comercios["com-1"]["paga_hasta"] = d(-9)
    assert job(repo, crepo)["unpaid_skipped"] == 1


def test_daily_tick_una_vez_por_dia_y_despues_de_las_7(repo, crepo):
    bo = lambda h_: datetime(2026, 11, 3, h_, 0, tzinfo=cargas.BOLIVIA)
    assert care.daily_tick(repo, crepo, bo(6)) is None
    assert care.daily_tick(repo, crepo, bo(7)) is not None
    assert care.daily_tick(repo, crepo, bo(15)) is None
    assert care.daily_tick(repo, crepo, bo(7) + timedelta(days=1)) is not None
    settings.content_care_hour = 7


# ── la API de suscriptores ───────────────────────────────────────────────────

def test_permisos_de_la_api(client, repo):
    comercio(repo)
    assert client.get("/admin/subscribers").status_code == 401
    assert client.get("/admin/subscribers", headers=h(auth.make_token("m@u", rol="moderador"))).status_code == 403
    for permisos in (["pagos"], ["difusion"]):
        assert client.get("/admin/subscribers", headers=h(auth.make_token("a@u", roles=["x"], permisos=permisos))).status_code == 200


def test_lista_de_suscriptores_con_su_estado_y_filtros(client, repo, crepo, token):
    comercio(repo, "al-dia", nombre="Al Día")
    comercio(repo, "vence", nombre="Vence", paga_hasta=d(3))
    comercio(repo, "vencido", nombre="Vencido", paga_hasta=d(-3))
    comercio(repo, "muy-vencido", nombre="Muy Vencido", paga_hasta=d(-90))
    comercio(repo, "cortesia", nombre="Cortesía", plan_cortesia=True, paga_hasta=None)
    comercio(repo, "gratis", nombre="Gratis", plan="gratis")
    comercio(repo, "sc", nombre="De Santa Cruz", ciudad_id="ciu-santa-cruz")
    autorizar(crepo, "al-dia")
    crepo.insert_task({"comercio_id": "vence", "kind": "renewal_before", "due_on": d(0)})
    crepo.insert_task({"comercio_id": "vencido", "kind": "renewal_overdue", "due_on": d(-2)})
    r = client.get("/admin/subscribers", headers=token).json()
    por_id = {i["comercio_id"]: i for i in r["items"]}
    assert set(por_id) == {"al-dia", "vence", "vencido", "cortesia", "sc"} and r["total"] == 5
    assert [por_id[k]["subscription_state"] for k in ("al-dia", "vence", "vencido", "cortesia")] == ["al_dia", "por_vencer", "vencido", "cortesia"]
    assert por_id["vencido"]["in_grace"] is True and por_id["al-dia"]["in_grace"] is False
    a = por_id["al-dia"]
    assert a["plan"] == "publica" and a["social_consent"]["granted"] is True and por_id["vence"]["social_consent"]["granted"] is None
    assert a["pieces"]["quota"] == 2 and a["pieces"]["used"] == 0 and a["pieces"]["cycle_start"] and a["pieces"]["next_scheduled_for"] is None
    assert por_id["vence"]["tasks"] == {"due_today": 1, "overdue": 0} and por_id["vencido"]["tasks"] == {"due_today": 0, "overdue": 1}
    assert [i["comercio_id"] for i in r["items"]][:2] == ["vencido", "vence"]                    # primero los atrasados
    tareas_ = client.get("/admin/subscribers?filtro=tareas", headers=token).json()
    assert {i["comercio_id"] for i in tareas_["items"]} == {"vence", "vencido"}
    pv = client.get("/admin/subscribers?filtro=por_vencer", headers=token).json()
    assert {i["comercio_id"] for i in pv["items"]} == {"vence", "vencido"}
    assert {i["comercio_id"] for i in client.get("/admin/subscribers?ciudad=santa-cruz", headers=token).json()["items"]} == {"sc"}
    assert client.get("/admin/subscribers?ciudad=no-existe", headers=token).status_code == 400
    assert client.get("/admin/subscribers?filtro=raro", headers=token).status_code == 400


def test_tareas_por_cuando_con_el_mensaje_y_el_whatsapp(client, repo, crepo, token):
    comercio(repo, whatsapp="59170001234", nombre="Vidriería Pacheco")
    comercio(repo, "sin-wa", whatsapp="123", nombre="Kiosco")
    crepo.upsert_profile("com-1", {"contact_person": "Ana"})
    crepo.insert_task({"comercio_id": "com-1", "kind": "welcome", "due_on": d(0)})
    crepo.insert_task({"comercio_id": "com-1", "kind": "profile_check", "due_on": d(0)})
    crepo.insert_task({"comercio_id": "sin-wa", "kind": "photo_refresh", "due_on": d(-3)})
    crepo.insert_task({"comercio_id": "com-1", "kind": "churn_call", "due_on": d(4)})
    hoy_ = client.get("/admin/subscribers/tasks?cuando=hoy", headers=token).json()
    assert hoy_["total"] == 2
    w = next(t for t in hoy_["items"] if t["kind"] == "welcome")
    assert w["message_template"] == "M1" and w["whatsapp"] == "59170001234" and w["kind_label"] == "Bienvenida"
    assert w["message_text"].startswith("Hola Ana, soy el equipo de URUKU. Gracias por sumarte con Vidriería Pacheco.")
    assert w["needs_outcome"] is False and w["overdue"] is False and w["call_script"] is None
    chk = next(t for t in hoy_["items"] if t["kind"] == "profile_check")
    assert chk["message_text"] is None and chk["whatsapp"] is None and chk["message_template"] is None
    atras = client.get("/admin/subscribers/tasks?cuando=atrasadas", headers=token).json()["items"]
    assert len(atras) == 1 and atras[0]["overdue"] is True and atras[0]["whatsapp"] is None and atras[0]["message_text"]
    sem = client.get("/admin/subscribers/tasks?cuando=semana", headers=token).json()["items"]
    assert {t["kind"] for t in sem} == {"welcome", "profile_check", "churn_call"}
    ll = next(t for t in sem if t["kind"] == "churn_call")
    assert ll["call_script"] == ["¿Te sirvió URUKU este mes?", "¿Qué te faltó?", "¿Seguimos?"] and ll["needs_outcome"] and ll["message_text"] is None
    assert client.get("/admin/subscribers/tasks?cuando=nunca", headers=token).status_code == 400


def test_el_firmante_es_quien_abre_la_pantalla(client, repo, crepo):
    comercio(repo)
    crepo.insert_task({"comercio_id": "com-1", "kind": "welcome", "due_on": d(0)})
    tk = h(auth.make_token("l@u", roles=["x"], permisos=["pagos"], nombre="Luis Vega"))
    assert "soy Luis Vega de URUKU" in client.get("/admin/subscribers/tasks", headers=tk).json()["items"][0]["message_text"]


def test_marcar_hecha_guarda_el_texto_enviado(client, repo, crepo, token):
    comercio(repo, nombre="Vidriería Pacheco")
    t = crepo.insert_task({"comercio_id": "com-1", "kind": "welcome", "due_on": d(0)})
    r = client.post(f"/admin/subscribers/tasks/{t['id']}/done", headers=token, json={"sent": True})
    assert r.status_code == 200 and r.json()["status"] == "done" and r.json()["done_by"] == "ana@uruku.bo"
    assert crepo.tasks[t["id"]]["sent_text"].startswith("Hola Vidriería Pacheco, soy el equipo de URUKU.")
    assert crepo.tasks[t["id"]]["done_at"]
    assert client.post(f"/admin/subscribers/tasks/{t['id']}/done", headers=token, json={}).json()["detail"] == "La tarea ya está cerrada"
    assert client.post(f"/admin/subscribers/tasks/{t['id']}/skip", headers=token, json={}).status_code == 409


def test_las_tareas_con_resultado_lo_exigen(client, repo, crepo, token):
    comercio(repo)
    t = crepo.insert_task({"comercio_id": "com-1", "kind": "week1_checkin", "due_on": d(0)})
    r = client.post(f"/admin/subscribers/tasks/{t['id']}/done", headers=token, json={"sent": True})
    assert r.status_code == 400 and r.json()["detail"] == "Contá qué te dijo" and crepo.tasks[t["id"]]["status"] == "open"
    ok = client.post(f"/admin/subscribers/tasks/{t['id']}/done", headers=token, json={"sent": True, "outcome": "Le fue bien"})
    assert ok.status_code == 200 and ok.json()["outcome"] == "Le fue bien"
    llamada = crepo.insert_task({"comercio_id": "com-1", "kind": "churn_call", "due_on": d(0)})
    assert client.post(f"/admin/subscribers/tasks/{llamada['id']}/done", headers=token, json={"outcome": "  "}).status_code == 400
    assert client.post(f"/admin/subscribers/tasks/{llamada['id']}/done", headers=token, json={"outcome": "x" * 501}).status_code == 400


def test_saltear_una_tarea_y_tarea_inexistente(client, repo, crepo, token):
    comercio(repo)
    t = crepo.insert_task({"comercio_id": "com-1", "kind": "photo_refresh", "due_on": d(0)})
    r = client.post(f"/admin/subscribers/tasks/{t['id']}/skip", headers=token, json={"note": "no quiere"})
    assert r.status_code == 200 and r.json()["status"] == "skipped" and crepo.tasks[t["id"]]["note"] == "no quiere"
    assert client.post("/admin/subscribers/tasks/nada/skip", headers=token, json={}).status_code == 404
    assert client.post("/admin/subscribers/tasks/nada/done", headers=token, json={}).status_code == 404


def test_perfil_el_patch_no_borra_lo_que_no_viene(client, repo, crepo, token):
    comercio(repo)
    r = client.patch("/admin/subscribers/com-1/profile", headers=token, json={"contact_person": "Ana", "notes": "llama de noche"})
    assert r.json() == {"ok": True, "contact_person": "Ana", "notes": "llama de noche"}
    r = client.patch("/admin/subscribers/com-1/profile", headers=token, json={"contact_person": "Ana María"})
    assert r.json() == {"ok": True, "contact_person": "Ana María", "notes": "llama de noche"}      # `notes` intacta
    r = client.patch("/admin/subscribers/com-1/profile", headers=token, json={"notes": ""})
    assert r.json()["notes"] is None and r.json()["contact_person"] == "Ana María"
    assert client.patch("/admin/subscribers/com-1/profile", headers=token, json={}).status_code == 400
    assert client.patch("/admin/subscribers/com-1/profile", headers=token, json={"contact_person": "x" * 81}).status_code == 400
    assert client.patch("/admin/subscribers/com-1/profile", headers=token, json={"notes": "x" * 1001}).status_code == 400


def test_detalle_del_suscriptor(client, repo, crepo, token):
    comercio(repo, nombre="Vidriería Pacheco", portada_url="x")
    autorizar(crepo, "com-1")
    crepo.insert_task({"comercio_id": "com-1", "kind": "welcome", "due_on": d(0)})
    pieza(crepo, status="queued")
    crepo.insert_report({"comercio_id": "com-1", "period_start": d(-20), "period_end": d(-1), "data": {"visits": 9}})
    r = client.get("/admin/subscribers/com-1", headers=token).json()
    assert set(r) == {"summary", "profile_check", "tasks", "pieces", "last_report"}
    assert r["summary"]["nombre"] == "Vidriería Pacheco" and len(r["profile_check"]) == 10
    assert r["tasks"][0]["kind"] == "welcome" and r["pieces"][0]["status"] == "queued"
    assert r["last_report"]["data"] == {"visits": 9} and r["last_report"]["period_start"] == d(-20)
