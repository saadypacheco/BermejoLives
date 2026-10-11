"""QA de «Lo que suma» en la ficha (docs/ficha-destacados.md): bordes, hostilidad
y contrato front <-> back que `test_ficha_destacados.py` no cubre.

Los 7 tests que nacieron como `xfail(strict=True)` (bugs confirmados: chunked sin
tope, slug largo, slug renombrado x3, IPv6 roto x2) ya pasan y perdieron la marca.
La carpeta de los catálogos es `catalogos/<comercio_id>/`, no el slug.

El `fotos_dir` es un tmp por test (autouse en conftest).
"""
import asyncio
from pathlib import Path

import pytest

from app.core import auth
from app.core.config import settings
from app.main import app
from app.services import ficha_catalogo as svc
from tests.conftest import comercio_token

MB = 1024 * 1024


# ── helpers ──────────────────────────────────────────────────────────────────
def _pdf(tam: int = 2048) -> bytes:
    return b"%PDF-1.4\n" + b"0" * (tam - 9)


def _hc(cid="com-f"):
    return {"Authorization": f"Bearer {comercio_token(comercio_id=cid)}"}


def _ha(email="agente@bermejolive.com", ciudad="bermejo"):
    return {"Authorization": f"Bearer {auth.make_agente_token(email, ciudad)}"}


def _subir(client, url, headers, data=None, nombre="catalogo.pdf", ctype="application/pdf"):
    data = _pdf() if data is None else data
    return client.post(url, headers=headers, files={"archivo": (nombre, data, ctype)})


def _archivos(slug: str) -> list[str]:
    c = Path(settings.fotos_dir) / "catalogos" / slug
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


def _multipart(pdf: bytes, boundary="qaboundary"):
    cabeza = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"c.pdf\"\r\n"
              f"Content-Type: application/pdf\r\n\r\n").encode()
    cola = f"\r\n--{boundary}--\r\n".encode()
    return cabeza, pdf, cola


def _asgi_post(path, headers, cuerpo_en_trozos, boundary="qaboundary"):
    """Llama a la app a nivel ASGI (sin servidor HTTP) y cuenta cuántos bytes del
    cuerpo llegó a LEER. Devuelve (status, cuerpo_respuesta, bytes_leidos)."""
    leidos = {"n": 0}
    trozos = list(cuerpo_en_trozos)
    i = {"k": 0}
    respuesta: dict = {"status": None, "body": b""}

    async def receive():
        if i["k"] >= len(trozos):
            return {"type": "http.disconnect"}
        c = trozos[i["k"]]
        i["k"] += 1
        leidos["n"] += len(c)
        return {"type": "http.request", "body": c, "more_body": i["k"] < len(trozos)}

    async def send(msg):
        if msg["type"] == "http.response.start":
            respuesta["status"] = msg["status"]
        elif msg["type"] == "http.response.body":
            respuesta["body"] += msg.get("body", b"")

    hdrs = {"content-type": f"multipart/form-data; boundary={boundary}", **{k.lower(): v for k, v in headers.items()}}
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
        "headers": [(k.encode(), v.encode()) for k, v in hdrs.items()],
        "server": ("testserver", 80), "client": ("203.0.113.9", 4444),
    }
    asyncio.run(app(scope, receive, send))
    return respuesta["status"], respuesta["body"], leidos["n"]


def _en_trozos(pdf: bytes, tam=64 * 1024):
    cabeza, cuerpo, cola = _multipart(pdf)
    yield cabeza
    for k in range(0, len(cuerpo), tam):
        yield cuerpo[k:k + tam]
    yield cola


# ═════════════════════════════════════════════════════════════════════════════
# Criterio 2: tamaño y tipo del PDF
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("endpoint,headers", [
    ("/comercio/catalogo", _hc), ("/campo/mis-comercios/com-f/catalogo", _ha)])
def test_8mb_exactos_pasan_y_8mb_mas_1_no(client, repo, comercio, endpoint, headers):
    ok = _subir(client, endpoint, headers(), data=_pdf(8 * MB))
    assert ok.status_code == 200, ok.text
    url_ok = ok.json()["catalogo_url"]
    assert _archivo_de(url_ok).stat().st_size == 8 * MB
    mal = _subir(client, endpoint, headers(), data=_pdf(8 * MB + 1))
    assert mal.status_code == 413
    assert mal.json()["detail"] == "El catálogo puede pesar hasta 8 MB."
    # el rechazo no tocó nada: el de 8 MB sigue siendo el catálogo y es el único archivo
    assert repo.comercios["com-f"]["catalogo_url"] == url_ok
    assert _archivos("com-f") == [url_ok.rsplit("/", 1)[1]]


def test_pdf_real_con_extension_txt_se_acepta_por_contenido(client, repo, comercio):
    """La spec: se valida por contenido, no por extensión. Se guarda siempre como .pdf."""
    r = _subir(client, "/comercio/catalogo", _hc(), nombre="catalogo.txt", ctype="text/plain")
    assert r.status_code == 200, r.text
    url = r.json()["catalogo_url"]
    assert url.endswith(".pdf") and _archivo_de(url).read_bytes() == _pdf()


@pytest.mark.parametrize("contenido", [
    b"<html><script>alert(1)</script></html>",
    b" %PDF-1.4 con un espacio antes",
    b"%PDF",                       # le falta el guion
    b"\xef\xbb\xbf%PDF-1.4",       # con BOM
    b"PK\x03\x04 zip",
    b"%pdf-1.4 en minuscula",
])
def test_lo_que_no_empieza_con_pdf_guion_se_rechaza_aunque_se_llame_pdf(client, repo, comercio, contenido):
    anterior = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    r = _subir(client, "/comercio/catalogo", _hc(), data=contenido, nombre="catalogo.pdf")
    assert r.status_code == 400
    assert r.json()["detail"] == "El catálogo tiene que ser un PDF."
    assert repo.comercios["com-f"]["catalogo_url"] == anterior
    assert _archivos("com-f") == [anterior.rsplit("/", 1)[1]]


def test_archivo_vacio_conserva_el_anterior(client, repo, comercio):
    anterior = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    r = _subir(client, "/comercio/catalogo", _hc(), data=b"")
    assert r.status_code == 400
    assert repo.comercios["com-f"]["catalogo_url"] == anterior
    assert _archivo_de(anterior).exists()


def test_el_campo_archivo_como_texto_plano_no_es_un_archivo(client, repo, comercio):
    r = client.post("/comercio/catalogo", headers=_hc(), data={"archivo": "%PDF-1.4 soy texto"})
    assert r.status_code == 400
    assert _todo_el_disco() == []


def test_un_pdf_de_un_solo_byte_o_truncado_en_el_encabezado_no_rompe(client, repo, comercio):
    for chico in (b"%", b"%P", b"%PDF-"):
        r = _subir(client, "/comercio/catalogo", _hc(), data=chico)
        assert r.status_code in (200, 400), (chico, r.status_code)


# ── Content-Length mentido / ausente ─────────────────────────────────────────
def test_content_length_enorme_en_los_dos_endpoints_se_corta_sin_leer(client, repo, comercio):
    for url, h in (("/comercio/catalogo", _hc()), ("/campo/mis-comercios/com-f/catalogo", _ha())):
        hh = {**h, "Content-Length": str(500 * MB), "Content-Type": "multipart/form-data; boundary=x"}
        r = client.post(url, headers=hh, content=b"--x--")
        assert r.status_code == 413, (url, r.status_code)


@pytest.mark.parametrize("valor", ["-1", "abc", "", "1e9", "9" * 40])
def test_content_length_basura_nunca_es_500(client, repo, comercio, valor):
    hh = {**_hc(), "Content-Length": valor, "Content-Type": "multipart/form-data; boundary=x"}
    try:
        r = client.post("/comercio/catalogo", headers=hh, content=b"--x--")
    except Exception:  # noqa: BLE001
        pytest.skip("el cliente no deja mandar ese Content-Length")
    assert r.status_code in (400, 413, 422), r.status_code


def test_content_length_mentido_chico_cuerpo_grande_no_guarda_nada(repo, client, comercio):
    """Dice 1000 bytes y manda 12 MB. A nivel ASGI no hay servidor que corte el
    cuerpo en el Content-Length (uvicorn/h11 sí lo hace): la app tiene que
    rechazarlo ella por el conteo de bytes leídos."""
    status, cuerpo, _ = _asgi_post("/comercio/catalogo",
                                   {**_hc(), "Content-Length": "1000"}, _en_trozos(_pdf(12 * MB)))
    assert status == 413, (status, cuerpo[:200])
    assert _todo_el_disco() == []


def test_sin_content_length_el_cuerpo_se_corta_cerca_de_8mb(repo, client, comercio):
    status, _, leidos = _asgi_post("/comercio/catalogo", _hc(), _en_trozos(_pdf(40 * MB)))
    assert status == 413
    assert leidos <= 8 * MB + 512 * 1024, f"el servidor leyó {leidos / MB:.1f} MB de un cuerpo que iba a rechazar"


def test_sin_content_length_igual_se_rechaza_y_no_deja_archivos(repo, client, comercio):
    status, _, _ = _asgi_post("/comercio/catalogo", _hc(), _en_trozos(_pdf(10 * MB)))
    assert status == 413
    assert _todo_el_disco() == []


def test_sin_token_no_se_lee_el_cuerpo(repo, client, comercio):
    """La autenticación corre antes que el parseo del multipart."""
    status, _, leidos = _asgi_post("/comercio/catalogo", {}, _en_trozos(_pdf(20 * MB)))
    assert status == 401
    assert leidos <= 1 * MB, f"leyó {leidos / MB:.1f} MB sin estar autenticado"
    status, _, leidos = _asgi_post("/campo/mis-comercios/com-f/catalogo", {}, _en_trozos(_pdf(20 * MB)))
    assert status == 401
    assert leidos <= 1 * MB


# ═════════════════════════════════════════════════════════════════════════════
# Criterio 3: reemplazar borra el anterior
# ═════════════════════════════════════════════════════════════════════════════
def test_tres_subidas_seguidas_dejan_un_solo_archivo(client, repo, comercio):
    urls = [_subir(client, "/comercio/catalogo", _hc(), data=_pdf(2048 + k)).json()["catalogo_url"]
            for k in range(3)]
    assert len(set(urls)) == 3
    assert _archivos("com-f") == [urls[-1].rsplit("/", 1)[1]]
    assert repo.comercios["com-f"]["catalogo_url"] == urls[-1]


def test_comerciante_y_agente_alternados_se_reemplazan_entre_si(client, repo, comercio):
    a = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    b = _subir(client, "/campo/mis-comercios/com-f/catalogo", _ha()).json()["catalogo_url"]
    c = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    assert _archivos("com-f") == [c.rsplit("/", 1)[1]]
    assert not _archivo_de(a).exists() and not _archivo_de(b).exists()


def test_el_archivo_anterior_ya_no_estaba_en_disco_no_es_error(client, repo, comercio):
    a = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    _archivo_de(a).unlink()
    r = _subir(client, "/comercio/catalogo", _hc())
    assert r.status_code == 200, r.text
    assert client.delete("/comercio/catalogo", headers=_hc()).status_code == 200
    assert _archivos("com-f") == []


def test_el_agente_tambien_puede_pegar_el_pdf_de_otro_y_no_se_borra(client, repo, comercio):
    repo.seed_comercio(id="com-g", slug="tienda-g", nombre="Tienda G", whatsapp="59170002222",
                       ciudad_id="ciu-1", cargado_por="agente@bermejolive.com")
    ajeno = _subir(client, "/comercio/catalogo", _hc("com-g")).json()["catalogo_url"]
    r = client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"catalogo_url": ajeno})
    assert r.status_code == 200, r.text
    # ahora sube uno propio, lo cambia por un enlace y lo quita: el ajeno no se toca nunca
    _subir(client, "/campo/mis-comercios/com-f/catalogo", _ha())
    client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"catalogo_url": "https://x.com/y"})
    client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"catalogo_url": ajeno})
    client.delete("/campo/mis-comercios/com-f/catalogo", headers=_ha())
    assert _archivo_de(ajeno).exists()
    assert _archivos("com-g") == [ajeno.rsplit("/", 1)[1]]


def test_url_con_pinta_de_propia_pero_de_otra_carpeta_o_forma_no_se_borra(client, repo, comercio):
    """Archivos reales en disco que una URL escrita a mano intenta señalar."""
    raiz = Path(settings.fotos_dir)
    for rel in ("catalogos/com-g/abcdef0123456789.pdf", "com-f/abcdef0123456789.jpg",
                "catalogos/com-f.pdf", "secreto.pdf"):
        p = raiz / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(_pdf())
    base = settings.fotos_public_base_url.rstrip("/")
    hostiles = [
        f"{base}/catalogos/com-g/abcdef0123456789.pdf",
        f"{base}/com-f/abcdef0123456789.jpg",
        f"{base}/catalogos/com-f/../../secreto.pdf",
        f"{base}/catalogos/com-f/..%2F..%2Fsecreto.pdf",
        f"{base}/catalogos/com-f/./abcdef0123456789.pdf/../../../secreto.pdf",
        f"{base}/../secreto.pdf",
        f"{base}//catalogos/com-f/abcdef0123456789.pdf",
    ]
    for u in hostiles:
        comercio["catalogo_url"] = u
        client.delete("/comercio/catalogo", headers=_hc())
    assert (raiz / "catalogos/com-g/abcdef0123456789.pdf").exists()
    assert (raiz / "com-f/abcdef0123456789.jpg").exists()
    assert (raiz / "catalogos/com-f.pdf").exists()
    assert (raiz / "secreto.pdf").exists()


# ── slug con caracteres raros ────────────────────────────────────────────────
@pytest.mark.parametrize("slug", [
    "Tienda F", "tienda_f", "ñandú", "a/b", "../x", "..", ".", "tienda-f\x00", "-empieza", "TIENDA", "a" * 101, "", None,
])
def test_el_slug_no_importa_la_carpeta_es_el_id(client, repo, slug):
    """Antes la carpeta era el slug y un slug raro (o largo, o vacío) daba 409 o,
    peor, dejaba elegir la ruta. Ahora la carpeta es el id: el slug no entra en
    ninguna ruta de disco."""
    repo.seed_comercio(id="com-x", slug=slug, nombre="X", whatsapp="59170003333", ciudad_id="ciu-1",
                       cargado_por="agente@bermejolive.com")
    for url, h in (("/comercio/catalogo", _hc("com-x")), ("/campo/mis-comercios/com-x/catalogo", _ha())):
        r = _subir(client, url, h)
        assert r.status_code == 200, (slug, r.status_code, r.text)
        assert "/catalogos/com-x/" in r.json()["catalogo_url"]
    assert _todo_el_disco() == [p for p in _todo_el_disco() if p.replace("\\", "/").startswith("catalogos/com-x/")]
    assert len(_archivos("com-x")) == 1
    assert client.delete("/comercio/catalogo", headers=_hc("com-x")).status_code == 200
    assert _todo_el_disco() == []


def test_slug_de_100_caracteres_exactos_sube(client, repo):
    slug = "a" * 100
    repo.seed_comercio(id="com-x", slug=slug, nombre="X", whatsapp="59170003333")
    assert _subir(client, "/comercio/catalogo", _hc("com-x")).status_code == 200


def test_un_nombre_largo_legitimo_puede_subir_catalogo(client, repo):
    from app.core.text import slugify
    slug = slugify("Distribuidora Mayorista Importadora y Exportadora de Productos de Primera Necesidad "
                   "Frontera Norte Sociedad Anonima Bermejo")
    assert len(slug) > 100
    repo.seed_comercio(id="com-x", slug=slug, nombre="X", whatsapp="59170003333")
    assert _subir(client, "/comercio/catalogo", _hc("com-x")).status_code == 200


# ── renombrar un comercio de slug genérico ───────────────────────────────────
@pytest.mark.parametrize("quien", ["agente", "comerciante"])
def test_renombrar_un_slug_generico_no_deja_el_pdf_huerfano(client, repo, quien):
    repo.seed_comercio(id="com-g", slug="comercio-7", nombre=None, whatsapp="59170004444",
                       ciudad_id="ciu-1", cargado_por="agente@bermejolive.com")
    if quien == "agente":
        subir = lambda: _subir(client, "/campo/mis-comercios/com-g/catalogo", _ha())      # noqa: E731
        renombrar = lambda: client.patch("/campo/mis-comercios/com-g", headers=_ha(),     # noqa: E731
                                         json={"nombre": "Ferretería López"})
    else:
        subir = lambda: _subir(client, "/comercio/catalogo", _hc("com-g"))                # noqa: E731
        renombrar = lambda: client.put("/comercio/perfil", headers=_hc("com-g"),          # noqa: E731
                                       json={"nombre": "Ferretería López"})
    viejo = subir().json()["catalogo_url"]
    assert renombrar().status_code == 200
    assert repo.comercios["com-g"]["slug"] == "ferreteria-lopez"
    nuevo = subir().json()["catalogo_url"]
    assert not _archivo_de(viejo).exists(), "el PDF anterior quedó huérfano en el disco"
    assert _archivo_de(nuevo).exists()


def test_renombrar_y_cambiar_a_enlace_en_la_misma_llamada(client, repo):
    repo.seed_comercio(id="com-g", slug="comercio-8", nombre=None, whatsapp="59170004444")
    viejo = _subir(client, "/comercio/catalogo", _hc("com-g")).json()["catalogo_url"]
    r = client.put("/comercio/perfil", headers=_hc("com-g"),
                   json={"nombre": "Zapatería Sur", "catalogo_url": "https://drive.google.com/x"})
    assert r.status_code == 200, r.text
    assert not _archivo_de(viejo).exists()


# ═════════════════════════════════════════════════════════════════════════════
# Criterio 4: datos de la ficha. Enlaces hostiles, pedido mínimo, booleanos
# ═════════════════════════════════════════════════════════════════════════════
HOSTILES = [
    "javascript:alert(1)", "JaVaScRiPt:alert(1)", " javascript:alert(1)", "data:text/html;base64,PHNjcmlwdD4=",
    "vbscript:msgbox(1)", "file:///etc/passwd", "ftp://x.com/a", "//evil.com/x", "evil.com/catalogo",
    "wa.me/59170001111", "https:evil.com", "http:///sin-host", "https://", "http://a b.com", "https://a.com/\tx",
    "https://a.com/\nx", "https://a.com/\x00", "x" * 10, "https://a.com/" + "x" * 500,
]


@pytest.mark.parametrize("campo", ["canal_wa_url", "catalogo_url"])
@pytest.mark.parametrize("valor", HOSTILES)
def test_enlace_hostil_se_rechaza_en_put_y_patch_sin_500(client, repo, comercio, campo, valor):
    r1 = client.put("/comercio/perfil", headers=_hc(), json={campo: valor})
    r2 = client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={campo: valor})
    assert r1.status_code == 400, (valor, r1.status_code, r1.text)
    assert r2.status_code == 400, (valor, r2.status_code, r2.text)
    assert campo not in repo.comercios["com-f"]


@pytest.mark.parametrize("valor", ["http://[::1", "http://[bad"])
def test_enlace_ipv6_roto_es_400_con_mensaje_en_espanol(client, repo, comercio, valor):
    """`urlsplit` lanza ValueError('Invalid IPv6 URL'): tiene que salir el mensaje propio, no el de Python."""
    r = client.put("/comercio/perfil", headers=_hc(), json={"canal_wa_url": valor})
    assert r.status_code == 400
    assert "http" in r.json()["detail"] and "Invalid" not in r.json()["detail"], r.json()["detail"]


@pytest.mark.parametrize("valor", ["HTTP://EJEMPLO.COM/Catalogo", "https://ejemplo.com/a?b=c#d", "http://localhost:3000/x",
                                   "https://wa.me/59170001111", "  https://ejemplo.com  "])
def test_enlaces_http_validos_pasan(client, repo, comercio, valor):
    r = client.put("/comercio/perfil", headers=_hc(), json={"catalogo_url": valor})
    assert r.status_code == 200, (valor, r.text)
    assert repo.comercios["com-f"]["catalogo_url"] == valor.strip()


def test_enlace_de_500_caracteres_pasa_y_de_501_no(client, repo, comercio):
    base = "https://wa.me/"
    assert client.put("/comercio/perfil", headers=_hc(), json={"canal_wa_url": base + "x" * (500 - len(base))}).status_code == 200
    assert client.put("/comercio/perfil", headers=_hc(), json={"canal_wa_url": base + "x" * (501 - len(base))}).status_code == 400


def test_pedido_minimo_121_rechazado_120_ok_en_ambos(client, repo, comercio):
    llamadas = (("comerciante", lambda v: client.put("/comercio/perfil", headers=_hc(), json={"pedido_minimo": v})),
                ("agente", lambda v: client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"pedido_minimo": v})))
    for quien, call in llamadas:
        assert call("x" * 121).status_code == 400, quien
        assert call("ñ" * 121).status_code == 400, quien
        assert call("x" * 120).status_code == 200, quien
        assert call("  " + "x" * 120 + "  ").status_code == 200, quien       # se recorta antes de contar
        assert repo.comercios["com-f"]["pedido_minimo"] == "x" * 120, quien
        assert call("y" * 121).status_code == 400, quien
        assert repo.comercios["com-f"]["pedido_minimo"] == "x" * 120, quien   # el rechazo no pisó


@pytest.mark.parametrize("valor", [5, ["a"], {"a": 1}, True])
def test_pedido_minimo_que_no_es_texto_es_422(client, repo, comercio, valor):
    assert client.put("/comercio/perfil", headers=_hc(), json={"pedido_minimo": valor}).status_code == 422
    assert client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"pedido_minimo": valor}).status_code == 422


def test_pedido_minimo_con_html_llega_crudo_al_back(client, repo, comercio):
    """El back no escapa (React lo hace al pintar). Se documenta que llega tal cual."""
    r = client.put("/comercio/perfil", headers=_hc(), json={"pedido_minimo": "<img src=x onerror=alert(1)>"})
    assert r.status_code == 200
    assert repo.comercios["com-f"]["pedido_minimo"] == "<img src=x onerror=alert(1)>"


@pytest.mark.parametrize("valor,esperado", [("true", True), ("false", False), ("1", True), ("0", False),
                                            ("yes", True), ("no", False), (1, True), (0, False)])
def test_booleanos_como_string_o_numero_se_coercionan_bien(client, repo, comercio, valor, esperado):
    r = client.put("/comercio/perfil", headers=_hc(), json={"tiene_pasero": valor})
    assert r.status_code == 200, (valor, r.text)
    assert repo.comercios["com-f"]["tiene_pasero"] is esperado
    r = client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"tiene_factura": valor})
    assert r.status_code == 200, (valor, r.text)
    assert repo.comercios["com-f"]["tiene_factura"] is esperado


@pytest.mark.parametrize("valor", ["maybe", "", "verdadero", 2, [], {}, "null"])
def test_booleano_basura_es_422_y_no_cambia_nada(client, repo, comercio, valor):
    comercio["tiene_pasero"] = True
    assert client.put("/comercio/perfil", headers=_hc(), json={"tiene_pasero": valor}).status_code == 422
    assert client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"envios_internacionales": valor}).status_code == 422
    assert repo.comercios["com-f"]["tiene_pasero"] is True
    assert "envios_internacionales" not in repo.comercios["com-f"]


def test_booleano_null_no_borra_ni_rompe(client, repo, comercio):
    comercio.update(tiene_pasero=True, tiene_factura=True)
    r = client.put("/comercio/perfil", headers=_hc(), json={"tiene_pasero": None, "pedido_minimo": "2"})
    assert r.status_code == 200 and repo.comercios["com-f"]["tiene_pasero"] is True
    r = client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"tiene_factura": None, "pedido_minimo": "3"})
    assert r.status_code == 200 and repo.comercios["com-f"]["tiene_factura"] is True
    # solo el null, sin nada más: no hay campos
    assert client.put("/comercio/perfil", headers=_hc(), json={"tiene_pasero": None}).status_code == 400
    assert client.patch("/campo/mis-comercios/com-f", headers=_ha(), json={"tiene_pasero": None}).status_code == 400


def test_un_comerciante_no_puede_colarse_campos_de_admin_por_el_perfil(client, repo, comercio):
    r = client.put("/comercio/perfil", headers=_hc(), json={"confiable": True, "plan": "pro", "verificado": True,
                                                              "tiene_pasero": True})
    assert r.status_code == 200
    fila = repo.comercios["com-f"]
    assert fila["confiable"] is False and fila["plan"] == "gratis" and fila["verificado"] is False
    assert fila["tiene_pasero"] is True


# ── contrato de lo que lee el frontend ───────────────────────────────────────
def test_la_respuesta_del_put_trae_los_campos_nuevos_para_el_setPerfil_del_front(client, repo, comercio):
    r = client.put("/comercio/perfil", headers=_hc(), json={
        "canal_wa_url": "https://whatsapp.com/channel/z", "catalogo_url": "https://x.com/k",
        "tiene_pasero": True, "envios_internacionales": False, "tiene_factura": True, "pedido_minimo": "2"})
    assert r.status_code == 200
    for campo in ("canal_wa_url", "catalogo_url", "tiene_pasero", "envios_internacionales", "tiene_factura", "pedido_minimo"):
        assert campo in r.json(), campo
    assert r.json()["tiene_pasero"] is True and r.json()["envios_internacionales"] is False


def test_la_url_subida_tiene_la_forma_que_reconoce_esCatalogoSubido(client, repo, comercio):
    """Espejo de la regex de frontend/lib/catalogo.ts: /\\/catalogos\\/[^?#]+\\.pdf(?:[?#].*)?$/i"""
    import re
    regex = re.compile(r"/catalogos/[^?#]+\.pdf(?:[?#].*)?$", re.I)
    for url, h in (("/comercio/catalogo", _hc()), ("/campo/mis-comercios/com-f/catalogo", _ha())):
        u = _subir(client, url, h).json()["catalogo_url"]
        assert regex.search(u), u
        assert u.startswith("http"), u            # urlHttp() la muestra con «Ver»
    for ajeno in ("https://drive.google.com/file/d/x", "https://tienda.com/catalogo.pdf", "https://wa.me/1"):
        assert not regex.search(ajeno)


def test_esCatalogoSubido_da_falso_positivo_con_un_enlace_externo_que_tiene_catalogos_en_la_ruta():
    """Informativo (bajo): la heurística del front es solo de forma. Un enlace pegado a mano como
    https://tienda.com/catalogos/primavera.pdf se trata como 'PDF subido' (oculta el campo de enlace,
    ofrece 'Quitar'). El back, en cambio, lo trata bien (no es nuestro y no se borra nada)."""
    import re
    regex = re.compile(r"/catalogos/[^?#]+\.pdf(?:[?#].*)?$", re.I)
    externo = "https://tienda.com/catalogos/primavera.pdf"
    assert regex.search(externo)                              # el front lo confunde
    assert svc.archivo_propio(externo, "tienda-f") is None    # el back no


def test_multipart_armado_a_mano_como_lo_hace_el_front_es_aceptado(client, repo, comercio):
    """lib/upload.ts `armarMultipart` manda CRLF, name="archivo", filename y Content-Type propios.
    Se reproduce el mismo formato en bytes (con un nombre de archivo con tildes y paréntesis)."""
    b = "----bermejoQA123"
    cuerpo = (f"--{b}\r\nContent-Disposition: form-data; name=\"archivo\"; filename=\"Catálogo 2026 (1).pdf\"\r\n"
              f"Content-Type: application/pdf\r\n\r\n").encode("utf-8") + _pdf() + f"\r\n--{b}--\r\n".encode()
    r = client.post("/comercio/catalogo", content=cuerpo,
                    headers={**_hc(), "Content-Type": f"multipart/form-data; boundary={b}"})
    assert r.status_code == 200, r.text
    assert _archivo_de(r.json()["catalogo_url"]).read_bytes() == _pdf()


def test_las_respuestas_de_error_tienen_detail_de_texto(client, repo, comercio):
    """postFormData sólo muestra `detail` si es string; los 422 (lista) se arman aparte."""
    for r in (_subir(client, "/comercio/catalogo", _hc(), data=b"nada"),
              _subir(client, "/comercio/catalogo", _hc(), data=_pdf(9 * MB)),
              client.post("/comercio/catalogo", headers=_hc())):
        assert isinstance(r.json()["detail"], str), r.text


# ═════════════════════════════════════════════════════════════════════════════
# Permisos / multi-tenant
# ═════════════════════════════════════════════════════════════════════════════
def test_cada_comerciante_solo_toca_su_comercio(client, repo, comercio):
    repo.seed_comercio(id="com-g", slug="tienda-g", nombre="G", whatsapp="59170002222")
    u = _subir(client, "/comercio/catalogo", _hc("com-g")).json()["catalogo_url"]
    assert "/com-g/" in u and "/com-f/" not in u
    assert repo.comercios["com-g"]["catalogo_url"] == u
    assert "catalogo_url" not in repo.comercios["com-f"]
    client.put("/comercio/perfil", headers=_hc("com-g"), json={"tiene_pasero": True})
    assert "tiene_pasero" not in repo.comercios["com-f"]
    client.delete("/comercio/catalogo", headers=_hc("com-f"))
    assert _archivo_de(u).exists() and repo.comercios["com-g"]["catalogo_url"] == u


def test_el_id_en_la_url_del_agente_no_deja_saltar_de_ciudad(client, repo):
    repo.seed_comercio(id="com-ajeno", slug="local-ajeno", nombre="A", whatsapp="59170005555", ciudad_id="ciu-OTRA",
                       cargado_por="otro@bermejolive.com")
    h = _ha()
    assert _subir(client, "/campo/mis-comercios/com-ajeno/catalogo", h).status_code == 404
    assert client.delete("/campo/mis-comercios/com-ajeno/catalogo", headers=h).status_code == 404
    assert client.patch("/campo/mis-comercios/com-ajeno", headers=h,
                        json={"canal_wa_url": "https://x.com", "catalogo_url": "https://x.com/y"}).status_code == 404
    assert _todo_el_disco() == []
    assert "canal_wa_url" not in repo.comercios["com-ajeno"]


def test_agente_de_otra_ciudad_no_borra_el_pdf_de_un_comercio_ajeno(client, repo, comercio):
    u = _subir(client, "/campo/mis-comercios/com-f/catalogo", _ha()).json()["catalogo_url"]
    h = _ha(email="otro@bermejolive.com", ciudad="atlantida")
    assert client.delete("/campo/mis-comercios/com-f/catalogo", headers=h).status_code == 404
    assert client.patch("/campo/mis-comercios/com-f", headers=h, json={"catalogo_url": ""}).status_code == 404
    assert repo.comercios["com-f"]["catalogo_url"] == u and _archivo_de(u).exists()


@pytest.mark.parametrize("token", [
    "basura", "", "Bearer.x.y",
    auth.make_token("mod@x.com", rol="moderador"),                   # moderador: no tiene comercios.cargar
    auth.make_usuario_token("u-1", "59170009999"),                   # comprador
    comercio_token("com-f"),                                         # comerciante en endpoints de agente
])
def test_tokens_que_no_son_de_agente_no_pasan_por_los_endpoints_de_campo(client, repo, comercio, token):
    h = {"Authorization": f"Bearer {token}"}
    for r in (_subir(client, "/campo/mis-comercios/com-f/catalogo", h),
              client.delete("/campo/mis-comercios/com-f/catalogo", headers=h),
              client.patch("/campo/mis-comercios/com-f", headers=h, json={"tiene_pasero": True})):
        assert r.status_code in (401, 403), (token[:12], r.status_code)
    assert _todo_el_disco() == [] and "tiene_pasero" not in repo.comercios["com-f"]


@pytest.mark.parametrize("token", [
    "basura",
    auth.make_agente_token("agente@bermejolive.com", "bermejo"),
    auth.make_token("admin@x.com", rol="admin"),
    auth.make_usuario_token("u-1", "59170009999"),
])
def test_tokens_que_no_son_de_comercio_no_pasan_por_los_endpoints_de_comercio(client, repo, comercio, token):
    h = {"Authorization": f"Bearer {token}"}
    for r in (_subir(client, "/comercio/catalogo", h), client.delete("/comercio/catalogo", headers=h),
              client.put("/comercio/perfil", headers=h, json={"tiene_pasero": True})):
        assert r.status_code in (401, 403), (token[:12], r.status_code)
    assert _todo_el_disco() == []


def test_token_de_comercio_inexistente_es_404_y_no_escribe(client, repo):
    assert _subir(client, "/comercio/catalogo", _hc("fantasma")).status_code == 404
    assert client.delete("/comercio/catalogo", headers=_hc("fantasma")).status_code == 404
    assert _todo_el_disco() == []


def test_token_vencido_es_401(client, repo, comercio):
    import time

    import jwt as pyjwt
    tok = pyjwt.encode({"sub": "x@y.com", "email": "x@y.com", "rol": "comercio", "comercio_id": "com-f",
                        "exp": int(time.time()) - 10}, settings.jwt_secret, algorithm="HS256")
    assert _subir(client, "/comercio/catalogo", {"Authorization": f"Bearer {tok}"}).status_code == 401


# ═════════════════════════════════════════════════════════════════════════════
# Fallas de infraestructura
# ═════════════════════════════════════════════════════════════════════════════
def test_disco_lleno_o_sin_permiso_es_502_y_el_catalogo_anterior_queda(client, repo, comercio, monkeypatch):
    anterior = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]
    with monkeypatch.context() as m:
        # El archivo se escribe por trozos en la carpeta del comercio: si el disco
        # no deja ni crearla, tiene que ser un 502 claro y no un 500.
        m.setattr(Path, "mkdir", lambda self, *a, **k: (_ for _ in ()).throw(OSError("No space left on device")))
        r = _subir(client, "/comercio/catalogo", _hc())
    assert r.status_code == 502
    assert "probá de nuevo" in r.json()["detail"]
    assert repo.comercios["com-f"]["catalogo_url"] == anterior and _archivo_de(anterior).exists()


def test_si_borrar_el_archivo_viejo_falla_igual_responde_ok(client, repo, comercio, monkeypatch):
    _subir(client, "/comercio/catalogo", _hc())
    monkeypatch.setattr(Path, "unlink", lambda self, missing_ok=False: (_ for _ in ()).throw(PermissionError("bloqueado")))
    r = _subir(client, "/comercio/catalogo", _hc())
    assert r.status_code == 200, r.text
    assert repo.comercios["com-f"]["catalogo_url"] == r.json()["catalogo_url"]


def test_quitar_con_base_caida_no_borra_el_archivo(client, repo, comercio, monkeypatch):
    """Quitar actualiza la base ANTES de borrar el archivo: si la base falla, el PDF sigue."""
    u = _subir(client, "/comercio/catalogo", _hc()).json()["catalogo_url"]

    def falla(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "update_comercio", falla)
    with pytest.raises(RuntimeError):
        client.delete("/comercio/catalogo", headers=_hc())
    assert _archivo_de(u).exists() and repo.comercios["com-f"]["catalogo_url"] == u


def test_los_topes_del_codigo_coinciden_con_la_spec():
    assert svc.MAX_BYTES == 8 * 1024 * 1024
    assert svc.MAX_PEDIDO_MINIMO == 120
    assert svc._MSG_PESADO == "El catálogo puede pesar hasta 8 MB."
