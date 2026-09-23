"""El equipo, los roles y los permisos (0126).

Antes: admin, publicador y agente eran tres pares correo/clave en el `.env`,
compartidos, y lo que podía hacer cada uno estaba escrito endpoint por
endpoint (`require_admin` en 68 lugares). Ahora cada persona tiene su cuenta,
sus roles salen de la base, y cada endpoint pide un PERMISO.
"""
from app.core.permisos import ROLES_BASE, permisos_de_roles, tiene


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _crear(client, admin_token, **kw):
    cuerpo = {"email": "ana@uruku.bo", "password": "campo2026", "roles": ["agente"], **kw}
    return client.post("/admin/equipo", headers=_h(admin_token), json=cuerpo)


# ─────────────────────────────────────────────────────── el catálogo de permisos

def test_un_token_viejo_sigue_pudiendo_lo_mismo():
    """Los tokens emitidos antes de este cambio sólo llevan `rol`. Mientras no
    venzan tienen que seguir funcionando: un deploy no puede dejar a nadie
    afuera en medio de la jornada."""
    viejo_admin = {"rol": "admin"}
    viejo_agente = {"rol": "agente"}
    assert tiene(viejo_admin, "equipo") and tiene(viejo_admin, "pagos")
    assert tiene(viejo_agente, "comercios.cargar")
    assert not tiene(viejo_agente, "pagos")


def test_los_permisos_de_un_rol_salen_de_la_base_si_los_hay():
    """El catálogo de permisos vive en el código; qué permisos tiene cada rol,
    en la base. Un rol nuevo funciona sin tocar código."""
    de_la_base = {"cargador-sc": ["comercios.cargar", "lugares"]}
    assert permisos_de_roles(["cargador-sc"], de_la_base) == ["comercios.cargar", "lugares"]
    # Sin catálogo de la base, los roles del sistema.
    assert permisos_de_roles(["agente"]) == ROLES_BASE["agente"]["permisos"]


# ─────────────────────────────────────────────────────── el equipo

def test_crear_alguien_del_equipo_y_que_entre(client, repo, admin_token):
    r = _crear(client, admin_token, email="Ana@uruku.bo", nombre="Ana", ciudad_slug="santa-cruz")
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["email"] == "ana@uruku.bo"      # el correo, en minúsculas
    assert "password_hash" not in r.json()["usuario"]          # nunca sale el hash

    login = client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "campo2026"})
    assert login.status_code == 200
    assert login.json()["agente"]["ciudad"] == "santa-cruz"
    assert login.json()["user"]["permisos"] == ["comercios.cargar"]
    # Con la clave mal, no. Dos veces el mismo correo, no. Sin rol, no.
    assert client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "otra"}).status_code == 401
    assert _crear(client, admin_token, email="ana@uruku.bo").status_code == 409
    assert _crear(client, admin_token, email="otro@uruku.bo", roles=[]).status_code == 400
    assert _crear(client, admin_token, email="otro@uruku.bo", password="123").status_code == 400


def test_el_rol_decide_que_puede_hacer(client, repo, admin_token):
    """Un agente no entra al panel; un moderador sí, pero no a la plata."""
    _crear(client, admin_token, email="ana@uruku.bo", roles=["agente"])
    _crear(client, admin_token, email="moni@uruku.bo", password="moni2026", roles=["moderador"])
    t_agente = client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "campo2026"}).json()["access_token"]
    t_moni = client.post("/auth/login", json={"email": "moni@uruku.bo", "password": "moni2026"}).json()["access_token"]

    # El agente: carga comercios y nada más.
    assert client.get("/admin/equipo", headers=_h(t_agente)).status_code == 403
    assert client.get("/admin/pagos/pendientes", headers=_h(t_agente)).status_code == 403
    # La moderadora: modera, pero no toca la plata ni el equipo.
    assert client.get("/moderacion/publicaciones?estado=pendiente", headers=_h(t_moni)).status_code == 200
    assert client.get("/admin/pagos/pendientes", headers=_h(t_moni)).status_code == 403
    assert client.get("/admin/equipo", headers=_h(t_moni)).status_code == 403
    # El admin, todo.
    assert client.get("/admin/equipo", headers=_h(admin_token)).status_code == 200


def test_apagar_a_alguien_lo_deja_afuera(client, repo, admin_token):
    u = _crear(client, admin_token, email="beto@uruku.bo").json()["usuario"]
    assert client.post("/auth/campo/login", json={"email": "beto@uruku.bo", "password": "campo2026"}).status_code == 200
    client.put(f"/admin/equipo/{u['id']}", headers=_h(admin_token),
               json={"email": "beto@uruku.bo", "activo": False, "roles": ["agente"]})
    assert client.post("/auth/campo/login", json={"email": "beto@uruku.bo", "password": "campo2026"}).status_code == 401


def test_la_cuenta_del_env_sigue_andando(client):
    """La llave de emergencia: si alguien se deja afuera a sí mismo, entra por acá."""
    from app.core.config import settings
    r = client.post("/auth/login", json={"email": settings.admin_email, "password": settings.admin_password})
    assert r.status_code == 200 and r.json()["user"]["rol"] == "admin"


# ─────────────────────────────────────────────────────── los roles

def test_crear_un_rol_nuevo_desde_el_panel(client, repo, admin_token):
    r = client.put("/admin/roles/cargador-sc", headers=_h(admin_token), json={
        "slug": "cargador-sc", "nombre": "Cargador de Santa Cruz",
        "permisos": ["comercios.cargar", "lugares", "facturar-la-luna"]})
    assert r.status_code == 200
    # El permiso inventado no entra: el catálogo lo decide el código.
    assert r.json()["rol"]["permisos"] == ["comercios.cargar", "lugares"]

    _crear(client, admin_token, email="luis@uruku.bo", roles=["cargador-sc"])
    t = client.post("/auth/campo/login", json={"email": "luis@uruku.bo", "password": "campo2026"}).json()
    assert t["user"]["permisos"] == ["comercios.cargar", "lugares"]
    # `lugares` en el rol le abre el ABM de lugares; el resto del panel, no.
    assert client.get("/admin/lugares", headers=_h(t["access_token"])).status_code == 200
    assert client.get("/admin/equipo", headers=_h(t["access_token"])).status_code == 403


def test_un_rol_del_sistema_no_se_borra(client, repo, admin_token):
    assert client.delete("/admin/roles/admin", headers=_h(admin_token)).status_code == 400
    client.put("/admin/roles/temporal", headers=_h(admin_token), json={"slug": "temporal", "nombre": "Temporal", "permisos": []})
    assert client.delete("/admin/roles/temporal", headers=_h(admin_token)).status_code == 200
