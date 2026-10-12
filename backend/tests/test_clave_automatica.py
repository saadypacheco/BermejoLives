"""Clave automática del comercio y código sólo en el admin (docs/clave-automatica.md).

Criterios de aceptación que cubre (los del backend):
  1. Un alta de agente devuelve una clave `PREFIJO-XXXXXX` y con celular + esa clave
     (en minúsculas, con o sin guion) se entra.
  2. Sin cartel -> prefijo de lo que vende; sin nada -> `LOCAL`; nunca `URUKU`.
  3. Una clave vieja de 6 números sigue entrando.
  4. «Generar clave nueva» del admin invalida la anterior; sin `comercios.cuenta` -> 403.
  5. (backend) Ninguna respuesta de /comercio/*, /campo/* ni del autoregistro trae el código.
  6. La ingesta con `URUKU-XXXX` sigue funcionando.
La migración 0148 se prueba en test_comercios_columnas_publicas.py.
"""
import json
import re
from io import BytesIO

import pytest
from PIL import Image

from app.core import auth, clave_comercio
from app.core.codigo import formatear
from app.services import ingest

ALFABETO = set(clave_comercio.ALFABETO)
FORMATO = re.compile(r"^[A-Z0-9]{1,8}-[2-9A-HJKMNP-Z]{6}$")


# ═════════════════════════════════════════════════════════ el prefijo
@pytest.mark.parametrize("nombre,esperado", [
    ("Boutique Lucía", "BOUTIQUE"),
    ("La Casa del Jean", "CASA"),                       # sin artículos
    ("El Rápido", "RAPIDO"),
    ("Mi Tu Su Un Una Los Las Lo De Del Y E Ferretería", "FERRETER"),   # todos los artículos, y máximo 8
    ("de la y el Gomería", "GOMERIA"),
    ("Ñandú Calzados", "NANDU"),                        # Ñ -> N, sin tildes
    ("Peñarol", "PENAROL"),
    ("Óptica Ángel", "OPTICA"),
    ("D'Elegance", "DELEGANC"),                         # el apóstrofe no parte la palabra
    ("&  Co. Hogar", "CO"),
    ("2 Hermanos", "2"),
    ("Supercalifragilistico", "SUPERCAL"),              # máximo 8
    ("  Zapatos   Ruiz  ", "ZAPATOS"),
])
def test_prefijo_con_nombre(nombre, esperado):
    p = clave_comercio.prefijo_de(nombre)
    assert p == esperado
    assert len(p) <= 8 and re.fullmatch(r"[A-Z0-9]+", p)


def test_el_prefijo_nunca_es_URUKU():
    assert clave_comercio.prefijo_de("URUKU") == "LOCAL"
    assert clave_comercio.prefijo_de("Uruku Bazar") == "BAZAR"
    assert clave_comercio.prefijo_de("uruku") == "LOCAL"
    assert clave_comercio.prefijo_de(None, sin_cartel=True, subcategoria="uruku") == "LOCAL"
    for _ in range(50):
        assert not clave_comercio.generar_clave("Uruku Tienda").startswith("URUKU")


def test_sin_cartel_el_prefijo_sale_de_la_subcategoria():
    # El nombre que arma la base («Ropa femenina · Calle 23») NO cuenta si no tiene cartel.
    p = clave_comercio.prefijo_de("Ropa femenina · Calle 23 de Marzo", sin_cartel=True,
                                  subcategoria="jean para dama", rubro="Ropa")
    assert p == "JEAN"
    assert clave_comercio.prefijo_de("x", sin_cartel=True, subcategoria="la zapatería") == "ZAPATERI"


def test_sin_cartel_y_sin_subcategoria_sale_del_rubro():
    assert clave_comercio.prefijo_de("Comercio 437", sin_cartel=True, subcategoria=None, rubro="Ropa y calzado") == "ROPA"
    assert clave_comercio.prefijo_de("Comercio 437", sin_cartel=True, subcategoria="  ", rubro="Gastronomía") == "GASTRONO"


@pytest.mark.parametrize("kw", [
    dict(nombre=None),
    dict(nombre=""),
    dict(nombre="   "),
    dict(nombre="El de la"),                            # sólo artículos
    dict(nombre="&&& ---"),                             # sin letras utilizables
    dict(nombre="Comercio 5", sin_cartel=True),         # sin cartel y sin qué vende
    dict(nombre=None, sin_cartel=True, subcategoria="", rubro=None),
    dict(nombre=None, sin_cartel=True, subcategoria="de la", rubro="el"),
])
def test_sin_nada_utilizable_es_LOCAL(kw):
    assert clave_comercio.prefijo_de(**kw) == "LOCAL"


# ═════════════════════════════════════════════════════════ el azar
def test_el_azar_son_6_del_alfabeto_sin_confundibles():
    vistos = set()
    for _ in range(400):
        a = clave_comercio.generar_azar()
        assert len(a) == 6 and set(a) <= ALFABETO
        assert not (set(a) & set("01OIL"))
        vistos.add(a)
    assert len(vistos) > 390                             # aleatorio, no un contador


def test_la_clave_tiene_el_formato_prefijo_guion_azar():
    for nombre in ("Boutique", "La Casa del Jean", "Ñandú", None):
        c = clave_comercio.generar_clave(nombre)
        assert FORMATO.match(c), c
    assert clave_comercio.generar_clave("Boutique").startswith("BOUTIQUE-")
    assert len(clave_comercio.generar_clave("Boutique")) == len("BOUTIQUE-K7M2P9")


def test_el_azar_usa_secrets(monkeypatch):
    import secrets
    llamadas = []
    original = secrets.choice
    monkeypatch.setattr(clave_comercio.secrets, "choice", lambda s: llamadas.append(1) or original(s))
    clave_comercio.generar_azar()
    assert len(llamadas) == 6


# ═════════════════════════════════════════════════════════ normalizar y comparar
@pytest.mark.parametrize("tipeada", [
    "BOUTIQUE-K7M2P9", "boutique-k7m2p9", "boutique k7m2p9", "  Boutique - K7M2P9  ",
    "BOUTIQUEK7M2P9", "boutique_k7m2p9", "bou tique-k7 m2p9", "BOUTIQUE–K7M2P9",
])
def test_normalizar_ignora_mayusculas_espacios_y_guiones(tipeada):
    assert clave_comercio.normalizar(tipeada) == "BOUTIQUEK7M2P9"
    h = clave_comercio.hash_clave("BOUTIQUE-K7M2P9")
    assert clave_comercio.clave_coincide(tipeada, h) is True


def test_la_clave_vieja_de_6_numeros_normaliza_a_si_misma():
    assert clave_comercio.normalizar("004217") == "004217"
    h = auth.hash_password("004217")                      # como se guardaba antes
    assert clave_comercio.clave_coincide("004217", h) is True
    assert clave_comercio.clave_coincide("004 217", h) is True
    assert clave_comercio.clave_coincide("004218", h) is False


def test_lo_que_no_tiene_forma_de_clave_no_coincide_ni_gasta_pbkdf2(monkeypatch):
    h = clave_comercio.hash_clave("BOUTIQUE-K7M2P9")
    gastos = []
    monkeypatch.setattr(auth, "verify_password", lambda *a: gastos.append(a) or False)
    for basura in (None, "", "   ", "12345", "A" * 25, "x" * 100, "boutique!k7m2p9", "ñandú-k7m2p9"):
        assert clave_comercio.clave_coincide(basura, h) is False
    assert gastos == []
    assert clave_comercio.clave_coincide("BOUTIQUE-K7M2P9", None) is False


def test_se_guarda_el_hash_y_no_la_clave():
    h = clave_comercio.hash_clave("Boutique-K7M2P9")
    assert "K7M2P9" not in h and "BOUTIQUE" not in h.upper()
    assert clave_comercio.hash_clave("boutique k7m2p9") != h          # sal distinta en cada hash, aunque sea la misma clave


# ═════════════════════════════════════════════════════════ helpers HTTP
def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("test.jpg", buf, "image/jpeg")}


def _login_agente(client):
    return client.post("/auth/campo/login", json={"email": "agente@bermejolive.com",
                                                  "password": "campo1234"}).json()["access_token"]


def _alta(client, whatsapp="70002222", **extra):
    datos = {"nombre": "Boutique Lucía", "whatsapp": whatsapp, "modalidad": "minorista",
             "lat": "-22.7361", "lng": "-64.3433", **extra}
    return client.post("/campo/comercio", headers=_hdr(_login_agente(client)), data=datos, files=_foto())


def _ingresar(client, whatsapp, clave):
    return client.post("/auth/comercio/ingresar", json={"whatsapp": whatsapp, "clave": clave})


def _con_cuenta(repo, **kw):
    c = repo.seed_comercio(activo=True, **{"id": "com-1", "slug": "boutique", "nombre": "Boutique Lucía",
                                          "whatsapp": "59170123456", **kw})
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    return c, cuenta


def _con_codigo_en_texto(valor, codigo):
    """¿Aparece el código (URUKU-XXXX o XXXX) en cualquier parte de la respuesta?"""
    texto = json.dumps(valor, ensure_ascii=False)
    return codigo in texto or formatear(codigo) in texto


def _sin_claves_codigo(obj, ruta="$"):
    """Ninguna llave `codigo` ni `codigo_formateado` en todo el JSON."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            assert k not in ("codigo", "codigo_formateado"), f"{ruta}.{k}"
            _sin_claves_codigo(v, f"{ruta}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _sin_claves_codigo(v, f"{ruta}[{i}]")


# ═════════════════════════════════════════════════════════ criterio 1: alta de agente
def test_el_alta_del_agente_devuelve_la_clave_y_con_ella_se_entra(client, repo):
    r = _alta(client)
    assert r.status_code == 200, r.text
    d = r.json()
    clave = d["clave"]
    assert FORMATO.match(clave) and clave.startswith("BOUTIQUE-"), clave
    assert d["clave_inicial"] == clave                       # el nombre de antes, mismo valor
    assert "clave" not in d["comercio"] and "clave_inicial" not in d["comercio"]   # sólo en la raíz
    assert r.headers["cache-control"] == "no-store"
    # Con celular + clave (como se escribe, en minúsculas, con o sin guion, con espacios) entra.
    for tipeada in (clave, clave.lower(), clave.replace("-", ""), clave.replace("-", " ").lower(), f"  {clave}  "):
        e = _ingresar(client, "70002222", tipeada)
        assert e.status_code == 200, (tipeada, e.text)
        assert e.json()["comercio"]["id"] == d["comercio"]["id"]
    # Y el hash guardado es el de la forma normalizada.
    (cuenta,) = [u for u in repo.usuarios.values() if u["comercio_id"] == d["comercio"]["id"]]
    assert clave_comercio.clave_coincide(clave, cuenta["clave_hash"])
    assert clave not in json.dumps(cuenta)                   # no se guardó la clave en claro


def test_una_clave_equivocada_o_de_otro_formato_da_401(client, repo):
    clave = _alta(client).json()["clave"]
    azar = clave.split("-")[1]
    for mala in (f"OTRO-{azar}", clave[:-1] + ("2" if clave[-1] != "2" else "3"), "BOUTIQUE", "123456", ""):
        assert _ingresar(client, "70002222", mala).status_code == 401, mala


@pytest.mark.parametrize("nombre,prefijo", [
    ("La Casa del Jean", "CASA-"),
    ("Ñandú Calzados", "NANDU-"),
    ("Óptica Ángel", "OPTICA-"),
])
def test_el_alta_arma_el_prefijo_con_el_nombre(client, repo, nombre, prefijo):
    clave = _alta(client, nombre=nombre).json()["clave"]
    assert clave.startswith(prefijo) and FORMATO.match(clave)


def test_alta_sin_cartel_con_subcategoria_toma_el_prefijo_de_lo_que_vende(client, repo, monkeypatch):
    """Sin nombre -> sin_cartel. La subcategoría la completa la IA después; si ya está, manda."""
    original = repo.crear_comercio

    def crear(row):
        c = original(row)
        c["subcategoria"] = "jean para dama"         # lo que la base/IA dejó
        c["nombre"] = "Ropa · Calle 23 de Marzo"      # el nombre que arma el trigger
        return c

    monkeypatch.setattr(repo, "crear_comercio", crear)
    r = _alta(client, nombre="")
    assert r.status_code == 200, r.text
    assert r.json()["clave"].startswith("JEAN-")


def test_alta_sin_cartel_con_rubro_toma_el_prefijo_del_rubro(client, repo):
    r = _alta(client, nombre="", rubro_slugs=["gomeria"])
    assert r.status_code == 200, r.text
    assert r.json()["clave"].startswith("GOMERIA-"), r.json()["clave"]


def test_alta_sin_cartel_y_sin_nada_es_LOCAL(client, repo):
    r = _alta(client, nombre="")
    assert r.status_code == 200, r.text
    assert r.json()["clave"].startswith("LOCAL-")
    assert not r.json()["clave"].startswith("URUKU")


def test_si_la_cuenta_falla_el_alta_no_se_cae_y_no_hay_clave(client, repo, monkeypatch):
    def roto(_cid):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "asegurar_comercio_usuario", roto)
    r = _alta(client)
    assert r.status_code == 200, r.text
    assert r.json()["clave"] is None and r.json()["clave_inicial"] is None


def test_la_clave_no_va_a_los_logs(client, repo):
    import structlog
    with structlog.testing.capture_logs() as logs:
        clave = _alta(client).json()["clave"]
        _ingresar(client, "70002222", clave)
        _ingresar(client, "70002222", "BOUTIQUE-ZZZZZZ")
    azar = clave.split("-")[1]
    assert logs, "esperaba eventos de log"
    assert clave not in json.dumps(logs, default=str) and azar not in json.dumps(logs, default=str)


# ═════════════════════════════════════════════════════════ criterio 3: la vieja sigue
def test_una_clave_vieja_de_6_numeros_sigue_entrando(client, repo):
    c, cuenta = _con_cuenta(repo)
    cuenta["clave_hash"] = auth.hash_password("004217")      # como la guardaba la versión anterior
    r = _ingresar(client, "70123456", "004217")
    assert r.status_code == 200 and r.json()["comercio"]["id"] == c["id"]
    assert _ingresar(client, "70123456", "004218").status_code == 401


def test_pedir_otra_clave_la_deja_en_el_formato_nuevo_y_la_vieja_deja_de_servir(client, repo):
    c, cuenta = _con_cuenta(repo)
    cuenta["clave_hash"] = auth.hash_password("004217")
    r = client.post("/comercio/clave", headers=_hdr(auth.make_comercio_token(c["id"], "x@y.com")))
    assert r.status_code == 200, r.text
    nueva = r.json()["clave"]
    assert FORMATO.match(nueva) and nueva.startswith("BOUTIQUE-")
    assert r.headers["cache-control"] == "no-store"
    assert _ingresar(client, "70123456", nueva.lower()).status_code == 200
    assert _ingresar(client, "70123456", "004217").status_code == 401


def test_la_confirmacion_por_whatsapp_sin_clave_previa_da_el_formato_nuevo(client, repo):
    c, cuenta = _con_cuenta(repo)
    cod = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).json()["codigo"]
    assert ingest.handle_message({
        "event": "message", "session": "obs@c.us",
        "payload": {"id": "wa-conf", "from": "59170123456@c.us", "fromMe": False,
                    "body": f"CONFIRMAR-{cod}", "type": "text", "timestamp": 1700000000},
    }, repo)["confirmado"] is True
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70123456", "codigo": cod})
    assert r.status_code == 200, r.text
    nueva = r.json()["clave_nueva"]
    assert FORMATO.match(nueva) and nueva.startswith("BOUTIQUE-"), nueva
    assert _ingresar(client, "70123456", nueva.lower().replace("-", " ")).status_code == 200


def test_en_un_numero_con_dos_comercios_cada_clave_abre_el_suyo(client, repo):
    a = repo.seed_comercio(id="com-a", slug="a", nombre="Puesto A", whatsapp="59170123456", activo=True)
    b = repo.seed_comercio(id="com-b", slug="b", nombre="Puesto A", whatsapp="70123456", activo=True)
    for c in (a, b):
        repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    ca = client.post("/comercio/clave", headers=_hdr(auth.make_comercio_token("com-a", "x@y.com"))).json()["clave"]
    cb = client.post("/comercio/clave", headers=_hdr(auth.make_comercio_token("com-b", "x@y.com"))).json()["clave"]
    assert ca.startswith("PUESTO-") and cb.startswith("PUESTO-") and ca != cb
    assert _ingresar(client, "70123456", ca).json()["comercio"]["id"] == "com-a"
    assert _ingresar(client, "70123456", cb).json()["comercio"]["id"] == "com-b"


def test_la_clave_nueva_nunca_coincide_con_la_de_otro_comercio_del_numero(client, repo, monkeypatch):
    a = repo.seed_comercio(id="com-a", slug="a", nombre="Puesto", whatsapp="59170123456", activo=True)
    b = repo.seed_comercio(id="com-b", slug="b", nombre="Puesto", whatsapp="70123456", activo=True)
    for c in (a, b):
        repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    ca = client.post("/comercio/clave", headers=_hdr(auth.make_comercio_token("com-a", "x@y.com"))).json()["clave"]
    azar_a = ca.split("-")[1]
    # El azar «saca» primero el de A, dos veces: tiene que descartarlo.
    salidas = iter([azar_a, azar_a, "K7M2P9"])
    monkeypatch.setattr(clave_comercio, "generar_azar", lambda: next(salidas))
    cb = client.post("/comercio/clave", headers=_hdr(auth.make_comercio_token("com-b", "x@y.com"))).json()["clave"]
    assert cb == "PUESTO-K7M2P9"


# ═════════════════════════════════════════════════════════ criterio 4: el admin
# El admin valida que el id del comercio sea un UUID (404 si no): los ids de los tests, también.
ID_COMERCIO = "5f0c1b7e-3a2d-4c8e-9b1f-0a6d2e4c7b91"


def _admin_con(permisos, email="m@uruku.bo"):
    return auth.make_token(email, rol="moderador", permisos=permisos)


def test_el_admin_genera_una_clave_nueva_y_la_anterior_deja_de_servir(client, repo, admin_token):
    c, cuenta = _con_cuenta(repo, id=ID_COMERCIO)
    cuenta["clave_hash"] = auth.hash_password("004217")
    assert _ingresar(client, "70123456", "004217").status_code == 200

    r = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"clave"}
    nueva = r.json()["clave"]
    assert FORMATO.match(nueva) and nueva.startswith("BOUTIQUE-")
    assert r.headers["cache-control"] == "no-store"

    assert _ingresar(client, "70123456", "004217").status_code == 401          # la anterior ya no sirve
    assert _ingresar(client, "70123456", nueva.lower()).status_code == 200      # la nueva sí

    # Otra vez: la que acaba de ver deja de servir.
    r2 = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    assert r2.json()["clave"] != nueva
    assert _ingresar(client, "70123456", nueva).status_code == 401
    assert _ingresar(client, "70123456", r2.json()["clave"]).status_code == 200


def test_el_admin_destraba_al_dueno_bloqueado_por_fallos(client, repo, admin_token):
    c, cuenta = _con_cuenta(repo, id=ID_COMERCIO)
    cuenta["clave_hash"] = clave_comercio.hash_clave("BOUTIQUE-K7M2P9")
    for _ in range(5):
        assert _ingresar(client, "70123456", "BOUTIQUE-ZZZZZZ").status_code == 401
    assert _ingresar(client, "70123456", "BOUTIQUE-K7M2P9").status_code == 429        # bloqueado 15 min
    nueva = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token)).json()["clave"]
    assert _ingresar(client, "70123456", nueva).status_code == 200                    # los fallos quedaron obsoletos


def test_el_admin_crea_la_cuenta_si_el_comercio_no_tenia(client, repo, admin_token):
    c = repo.seed_comercio(id=ID_COMERCIO, slug="sin-cuenta", nombre="Sin Cuenta", whatsapp="59171112222", activo=True)
    assert not repo.usuarios
    r = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    assert r.status_code == 200 and r.json()["clave"].startswith("SIN-")
    assert _ingresar(client, "71112222", r.json()["clave"]).status_code == 200


def test_el_admin_con_un_comercio_inexistente_da_404(client, repo, admin_token):
    assert client.post("/admin/comercio/no-existe/clave", headers=_hdr(admin_token)).status_code == 404


def test_el_moderador_con_comercios_cuenta_puede(client, repo):
    c, _u = _con_cuenta(repo, id=ID_COMERCIO)
    r = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(_admin_con(["comercios.cuenta"])))
    assert r.status_code == 200 and "clave" in r.json()


def test_sin_comercios_cuenta_es_403_y_no_toca_la_clave(client, repo):
    c, cuenta = _con_cuenta(repo, id=ID_COMERCIO)
    cuenta["clave_hash"] = auth.hash_password("004217")
    sin_permiso = {
        "sin permisos": _admin_con([]),
        "solo editar": _admin_con(["comercios.editar", "moderar", "panel"]),
        "publicador (rol del sistema)": auth.make_publicador_token("pub@uruku.bo"),
        "agente": auth.make_agente_token("agente@bermejolive.com"),
        "comercio": auth.make_comercio_token(c["id"], "x@y.com"),
    }
    for quien, token in sin_permiso.items():
        r = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(token))
        assert r.status_code == 403, (quien, r.status_code, r.text)
        assert "clave" not in r.json()
    assert client.post(f"/admin/comercio/{c['id']}/clave").status_code in (401, 403)       # sin token
    assert _ingresar(client, "70123456", "004217").status_code == 200                      # intacta


def test_el_publicador_del_catalogo_de_roles_no_tiene_el_permiso():
    from app.core.permisos import ROLES_BASE
    assert "comercios.cuenta" not in ROLES_BASE["publicador"]["permisos"]
    assert "comercios.cuenta" in ROLES_BASE["moderador"]["permisos"]


# ═════════════════════════════════════════════════════════ criterio 5: el código sólo es del admin
def test_el_alta_de_campo_no_devuelve_el_codigo(client, repo):
    r = _alta(client)
    assert r.status_code == 200
    (c,) = repo.comercios.values()
    assert c["codigo"]                                    # existe en la base...
    _sin_claves_codigo(r.json())
    assert not _con_codigo_en_texto(r.json(), c["codigo"])  # ...y no sale por acá


def test_el_autoregistro_no_devuelve_el_codigo_pero_si_la_clave(client, repo):
    r = client.post("/auth/comercio/registro", files=_foto(),
                    data={"nombre": "Mi Tienda Linda", "whatsapp": "70001111", "lat": "-22.7", "lng": "-64.3"})
    assert r.status_code == 200, r.text
    (c,) = repo.comercios.values()
    _sin_claves_codigo(r.json())
    assert not _con_codigo_en_texto(r.json(), c["codigo"])
    clave = r.json()["clave_inicial"]
    assert FORMATO.match(clave) and clave.startswith("TIENDA-"), clave      # «Mi» es artículo
    assert _ingresar(client, "70001111", clave.lower()).status_code == 200


def test_ninguna_respuesta_de_comercio_ni_campo_trae_el_codigo(client, repo):
    """Recorre las lecturas y escrituras del comerciante y del agente: ni la llave ni el valor."""
    r = _alta(client)
    com_id = r.json()["comercio"]["id"]
    clave = r.json()["clave"]
    codigo = repo.comercios[com_id]["codigo"]
    token = _ingresar(client, "70002222", clave).json()["access_token"]
    h = _hdr(token)
    agente = _hdr(_login_agente(client))

    respuestas = {
        "GET /comercio/perfil": client.get("/comercio/perfil", headers=h),
        "PUT /comercio/perfil": client.put("/comercio/perfil", headers=h, json={"horario": "Lun-Vie 9 a 18"}),
        "GET /comercio/suscripcion": client.get("/comercio/suscripcion", headers=h),
        "GET /comercio/metricas": client.get("/comercio/metricas", headers=h),
        "GET /comercio/mis-publicaciones": client.get("/comercio/mis-publicaciones", headers=h),
        "GET /comercio/productos": client.get("/comercio/productos", headers=h),
        "GET /comercio/mensajes": client.get("/comercio/mensajes", headers=h),
        "GET /comercio/fotos": client.get("/comercio/fotos", headers=h),
        "GET /comercio/videos": client.get("/comercio/videos", headers=h),
        "POST /comercio/clave": (clave_nueva := client.post("/comercio/clave", headers=h)),
        # Cambiar la clave cierra la sesión de antes (0149): la segunda va con el token nuevo.
        "POST /auth/comercio/ingresar": _ingresar(client, "70002222", client.post(
            "/comercio/clave", headers=_hdr(clave_nueva.json()["access_token"])).json()["clave"]),
        "GET /campo/mis-comercios": client.get("/campo/mis-comercios", headers=agente),
        "GET /campo/mis-comercios/{id}": client.get(f"/campo/mis-comercios/{com_id}", headers=agente),
        "PATCH /campo/mis-comercios/{id}": client.patch(f"/campo/mis-comercios/{com_id}", headers=agente,
                                                        json={"horario": "Lun-Sáb 8 a 20"}),
        "POST /campo/mis-comercios/{id}/foto": client.post(f"/campo/mis-comercios/{com_id}/foto",
                                                           headers=agente, files=_foto()),
        "GET /campo/mis-comercios/{id}/fotos": client.get(f"/campo/mis-comercios/{com_id}/fotos", headers=agente),
    }
    vistas = 0
    for nombre, resp in respuestas.items():
        if resp.status_code != 200:                     # alguna puede no aplicar al fake; lo que sí responde, limpio
            continue
        vistas += 1
        _sin_claves_codigo(resp.json(), nombre)
        assert not _con_codigo_en_texto(resp.json(), codigo), nombre
    assert vistas >= 10, {k: v.status_code for k, v in respuestas.items()}
    # Las que más importan, sí o sí 200.
    for clave_ok in ("GET /comercio/perfil", "PUT /comercio/perfil", "GET /campo/mis-comercios",
                     "GET /campo/mis-comercios/{id}", "PATCH /campo/mis-comercios/{id}",
                     "POST /campo/mis-comercios/{id}/foto"):
        assert respuestas[clave_ok].status_code == 200, (clave_ok, respuestas[clave_ok].text)


def test_el_perfil_sigue_trayendo_lo_demas(client, repo):
    c, cuenta = _con_cuenta(repo)
    cuenta["clave_hash"] = clave_comercio.hash_clave("BOUTIQUE-K7M2P9")
    token = _ingresar(client, "70123456", "boutique-k7m2p9").json()["access_token"]
    p = client.get("/comercio/perfil", headers=_hdr(token)).json()
    assert p["id"] == c["id"] and p["nombre"] == "Boutique Lucía" and "rubro_slugs" in p
    assert "codigo" not in p and "codigo_formateado" not in p


def test_la_confirmacion_por_whatsapp_sigue_usando_su_codigo_de_6_digitos(client, repo):
    """`codigo` en /auth/comercio/recuperar NO es el URUKU-XXXX: es el CONFIRMAR-XXXXXX de un solo uso."""
    _con_cuenta(repo)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"})
    assert r.status_code == 200
    assert re.fullmatch(r"\d{6}", r.json()["codigo"])
    assert "codigo_formateado" not in r.json()


def test_el_admin_si_sigue_viendo_el_codigo(client, repo, admin_token):
    c = repo.seed_comercio(id="com-1", slug="boutique", nombre="Boutique Lucía", whatsapp="59170123456",
                           activo=True, codigo="K7M2")
    r = client.get("/moderacion/comercios?todos=true", headers=_hdr(admin_token))
    assert r.status_code == 200, r.text
    item = next(i for i in r.json()["items"] if i.get("slug") == "boutique")
    assert item["codigo"] == "K7M2"
    assert c["codigo"] == "K7M2"


# ═════════════════════════════════════════════════════════ criterio 6: la ingesta
def _ingestar(repo, phone, body, msg_id="msg-1"):
    return ingest.handle_message({
        "event": "message", "session": "obs@c.us",
        "payload": {"id": msg_id, "from": f"{phone}@c.us", "fromMe": False,
                    "body": body, "type": "text", "timestamp": 1700000000},
    }, repo)


def test_la_ingesta_por_codigo_sigue_andando(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 oferta: taladro a 300")
    pubs = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]]
    assert len(pubs) == 1
    assert pubs[0]["identidad_origen"] == "codigo" and pubs[0]["codigo_recibido"] == "K7M2"
    assert pubs[0]["estado"] == "pendiente"                  # por código nunca publica directo


def test_la_clave_no_se_confunde_con_el_codigo_en_la_ingesta(repo):
    """Una clave `PREFIJO-AZAR` en un mensaje no identifica a nadie ni crea nada."""
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    antes = len(repo.publicaciones)
    _ingestar(repo, "59177777777", "oferta FERRETER-K7M2P9 taladro a 300")
    assert [p for p in repo.publicaciones[antes:] if p.get("comercio_id") == c["id"]] == []
