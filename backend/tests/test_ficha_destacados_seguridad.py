"""Seguridad de «Lo que suma» y de las subidas de archivos.

- Enlaces peligrosos (`javascript:`, `usuario@dominio`) en sitio_web, redes y
  como_llegar, por cada vía que los guarda.
- El canal de WhatsApp sólo puede ser de WhatsApp; sin IP ni usuario.
- Carpeta del catálogo por id, carrera de subidas, huérfanos y límite por hora.
- Tope global al cuerpo (LimiteCuerpoMiddleware) y cabeceras de /fotos/.
"""
import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.core import auth
from app.core.config import settings
from app.core.limite_cuerpo import HOLGURA, TOPE_POR_DEFECTO, tope_para
from app.main import app
from app.services import enlaces
from app.services import ficha_catalogo as catalogo_svc
from tests.conftest import comercio_token
from tests.test_campo import _foto_test

MB = 1024 * 1024


def _pdf(tam: int = 2048) -> bytes:
    return b"%PDF-1.4\n" + b"0" * (tam - 9)


def _hc(cid="com-f"):
    return {"Authorization": f"Bearer {comercio_token(comercio_id=cid)}"}


def _ha(email="agente@bermejolive.com", ciudad="bermejo"):
    return {"Authorization": f"Bearer {auth.make_agente_token(email, ciudad)}"}


def _subir(client, url, headers, data=None):
    data = _pdf() if data is None else data
    return client.post(url, headers=headers, files={"archivo": ("c.pdf", data, "application/pdf")})


def _archivos(cid: str) -> list[str]:
    c = Path(settings.fotos_dir) / "catalogos" / cid
    return sorted(p.name for p in c.glob("*")) if c.exists() else []


def _archivo_de(url: str) -> Path:
    return Path(settings.fotos_dir) / url.split("/fotos/", 1)[1]


def _todo_el_disco() -> list[str]:
    raiz = Path(settings.fotos_dir)
    return sorted(str(p.relative_to(raiz)) for p in raiz.rglob("*") if p.is_file()) if raiz.exists() else []


@pytest.fixture
def comercio(repo):
    return repo.seed_comercio(id="com-f", slug="tienda-f", nombre="Tienda F", whatsapp="59170001111",
                              ciudad_id="ciu-1", cargado_por="agente@bermejolive.com")


# ═════════════════════════════════════════════════════════════════════════════
# Enlaces peligrosos: sitio_web, redes y como_llegar (van al href de la ficha)
# ═════════════════════════════════════════════════════════════════════════════
CAMPOS_RED = ["sitio_web", "facebook_url", "instagram_url", "tiktok_url"]
PELIGROSOS = ["javascript:alert(1)", "JaVaScRiPt:alert(document.cookie)", " javascript:alert(1)",
              "data:text/html;base64,PHNjcmlwdD4=", "vbscript:msgbox(1)", "file:///etc/passwd",
              "ftp://x.com/a", "https:evil.com", "https://uruku.bo@evil.com", "http://user:pass@evil.com/x",
              "https://a.com/\tx", "http://[::1", "https://" + "a" * 600 + ".com"]
LEGITIMOS = ["@mitienda", "mitienda.com", "instagram.com/mitienda", "https://instagram.com/mitienda",
             "HTTP://MITIENDA.COM/Catalogo", "www.mitienda.com/a?b=c#d"]


def _vias_de_edicion(client, admin_token):
    """(nombre, función(campo, valor) -> respuesta) por cada vía que guarda redes."""
    admin = {"Authorization": f"Bearer {admin_token}"}
    return [
        ("comerciante", lambda c, v: client.put("/comercio/perfil", headers=_hc(), json={c: v})),
        ("agente", lambda c, v: client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={c: v})),
        ("admin", lambda c, v: client.put("/admin/comercio/com-f", headers=admin, json={c: v})),
    ]


@pytest.mark.parametrize("campo", CAMPOS_RED)
@pytest.mark.parametrize("valor", PELIGROSOS)
def test_redes_con_esquema_peligroso_o_usuario_se_rechazan_por_cada_via(client, repo, comercio, admin_token, campo, valor):
    for via, llamar in _vias_de_edicion(client, admin_token):
        r = llamar(campo, valor)
        assert r.status_code == 400, (via, campo, valor, r.status_code, r.text)
        assert "Invalid" not in r.json()["detail"], (via, r.json()["detail"])
        assert campo not in repo.comercios["com-f"], (via, campo)


@pytest.mark.parametrize("campo", CAMPOS_RED)
@pytest.mark.parametrize("valor", LEGITIMOS)
def test_redes_sin_esquema_o_con_http_se_aceptan_por_cada_via(client, repo, comercio, admin_token, campo, valor):
    for via, llamar in _vias_de_edicion(client, admin_token):
        r = llamar(campo, valor)
        assert r.status_code == 200, (via, campo, valor, r.status_code, r.text)
        assert repo.comercios["com-f"][campo] == valor.strip(), via


@pytest.mark.parametrize("valor", PELIGROSOS)
def test_como_llegar_peligroso_se_rechaza(client, repo, comercio, valor):
    r = client.put("/comercio/perfil", headers=_hc(), json={"como_llegar": valor})
    assert r.status_code == 400, (valor, r.text)
    assert "como_llegar" not in repo.comercios["com-f"]
    ok = client.put("/comercio/perfil", headers=_hc(),
                    json={"como_llegar": "https://www.google.com/maps/search/?api=1&query=-22.7,-64.3"})
    assert ok.status_code == 200


def test_el_mensaje_dice_cual_campo_esta_mal(client, repo, comercio):
    r = client.put("/comercio/perfil", headers=_hc(), json={"instagram_url": "javascript:alert(1)"})
    assert "Instagram" in r.json()["detail"] and "http" in r.json()["detail"]
    r = client.put("/comercio/perfil", headers=_hc(), json={"sitio_web": "http://[::1"})
    assert r.status_code == 400 and "sitio web" in r.json()["detail"] and "Invalid" not in r.json()["detail"]


@pytest.mark.parametrize("campo", CAMPOS_RED)
def test_alta_de_campo_rechaza_redes_peligrosas_antes_de_guardar_nada(client, repo, campo):
    token = client.post("/auth/campo/login",
                        json={"email": "agente@bermejolive.com", "password": "campo1234"}).json()["access_token"]
    base = {"nombre": "Gomería", "whatsapp": "59170002222", "modalidad": "minorista",
            "lat": "-22.7361", "lng": "-64.3433"}
    h = {"Authorization": f"Bearer {token}"}
    r = client.post("/campo/comercio", headers=h, data={**base, campo: "javascript:alert(1)"}, files=_foto_test())
    assert r.status_code == 400, r.text
    assert not repo.comercios
    assert _todo_el_disco() == []
    ok = client.post("/campo/comercio", headers=h, data={**base, campo: "@mitienda"}, files=_foto_test())
    assert ok.status_code == 200, ok.text


def test_la_importacion_descarta_un_sitio_web_peligroso_en_vez_de_guardarlo():
    assert enlaces.sanear_red("javascript:alert(1)") is None
    assert enlaces.sanear_red("https://tienda.com") == "https://tienda.com"
    assert enlaces.sanear_red(None) is None


# ── canal de WhatsApp: sólo WhatsApp ─────────────────────────────────────────
@pytest.mark.parametrize("valor", ["https://whatsapp.com/channel/0029Va", "https://www.whatsapp.com/channel/x",
                                   "https://chat.whatsapp.com/abc", "https://wa.me/59170001111", "HTTPS://WA.ME/x"])
def test_canal_de_whatsapp_acepta_whatsapp_y_wa_me(client, repo, comercio, valor):
    r = client.put("/comercio/perfil", headers=_hc(), json={"canal_wa_url": valor})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("valor", ["https://t.me/canal", "https://evil.com/whatsapp.com", "https://whatsapp.com.evil.com/c",
                                   "https://notwhatsapp.com/c", "https://wa.me.evil.com/x", "https://evil.com/?u=wa.me"])
def test_canal_que_no_es_de_whatsapp_400(client, repo, comercio, valor):
    for r in (client.put("/comercio/perfil", headers=_hc(), json={"canal_wa_url": valor}),
              client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"canal_wa_url": valor})):
        assert r.status_code == 400, (valor, r.text)
        assert r.json()["detail"] == "El canal tiene que ser un enlace de WhatsApp."


@pytest.mark.parametrize("valor", ["https://wa.me@evil.com/x", "https://whatsapp.com:pass@evil.com/c",
                                   "http://127.0.0.1/c", "http://192.168.1.5/c", "http://[::1]/c",
                                   "http://2130706433/c", "http://0x7f.0.0.1/c", "http://[::1"])
@pytest.mark.parametrize("campo", ["canal_wa_url", "catalogo_url"])
def test_enlaces_con_usuario_ip_o_ipv6_roto_400_en_espanol(client, repo, comercio, campo, valor):
    for r in (client.put("/comercio/perfil", headers=_hc(), json={campo: valor}),
              client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={campo: valor})):
        assert r.status_code == 400, (valor, r.text)
        assert "Invalid" not in r.json()["detail"]
        assert r.json()["detail"].startswith("El enlace") or r.json()["detail"].startswith("El canal")


# ── Carpeta por id ───────────────────────────────────────────────────────────
def test_un_nombre_largo_no_impide_subir_el_catalogo(client, repo):
    """El slug de un nombre larguísimo pasaba los 100 caracteres y el catálogo
    daba 409. La carpeta es el id: el slug no interviene."""
    from app.core.text import slugify
    slug = slugify("Distribuidora Mayorista Importadora y Exportadora de Productos de Primera Necesidad "
                   "Frontera Norte Sociedad Anonima Bermejo")
    assert len(slug) > 100
    repo.seed_comercio(id="com-largo", slug=slug, nombre="X", whatsapp="59170003333")
    r = _subir(client, "/comercio/catalogo", _hc("com-largo"))
    assert r.status_code == 200, r.text
    assert "/catalogos/com-largo/" in r.json()["catalogo_url"]


def test_un_slug_liberado_y_reutilizado_no_permite_borrar_el_pdf_de_otro(client, repo):
    """El segundo comercio hereda el slug del primero (dado de baja). El PDF del
    primero está en SU carpeta, por id: el segundo no lo alcanza."""
    repo.seed_comercio(id="com-viejo", slug="ferreteria", nombre="Vieja", whatsapp="59170001111")
    viejo_pdf = _subir(client, "/comercio/catalogo", _hc("com-viejo")).json()["catalogo_url"]
    repo.seed_comercio(id="com-nuevo", slug="ferreteria", nombre="Nueva", whatsapp="59170002222")
    client.put("/comercio/perfil", headers=_hc("com-nuevo"), json={"catalogo_url": viejo_pdf})
    _subir(client, "/comercio/catalogo", _hc("com-nuevo"))
    client.delete("/comercio/catalogo", headers=_hc("com-nuevo"))
    assert _archivo_de(viejo_pdf).exists()


# ── Carrera, huérfanos y límite ──────────────────────────────────────────────
def test_diez_subidas_en_paralelo_dejan_un_solo_archivo(client, repo, comercio):
    def subir(k):
        return _subir(client, "/comercio/catalogo", _hc(), data=_pdf(2048 + k))

    with ThreadPoolExecutor(max_workers=10) as pool:
        respuestas = list(pool.map(subir, range(10)))
    assert [r.status_code for r in respuestas] == [200] * 10, [r.text for r in respuestas]
    vigente = repo.comercios["com-f"]["catalogo_url"]
    assert _archivos("com-f") == [vigente.rsplit("/", 1)[1]]
    assert _archivo_de(vigente).exists()


def test_la_subida_barre_los_huerfanos_y_los_temporales(client, repo, comercio):
    carpeta = Path(settings.fotos_dir) / "catalogos" / "com-f"
    carpeta.mkdir(parents=True)
    for nombre in ("aaaaaaaaaaaaaaaa.pdf", "bbbbbbbbbbbbbbbb.pdf", ".cccccccc.tmp"):
        (carpeta / nombre).write_bytes(_pdf())
    (carpeta / "notas.txt").write_text("no es nuestro")      # lo que no es .pdf/.tmp no se toca
    url = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    assert sorted(p.name for p in carpeta.iterdir()) == sorted(["notas.txt", url.rsplit("/", 1)[1]])


def test_no_quedan_temporales_ni_tras_un_rechazo(client, repo, comercio):
    _subir(client, "/comercio/catalogo", _hc(), data=b"no soy pdf")
    _subir(client, "/comercio/catalogo", _hc(), data=_pdf(8 * MB + 1))
    _subir(client, "/comercio/catalogo", _hc())
    assert [n for n in _archivos("com-f") if n.endswith(".tmp")] == []
    assert len(_archivos("com-f")) == 1


def test_la_onceava_subida_de_la_hora_es_429(client, repo, comercio):
    for _ in range(10):
        assert _subir(client, "/comercio/catalogo", _hc()).status_code == 200
    r = _subir(client, "/comercio/catalogo", _hc())
    assert r.status_code == 429
    assert r.json()["detail"] == "Subiste muchos catálogos seguidos. Probá de nuevo en un rato."
    # el agente comparte el contador del comercio; otro comercio tiene el suyo
    assert _subir(client, "/campo/mis-comercios/com-f/catalogo", _ha()).status_code == 429
    repo.seed_comercio(id="com-g", slug="tienda-g", nombre="G", whatsapp="59170002222")
    assert _subir(client, "/comercio/catalogo", _hc("com-g")).status_code == 200


def test_pasada_la_hora_se_puede_volver_a_subir(client, repo, comercio, monkeypatch):
    for _ in range(10):
        _subir(client, "/comercio/catalogo", _hc())
    assert _subir(client, "/comercio/catalogo", _hc()).status_code == 429
    ahora = catalogo_svc.time.monotonic()
    monkeypatch.setattr(catalogo_svc.time, "monotonic", lambda: ahora + 3601)
    assert _subir(client, "/comercio/catalogo", _hc()).status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# Tope global al cuerpo (LimiteCuerpoMiddleware)
# ═════════════════════════════════════════════════════════════════════════════
def _asgi_post(path, headers, trozos, content_type="multipart/form-data; boundary=qa"):
    """Una llamada a la app a nivel ASGI, SIN Content-Length (chunked). Devuelve
    (status, cuerpo, bytes que la app llegó a leer)."""
    cola = list(trozos)
    leidos = {"n": 0, "i": 0}
    resp = {"status": None, "body": b""}

    async def receive():
        if leidos["i"] >= len(cola):
            return {"type": "http.disconnect"}
        c = cola[leidos["i"]]
        leidos["i"] += 1
        leidos["n"] += len(c)
        return {"type": "http.request", "body": c, "more_body": leidos["i"] < len(cola)}

    async def send(msg):
        if msg["type"] == "http.response.start":
            resp["status"] = msg["status"]
        elif msg["type"] == "http.response.body":
            resp["body"] += msg.get("body", b"")

    hdrs = {"content-type": content_type, "transfer-encoding": "chunked", **{k.lower(): v for k, v in headers.items()}}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": path, "raw_path": path.encode(), "query_string": b"",
             "headers": [(k.encode(), v.encode()) for k, v in hdrs.items()],
             "server": ("testserver", 80), "client": ("203.0.113.9", 4444)}
    asyncio.run(app(scope, receive, send))
    return resp["status"], resp["body"], leidos["n"]


def _multipart_en_trozos(campo, contenido, tam=256 * 1024):
    yield (f'--qa\r\nContent-Disposition: form-data; name="{campo}"; filename="a.bin"\r\n'
           f"Content-Type: application/octet-stream\r\n\r\n").encode()
    for k in range(0, len(contenido), tam):
        yield contenido[k:k + tam]
    yield b"\r\n--qa--\r\n"


@pytest.mark.parametrize("ruta,campo,tope_mb", [
    ("/comercio/fotos", "foto", 15),
    ("/comercio/catalogo", "archivo", 8),
    ("/campo/mis-comercios/x/foto", "foto", 15),
    ("/admin/comercio/x/fotos", "foto", 15),
    ("/comercio/videos", "video", 50),
])
def test_chunked_sin_token_se_corta_con_413_y_no_escribe_nada(repo, client, ruta, campo, tope_mb):
    """El agujero que ya existía: 30 MB sin token se escribían a disco antes del
    401, y sin Content-Length nada frenaba el cuerpo."""
    status, cuerpo, leidos = _asgi_post(ruta, {}, _multipart_en_trozos(campo, b"\x00" * ((tope_mb + 2) * MB)))
    if ruta == "/comercio/catalogo":
        # Lee el Request a mano: la autenticación corre primero y contesta 401
        # sin tocar el cuerpo (si no, lo corta el tope con 413).
        assert status in (401, 413), (ruta, status, cuerpo[:200])
    else:
        assert status == 413, (ruta, status, cuerpo[:200])
        assert b"demasiado grande" in cuerpo
    assert leidos <= (tope_mb + 1) * MB, f"leyó {leidos / MB:.1f} MB de un cuerpo que se iba a rechazar"
    assert _todo_el_disco() == []


def test_json_grande_a_cualquier_ruta_es_413(client, repo):
    r = client.post("/auth/comercio/ingresar", json={"whatsapp": "5917", "clave": "x" * (3 * MB)})
    assert r.status_code == 413
    assert r.json() == {"detail": "El archivo es demasiado grande."}
    # y por Content-Length declarado, sin leer nada
    r = client.post("/auth/comercio/ingresar", content=b"{}",
                    headers={"Content-Length": str(50 * MB), "Content-Type": "application/json"})
    assert r.status_code == 413


def test_un_json_normal_pasa_el_tope(client, repo):
    r = client.post("/auth/comercio/ingresar", json={"whatsapp": "59170000000", "clave": "123456"})
    assert r.status_code != 413


def test_el_413_lleva_cabeceras_cors(client, repo):
    r = client.post("/auth/comercio/ingresar", content=b"x" * (3 * MB),
                    headers={"Origin": "http://localhost:3000", "Content-Type": "application/json"})
    assert r.status_code == 413
    assert r.headers.get("access-control-allow-origin")


def test_una_foto_de_14mb_pasa_el_tope(client, repo, comercio):
    r = client.post("/comercio/fotos", headers=_hc(),
                    files={"foto": ("f.jpg", b"\xff\xd8\xff" + b"0" * (14 * MB), "image/jpeg")})
    # el tope no la corta; la rechaza el handler porque no es una imagen real
    assert r.status_code == 400, r.text


def test_una_foto_de_16mb_no_pasa(client, repo, comercio):
    r = client.post("/comercio/fotos", headers=_hc(),
                    files={"foto": ("f.jpg", b"\xff\xd8\xff" + b"0" * (16 * MB), "image/jpeg")})
    assert r.status_code == 413


def test_un_video_de_49mb_pasa_y_uno_de_52_no(client, repo, comercio):
    ok = client.post("/comercio/videos", headers=_hc(),
                     files={"video": ("v.mp4", b"\x00" * (49 * MB), "video/mp4")})
    assert ok.status_code == 200, ok.text
    mal = client.post("/comercio/videos", headers=_hc(),
                      files={"video": ("v.mp4", b"\x00" * (52 * MB), "video/mp4")})
    assert mal.status_code == 413


def test_el_webhook_acepta_hasta_25mb_y_corta_mas(client, repo):
    h = {"Content-Type": "application/json"}
    ok = client.post("/ingest/webhook", content=b"{" + b" " * (20 * MB) + b"}", headers=h)
    assert ok.status_code != 413
    mal = client.post("/ingest/webhook", content=b"{" + b" " * (27 * MB) + b"}", headers=h)
    assert mal.status_code == 413


def test_la_tabla_de_topes():
    esperado = {
        "/comercio/catalogo": 8, "/campo/mis-comercios/abc/catalogo": 8, "/admin/comercio/abc/catalogo": 8, "/comercio/fotos": 15,
        "/campo/comercio": 15, "/campo/mis-comercios/abc/foto": 15, "/campo/mis-comercios/abc/fotos": 15,
        "/admin/comercio/abc/fotos": 15, "/admin/comercio/abc/foto": 15, "/comercio/perfil/foto": 15, "/auth/comercio/registro": 15,
        "/comercio/abc/solicitar-cambio-numero": 15, "/campo/lugares/abc/portada": 15, "/comercio/pago": 15,
        "/comercio/productos": 45, "/comercio/videos": 50, "/campo/mis-comercios/abc/videos": 50,
        "/campo/lugares/abc/video": 50, "/contenido/videos-promo": 100, "/ingest/webhook": 25,
        "/contenido/novedades/abc/portada": 15, "/contenido/novedades/abc/fotos": 15,
        "/contenido/novedades/abc/video": 100,
        "/campo/transcribir": 25, "/admin/contactos/importar": 8,
    }
    for ruta, mb in esperado.items():
        assert tope_para(ruta) == mb * MB + HOLGURA, ruta
        assert tope_para(ruta + "/") == mb * MB + HOLGURA, ruta
    for ruta in ("/comercio/perfil", "/auth/comercio/ingresar", "/lead", "/otra/cosa"):
        assert tope_para(ruta) == TOPE_POR_DEFECTO == 2 * MB, ruta


def test_toda_ruta_con_archivos_tiene_tope_propio():
    """Una ruta nueva que reciba archivos y no se sume a la tabla quedaría con 2 MB
    y fallaría en producción con una foto normal. Este test lo avisa antes."""
    rutas = [p for p, v in app.openapi()["paths"].items() for op in v.values()
             if "multipart/form-data" in op.get("requestBody", {}).get("content", {})]
    assert len(rutas) >= 15
    for ruta in rutas:
        concreta = re.sub(r"\{[^}]+\}", "abc", ruta)
        assert tope_para(concreta) > TOPE_POR_DEFECTO, f"{ruta} quedó con el tope por defecto (2 MB)"
    # las que leen el Request a mano no figuran como multipart en OpenAPI
    for ruta in ("/comercio/catalogo", "/campo/mis-comercios/abc/catalogo", "/admin/comercio/abc/catalogo", "/ingest/webhook"):
        assert tope_para(ruta) > TOPE_POR_DEFECTO


# ── Cabeceras de /fotos/ ─────────────────────────────────────────────────────
@pytest.fixture
def archivo_servido():
    """El StaticFiles de main.py se montó con el fotos_dir del import: se escribe
    ahí y se limpia al terminar."""
    montaje = next(r for r in app.routes if getattr(r, "name", None) == "fotos")
    raiz = Path(montaje.app.directory)
    creados = []

    def crear(rel, contenido):
        ruta = raiz / rel
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
        creados.append(ruta)

    yield crear
    for ruta in creados:
        ruta.unlink(missing_ok=True)
        try:
            ruta.parent.rmdir()
        except OSError:
            pass


def test_fotos_lleva_nosniff_y_el_catalogo_su_disposicion_y_cache_corto(client, archivo_servido):
    archivo_servido("catalogos/com-hdr/abcdef0123456789.pdf", _pdf())
    archivo_servido("com-hdr/foto.jpg", b"\xff\xd8\xff")
    pdf = client.get("/fotos/catalogos/com-hdr/abcdef0123456789.pdf")
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.headers["x-content-type-options"] == "nosniff"
    assert pdf.headers["content-disposition"] == 'inline; filename="catalogo.pdf"'
    assert pdf.headers["cache-control"] == "public, max-age=3600"
    assert "content-security-policy" not in pdf.headers       # un sandbox rompe el visor de PDF
    foto = client.get("/fotos/com-hdr/foto.jpg")
    assert foto.headers["x-content-type-options"] == "nosniff"
    assert foto.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "content-disposition" not in foto.headers
    falta = client.get("/fotos/catalogos/com-hdr/no-existe.pdf")
    assert falta.status_code == 404 and falta.headers["x-content-type-options"] == "nosniff"
