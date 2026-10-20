"""E1 · Ingesta segura (docs/grupos-por-comercio.md §6.2 y §10.1, criterios 1-5, 8, 9 y 10).

  1. Un número de URUKU que escribe 1-a-1 con un código válido NO queda autorizado.
  2. El explorador sigue publicando por código (regresión).
  3. La charla 1-a-1 («hola, ¿cuánto sale el plan?») no crea una novedad.
  4. Foto 1-a-1 de un número conocido: confiable -> aprobada; si no, a la cola.
  5. La foto de un desconocido se guarda en el disco PRIVADO, nunca bajo /fotos.
  8. La retención borra el archivo y deja la fila.
  9. `clean_own_numbers` sin --apply no cambia nada; con --apply da de baja, sin DELETE.
 10. Un mensaje de grupo con `participant` LID y `participantAlt` aprende el par.
"""
import os
from io import BytesIO
from pathlib import Path

import pytest

from app.core import config as cfg
from app.core.config import settings
from app.services import ingest, wa_received

PROPIO = "59175314737"          # el Anfitrión
EXPLORADOR = "59170000555"
DESCONOCIDO = "59171234567"
GRUPO = "120363111222333@g.us"


def _jpeg() -> bytes:
    from PIL import Image

    b = BytesIO()
    Image.new("RGB", (60, 40), (200, 30, 30)).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture
def propios(monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_propios", f"{PROPIO},{EXPLORADOR}", raising=False)
    monkeypatch.setattr(settings, "wa_numeros_explorador", EXPLORADOR, raising=False)
    monkeypatch.setattr(settings, "wa_contacto_explorador", "59170000999", raising=False)
    cfg._numeros_propios.cache_clear()
    yield
    cfg._numeros_propios.cache_clear()


@pytest.fixture
def waha_con_foto(monkeypatch):
    """WAHA 'entrega' una foto real cuando el backend la pide."""
    from app.services import wa_media

    monkeypatch.setattr(wa_media, "descargar_media", lambda url: _jpeg() if url else None)


def _ev(wamid, body="", numero=DESCONOCIDO, tipo="text", media=False, data=None):
    p = {"id": wamid, "from": f"{numero}@c.us", "fromMe": False, "body": body, "type": tipo,
         "timestamp": 1760880000}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha:3000/api/files/x.jpg", "mimetype": "image/jpeg"})
    if data:
        p["_data"] = data
    return {"event": "message", "session": "default", "payload": p}


def _ev_grupo(wamid, body="", participante=f"{DESCONOCIDO}@c.us", grupo=GRUPO, media=False, data=None):
    key = {"participant": participante}
    key.update(data or {})
    p = {"id": wamid, "from": grupo, "fromMe": False, "body": body,
         "type": "image" if media else "text", "timestamp": 1760880000, "_data": {"key": key}}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha:3000/api/files/g.jpg", "mimetype": "image/jpeg"})
    return {"event": "message", "session": "default", "payload": p}


# ── 1 · El bug del número propio ─────────────────────────────────────────────
def test_1_un_propio_1a1_con_codigo_valido_no_queda_autorizado(repo, propios):
    c = repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", codigo="K7M2", activo=True)

    res = ingest.handle_message(_ev("p1", "URUKU-K7M2 oferta taladro Bs 300", numero=PROPIO), repo)

    assert res["publicada"] is False
    assert repo.comercio_numeros == []                      # no se autorizó nada
    assert repo.publicaciones == []
    fila = repo.wa_inbox["p1"]
    assert fila["resultado"] == "ignorada"
    assert "1-a-1 de un número de URUKU" in fila["motivo"]
    assert not c.get("wa_jid")                              # tampoco se le ató el jid


def test_1_un_propio_que_llega_como_lid_conocido_tampoco(repo, propios):
    """El Samsung llegó como LID el 11/9. Con el par aprendido, se lo reconoce."""
    repo.upsert_wa_lid("160138577080406@lid", PROPIO, "message")
    repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", codigo="K7M2", activo=True)
    ev = _ev("p1b", "URUKU-K7M2 hola", numero="x")
    ev["payload"]["from"] = "160138577080406@lid"

    res = ingest.handle_message(ev, repo)

    assert res["publicada"] is False
    assert repo.comercio_numeros == []
    assert "número de URUKU" in repo.wa_inbox["p1b"]["motivo"]


def test_1_un_propio_que_llega_como_lid_con_el_numero_al_lado(repo, propios):
    repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", codigo="K7M2", activo=True)
    ev = _ev("p1c", "URUKU-K7M2", numero="x",
             data={"key": {"remoteJidAlt": f"{PROPIO}@s.whatsapp.net"}})
    ev["payload"]["from"] = "160138577080406@lid"

    ingest.handle_message(ev, repo)

    assert repo.comercio_numeros == []
    assert repo.wa_inbox["p1c"]["resultado"] == "ignorada"


def test_1_el_doble_candado_de_identificar_comercio(repo, propios):
    """Aunque alguien llame a `_identificar_comercio` directo, un propio no se autoriza."""
    from app.models.whatsapp import WahaMessagePayload

    repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", codigo="K7M2", activo=True)
    payload = WahaMessagePayload.model_validate(_ev("p1d", "URUKU-K7M2", numero=PROPIO)["payload"])

    comercio, origen, _ = ingest._identificar_comercio(repo, payload)

    assert comercio is None and origen == "desconocido"
    assert repo.comercio_numeros == []


def test_1_un_numero_comun_con_codigo_sigue_identificandose(repo, propios):
    """No se rompió lo que anda: un número que NO es nuestro, con código, se identifica."""
    repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", codigo="K7M2", activo=True)

    res = ingest.handle_message(_ev("p1e", "URUKU-K7M2 zapatillas Bs 250"), repo)

    assert res["estado"] == "pendiente"
    assert [n["numero"] for n in repo.comercio_numeros] == [DESCONOCIDO]


# ── 2 · El explorador (regresión) ────────────────────────────────────────────
def test_2_el_explorador_sigue_publicando_por_codigo(repo, propios):
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2", activo=True)
    repo.seed_comercio(id="com-b", slug="local-b", nombre="B", codigo="BBB3", activo=True)

    ingest.handle_message(_ev("e1", "URUKU-AAA2 remera Bs 90", numero=EXPLORADOR), repo)
    ingest.handle_message(_ev("e2", "URUKU-BBB3 campera Bs 300", numero=EXPLORADOR), repo)

    assert [p["comercio_id"] for p in repo.publicaciones] == ["com-a", "com-b"]
    assert all(p["origen"] == "explorador" and p["estado"] == "pendiente" for p in repo.publicaciones)
    assert repo.comercio_numeros == []                     # y no se queda pegado a ninguno


# ── 3 · La charla 1-a-1 no publica ───────────────────────────────────────────
@pytest.fixture
def conocido(repo):
    return repo.seed_comercio(id="com-k", slug="kiosco", nombre="Kiosco", whatsapp=DESCONOCIDO,
                              activo=True)


def test_3_una_charla_1a1_no_crea_una_novedad(repo, conocido):
    res = ingest.handle_message(_ev("c1", "hola, ¿cuánto sale el plan?"), repo)

    assert res["publicada"] is False
    assert repo.publicaciones == []
    fila = repo.wa_inbox["c1"]
    assert fila["resultado"] == "ignorada"
    assert "charla 1-a-1" in fila["motivo"]
    assert fila["comercio_id"] == "com-k"


@pytest.mark.parametrize("cuerpo", ["Zapatillas Bs 250", "oferta de la semana",
                                    "mirá https://www.tiktok.com/@kiosco/video/123",
                                    # El precio sin «Bs», como lo escribe el comerciante.
                                    "zapatillas 250", "jean tiro alto 180"])
def test_3_con_precio_oferta_o_tiktok_publica_como_siempre(repo, conocido, cuerpo):
    res = ingest.handle_message(_ev("c2", cuerpo), repo)
    assert res["estado"] == "pendiente"
    assert len(repo.publicaciones) == 1


def test_3_una_pregunta_con_numero_sigue_siendo_charla(repo, conocido):
    """«¿cuánto sale el plan de 140?» trae un número pero es una pregunta."""
    res = ingest.handle_message(_ev("c4", "hola, ¿cuánto sale el plan de 140?"), repo)
    assert res["publicada"] is False
    assert repo.publicaciones == []


def test_3_con_ubicacion_actualiza_como_siempre(repo, conocido):
    ev = _ev("c3", "", tipo="location")
    ev["payload"]["location"] = {"latitude": -22.7361, "longitude": -64.3433}
    res = ingest.handle_message(ev, repo)
    assert res["ubicacion_actualizada"] is True


def test_3_un_texto_suelto_en_un_grupo_sigue_siendo_una_novedad(repo):
    """La regla es del chat 1-a-1: en el grupo del comercio el texto sí puede ser una novedad."""
    repo.seed_comercio(id="com-g", slug="g", nombre="G", whatsapp="59170000007", activo=True)
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "t")

    res = ingest.handle_message(
        _ev_grupo("g1", "llegó la colección nueva", participante="59170000007@c.us"), repo)

    assert res["estado"] == "pendiente"


# ── 4 · Foto 1-a-1 de un conocido ────────────────────────────────────────────
def test_4_foto_de_un_conocido_confiable_se_aprueba(repo, waha_con_foto):
    repo.seed_comercio(id="com-k", slug="kiosco", nombre="Kiosco", whatsapp=DESCONOCIDO,
                       activo=True, confiable=True)
    # El número lo autorizó una persona: sólo así hereda `confiable`.
    repo.agregar_numero_comercio("com-k", DESCONOCIDO, "dueño", "admin@x.com")

    res = ingest.handle_message(_ev("f1", "", tipo="image", media=True), repo)

    assert res["estado"] == "aprobado"
    assert repo.publicaciones[0]["imagen_url"]


def test_4_foto_de_un_conocido_no_confiable_va_a_la_cola(repo, conocido, waha_con_foto):
    res = ingest.handle_message(_ev("f2", "", tipo="image", media=True), repo)
    assert res["estado"] == "pendiente"
    assert repo.publicaciones[0]["imagen_url"]


# ── 5 · La foto de un desconocido se guarda, en privado ──────────────────────
def test_5_foto_de_un_desconocido_queda_en_el_disco_privado(repo, waha_con_foto, client):
    res = ingest.handle_message(_ev("d1", "precio 120", tipo="image", media=True), repo)

    assert res["publicada"] is False
    fila = repo.wa_inbox["d1"]
    assert fila["resultado"] == "sin_comercio"
    ruta = fila["media_path"]
    assert ruta and not ruta.startswith(("/", ".."))
    archivo = Path(settings.wa_received_dir) / ruta
    assert archivo.is_file() and archivo.read_bytes()[:2] == b"\xff\xd8"          # JPEG
    # NUNCA bajo el directorio público de fotos.
    assert Path(settings.fotos_dir).resolve() not in archivo.resolve().parents
    assert not (Path(settings.fotos_dir) / ruta).exists()
    # Y por /fotos no se puede pedir.
    for candidata in (ruta, Path(ruta).name):
        assert client.get(f"/fotos/{candidata}").status_code == 404
    assert repo.comercio_numeros == [] and repo.publicaciones == []


def test_5_foto_de_un_grupo_sin_atar_tambien_se_guarda(repo, waha_con_foto):
    res = ingest.handle_message(_ev_grupo("d2", "", media=True), repo)
    assert res["publicada"] is False
    fila = repo.wa_inbox["d2"]
    assert fila["resultado"] == "sin_comercio" and fila["media_path"]


def test_5_si_no_se_puede_bajar_la_foto_el_mensaje_igual_queda(repo, monkeypatch):
    from app.services import wa_media

    monkeypatch.setattr(wa_media, "descargar_media", lambda url: None)
    ingest.handle_message(_ev("d3", "", tipo="image", media=True), repo)
    fila = repo.wa_inbox["d3"]
    assert fila["resultado"] == "sin_comercio" and not fila.get("media_path")


def test_5_lo_que_no_es_una_imagen_no_se_guarda(repo, monkeypatch):
    from app.services import wa_media

    monkeypatch.setattr(wa_media, "descargar_media", lambda url: b"esto no es una foto")
    ingest.handle_message(_ev("d4", "", tipo="image", media=True), repo)
    assert not repo.wa_inbox["d4"].get("media_path")


def test_5_el_id_del_mensaje_no_escapa_del_directorio(repo, waha_con_foto):
    ev = _ev("../../etc/passwd@c.us_X", "", tipo="image", media=True)
    ingest.handle_message(ev, repo)
    ruta = repo.wa_inbox["../../etc/passwd@c.us_X"]["media_path"]
    raiz = Path(settings.wa_received_dir).resolve()
    assert raiz in (raiz / ruta).resolve().parents
    assert ".." not in ruta


def test_5_un_media_path_adulterado_no_se_lee():
    assert wa_received.read("../../../../etc/passwd") is None
    assert wa_received.safe_path("/etc/passwd") is None
    assert wa_received.safe_path("") is None


# ── 8 · Retención ────────────────────────────────────────────────────────────
def test_8_la_retencion_borra_el_archivo_y_deja_la_fila(repo, waha_con_foto, monkeypatch):
    ingest.handle_message(_ev("r1", "", tipo="image", media=True), repo)
    ruta = repo.wa_inbox["r1"]["media_path"]
    archivo = Path(settings.wa_received_dir) / ruta
    assert archivo.is_file()

    # Con 30 días, una foto de hoy se queda.
    assert wa_received.purge_expired(repo, 30) == 0
    assert archivo.is_file() and not repo.wa_inbox["r1"].get("media_purged_at")

    monkeypatch.setattr(settings, "wa_received_retention_days", 0)
    assert wa_received.purge_expired(repo) == 1

    assert not archivo.exists()
    fila = repo.wa_inbox["r1"]
    assert fila["media_purged_at"] and fila["media_path"] == ruta      # la fila queda
    assert wa_received.purge_expired(repo) == 0                          # no se repite


def test_8_purgar_con_el_archivo_ya_borrado_no_falla(repo, waha_con_foto):
    ingest.handle_message(_ev("r2", "", tipo="image", media=True), repo)
    os.remove(Path(settings.wa_received_dir) / repo.wa_inbox["r2"]["media_path"])
    assert wa_received.purge_expired(repo, 0) == 1
    assert repo.wa_inbox["r2"]["media_purged_at"]


# ── 9 · Limpieza única del bug P1 ────────────────────────────────────────────
def test_9_clean_own_numbers_lista_y_solo_con_apply_da_de_baja(repo, propios, capsys):
    from app.scripts import clean_own_numbers

    repo.seed_comercio(id="com-s", slug="sol", nombre="Sol", activo=True)
    repo.agregar_numero_comercio("com-s", PROPIO, "se identificó con el código", "ingest-codigo")
    repo.agregar_numero_comercio("com-s", DESCONOCIDO, "dueño", "admin@x.com")      # uno legítimo
    repo.insert_wa_inbox({"wa_message_id": "viejo", "wa_jid": f"{PROPIO}@c.us", "phone": PROPIO,
                          "raw": {}})
    repo.marcar_wa_inbox("viejo", "publicada", "oferta", "com-s")

    assert clean_own_numbers.main([], repo) == 0
    salida = capsys.readouterr().out
    assert PROPIO in salida and "viejo" in salida and "SIN --apply" in salida
    assert all(n["activo"] for n in repo.comercio_numeros)                       # no cambió nada

    assert clean_own_numbers.main(["--apply"], repo) == 0
    estado = {n["numero"]: n["activo"] for n in repo.comercio_numeros}
    assert estado == {PROPIO: False, DESCONOCIDO: True}                          # baja lógica, sin DELETE
    assert len(repo.comercio_numeros) == 2


def test_9_el_script_no_tiene_delete():
    fuente = (Path(__file__).resolve().parents[1] / "app/scripts/clean_own_numbers.py").read_text(encoding="utf-8")
    codigo = "\n".join(l for l in fuente.splitlines() if not l.strip().startswith("#"))
    assert ".delete(" not in codigo


# ── 10 · Aprender el LID ─────────────────────────────────────────────────────
def test_10_un_mensaje_de_grupo_con_lid_y_alt_crea_el_mapa(repo):
    ingest.handle_message(
        _ev_grupo("l1", "hola", participante="160138577080406@lid",
                  data={"participantAlt": f"{DESCONOCIDO}@s.whatsapp.net"}), repo)

    assert repo.wa_lid_map["160138577080406@lid"]["phone"] == DESCONOCIDO
    assert repo.wa_lid_map["160138577080406@lid"]["source"] == "message"


def test_10_actualiza_si_el_par_ya_estaba(repo):
    for n in range(2):
        ingest.handle_message(
            _ev_grupo(f"l2-{n}", "hola", participante="160138577080406@lid",
                      data={"participantAlt": f"{DESCONOCIDO}@s.whatsapp.net"}), repo)
    assert len(repo.wa_lid_map) == 1


def test_10_un_1a1_con_lid_y_remote_jid_alt_tambien(repo):
    ev = _ev("l3", "hola", numero="x", data={"key": {"remoteJidAlt": f"{DESCONOCIDO}@s.whatsapp.net"}})
    ev["payload"]["from"] = "160138577080406@lid"
    ingest.handle_message(ev, repo)
    assert repo.wa_lid_map["160138577080406@lid"]["phone"] == DESCONOCIDO


def test_10_sin_numero_al_lado_no_se_inventa_nada(repo):
    ingest.handle_message(_ev_grupo("l4", "hola", participante="160138577080406@lid"), repo)
    assert repo.wa_lid_map == {}


def test_10_un_fallo_al_aprender_no_tumba_la_ingesta(repo, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("base caída")

    monkeypatch.setattr(repo, "upsert_wa_lid", roto)
    res = ingest.handle_message(
        _ev_grupo("l5", "hola", participante="160138577080406@lid",
                  data={"participantAlt": f"{DESCONOCIDO}@s.whatsapp.net"}), repo)
    assert res["captured"] is True
