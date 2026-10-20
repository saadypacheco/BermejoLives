"""E1 · Eventos de grupo de WAHA, mapa LID y la migración 0159
(docs/grupos-por-comercio.md §6.3, §6.4 y §10.1, criterios 11, 12 y 13).

E1 sólo GUARDA los eventos (crudos, idempotentes) y aprende el par LID <-> número.
No actúa sobre ellos: eso es de las entregas siguientes, detrás de `WA_EVENTS_ACT`.
"""
import re
from pathlib import Path

import pytest
import structlog

from app.core.config import settings
from app.services import wa_events, wa_identity

RAIZ = Path(__file__).resolve().parents[2]
SQL = "0159_wa_inbox_media_and_group_events.sql"
GRUPO = "120363999888777@g.us"


def _join(participantes=None, grupo=GRUPO, ts=1760881200, evento="group.v2.join", **extra):
    participantes = participantes if participantes is not None else [
        {"id": "59175314737@c.us", "role": "superadmin"},
        {"id": "160138577080406@lid", "role": "participant"},
        {"id": "59164610187@c.us", "role": "participant"}]
    return {"event": evento, "session": "default", "payload": {
        "group": {"id": grupo, "subject": "URUKU · Ferretería Sol · Barrientos",
                  "participants": participantes},
        "timestamp": ts, "_data": {}, **extra}}


def _participants(tipo="join", ids=("59171234567@c.us",), grupo=GRUPO, ts=1760881300):
    return {"event": "group.v2.participants", "session": "default", "payload": {
        "group": {"id": grupo}, "type": tipo,
        "participants": [{"id": i, "role": "participant"} for i in ids], "timestamp": ts}}


# ── 11 · Se guardan crudos e idempotentes ────────────────────────────────────
def test_11_un_join_se_guarda_crudo_por_el_webhook(client, repo):
    r = client.post("/ingest/webhook", json=_join())
    assert r.status_code == 200 and r.json()["stored"] is True
    fila = next(iter(repo.wa_group_events.values()))
    assert fila["event"] == "group.v2.join" and fila["group_jid"] == GRUPO
    assert fila["result"] == "captured"
    assert [p["id"] for p in fila["participants"]][0] == "59175314737@c.us"
    assert fila["raw"]["payload"]["group"]["subject"].startswith("URUKU")      # el crudo entero


def test_11_el_mismo_evento_dos_veces_es_una_fila(client, repo):
    for _ in range(2):
        r = client.post("/ingest/webhook", json=_join())
        assert r.status_code == 200
    assert r.json()["duplicate"] is True
    assert len(repo.wa_group_events) == 1


def test_11_el_mismo_orden_de_participantes_da_la_misma_clave():
    a = wa_events.dedupe_key(wa_events.extraer(_join()))
    invertido = _join(participantes=list(reversed(_join()["payload"]["group"]["participants"])))
    assert wa_events.dedupe_key(wa_events.extraer(invertido)) == a


def test_11_eventos_distintos_son_filas_distintas(client, repo):
    client.post("/ingest/webhook", json=_join())
    client.post("/ingest/webhook", json=_join(ts=1760889999))                  # otro momento
    client.post("/ingest/webhook", json=_participants("join"))
    client.post("/ingest/webhook", json=_participants("leave"))
    client.post("/ingest/webhook", json=_participants("promote"))
    client.post("/ingest/webhook", json={"event": "group.v2.leave", "payload": {"id": GRUPO, "timestamp": 5}})
    client.post("/ingest/webhook", json={"event": "group.v2.update", "payload": {
        "group": {"id": GRUPO, "subject": "Otro nombre"}, "timestamp": 6}})
    assert len(repo.wa_group_events) == 7
    tipos = sorted((f["event"], f["change_type"]) for f in repo.wa_group_events.values())
    assert ("group.v2.participants", "promote") in tipos and ("group.v2.leave", "leave") in tipos


def test_11_tolera_formas_distintas_del_evento(repo):
    """La forma real de las comunidades se desconoce: el grupo y los participantes
    pueden venir sueltos en el payload o como texto."""
    plano = {"event": "group.v2.participants", "payload": {
        "id": GRUPO, "type": "join", "participants": ["59171234567@c.us"], "timestamp": 1}}
    assert wa_events.handle(plano, repo)["stored"] is True
    fila = next(iter(repo.wa_group_events.values()))
    assert fila["group_jid"] == GRUPO and fila["participants"] == [{"id": "59171234567@c.us"}]
    sin_nada = {"event": "group.v2.update", "payload": {}}
    assert wa_events.handle(sin_nada, repo)["stored"] is True               # igual queda guardado


def test_11_no_actua_con_wa_events_act_apagado(client, repo):
    """Nada de atar grupos, ni comunidades, ni tareas: sólo guardar."""
    assert settings.wa_events_act is False
    repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", whatsapp="59171234567", activo=True)
    client.post("/ingest/webhook", json=_participants("join"))
    assert repo.wa_grupos == {} and repo.comercio_numeros == [] and repo.publicaciones == []


def test_11_los_eventos_pasan_por_la_firma(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "secreto")
    assert client.post("/ingest/webhook", json=_join()).status_code == 401


def test_11_los_eventos_aprenden_el_lid_si_traen_el_numero(client, repo):
    participantes = [{"id": "160138577080406@lid", "role": "participant",
                      "phoneNumber": "59171234567@c.us"},
                     {"id": "999000111222333@lid", "role": "participant"}]       # éste no trae nada
    client.post("/ingest/webhook", json=_join(participantes))
    assert repo.wa_lid_map["160138577080406@lid"] == {
        **repo.wa_lid_map["160138577080406@lid"], "phone": "59171234567", "source": "event"}
    assert "999000111222333@lid" not in repo.wa_lid_map


def test_11_un_fallo_al_guardar_se_reintenta_no_se_traga(client, repo, monkeypatch):
    """Si la base falla, el webhook responde error (WAHA reintenta); no 200 mudo."""
    def roto(row):
        raise RuntimeError("base caída")

    monkeypatch.setattr(repo, "insert_wa_group_event", roto)
    with pytest.raises(RuntimeError):
        client.post("/ingest/webhook", json=_join())


# ── 12 · Un evento desconocido: 200 y log ────────────────────────────────────
def test_12_un_evento_desconocido_da_200_y_deja_rastro(client, repo):
    with structlog.testing.capture_logs() as logs:
        r = client.post("/ingest/webhook", json={"event": "presence.update", "payload": {"x": 1}})
    assert r.status_code == 200 and r.json()["ignored"] == "presence.update"
    assert any(l["event"] == "webhook.evento_ignorado" and l["evento"] == "presence.update" for l in logs)
    assert repo.wa_group_events == {}


def test_12_session_status_sigue_andando(client):
    r = client.post("/ingest/webhook", json={"event": "session.status", "payload": {"status": "WORKING"}})
    assert r.json()["handled"] == "session.status"


# ── LID: resolver ────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _cupo():
    wa_identity.reset_quota()
    yield
    wa_identity.reset_quota()


def test_resolver_un_c_us_es_el_numero(repo):
    assert wa_identity.resolve(repo, "59171234567@c.us") == "59171234567"
    assert wa_identity.resolve(repo, {"id": "59171234567@s.whatsapp.net"}) == "59171234567"


def test_resolver_un_objeto_con_el_numero_al_lado(repo):
    assert wa_identity.resolve(repo, {"id": "160138577080406@lid", "phoneNumber": "59171234567@c.us"}) == "59171234567"


def test_resolver_un_lid_usa_el_mapa_local(repo):
    repo.upsert_wa_lid("160138577080406@lid", "59171234567", "message")
    assert wa_identity.resolve(repo, "160138577080406@lid") == "59171234567"
    assert wa_identity.resolve(repo, "999@lid") is None


def test_resolver_no_consulta_a_waha_si_esta_apagado(repo, monkeypatch):
    import httpx

    monkeypatch.setattr(httpx, "get", lambda *a, **k: pytest.fail("no debe consultar a WAHA"))
    assert settings.wa_lid_lookup is False
    assert wa_identity.resolve(repo, "160138577080406@lid") is None


class _Resp:
    def __init__(self, data):
        self._d = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._d


def test_resolver_con_lookup_consulta_a_waha_en_solo_lectura_y_guarda(repo, monkeypatch):
    import httpx

    llamadas = []

    def get(url, **k):
        llamadas.append(url)
        return _Resp({"lid": "160138577080406@lid", "pn": "59171234567@c.us"})

    monkeypatch.setattr(settings, "wa_lid_lookup", True)
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("WAHA no escribe"))

    assert wa_identity.resolve(repo, "160138577080406@lid") == "59171234567"
    assert llamadas[0].endswith("/api/default/lids/160138577080406")
    assert repo.wa_lid_map["160138577080406@lid"]["source"] == "waha_api"
    # La segunda vez sale del mapa local, sin ir a WAHA.
    assert wa_identity.resolve(repo, "160138577080406@lid") == "59171234567"
    assert len(llamadas) == 1


def test_resolver_el_lookup_tiene_tope_por_hora(repo, monkeypatch):
    import httpx

    n = {"c": 0}

    def get(url, **k):
        n["c"] += 1
        return _Resp({"pn": None})

    monkeypatch.setattr(settings, "wa_lid_lookup", True)
    monkeypatch.setattr(settings, "wa_lid_lookup_max_per_hour", 3)
    monkeypatch.setattr(httpx, "get", get)
    for i in range(10):
        assert wa_identity.resolve(repo, f"1601385770804{i:02d}@lid") is None
    assert n["c"] == 3


def test_resolver_un_fallo_de_waha_no_lanza(repo, monkeypatch):
    import httpx

    def get(url, **k):
        raise httpx.ConnectError("sin red")

    monkeypatch.setattr(settings, "wa_lid_lookup", True)
    monkeypatch.setattr(httpx, "get", get)
    assert wa_identity.resolve(repo, "160138577080406@lid") is None


def test_propio_incluye_el_lid_mapeado(repo, monkeypatch):
    from app.core import config as cfg

    monkeypatch.setattr(settings, "wa_numeros_propios", "59175314737", raising=False)
    cfg._numeros_propios.cache_clear()
    repo.upsert_wa_lid("160138577080406@lid", "59175314737", "message")
    assert wa_identity.is_own(repo, "59175314737")
    assert wa_identity.is_own(repo, "160138577080406@lid")
    assert not wa_identity.is_own(repo, "999@lid")
    assert not wa_identity.is_own(repo, None)
    cfg._numeros_propios.cache_clear()


# ── 13 · La migración 0159 ───────────────────────────────────────────────────
def _sql() -> str:
    return (RAIZ / "supabase/migrations" / SQL).read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return "\n".join(l.split("--")[0] for l in sql.splitlines())


def test_13_la_migracion_es_identica_en_las_dos_carpetas():
    a = (RAIZ / "supabase/migrations" / SQL).read_bytes()
    b = (RAIZ / "selfhost/postgres-init" / SQL).read_bytes()
    assert a == b


def test_13_el_numero_de_la_migracion_no_choca():
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        nums = [p.name[:4] for p in (RAIZ / carpeta).glob("*.sql")]
        assert nums.count("0159") == 1, carpeta


def test_13_anon_no_tiene_acceso_a_las_tablas_nuevas():
    sql = _sin_comentarios(_sql())
    assert not re.search(r"\bgrant\b[^;]*\b(anon|authenticated)\b", sql, re.I)
    assert re.search(r"revoke all on public\.wa_group_events, public\.wa_lid_map from public, anon, authenticated", sql)
    assert re.search(r"grant all on public\.wa_group_events, public\.wa_lid_map to service_role", sql)
    for t in ("wa_group_events", "wa_lid_map"):
        assert re.search(rf"alter table public\.{t}\s+enable row level security", sql)
    assert "do $chk$" in sql and "notify pgrst, 'reload schema'" in sql


def test_13_sin_borrado_fisico_ni_la_palabra_del_codigo_del_comercio():
    sql = _sql()
    assert not re.search(r"\bdelete\s+from\b|\bdrop\b|\btruncate\b", _sin_comentarios(sql), re.I)
    # La busca test_ninguna_vista_ni_funcion_publica_expone_codigo, comentarios incluidos.
    assert not re.search(r"\bcodigo\b", sql, re.I)


def test_13_la_migracion_es_idempotente_y_transaccional():
    sql = _sin_comentarios(_sql())
    assert sql.count("add column if not exists") == 4
    assert not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"create index(?! if not exists)", sql)
    assert re.search(r"^\s*begin;", sql, re.M) and re.search(r"^\s*commit;", sql, re.M)


def test_13_las_columnas_de_la_spec_estan():
    sql = _sql()
    for col in ("media_path", "media_purged_at", "assigned_by", "assigned_at"):
        assert f"public.wa_inbox add column if not exists {col}" in sql
    assert "dedupe_key   text not null unique" in sql
    assert "check (lid like '%@lid')" in sql
    assert "source in ('message', 'event', 'waha_api', 'admin')" in sql


# ── Compose y variables ──────────────────────────────────────────────────────
@pytest.mark.parametrize("archivo", ["docker-compose.prod.yml", "infra/docker-compose.yml"])
def test_el_compose_suscribe_los_eventos_de_grupo(archivo):
    txt = (RAIZ / archivo).read_text(encoding="utf-8")
    linea = next(l for l in txt.splitlines() if "WHATSAPP_HOOK_EVENTS=" in l)
    eventos = set(linea.split("=", 1)[1].strip().split(","))
    assert {"message", "message.any", "session.status", "group.v2.join", "group.v2.leave",
            "group.v2.participants", "group.v2.update"} <= eventos
    assert "wa_received:/data/wa_received" in txt


def test_el_volumen_privado_no_esta_bajo_el_de_fotos():
    txt = (RAIZ / "docker-compose.prod.yml").read_text(encoding="utf-8")
    assert "comercio_fotos:/data/fotos" in txt and "wa_received:/data/wa_received" in txt
    from app.core.config import Settings
    assert Settings.model_fields["wa_received_dir"].default == "/data/wa_received"
    assert Settings.model_fields["wa_events_act"].default is False
    assert Settings.model_fields["wa_lid_lookup"].default is False
    assert Settings.model_fields["wa_received_retention_days"].default == 30
