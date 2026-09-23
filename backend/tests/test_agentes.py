"""Agentes de campo: varios, cada uno con su ciudad, creados desde el panel.

Antes había uno solo, con el usuario y la clave en el `.env`. Con más de una
ciudad eso no alcanza: hace falta saber quién cargó qué, y que lo que carga
un agente de Santa Cruz nazca en Santa Cruz."""


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_crear_un_agente_y_que_entre_con_su_ciudad(client, repo, admin_token):
    r = client.post("/admin/agentes", headers=_h(admin_token), json={
        "email": "Ana@uruku.bo", "password": "campo2026", "nombre": "Ana", "ciudad_slug": "santa-cruz"})
    assert r.status_code == 200, r.text
    assert r.json()["agente"]["email"] == "ana@uruku.bo"       # el correo, en minúsculas
    assert "password_hash" not in r.json()["agente"]           # nunca sale el hash
    # Entra con su correo y su clave, y el token dice su ciudad.
    login = client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "campo2026"})
    assert login.status_code == 200 and login.json()["agente"]["ciudad"] == "santa-cruz"
    # Con la clave mal, no.
    assert client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "otra"}).status_code == 401
    # Dos veces el mismo correo, no.
    assert client.post("/admin/agentes", headers=_h(admin_token), json={
        "email": "ana@uruku.bo", "password": "campo2026"}).status_code == 409
    # Una clave corta, tampoco.
    assert client.post("/admin/agentes", headers=_h(admin_token), json={
        "email": "otro@uruku.bo", "password": "123"}).status_code == 400
    # El listado los muestra con su ciudad y sin contraseñas.
    items = client.get("/admin/agentes", headers=_h(admin_token)).json()["items"]
    assert items[0]["ciudad_nombre"] == "Santa Cruz" and "password_hash" not in items[0]


def test_apagar_un_agente_lo_deja_afuera(client, repo, admin_token):
    a = client.post("/admin/agentes", headers=_h(admin_token), json={
        "email": "beto@uruku.bo", "password": "campo2026"}).json()["agente"]
    assert client.post("/auth/campo/login", json={"email": "beto@uruku.bo", "password": "campo2026"}).status_code == 200
    client.put(f"/admin/agentes/{a['id']}", headers=_h(admin_token), json={"email": "beto@uruku.bo", "activo": False})
    assert client.post("/auth/campo/login", json={"email": "beto@uruku.bo", "password": "campo2026"}).status_code == 401


def test_la_cuenta_del_env_sigue_andando(client):
    """La que está en los teléfonos hoy: un deploy no le corta el trabajo a nadie."""
    from app.core.config import settings
    r = client.post("/auth/campo/login", json={"email": settings.agente_email, "password": settings.agente_password})
    assert r.status_code == 200 and r.json()["agente"].get("ciudad") is None


def test_lo_que_carga_un_agente_nace_donde_esta_el_local(client, repo, admin_token, monkeypatch):
    """La ciudad la deciden las coordenadas, no el selector del formulario:
    así nadie carga treinta locales en la ciudad equivocada."""
    from io import BytesIO
    from PIL import Image
    client.post("/admin/agentes", headers=_h(admin_token), json={
        "email": "cruz@uruku.bo", "password": "campo2026", "ciudad_slug": "santa-cruz"})
    token = client.post("/auth/campo/login", json={"email": "cruz@uruku.bo", "password": "campo2026"}).json()["access_token"]
    buf = BytesIO(); Image.new("RGB", (10, 10), "blue").save(buf, format="JPEG"); buf.seek(0)
    r = client.post("/campo/comercio", headers=_h(token),
                    data={"nombre": "Tienda Cruceña", "lat": "-17.78", "lng": "-63.18", "ciudad_slug": "bermejo"},
                    files={"foto": ("t.jpg", buf, "image/jpeg")})
    assert r.status_code == 200, r.text
    creado = next(c for c in repo.comercios.values() if c["nombre"] == "Tienda Cruceña")
    assert creado["ciudad_id"] == "ciu-santa-cruz"
