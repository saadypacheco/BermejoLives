"""Leer la foto de origen (docs/fotos-estilo-uruku.md §8.1) y el caso de QA.

QA tiene la base de producción (las portadas apuntan a `https://api.uruku.bo/fotos/...`) pero sus archivos viven en el disco
de producción: con `FOTOS_LECTURA_REMOTA_BASES` puesto, la foto se lee por HTTPS (sólo leer) y lo que se arma se guarda en el
disco local de QA. Sin red real: `httpx.MockTransport`.
"""
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.services import fotos_origen as fo
from app.services.imagenes import guardar_foto_local

PROD = "https://api.uruku.bo/fotos"
QA = "https://api.encontralo.store/fotos"


def _jpeg(w=800, h=600, color="green") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


class Red:
    """Un transporte falso: anota los pedidos y contesta lo que se le pida."""

    def __init__(self, respuesta=None):
        self.pedidos: list[httpx.Request] = []
        self.respuesta = respuesta or (lambda req: httpx.Response(200, content=_jpeg()))

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.pedidos.append(request)
        return self.respuesta(request)


@pytest.fixture
def qa(monkeypatch):
    """QA: sirve fotos en su propio dominio y puede leer las de producción."""
    monkeypatch.setattr(settings, "fotos_public_base_url", QA)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)


@pytest.fixture
def red(monkeypatch):
    r = Red()
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(r))
    return r


# ───────────────────────────────────────── la validación pura de rutas (compartida con fotos_galeria)

def test_ruta_relativa_canonica_acepta_solo_dos_tramos_jpg_bajo_la_base():
    assert fo.ruta_relativa_canonica(f"{PROD}/local/a.jpg", PROD) == "local/a.jpg"
    assert fo.ruta_relativa_canonica(f"{PROD}/local/a.jpg", PROD + "/") == "local/a.jpg"
    assert fo.ruta_relativa_canonica(f"{PROD}/local/a.jpg", PROD, "local") == "local/a.jpg"
    assert fo.ruta_relativa_canonica(f"{PROD}/local/a.jpg", PROD, "otro") is None          # la carpeta tiene que ser el slug


@pytest.mark.parametrize("malo", [
    f"{PROD}/local/../a.jpg", f"{PROD}/../a.jpg", f"{PROD}/./a.jpg", f"{PROD}/local/%2e%2e/a.jpg", f"{PROD}/local/%2E/a.jpg",
    f"{PROD}/local/a.jpg?x=1", f"{PROD}/local/a.jpg#x", f"{PROD}/local\\a.jpg", f"{PROD}/local/a\x00.jpg",
    f"{PROD}/a/b/c.jpg", f"{PROD}/a.jpg", f"{PROD}//a.jpg", f"{PROD}/local/a.png", f"{PROD}/local/a.jpg/",
    f"{PROD}-evil/local/a.jpg", "https://otro.host/fotos/local/a.jpg", "http://api.uruku.bo/fotos/local/a.jpg", "", None,
])
def test_ruta_relativa_canonica_rechaza_lo_raro(malo):
    assert fo.ruta_relativa_canonica(malo, PROD) is None


def test_fotos_galeria_usa_la_misma_validacion(monkeypatch):
    """`_ruta_en_disco` y la lectura remota comparten `ruta_relativa_canonica`: no se separan nunca."""
    from app.services import fotos_galeria
    monkeypatch.setattr(settings, "fotos_public_base_url", PROD)
    assert fotos_galeria._ruta_en_disco(f"{PROD}/local/a.jpg") is not None
    for malo in (f"{PROD}/local/../a.jpg", f"{PROD}/local/%2e%2e/a.jpg", f"{PROD}/local/a.jpg?x", f"{PROD}/a/b/c.jpg"):
        assert fotos_galeria._ruta_en_disco(malo) is None
    assert fotos_galeria._ruta_en_disco(f"{PROD}/local/a.jpg", "otro") is None


# ───────────────────────────────────────── las bases del setting

def test_las_bases_http_o_mal_armadas_se_ignoran(monkeypatch):
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases",
                        "http://inseguro.test/fotos, https://ok.test/fotos/ ,https://x.test/f?k=1, ,https://u@h.test/f,https://ok.test/fotos")
    assert settings.fotos_lectura_remota_bases_list() == ["https://ok.test/fotos/"]
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "")
    assert settings.fotos_lectura_remota_bases_list() == []


def test_al_arrancar_se_avisa_de_las_bases_ignoradas(monkeypatch):
    avisos = []
    monkeypatch.setattr(fo.logger, "warning", lambda evento, **kw: avisos.append((evento, kw)))
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "http://inseguro.test/fotos," + PROD)
    fo.registrar_arranque()
    assert [a[0] for a in avisos] == ["fotos.lectura_remota_base_ignorada"]


def test_una_base_http_en_el_setting_no_hace_red(monkeypatch, red):
    monkeypatch.setattr(settings, "fotos_public_base_url", QA)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "http://api.uruku.bo/fotos")
    assert fo.leer_foto_origen("http://api.uruku.bo/fotos/local/a.jpg") is None
    assert red.pedidos == []


# ───────────────────────────────────────── leer_foto_origen

def test_setting_vacio_nunca_hay_red_ni_con_una_url_de_produccion(monkeypatch, red):
    monkeypatch.setattr(settings, "fotos_public_base_url", QA)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "")
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None
    assert red.pedidos == []


def test_base_no_listada_da_none_sin_red(qa, red):
    assert fo.leer_foto_origen("https://otro.host/fotos/local/a.jpg") is None
    assert fo.leer_foto_origen(f"{PROD}-evil/local/a.jpg") is None
    assert red.pedidos == []


@pytest.mark.parametrize("sufijo", ["local/../a.jpg", "local/%2e%2e/a.jpg", "local/%2E/a.jpg", "local/a.jpg?x=1",
                                    "local\\a.jpg", "a/b/c.jpg", "local/a.png", "a.jpg", "local/./a.jpg"])
def test_rutas_raras_dan_none_sin_red(qa, red, sufijo):
    assert fo.leer_foto_origen(f"{PROD}/{sufijo}") is None
    assert red.pedidos == []


def test_200_valido_devuelve_los_bytes(qa, red):
    datos = fo.leer_foto_origen(f"{PROD}/local/a.jpg")
    assert datos == _jpeg()
    assert len(red.pedidos) == 1 and red.pedidos[0].method == "GET"
    assert str(red.pedidos[0].url) == f"{PROD}/local/a.jpg"


def test_con_slug_la_carpeta_tiene_que_coincidir(qa, red):
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg", "otro") is None and red.pedidos == []
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg", "local") == _jpeg()


def test_una_redireccion_no_se_sigue(qa, monkeypatch):
    r = Red(lambda req: httpx.Response(302, headers={"location": "https://evil.test/x.jpg"}))
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(r))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None
    assert len(r.pedidos) == 1                                 # ni siquiera pidió el destino


@pytest.mark.parametrize("estado", [404, 500, 204, 301])
def test_solo_el_200_sirve(qa, monkeypatch, estado):
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(Red(lambda req: httpx.Response(estado, content=b"x"))))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None


def test_un_cuerpo_vacio_no_es_una_foto(qa, monkeypatch):
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(Red(lambda req: httpx.Response(200, content=b""))))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None


def test_si_content_length_pasa_el_tope_ni_la_baja(qa, monkeypatch):
    def grande(req):
        return httpx.Response(200, headers={"content-length": str(fo.MAX_BYTES_FOTO + 1)}, content=b"x")
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(Red(grande)))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None


def test_sin_content_length_se_corta_al_pasar_el_tope(qa, monkeypatch):
    monkeypatch.setattr(fo, "MAX_BYTES_FOTO", 1000)
    leidos = []

    def trozos():
        for _ in range(100):
            leidos.append(1)
            yield b"x" * 400

    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(Red(lambda req: httpx.Response(200, content=trozos()))))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None
    assert len(leidos) < 100                              # dejó de leer: no bajó los 40 KB


def test_justo_en_el_tope_pasa(qa, monkeypatch):
    monkeypatch.setattr(fo, "MAX_BYTES_FOTO", 1000)
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(Red(lambda req: httpx.Response(200, content=b"x" * 1000))))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") == b"x" * 1000


def test_error_de_red_o_timeout_dan_none_y_no_lanzan(qa, monkeypatch):
    def cae(req):
        raise httpx.ConnectTimeout("no conecta", request=req)
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(Red(cae)))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") is None


def test_el_cliente_no_sigue_redirecciones_y_usa_timeouts_cortos():
    c = fo._cliente()
    try:
        assert c.follow_redirects is False
        assert c.timeout.connect == 3.0 and c.timeout.read == 10.0
    finally:
        c.close()


def test_si_esta_en_el_disco_no_hay_red(qa, red):
    """Primero el disco: una foto que existe localmente no se baja de ningún lado."""
    guardar_foto_local("local/a.jpg", _jpeg(color="red"))
    assert fo.leer_foto_origen(f"{QA}/local/a.jpg") == _jpeg(color="red")
    assert red.pedidos == []


def test_en_el_disco_pero_de_otra_base_listada_se_baja_de_la_red(qa, red):
    """El archivo local con el mismo nombre NO cuenta si la URL es de la base de producción (otro `startswith`)."""
    guardar_foto_local("local/a.jpg", _jpeg(color="red"))
    assert fo.leer_foto_origen(f"{PROD}/local/a.jpg") == _jpeg()
    assert len(red.pedidos) == 1


def test_disco_pesado_de_nuestra_base_no_hace_red(qa, red, monkeypatch):
    monkeypatch.setattr(fo, "MAX_BYTES_FOTO", 50)
    guardar_foto_local("local/a.jpg", b"x" * 100)
    assert fo.leer_foto_origen(f"{QA}/local/a.jpg") is None          # nuestra base, demasiado grande: nada de red
    assert red.pedidos == []


def test_nunca_se_escribe_ni_se_borra_nada_remoto_ni_local(qa, red):
    fo.leer_foto_origen(f"{PROD}/local/a.jpg")
    assert [p.method for p in red.pedidos] == ["GET"]
    assert not (Path(settings.fotos_dir) / "local").exists()          # lo leído no se guarda


def test_se_registra_el_evento_sin_la_url_completa(qa, red, monkeypatch):
    eventos = []
    monkeypatch.setattr(fo.logger, "info", lambda evento, **kw: eventos.append((evento, kw)))
    fo.leer_foto_origen(f"{PROD}/local/a.jpg")
    assert eventos == [("fotos.lectura_remota", {"host": "api.uruku.bo", "resultado": "ok", "bytes": len(_jpeg())})]


# ───────────────────────────────────────── el caso de QA, de punta a punta

def _comercio_qa(repo, url_portada):
    repo.rubros["ferreteria"] = "rub-ferre"
    return repo.seed_comercio(id="com-qa", slug="local-qa", nombre="Ferretería QA", whatsapp="59170000077",
                              ciudad_id="ciu-1", rubro_id="rub-ferre", portada_url=url_portada, portada_pos=None)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_qa_la_portada_de_diseno_se_arma_con_una_portada_de_api_uruku_bo(client, repo, admin_token, qa, red):
    c = _comercio_qa(repo, f"{PROD}/local-qa/orig.jpg")
    r = client.post(f"/admin/comercio/{c['id']}/portada-diseno", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    url = r.json()["portada_diseno_propuesta_url"]
    # Lo armado se guarda en el disco LOCAL de QA, con la base de QA: nunca se escribe nada remoto.
    assert url.startswith(f"{QA}/local-qa/diseno-")
    assert (Path(settings.fotos_dir) / "local-qa" / url.rsplit("/", 1)[1]).is_file()
    assert [str(p.url) for p in red.pedidos] == [f"{PROD}/local-qa/orig.jpg"]
    assert [p.method for p in red.pedidos] == ["GET"]
    assert repo.comercios[c["id"]]["portada_diseno_propuesta_url"] == url


def test_qa_sin_la_variable_el_error_de_siempre(client, repo, admin_token, monkeypatch, red):
    monkeypatch.setattr(settings, "fotos_public_base_url", QA)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "")
    c = _comercio_qa(repo, f"{PROD}/local-qa/orig.jpg")
    r = client.post(f"/admin/comercio/{c['id']}/portada-diseno", headers=_h(admin_token))
    assert r.status_code == 400 and r.json()["detail"] == "No se pudo leer la foto de portada desde el servidor"
    assert red.pedidos == []


def test_qa_la_galeria_tambien_lee_de_produccion(client, repo, admin_token, qa, red):
    c = _comercio_qa(repo, f"{QA}/local-qa/otra.jpg")
    repo.comercio_fotos.append({"id": "f1", "comercio_id": c["id"], "url": f"{PROD}/local-qa/g1.jpg",
                                "thumb_url": None, "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    r = client.post(f"/admin/comercio/{c['id']}/fotos/f1/diseno", headers=_h(admin_token), json={"method": "free"})
    assert r.status_code == 200, r.text
    assert r.json()["proposal_url"].startswith(f"{QA}/local-qa/diseno-")
    assert [str(p.url) for p in red.pedidos] == [f"{PROD}/local-qa/g1.jpg"]


def test_en_produccion_con_el_setting_vacio_una_portada_local_anda_sin_red(client, repo, admin_token, monkeypatch, red):
    monkeypatch.setattr(settings, "fotos_public_base_url", PROD)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "")
    guardar_foto_local("local-qa/orig.jpg", _jpeg())
    c = _comercio_qa(repo, f"{PROD}/local-qa/orig.jpg")
    assert client.post(f"/admin/comercio/{c['id']}/portada-diseno", headers=_h(admin_token)).status_code == 200
    assert red.pedidos == []


# ───────────────────────────────────────── configuración y docs

def test_el_setting_viene_vacio_y_esta_en_el_env_example_y_en_deploy_qa():
    raiz = Path(__file__).resolve().parents[2]
    from app.core.config import Settings
    assert Settings.model_fields["fotos_lectura_remota_bases"].default == ""                 # producción: sin red
    env = (raiz / "backend/.env.example").read_text(encoding="utf-8")
    assert "\nFOTOS_LECTURA_REMOTA_BASES=\n" in env.replace("\r\n", "\n")                    # vacío
    qa = (raiz / "docs/deploy-qa.md").read_text(encoding="utf-8")
    assert "FOTOS_LECTURA_REMOTA_BASES=https://api.uruku.bo/fotos" in qa
