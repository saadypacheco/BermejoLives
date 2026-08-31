"""Auth: hashing, tokens y guards de rol."""
import pytest

from app.core import auth


def test_hash_y_verify_password():
    h = auth.hash_password("comercio1234")
    assert h.startswith("pbkdf2_sha256$")
    assert auth.verify_password("comercio1234", h)
    assert not auth.verify_password("incorrecta", h)


def test_token_comercio_lleva_comercio_id():
    tok = auth.make_comercio_token("com-99", "x@y.com")
    claims = auth._decode(tok)
    assert claims["rol"] == "comercio"
    assert claims["comercio_id"] == "com-99"


def test_admin_login_ok(client):
    r = client.post("/auth/login", json={"email": "admin@bermejolive.com", "password": "bermejo1234"})
    assert r.status_code == 200
    assert r.json()["user"]["rol"] == "admin"


def test_admin_login_credenciales_malas(client):
    r = client.post("/auth/login", json={"email": "admin@bermejolive.com", "password": "mala"})
    assert r.status_code == 401


def test_comercio_no_puede_moderar(client):
    """Un token de comercio NO debe acceder a endpoints de moderación (403)."""
    from tests.conftest import comercio_token

    r = client.get("/moderacion/publicaciones", headers={"Authorization": f"Bearer {comercio_token()}"})
    assert r.status_code == 403


def test_sin_token_no_autenticado(client):
    assert client.get("/moderacion/publicaciones").status_code == 401


# ── El correo no distingue mayúsculas ────────────────────────────────────────
#
# El teclado del celular pone mayúscula en la primera letra solo. Un agente en
# la calle tipea "Agente@uruku.bo" sin verlo y el ingreso lo rechaza diciendo
# "credenciales incorrectas" — que lo manda a revisar la contraseña, la parte
# que estaba bien.

def test_login_admin_acepta_el_correo_en_mayusculas(client):
    from app.core.config import settings
    r = client.post("/auth/login", json={"email": settings.admin_email.upper(),
                                         "password": settings.admin_password})
    assert r.status_code == 200, r.text


def test_login_campo_acepta_el_correo_con_la_primera_en_mayuscula(client):
    from app.core.config import settings
    correo = settings.agente_email[0].upper() + settings.agente_email[1:]
    r = client.post("/auth/campo/login", json={"email": correo,
                                               "password": settings.agente_password})
    assert r.status_code == 200, r.text


def test_login_campo_acepta_espacios_de_mas(client):
    """Copiar y pegar arrastra un espacio adelante o atrás y no se ve."""
    from app.core.config import settings
    r = client.post("/auth/campo/login", json={"email": f"  {settings.agente_email} ",
                                               "password": settings.agente_password})
    assert r.status_code == 200, r.text


def test_la_contrasena_SI_distingue_mayusculas(client):
    """Sólo se relaja el correo. Una contraseña que ignora mayúsculas pierde
    buena parte de su fuerza, y ahí no hay teclado que justifique el riesgo."""
    from app.core.config import settings
    r = client.post("/auth/campo/login", json={"email": settings.agente_email,
                                               "password": settings.agente_password.upper()})
    assert r.status_code == 401
