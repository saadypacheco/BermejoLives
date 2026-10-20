"""Correcciones de la revisión del E1 (code review B1-B2, seguridad S1-S10).

  B1  el reproceso de «Es de…» no fusiona con lo que ya existía
  B2  «foto y después texto» en 1-a-1 sigue fusionándose (la regla de charla no lo rompe)
  S1  un LID sin número no autoriza por código ni ata el wa_jid
  S2  el reproceso es idempotente (liberar es condicional)
  S6  «hola URUKU-2345» es charla: el código no es un precio
  S7  clean_own_numbers también suelta comercios.wa_jid de números propios
  S8  retención por lotes, tope de fotos por remitente, vaciado de eventos y LID viejos
  S10 upsert_wa_lid no pisa `admin` ni reactiva filas de baja
"""
import re
from io import BytesIO
from pathlib import Path

import pytest

from app.core import config as cfg
from app.core.config import settings
from app.services import ingest, wa_received

RAIZ = Path(__file__).resolve().parents[2]
PROPIO = "59175314737"
EXPLORADOR = "59170000555"
NUM = "59171234567"
OTRO_NUM = "59172222222"
GRUPO = "120363111222333@g.us"
LID = "160138577080406@lid"
COM = "11111111-1111-4111-8111-111111111111"


def _jpeg() -> bytes:
    from PIL import Image

    b = BytesIO()
    Image.new("RGB", (60, 40), (200, 30, 30)).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    from app.services import wa_media

    monkeypatch.setattr(wa_media, "descargar_media", lambda url: _jpeg() if url and "gone" not in url else None)
    monkeypatch.setattr(settings, "wa_numeros_propios", f"{PROPIO},{EXPLORADOR}", raising=False)
    monkeypatch.setattr(settings, "wa_numeros_explorador", EXPLORADOR, raising=False)
    cfg._numeros_propios.cache_clear()
    yield
    cfg._numeros_propios.cache_clear()


def _ev(wamid, body="", numero=NUM, media=False, ts=1760880000, de=None, data=None):
    p = {"id": wamid, "from": de or f"{numero}@c.us", "fromMe": False, "body": body,
         "type": "image" if media else "text", "timestamp": ts}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha:3000/api/files/x.jpg", "mimetype": "image/jpeg"})
    if data:
        p["_data"] = data
    return {"event": "message", "session": "default", "payload": p}


def _comercio(repo, **kw):
    kw.setdefault("activo", True)
    return repo.seed_comercio(id=COM, slug="kiosco", nombre="Kiosco Ana", **kw)


def _reprocesar(repo, numero=NUM, by="admin@x.com"):
    filas = [repo.get_wa_inbox(f["wa_message_id"])
             for f in repo.list_wa_inbox_sin_dueno(30, numero, True)]
    return wa_received.reprocess(repo, filas, by)


# ── B1 · el reproceso no fusiona con lo que ya existía ───────────────────────
def test_b1_el_reproceso_no_toca_una_publicacion_existente(repo):
    _comercio(repo)
    # Hay una publicación de HOY con foto y sin texto (candidata perfecta a «fusionarse»).
    previa = repo.insert_publicacion({"comercio_id": COM, "tipo": "oferta", "descripcion": None,
                                      "imagen_url": "/fotos/kiosco/hoy.jpg", "estado": "aprobado",
                                      "wa_message_id": "hoy"})
    ingest.handle_message(_ev("v1", "zapatillas Bs 250"), repo)      # sin dueño: de hace semanas
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")

    cuenta = _reprocesar(repo)

    assert cuenta == {"reprocessed": 1, "published": 1, "ignored": 0}
    assert repo.publicaciones[0]["descripcion"] is None                 # la existente, intacta
    assert repo.publicaciones[0]["imagen_url"] == "/fotos/kiosco/hoy.jpg"
    assert repo.publicaciones[0]["estado"] == "aprobado" and repo.publicaciones[0]["id"] == previa["id"]
    assert len(repo.publicaciones) == 2
    assert repo.publicaciones[1]["descripcion"] == "zapatillas Bs 250"
    assert repo.publicaciones[1]["estado"] == "pendiente"


def test_b1_foto_y_texto_cercanos_de_la_misma_tanda_se_juntan(repo):
    _comercio(repo)
    ingest.handle_message(_ev("v1", "", media=True, ts=1760880000), repo)
    ingest.handle_message(_ev("v2", "zapatillas Bs 250", ts=1760880060), repo)   # 1 min después
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")

    cuenta = _reprocesar(repo)

    assert cuenta["reprocessed"] == 2 and cuenta["published"] == 2
    assert len(repo.publicaciones) == 1
    pub = repo.publicaciones[0]
    assert pub["imagen_url"] and pub["descripcion"] == "zapatillas Bs 250" and pub["estado"] == "pendiente"


def test_b1_si_los_mensajes_originales_estan_lejos_no_se_juntan(repo):
    _comercio(repo)
    ingest.handle_message(_ev("v1", "", media=True, ts=1760880000), repo)
    ingest.handle_message(_ev("v2", "zapatillas Bs 250", ts=1760880000 + 3 * 3600), repo)
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")

    _reprocesar(repo)

    assert len(repo.publicaciones) == 2


def test_b1_un_texto_viejo_sin_precio_despues_de_una_foto_lejana_es_charla(repo):
    _comercio(repo)
    ingest.handle_message(_ev("v1", "", media=True, ts=1760880000), repo)
    ingest.handle_message(_ev("v2", "hola buen día", ts=1760880000 + 3 * 3600), repo)
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")

    cuenta = _reprocesar(repo)

    assert cuenta["published"] == 1 and cuenta["ignored"] == 1
    assert repo.publicaciones[0]["descripcion"] is None


# ── B2 · «foto y después texto» en 1-a-1 ─────────────────────────────────────
def test_b2_foto_y_despues_texto_sin_precio_se_fusionan(repo):
    _comercio(repo, whatsapp=NUM)
    ingest.handle_message(_ev("f1", "", media=True), repo)
    assert repo.publicaciones[0]["descripcion"] is None

    res = ingest.handle_message(_ev("f2", "zapatillas urbanas de cuero"), repo)

    assert res.get("fusionada") is True
    assert len(repo.publicaciones) == 1
    assert repo.publicaciones[0]["descripcion"] == "zapatillas urbanas de cuero"
    assert repo.publicaciones[0]["imagen_url"]
    assert repo.wa_inbox["f2"]["resultado"] == "publicada"


def test_b2_texto_suelto_sin_foto_previa_sigue_siendo_charla(repo):
    _comercio(repo, whatsapp=NUM)
    res = ingest.handle_message(_ev("f3", "zapatillas urbanas de cuero"), repo)
    assert res["publicada"] is False and repo.publicaciones == []
    assert "charla" in repo.wa_inbox["f3"]["motivo"]


def test_b2_si_la_foto_ya_tiene_texto_el_siguiente_texto_es_charla(repo):
    _comercio(repo, whatsapp=NUM)
    ingest.handle_message(_ev("f4", "zapatillas Bs 250", media=True), repo)
    res = ingest.handle_message(_ev("f5", "gracias"), repo)
    assert res["publicada"] is False
    assert len(repo.publicaciones) == 1


# ── S1 · LID sin número ──────────────────────────────────────────────────────
def test_s1_un_lid_sin_numero_con_codigo_no_autoriza_ni_ata_el_jid(repo):
    c = repo.seed_comercio(id=COM, slug="sol", nombre="Sol", codigo="K7M2", activo=True)

    res = ingest.handle_message(_ev("l1", "URUKU-K7M2 zapatillas Bs 250", media=True, de=LID), repo)

    assert res["publicada"] is False
    assert repo.comercio_numeros == [] and repo.publicaciones == []
    assert not c.get("wa_jid")
    fila = repo.wa_inbox["l1"]
    assert fila["resultado"] == "sin_comercio" and fila["media_path"]        # la foto, a salvo (P2)


def test_s1_con_el_numero_al_lado_si_se_identifica_y_ata_el_telefono_no_el_lid(repo):
    c = repo.seed_comercio(id=COM, slug="sol", nombre="Sol", codigo="K7M2", activo=True)

    res = ingest.handle_message(
        _ev("l2", "URUKU-K7M2 zapatillas Bs 250", de=LID,
            data={"key": {"remoteJidAlt": f"{NUM}@s.whatsapp.net"}}), repo)

    assert res["estado"] == "pendiente"
    assert [n["numero"] for n in repo.comercio_numeros] == [NUM]
    assert c["wa_jid"] == f"{NUM}@c.us"


def test_s1_con_el_par_ya_aprendido_se_identifica_por_el_numero(repo):
    repo.upsert_wa_lid(LID, NUM, "event")
    repo.seed_comercio(id=COM, slug="sol", nombre="Sol", codigo="K7M2", activo=True)
    res = ingest.handle_message(_ev("l3", "URUKU-K7M2 zapatillas Bs 250", de=LID), repo)
    assert res["estado"] == "pendiente" and repo.comercio_numeros[0]["numero"] == NUM


def test_s1_un_lid_sin_numero_y_sin_codigo_tambien_queda_sin_dueno(repo):
    res = ingest.handle_message(_ev("l4", "hola", de=LID), repo)
    assert res["publicada"] is False and repo.wa_inbox["l4"]["resultado"] == "sin_comercio"


def test_s1_el_explorador_como_lid_mapeado_se_reconoce(repo):
    repo.upsert_wa_lid(LID, EXPLORADOR, "message")
    repo.seed_comercio(id=COM, slug="sol", nombre="Sol", codigo="K7M2", activo=True)
    ingest.handle_message(_ev("l5", "URUKU-K7M2 remera Bs 90", de=LID), repo)
    assert repo.publicaciones[0]["origen"] == "explorador"


# ── S2 · reproceso idempotente ───────────────────────────────────────────────
def test_s2_liberar_solo_libera_filas_sin_comercio(repo):
    ingest.handle_message(_ev("x1", "zapatillas Bs 250"), repo)
    assert repo.liberar_wa_inbox("x1", "a@x.com") is True
    assert repo.liberar_wa_inbox("x1", "b@x.com") is False          # ya está liberada (sin resultado)
    repo.marcar_wa_inbox("x1", "publicada")
    assert repo.liberar_wa_inbox("x1", "b@x.com") is False          # ya resuelta
    assert repo.liberar_wa_inbox("nadie", "b@x.com") is False


def test_s2_dos_es_de_con_las_mismas_filas_no_duplican(repo):
    _comercio(repo)
    ingest.handle_message(_ev("x1", "", media=True), repo)
    ingest.handle_message(_ev("x2", "zapatillas Bs 250", ts=1760880030), repo)
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")
    filas = [repo.get_wa_inbox(i) for i in ("x1", "x2")]               # las dos pestañas vieron lo mismo

    primera = wa_received.reprocess(repo, filas, "uno@x.com")
    segunda = wa_received.reprocess(repo, filas, "dos@x.com")

    assert primera["reprocessed"] == 2 and segunda == {"reprocessed": 0, "published": 0, "ignored": 0}
    assert len(repo.publicaciones) == 1                                 # ni duplicada ni re-fusionada
    assert repo.wa_inbox["x1"]["assigned_by"] == "uno@x.com"


def test_s2_si_otro_la_libero_antes_no_se_reprocesa(repo, monkeypatch):
    _comercio(repo)
    ingest.handle_message(_ev("x1", "zapatillas Bs 250"), repo)
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")
    monkeypatch.setattr(repo, "liberar_wa_inbox", lambda *a: False)    # perdió la carrera
    assert _reprocesar(repo)["reprocessed"] == 0
    assert repo.publicaciones == []


def test_s2_si_la_ingesta_se_corta_la_fila_vuelve_a_sin_dueno(repo, monkeypatch):
    _comercio(repo)
    ingest.handle_message(_ev("x1", "zapatillas Bs 250"), repo)
    repo.agregar_numero_comercio(COM, NUM, None, "admin@x.com")

    def roto(*a, **k):
        raise RuntimeError("base caída")

    monkeypatch.setattr(ingest, "handle_message", roto)
    cuenta = _reprocesar(repo)
    assert cuenta["reprocessed"] == 1 and cuenta["ignored"] == 1
    assert repo.wa_inbox["x1"]["resultado"] == "sin_comercio"           # no quedó sin resultado


# ── S6 · el código no es un precio ───────────────────────────────────────────
def test_s6_hola_mas_codigo_es_charla(repo):
    _comercio(repo, whatsapp=NUM)
    res = ingest.handle_message(_ev("c1", "hola URUKU-2345"), repo)
    assert res["publicada"] is False and repo.publicaciones == []
    assert "charla" in repo.wa_inbox["c1"]["motivo"]


def test_s6_un_precio_de_verdad_con_el_codigo_publica(repo):
    _comercio(repo, whatsapp=NUM)
    res = ingest.handle_message(_ev("c2", "URUKU-2345 zapatillas 250"), repo)
    assert res["estado"] == "pendiente"


# ── S7 · clean_own_numbers suelta el wa_jid ──────────────────────────────────
def test_s7_clean_own_numbers_lista_y_suelta_el_wa_jid_de_numeros_propios(repo, capsys):
    from app.scripts import clean_own_numbers

    repo.seed_comercio(id="c-1", slug="a", nombre="A", activo=True, wa_jid=f"{PROPIO}@c.us")
    repo.seed_comercio(id="c-2", slug="b", nombre="B", activo=True, wa_jid=f"{EXPLORADOR}@s.whatsapp.net")
    repo.seed_comercio(id="c-3", slug="c", nombre="C", activo=True, wa_jid=f"{NUM}@c.us")   # legítimo

    assert clean_own_numbers.main([], repo) == 0
    salida = capsys.readouterr().out
    assert f"{PROPIO}@c.us" in salida and f"{EXPLORADOR}@s.whatsapp.net" in salida and f"{NUM}@c.us" not in salida
    assert repo.comercios["c-1"]["wa_jid"] and repo.comercios["c-2"]["wa_jid"]      # sin --apply, nada cambia

    assert clean_own_numbers.main(["--apply"], repo) == 0
    assert repo.comercios["c-1"]["wa_jid"] is None and repo.comercios["c-2"]["wa_jid"] is None
    assert repo.comercios["c-3"]["wa_jid"] == f"{NUM}@c.us"


# ── S8 · retención ───────────────────────────────────────────────────────────
def test_s8_la_retencion_purga_por_lotes_hasta_vaciar(repo, monkeypatch):
    monkeypatch.setattr(wa_received, "_TAMANO_LOTE", 2)
    for n in range(7):
        ingest.handle_message(_ev(f"r{n}", "", media=True, numero=f"5917000{n:04d}"), repo)
    assert all(repo.wa_inbox[f"r{n}"]["media_path"] for n in range(7))

    assert wa_received.purge_expired(repo, 0) == 7
    assert all(repo.wa_inbox[f"r{n}"]["media_purged_at"] for n in range(7))


def test_s8_un_media_path_invalido_se_marca_purgado_y_no_traba_el_resto(repo, monkeypatch):
    monkeypatch.setattr(wa_received, "_TAMANO_LOTE", 2)
    ingest.handle_message(_ev("r1", "", media=True), repo)
    ingest.handle_message(_ev("r2", "", media=True, numero=OTRO_NUM), repo)
    ingest.handle_message(_ev("r3", "", media=True, numero="59173333333"), repo)
    repo.wa_inbox["r1"]["media_path"] = "../../../etc/passwd"

    wa_received.purge_expired(repo, 0)

    assert all(repo.wa_inbox[i]["media_purged_at"] for i in ("r1", "r2", "r3"))


def test_s8_tope_de_fotos_por_remitente_desconocido_por_dia(repo, monkeypatch):
    monkeypatch.setattr(settings, "wa_received_max_per_sender_per_day", 2)
    for n in range(4):
        ingest.handle_message(_ev(f"t{n}", "", media=True), repo)
    guardadas = [i for i in ("t0", "t1", "t2", "t3") if repo.wa_inbox[i].get("media_path")]
    assert guardadas == ["t0", "t1"]
    for i in ("t2", "t3"):
        assert repo.wa_inbox[i]["resultado"] == "sin_comercio"            # se registra igual
        assert "tope diario" in repo.wa_inbox[i]["motivo"]
    # Otro remitente tiene su propio cupo.
    ingest.handle_message(_ev("t9", "", media=True, numero=OTRO_NUM), repo)
    assert repo.wa_inbox["t9"]["media_path"]


def test_s8_el_tope_no_le_aplica_al_explorador(repo, monkeypatch):
    monkeypatch.setattr(settings, "wa_received_max_per_sender_per_day", 1)
    for n in range(3):
        ingest.handle_message(_ev(f"e{n}", "sin código", media=True, numero=EXPLORADOR), repo)
    assert all(repo.wa_inbox[f"e{n}"]["media_path"] for n in range(3))


def test_s8_el_tope_diario_tiene_default_30():
    assert cfg.Settings.model_fields["wa_received_max_per_sender_per_day"].default == 30
    assert cfg.Settings.model_fields["wa_events_retention_days"].default == 90


def test_s8_se_vacian_los_eventos_y_los_lid_inactivos_viejos_y_las_filas_quedan(repo):
    viejo, nuevo = "2020-01-01T00:00:00+00:00", None
    for clave, creado in (("k1", viejo), ("k2", viejo), ("k3", nuevo)):
        repo.insert_wa_group_event({"dedupe_key": clave, "event": "group.v2.join", "group_jid": GRUPO,
                                    "participants": [{"id": f"{NUM}@c.us"}], "raw": {"tel": NUM}})
        if creado:
            repo.wa_group_events[clave]["created_at"] = creado
    repo.wa_lid_map["1@lid"] = {"lid": "1@lid", "phone": NUM, "source": "event", "activo": False,
                                "last_seen_at": viejo}
    repo.wa_lid_map["2@lid"] = {"lid": "2@lid", "phone": NUM, "source": "event", "activo": True,
                                "last_seen_at": viejo}                       # activo: no se toca
    repo.wa_lid_map["3@lid"] = {"lid": "3@lid", "phone": NUM, "source": "event", "activo": False,
                                "last_seen_at": "2999-01-01T00:00:00+00:00"}  # reciente: no se toca

    assert wa_received.purge_events(repo, 90) == {"events": 2, "lids": 1}

    assert len(repo.wa_group_events) == 3                                   # ninguna fila se borra
    for k in ("k1", "k2"):
        e = repo.wa_group_events[k]
        assert e["raw"] == {} and e["participants"] is None and e["purged_at"]
    assert repo.wa_group_events["k3"]["raw"] == {"tel": NUM}
    assert repo.wa_lid_map["1@lid"]["phone"] == ""
    assert repo.wa_lid_map["2@lid"]["phone"] == NUM and repo.wa_lid_map["3@lid"]["phone"] == NUM
    assert wa_received.purge_events(repo, 90) == {"events": 0, "lids": 0}   # idempotente


def test_s8_el_loop_diario_tambien_vacia_los_eventos():
    fuente = (Path(__file__).resolve().parents[1] / "app/main.py").read_text(encoding="utf-8")
    assert "wa_received.purge_events" in fuente and "wa_received.purge_expired" in fuente


# ── S10 · upsert_wa_lid ──────────────────────────────────────────────────────
def test_s10_no_pisa_admin_ni_reactiva_una_baja(repo):
    repo.wa_lid_map["a@lid"] = {"lid": "a@lid", "phone": "59170000001", "source": "admin", "activo": True}
    repo.wa_lid_map["b@lid"] = {"lid": "b@lid", "phone": "59170000002", "source": "message", "activo": False}
    repo.wa_lid_map["c@lid"] = {"lid": "c@lid", "phone": "59170000003", "source": "message", "activo": True}

    for lid in ("a@lid", "b@lid", "c@lid"):
        repo.upsert_wa_lid(lid, NUM, "event")

    assert repo.wa_lid_map["a@lid"]["phone"] == "59170000001" and repo.wa_lid_map["a@lid"]["source"] == "admin"
    assert repo.wa_lid_map["b@lid"]["phone"] == "59170000002" and repo.wa_lid_map["b@lid"]["activo"] is False
    assert repo.wa_lid_map["c@lid"]["phone"] == NUM and repo.wa_lid_map["c@lid"]["source"] == "event"
    assert repo.get_wa_lid("b@lid") is None


def test_s10_el_repo_real_inserta_sin_pisar_y_solo_actualiza_filas_activas_no_admin():
    llamadas = []

    class Q:
        def __init__(self, tabla):
            self.tabla = tabla

        def upsert(self, row, **kw):
            llamadas.append(("upsert", kw))
            return self

        def update(self, patch):
            llamadas.append(("update", sorted(patch)))
            return self

        def eq(self, c, v):
            llamadas.append(("eq", c, v))
            return self

        def neq(self, c, v):
            llamadas.append(("neq", c, v))
            return self

        def execute(self):
            return None

    class Db:
        def table(self, nombre):
            return Q(nombre)

    from app.db.repository import SupabaseRepo

    SupabaseRepo(Db()).upsert_wa_lid(LID, NUM, "event")

    assert ("upsert", {"on_conflict": "lid", "ignore_duplicates": True}) in llamadas
    assert ("eq", "activo", True) in llamadas and ("neq", "source", "admin") in llamadas
    # El update no reescribe `activo`.
    assert ("update", ["last_seen_at", "phone", "source"]) in llamadas


# ── Migración 0168 ───────────────────────────────────────────────────────────
SQL = "0168_wa_retention.sql"


def test_0168_identica_en_las_dos_carpetas_y_numero_unico():
    assert (RAIZ / "supabase/migrations" / SQL).read_bytes() == (RAIZ / "selfhost/postgres-init" / SQL).read_bytes()
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        nums = [p.name[:4] for p in (RAIZ / carpeta).glob("*.sql")]
        assert nums.count("0168") == 1, carpeta


def test_0168_sin_borrado_fisico_sin_grants_a_anon_ni_la_palabra_del_codigo():
    sql = (RAIZ / "supabase/migrations" / SQL).read_text(encoding="utf-8")
    sin_comentarios = "\n".join(l.split("--")[0] for l in sql.splitlines())
    assert not re.search(r"\bdelete\s+from\b|\bdrop\b|\btruncate\b", sin_comentarios, re.I)
    assert not re.search(r"\bgrant\b[^;]*\b(anon|authenticated)\b", sin_comentarios, re.I)
    assert not re.search(r"\bcodigo\b", sql, re.I)
    assert "add column if not exists purged_at" in sin_comentarios
    assert "do $chk$" in sin_comentarios and "notify pgrst" in sin_comentarios
    assert re.search(r"^\s*begin;", sin_comentarios, re.M) and re.search(r"^\s*commit;", sin_comentarios, re.M)
