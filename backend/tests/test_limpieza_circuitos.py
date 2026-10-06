"""Limpieza de circuitos (docs/limpieza-circuitos.md, 6/10/2026): lo que no cubren
los archivos de cada módulo.

Lo del fantasma (criterio 1) está en test_ingest.py; el origen en los contactos
y las llegadas (criterio 3), en test_kpis.py; que la IA no apruebe lo del
explorador (criterio 5), en test_revision_ia.py; POST /mensaje (criterio 7), en
test_comercio.py. Acá: el comprador con una sola identidad (criterio 2), el
comercio de campo que entra a Mi comercio (criterio 4), el código del
autoregistro, los favoritos con soft-delete y la migración 0137.
"""
from io import BytesIO
from pathlib import Path

from PIL import Image

from app.services import ingest


# ═════════════════════════════════════════════ el comprador: una sola identidad
def _confirmar_por_webhook(repo, desde, codigo, wamid="wa-conf-1"):
    """Lo que hace WAHA cuando el comprador manda «CONFIRMAR-XXXXXX» desde SU número."""
    return ingest.handle_message({
        "event": "message", "session": "obs@c.us",
        "payload": {"id": wamid, "from": f"{desde}@c.us", "fromMe": False,
                    "body": f"CONFIRMAR-{codigo}", "type": "text", "timestamp": 1700000000},
    }, repo)


def test_el_comprador_que_escribe_70000001_confirma_y_queda_verificado(client, repo):
    """Criterio 2. Quien tipea su número sin el 591 antes NUNCA confirmaba: se
    guardaba «70000001» y el webhook buscaba «59170000001»."""
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"})
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp"] == "59170000001"
    codigo = r.json()["codigo"]

    (u,) = repo.compradores.values()
    assert u["whatsapp"] == "59170000001"                  # guardado normalizado
    assert u["verificado_en"] is None                      # todavía no nos escribió

    res = _confirmar_por_webhook(repo, "59170000001", codigo)
    assert res["confirmado"] is True
    assert u["verificado_en"] is not None

    # Y entra, aunque ahora escriba el número de otra forma.
    r = client.post("/auth/usuario/verificar", json={"whatsapp": "+591 7000 0001", "codigo": codigo})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"]["whatsapp"] == "59170000001"
    # El código se gastó, pero la prueba de que el número es suyo NO se borra.
    assert u["verificado_en"] is not None
    assert u["reset_code"] is None


def test_pedir_el_codigo_dos_veces_con_formas_distintas_es_el_mismo_comprador(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"})
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "+591 70000001"})
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "59170000001"})
    assert len(repo.compradores) == 1


def test_una_fila_vieja_sin_el_591_tambien_se_encuentra(repo):
    """Compradores creados antes de la 0137 quedaron guardados tal cual se
    tipearon: no se pierden, y si confirman desde el webhook, quedan verificados."""
    repo.compradores["viejo"] = {"id": "viejo", "whatsapp": "70000001", "activo": True,
                                 "reset_code": "111222", "reset_code_expira": "2099-01-01T00:00:00+00:00"}
    assert repo.get_usuario_por_whatsapp("59170000001")["id"] == "viejo"
    assert _confirmar_por_webhook(repo, "59170000001", "111222")["confirmado"] is True
    assert repo.compradores["viejo"]["verificado_en"] is not None


def test_un_numero_invalido_se_rechaza_con_un_mensaje(client, repo):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "7000"})
    assert r.status_code == 400
    assert repo.compradores == {}


def test_el_consentimiento_solo_cuenta_con_el_tilde_explicito(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"})
    (u,) = repo.compradores.values()
    assert u["consentimiento_en"] is None          # sin tilde: no hay consentimiento
    assert u["consentimiento_ofertas"] is False    # y ya no «nace en true»

    # Con tilde queda PENDIENTE: el número todavía no se verificó (tercera ronda).
    codigo = client.post("/auth/usuario/solicitar-codigo",
                         json={"whatsapp": "70000001", "consentimiento": True}).json()["codigo"]
    assert u["consentimiento_en"] is None and u["consentimiento_pendiente"] is True
    # Recién cuando el número confirma por WhatsApp cuenta el consentimiento.
    assert _confirmar_por_webhook(repo, "59170000001", codigo)["confirmado"] is True
    assert u["consentimiento_en"] is not None and u["consentimiento_ofertas"] is True
    assert u["consentimiento_pendiente"] is False
    primera = u["consentimiento_en"]
    # La fecha del primer tilde no se pisa.
    codigo = client.post("/auth/usuario/solicitar-codigo",
                         json={"whatsapp": "70000001", "consentimiento": True}).json()["codigo"]
    _confirmar_por_webhook(repo, "59170000001", codigo, wamid="wa-conf-2")
    assert u["consentimiento_en"] == primera


# ═════════════════════════════════════════ favoritos: soft-delete (punto 8)
def _comprador_con_token(client, repo, whatsapp="59171234567"):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": whatsapp}).json()
    repo.confirmar_reset_code_usuario(whatsapp, r["codigo"])
    token = client.post("/auth/usuario/verificar",
                        json={"whatsapp": whatsapp, "codigo": r["codigo"]}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_quitar_un_favorito_lo_apaga_no_lo_borra_y_volver_a_agregarlo_lo_reactiva(client, repo):
    h = _comprador_con_token(client, repo)
    c = repo.crear_comercio({"nombre": "Importadora ABC", "slug": "abc"})
    client.post("/usuario/favoritos", headers=h, json={"comercio_id": c["id"]})

    client.delete(f"/usuario/favoritos/{c['id']}", headers=h)
    assert client.get("/usuario/favoritos", headers=h).json()["items"] == []
    assert len(repo.favoritos) == 1 and repo.favoritos[0]["activo"] is False   # la fila sigue

    client.post("/usuario/favoritos", headers=h, json={"comercio_id": c["id"]})
    assert len(repo.favoritos) == 1                                            # misma fila
    assert [i["slug"] for i in client.get("/usuario/favoritos", headers=h).json()["items"]] == ["abc"]


# ═════════════════════════ el comercio de campo puede entrar a Mi comercio (punto 4)
def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("test.jpg", buf, "image/jpeg")}


def _alta_de_campo(client, **extra):
    token = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com",
                                                   "password": "campo1234"}).json()["access_token"]
    datos = {"nombre": "Gomería El Rápido", "whatsapp": "70002222", "modalidad": "minorista",
             "lat": "-22.7361", "lng": "-64.3433", **extra}
    r = client.post("/campo/comercio", headers={"Authorization": f"Bearer {token}"},
                    data=datos, files=_foto())
    assert r.status_code == 200, r.text
    return r.json()["comercio"]


def test_el_alta_de_campo_le_crea_la_cuenta_de_mi_comercio(client, repo):
    com = _alta_de_campo(client)
    cuentas = [u for u in repo.usuarios.values() if u["comercio_id"] == com["id"]]
    assert len(cuentas) == 1
    # Sin email ni contraseña: entra por el código de WhatsApp.
    assert not cuentas[0].get("email") and not cuentas[0].get("password_hash")


def test_un_comercio_de_campo_entra_a_mi_comercio_con_el_codigo_por_whatsapp(client, repo):
    """Criterio 4, de punta a punta: el agente lo carga con el número TAL CUAL se
    tipea en la calle («70002222»); el dueño pide el código escribiendo su número
    de cualquier forma, manda el CONFIRMAR desde WhatsApp (59170002222) y entra."""
    com = _alta_de_campo(client)

    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "+591 70002222"})
    assert r.status_code == 200, r.text
    codigo = r.json()["codigo"]
    assert f"CONFIRMAR-{codigo}" in r.json()["wa_link"]

    # Todavía no confirmó por WhatsApp.
    r = client.get("/auth/comercio/recuperar/estado", params={"whatsapp": "70002222", "codigo": codigo})
    assert r.json() == {"confirmado": False}

    assert _confirmar_por_webhook(repo, "59170002222", codigo)["confirmado"] is True
    r = client.get("/auth/comercio/recuperar/estado", params={"whatsapp": "70002222", "codigo": codigo})
    assert r.json() == {"confirmado": True}

    r = client.post("/auth/comercio/recuperar/confirmar", json={
        "whatsapp": "70002222", "codigo": codigo, "nueva_password": "claveNueva123"})
    assert r.status_code == 200, r.text
    assert r.json()["comercio"]["id"] == com["id"]
    token = r.json()["access_token"]

    # Y el token SIRVE: una cuenta sin email no puede dejar un «sub» nulo en el
    # JWT (PyJWT lo rechaza al decodificar y cada pantalla daría 401).
    r = client.get("/comercio/mis-publicaciones", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text


def test_un_comercio_activo_sin_cuenta_la_recibe_al_pedir_el_codigo(client, repo):
    """Los que ya existían (y los que cargue el admin) no tienen fila en
    `comercio_usuarios`: pedir el código se la crea al vuelo en vez de fallar."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)
    assert not repo.usuarios
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"})
    assert r.status_code == 200, r.text
    assert [u["comercio_id"] for u in repo.usuarios.values()] == [c["id"]]


def test_un_comercio_apagado_no_recibe_cuenta(client, repo):
    repo.seed_comercio(nombre="Cerrado", whatsapp="59170123456", activo=False)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170123456"})
    assert r.status_code == 404
    assert not repo.usuarios


def test_el_numero_del_empleado_no_abre_mi_comercio(client, repo):
    """Sólo entra el número de la FICHA. Un número autorizado a publicar (la
    vendedora del local) es de otra persona: puede mandar ofertas, no administrar."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)
    repo.agregar_numero_comercio(c["id"], "60999888", "vendedora", "test")
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "60999888"})
    assert r.status_code == 404


def test_si_varios_locales_comparten_el_numero_entra_al_que_tiene_cuenta(repo):
    a = repo.seed_comercio(id="com-a", nombre="Puesto A", whatsapp="70123456", activo=True)
    b = repo.seed_comercio(id="com-b", nombre="Puesto B", whatsapp="59170123456", activo=True)
    repo.crear_comercio_usuario({"comercio_id": b["id"], "nombre": "Puesto B"})
    assert repo.get_comercio_usuario_por_whatsapp("70123456")["comercio_id"] == "com-b"


# ═══════════════════════════════════ el autoregistro devuelve el código (punto 5)
def test_el_autoregistro_devuelve_el_codigo_uruku(client, repo):
    r = client.post("/auth/comercio/registro",
                    data={"nombre": "Mi Tienda", "whatsapp": "59170001111",
                          "lat": "-22.7361", "lng": "-64.3433"},
                    files=_foto())
    assert r.status_code == 200, r.text
    com = r.json()["comercio"]
    assert com["codigo"] and len(com["codigo"]) == 4
    assert com["codigo_formateado"] == f"URUKU-{com['codigo']}"
    # Es el MISMO que está guardado: con ése ata un grupo o publica 1 a 1.
    assert repo.get_comercio_por_codigo(com["codigo_formateado"])["id"] == com["id"]


# ═════════════════════════════════════════════════════ textos muertos (punto 7)
def test_el_mensaje_del_admin_va_firmado_uruku(client, repo, admin_token):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    client.post("/admin/comercio/com-p/mensaje",
                headers={"Authorization": f"Bearer {admin_token}"}, json={"cuerpo": "Pago confirmado"})
    (m,) = repo.mensajes.values()
    assert m["nombre"] == "URUKU"


def test_el_asistente_ya_no_promete_crear_el_grupo():
    from app.services import asistente

    textos = [resp for _patron, resp, _intent in asistente.FAQ]
    assert not any("te lo creamos" in t or "te creamos el grupo" in t for t in textos)
    publicar = next(resp for _p, resp, intent in asistente.FAQ if intent == "publicar_oferta")
    assert "/autoregistro" in publicar and "URUKU-XXXX" in publicar


# ═════════════════════════════════════════════════════════════ la migración 0137
def _sql(nombre):
    raiz = Path(__file__).resolve().parents[2]
    return (raiz / nombre).read_text(encoding="utf-8")


def test_la_migracion_0137_esta_igual_en_supabase_y_en_selfhost():
    a = _sql("supabase/migrations/0137_limpieza_de_circuitos.sql")
    b = _sql("selfhost/postgres-init/0137_limpieza_de_circuitos.sql")
    assert a == b


def test_la_migracion_0137_es_idempotente_y_no_abre_nada_a_anon():
    sql = _sql("supabase/migrations/0137_limpieza_de_circuitos.sql").lower()
    # Columnas nuevas, índice y backfill: re-ejecutables.
    assert "add column if not exists verificado_en" in sql
    assert "add column if not exists consentimiento_en" in sql
    assert "add column if not exists activo" in sql
    assert "create index if not exists" in sql
    assert "not exists" in sql and "insert into comercio_usuarios" in sql
    # GRANTs explícitos para el backend, RLS activo, y nada para anon/authenticated.
    assert "grant all on public.usuarios to service_role" in sql
    assert "grant all on public.favoritos to service_role" in sql
    assert "grant all on public.comercio_usuarios to service_role" in sql
    assert "enable row level security" in sql
    assert " to anon" not in sql and " to authenticated" not in sql
    assert "create policy" not in sql
    # Nunca borrado físico.
    assert "delete from" not in sql and "drop table" not in sql


# ═══════════════════════════════════════════════════════════════════════════════
# SEGUNDA RONDA (6/10/2026): la clave de 6 números y los arreglos de QA
# ═══════════════════════════════════════════════════════════════════════════════
import re

import pytest

from app.core import clave as claves
from app.core.config import settings


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def auth_token(comercio_id):
    from app.core import auth
    return auth.make_comercio_token(comercio_id, "x@y.com")


def _cuenta(repo, comercio_id):
    return next(u for u in repo.usuarios.values() if u["comercio_id"] == comercio_id)


def _ingresar(client, whatsapp, clave):
    return client.post("/auth/comercio/ingresar", json={"whatsapp": whatsapp, "clave": clave})


def _recuperar_y_confirmar(client, repo, whatsapp, desde, **extra):
    """El camino de «me olvidé»: pedir el código, mandar el CONFIRMAR, confirmar."""
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": whatsapp, **extra})
    assert r.status_code == 200, r.text
    codigo = r.json()["codigo"]
    assert _confirmar_por_webhook(repo, desde, codigo, wamid=f"wa-{codigo}")["confirmado"] is True
    return codigo, client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": whatsapp, "codigo": codigo})


# ──────────────────────────────────────── criterio 9: ficha «+591 7012-3456»
def test_criterio_9_la_ficha_con_formato_libre_entra_con_70123456(client, repo):
    token = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com",
                                                   "password": "campo1234"}).json()["access_token"]
    r = client.post("/campo/comercio", headers=_hdr(token), files=_foto(),
                    data={"nombre": "Ferretería Sur", "whatsapp": "+591 7012-3456", "modalidad": "minorista",
                          "lat": "-22.7361", "lng": "-64.3433"})
    assert r.status_code == 200, r.text
    clave = r.json()["clave_inicial"]
    assert "clave_inicial" not in r.json()["comercio"]          # sólo en la raíz (tercera ronda)
    assert re.fullmatch(r"\d{6}", clave)
    # La ficha quedó normalizada (E.164), no «+591 7012-3456».
    (c,) = repo.comercios.values()
    assert c["whatsapp"] == "59170123456"
    # Y entra escribiendo el número de cualquier forma.
    for tipeado in ("70123456", "7012 3456", "+591 70123456"):
        r = _ingresar(client, tipeado, clave)
        assert r.status_code == 200, (tipeado, r.text)
        assert r.json()["comercio"]["id"] == c["id"]


@pytest.mark.parametrize("quien", ["admin", "autoregistro", "importado"])
def test_el_whatsapp_se_guarda_normalizado_en_todos_los_caminos(client, repo, admin_token, quien):
    # (El comerciante ya no edita su WhatsApp desde Mi comercio: ver la tercera ronda.)
    if quien == "admin":
        repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="x", activo=True)
        r = client.put("/admin/comercio/com-a", headers=_hdr(admin_token), json={"whatsapp": "7012 3456"})
        assert r.status_code == 200, r.text
        assert repo.comercios["com-a"]["whatsapp"] == "59170123456"
    elif quien == "autoregistro":
        r = client.post("/auth/comercio/registro", files=_foto(),
                        data={"nombre": "Mi Tienda", "whatsapp": " +591 7012-3456 ",
                              "lat": "-22.7361", "lng": "-64.3433"})
        assert r.status_code == 200, r.text
        (c,) = repo.comercios.values()
        assert c["whatsapp"] == "59170123456"
    else:
        repo.upsert_importado({"fuente": "osm", "fuente_id": "n1", "nombre": "Kiosco",
                               "lat": -22.7, "lng": -64.3, "whatsapp": "7012-3456"})
        imp_id = next(iter(repo.importados))
        r = client.post(f"/admin/importados/{imp_id}/promover", headers=_hdr(admin_token), json={})
        assert r.status_code == 200, r.text
        assert r.json()["comercio"]["whatsapp"] == "59170123456"


def test_un_whatsapp_que_no_valida_se_guarda_como_viene(client, repo, admin_token):
    """No se inventa un número: «123» no es un celular y queda tal cual."""
    repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="x", activo=True)
    client.put("/admin/comercio/com-a", headers=_hdr(admin_token), json={"whatsapp": " 123 "})
    assert repo.comercios["com-a"]["whatsapp"] == "123"


def test_la_normalizacion_de_la_migracion_coincide_con_la_del_backend():
    """La 0137 normaliza en SQL con la misma regla que `whatsapp_para_guardar`:
    sólo dígitos; 8 que empiezan con 6/7 → 591 + ellos; 591 + 8 → se deja; el
    resto no se toca. Se replica la regla del SQL y se compara."""
    from app.core.telefono import whatsapp_para_guardar

    def regla_sql(valor):
        d = re.sub(r"[^0-9]", "", valor)
        if re.fullmatch(r"[67][0-9]{7}", d):
            return "591" + d
        if re.fullmatch(r"591[67][0-9]{7}", d):
            return d
        return valor            # el UPDATE no lo toca

    tocados = 0
    for v in ["+591 7012-3456", "70123456", "591-6012-3456", "(591) 7012 3456", "59170123456",
              "5491155551234", "4123456", "abc", "591701234", "00591 70123456"]:
        sql = regla_sql(v)
        if sql != v:                                   # los que la migración toca
            tocados += 1
            assert whatsapp_para_guardar(v) == sql, v
    assert tocados >= 4


# ──────────────────────────────────────── criterio 10: clave + bloqueo
def _comercio_con_clave(client, repo, whatsapp="59170123456", **kw):
    c = repo.seed_comercio(nombre=kw.pop("nombre", "Ferretería"), slug=kw.pop("slug", "ferreteria"),
                           whatsapp=whatsapp, activo=True, **kw)
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    r = client.post("/comercio/clave", headers=_hdr(auth_token(c["id"])))
    assert r.status_code == 200, r.text
    return c, cuenta, r.json()["clave"]


def _mala(clave):
    return "999999" if clave != "999999" else "888888"


def test_criterio_10_celular_mas_clave_correcta_entra(client, repo):
    c, _u, clave = _comercio_con_clave(client, repo)
    assert re.fullmatch(r"\d{6}", clave)
    r = _ingresar(client, "70123456", clave)
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d["comercio"]) == {"id", "nombre", "slug", "confiable"} and d["comercio"]["id"] == c["id"]
    assert client.get("/comercio/perfil", headers=_hdr(d["access_token"])).status_code == 200


def _fallos(repo, resultado="fallo"):
    return [f for f in repo.clave_fallos if f["resultado"] == resultado]


def _correr_el_reloj(repo, **delta):
    """Manda al pasado todos los intentos registrados (simula que pasó el tiempo)."""
    from datetime import timedelta
    for f in repo.clave_fallos:
        f["created_at"] -= timedelta(**delta)


def test_criterio_10_clave_mala_da_401_y_cinco_fallos_bloquean_15_minutos(client, repo):
    _c, _cuenta_, clave = _comercio_con_clave(client, repo)
    for i in range(5):
        r = _ingresar(client, "70123456", _mala(clave))
        assert r.status_code == 401, (i, r.text)
        assert r.json()["detail"] == "Celular o clave incorrectos"
    # El sexto, aunque sea la clave CORRECTA, está bloqueado (y no se verificó).
    r = _ingresar(client, "70123456", clave)
    assert r.status_code == 429
    assert r.json()["detail"] == "Demasiados intentos. Probá de nuevo en 15 minutos."
    assert len(_fallos(repo)) == 5 and len(_fallos(repo, "bloqueado")) == 1
    # Pasados los 15 minutos vuelve a andar.
    _correr_el_reloj(repo, minutes=16)
    assert _ingresar(client, "70123456", clave).status_code == 200


def test_un_ingreso_correcto_no_borra_los_fallos(client, repo):
    """Tercera ronda: antes un ingreso correcto ponía el contador en cero."""
    _c, _cuenta_, clave = _comercio_con_clave(client, repo)
    for _ in range(4):
        _ingresar(client, "70123456", _mala(clave))
    assert _ingresar(client, "70123456", clave).status_code == 200
    assert len(_fallos(repo)) == 4                       # siguen ahí
    assert _ingresar(client, "70123456", _mala(clave)).status_code == 401     # el quinto
    assert _ingresar(client, "70123456", clave).status_code == 429            # bloqueado: los 4 de antes cuentan


def test_la_ventana_es_deslizante_los_fallos_viejos_dejan_de_contar(client, repo):
    """Pasados los 15 minutos vuelve a tener 5 chances, no una."""
    _c, _cuenta_, clave = _comercio_con_clave(client, repo)
    for _ in range(4):
        assert _ingresar(client, "70123456", _mala(clave)).status_code == 401
    _correr_el_reloj(repo, minutes=16)
    for _ in range(4):
        assert _ingresar(client, "70123456", _mala(clave)).status_code == 401
    assert _ingresar(client, "70123456", clave).status_code == 200


def test_el_intento_se_registra_ANTES_de_verificar_la_clave(client, repo, monkeypatch):
    """Es lo que vuelve atómico el conteo: pedidos en paralelo ya se ven registrados
    mientras PBKDF2 corre."""
    _c, _cuenta_, clave = _comercio_con_clave(client, repo)
    vistos = []
    original = claves.clave_coincide

    def espiar(c, h):
        vistos.append(len(repo.clave_fallos))
        return original(c, h)

    monkeypatch.setattr(claves, "clave_coincide", espiar)
    _ingresar(client, "70123456", _mala(clave))
    assert vistos == [1]


def test_un_numero_sin_cuenta_contesta_igual_que_uno_con_otra_clave(client, repo):
    """Sin revelar si el número existe: mismo 401, mismo 429 al sexto intento."""
    for _ in range(5):
        r = _ingresar(client, "70999888", "123456")
        assert r.status_code == 401 and r.json()["detail"] == "Celular o clave incorrectos"
    assert _ingresar(client, "70999888", "123456").status_code == 429


@pytest.mark.parametrize("clave", ["", "12345", "1234567", "abcdef", "12 456", "1234 6"])
def test_una_clave_con_forma_rara_es_un_fallo_normal(client, repo, clave):
    _comercio_con_clave(client, repo)
    assert _ingresar(client, "70123456", clave).status_code == 401


def test_una_cuenta_sin_clave_no_entra_con_ninguna(client, repo):
    c = repo.seed_comercio(nombre="Sin clave", whatsapp="59170123456", activo=True)
    repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": "Sin clave"})
    assert _ingresar(client, "70123456", "000000").status_code == 401


def test_el_numero_de_uruku_nunca_abre_una_cuenta(client, repo, monkeypatch):
    from app.core import config as cfg
    monkeypatch.setattr(settings, "wa_numeros_propios", "59170123456", raising=False)
    cfg._numeros_propios.cache_clear()
    try:
        # El comercio tiene el número de URUKU en su ficha (mal cargado).
        _c, _u, clave = _comercio_con_clave(client, repo)
        assert _ingresar(client, "70123456", clave).status_code == 401
        assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).status_code == 404
        assert client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70123456"}).status_code == 400
    finally:
        cfg._numeros_propios.cache_clear()


def test_generar_otra_clave_deja_sin_efecto_la_anterior(client, repo):
    c, _u, vieja = _comercio_con_clave(client, repo)
    nueva = client.post("/comercio/clave", headers=_hdr(auth_token(c["id"]))).json()["clave"]
    if nueva != vieja:
        assert _ingresar(client, "70123456", vieja).status_code == 401
    assert _ingresar(client, "70123456", nueva).status_code == 200


def test_post_comercio_clave_pide_estar_autenticado(client):
    assert client.post("/comercio/clave").status_code == 401


# ──────────────────────────────────────── criterio 11: un número, dos comercios
def _dos_puestos(repo):
    a = repo.seed_comercio(id="com-a", slug="puesto-a", nombre="Puesto A", direccion="Calle 1", whatsapp="59170123456", activo=True)
    b = repo.seed_comercio(id="com-b", slug="puesto-b", nombre="Puesto B", direccion="Calle 2", whatsapp="70123456", activo=True)
    for c in (a, b):
        repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    return a, b


def test_criterio_11_la_clave_de_cada_comercio_abre_el_suyo(client, repo):
    _dos_puestos(repo)
    ca = client.post("/comercio/clave", headers=_hdr(auth_token("com-a"))).json()["clave"]
    cb = client.post("/comercio/clave", headers=_hdr(auth_token("com-b"))).json()["clave"]
    assert ca != cb                           # se garantiza que no se repiten dentro del número
    assert _ingresar(client, "70123456", ca).json()["comercio"]["id"] == "com-a"
    assert _ingresar(client, "70123456", cb).json()["comercio"]["id"] == "com-b"


def test_la_clave_nueva_nunca_coincide_con_la_de_otro_comercio_del_numero(client, repo, monkeypatch):
    _dos_puestos(repo)
    ca = client.post("/comercio/clave", headers=_hdr(auth_token("com-a"))).json()["clave"]
    # Se fuerza que el azar «saque» primero la clave de A: tiene que descartarla.
    salidas = iter([ca, ca, "424242"])
    monkeypatch.setattr(claves, "generar_clave", lambda: next(salidas))
    cb = client.post("/comercio/clave", headers=_hdr(auth_token("com-b"))).json()["clave"]
    assert cb == "424242"


def test_criterio_11_la_recuperacion_pide_elegir_y_el_codigo_queda_atado_a_esa_cuenta(client, repo):
    _dos_puestos(repo)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"})
    assert r.status_code == 409
    d = r.json()
    assert "detail" in d
    assert d["negocios"] == [{"id": "com-a", "nombre": "Puesto A", "direccion": "Calle 1"},
                             {"id": "com-b", "nombre": "Puesto B", "direccion": "Calle 2"}]
    assert not any(u.get("reset_code") for u in repo.usuarios.values())     # no se eligió ninguno en silencio

    # Un negocio que no es de ese número no sirve.
    repo.seed_comercio(id="com-z", nombre="Z", whatsapp="59171111111", activo=True)
    assert client.post("/auth/comercio/recuperar",
                       json={"whatsapp": "70123456", "comercio_id": "com-z"}).status_code == 400

    _codigo, r = _recuperar_y_confirmar(client, repo, "70123456", "59170123456", comercio_id="com-b")
    assert r.status_code == 200, r.text
    assert r.json()["comercio"]["id"] == "com-b"
    assert [u["comercio_id"] for u in repo.usuarios.values() if u.get("clave_hash")] == ["com-b"]


def test_el_estado_de_la_recuperacion_busca_entre_las_cuentas_la_del_codigo(client, repo):
    _dos_puestos(repo)
    codigo = client.post("/auth/comercio/recuperar",
                         json={"whatsapp": "70123456", "comercio_id": "com-b"}).json()["codigo"]

    def est():
        return client.get("/auth/comercio/recuperar/estado",
                          params={"whatsapp": "70123456", "codigo": codigo}).json()

    assert est() == {"confirmado": False}
    _confirmar_por_webhook(repo, "59170123456", codigo)
    assert est() == {"confirmado": True}
    assert _cuenta(repo, "com-b")["reset_code_confirmado_at"]
    assert not _cuenta(repo, "com-a").get("reset_code_confirmado_at")


def test_un_numero_con_un_solo_comercio_no_pide_elegir(client, repo):
    repo.seed_comercio(nombre="Único", whatsapp="59170123456", activo=True)
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).status_code == 200
    # Pasar un comercio_id ajeno aun así se rechaza.
    assert client.post("/auth/comercio/recuperar",
                       json={"whatsapp": "70123456", "comercio_id": "otro"}).status_code == 400


def test_el_orden_de_las_busquedas_por_numero_es_determinista(repo):
    for i in range(4):
        repo.seed_comercio(id=f"com-{i}", nombre=f"C{i}", whatsapp="70123456", activo=True)
    assert [c["id"] for c in repo.list_comercios_por_whatsapp("59170123456")] == [f"com-{i}" for i in range(4)]
    assert repo.get_comercio_por_whatsapp("70123456")["id"] == "com-0"


# ──────────────────────────────────────── confirmar: siempre una clave nueva
def test_cada_confirmacion_por_whatsapp_del_comerciante_devuelve_una_clave_nueva(client, repo):
    _c, _u, clave0 = _comercio_con_clave(client, repo)
    _codigo, r = _recuperar_y_confirmar(client, repo, "70123456", "59170123456")
    assert r.status_code == 200, r.text
    nueva = r.json()["clave_nueva"]
    assert re.fullmatch(r"\d{6}", nueva)
    assert _ingresar(client, "70123456", nueva).status_code == 200
    if nueva != clave0:
        assert _ingresar(client, "70123456", clave0).status_code == 401      # la vieja quedó sin efecto


def test_el_dueno_que_nunca_recibio_clave_la_recibe_al_confirmar(client, repo):
    com = _alta_de_campo(client)
    _cuenta(repo, com["id"])["clave_hash"] = None        # (caso: nunca se la dieron)
    _codigo, r = _recuperar_y_confirmar(client, repo, "70002222", "59170002222")
    assert r.status_code == 200, r.text
    assert _ingresar(client, "70002222", r.json()["clave_nueva"]).status_code == 200


def test_el_autoregistro_devuelve_clave_inicial_y_con_ella_vuelve_a_entrar(client, repo):
    r = client.post("/auth/comercio/registro", files=_foto(),
                    data={"nombre": "Mi Tienda", "whatsapp": "70001111", "lat": "-22.7361", "lng": "-64.3433"})
    assert r.status_code == 200, r.text
    clave = r.json()["clave_inicial"]
    assert "clave_inicial" not in r.json()["comercio"]
    assert _ingresar(client, "59170001111", clave).status_code == 200


def test_el_perfil_trae_el_codigo_y_el_codigo_formateado(client, repo):
    repo.seed_comercio(id="com-1", nombre="X", whatsapp="59170123456", activo=True, codigo="KPXN")
    r = client.get("/comercio/perfil", headers=_hdr(auth_token("com-1")))
    assert r.status_code == 200
    assert r.json()["codigo"] == "KPXN" and r.json()["codigo_formateado"] == "URUKU-KPXN"
    assert "clave_hash" not in r.json() and "clave" not in r.json()


# ──────────────────────────────────────── criterio 12: la clave no se filtra
def test_criterio_12_la_clave_nunca_va_a_un_log_a_la_ficha_ni_al_enlace(client, repo, capfd):
    com = _alta_de_campo(client)
    cuenta = _cuenta(repo, com["id"])
    clave = client.post("/comercio/clave", headers=_hdr(auth_token(com["id"]))).json()["clave"]
    _ingresar(client, "70002222", clave)
    _ingresar(client, "70002222", _mala(clave))
    _codigo, conf = _recuperar_y_confirmar(client, repo, "70002222", "59170002222")
    nueva = conf.json()["clave_nueva"]
    salida = capfd.readouterr()
    todo = salida.out + salida.err
    assert "comercio.ingresar" in todo and "comercio.recuperar.confirmado" in todo     # sí se loguea el evento
    for secreto in (clave, nueva):
        assert not re.search(rf"(?<!\d){secreto}(?!\d)", todo), "la clave apareció en un log"
    # En la base queda sólo el hash.
    assert cuenta["clave_hash"].startswith("pbkdf2_sha256$")
    # Nada de la clave en `comercios` (esa tabla la lee el sitio con la llave pública).
    for fila in repo.comercios.values():
        assert not any("clave" in k for k in fila), fila.keys()
    # Ni en la ficha ni en el enlace de WhatsApp.
    perfil = client.get("/comercio/perfil", headers=_hdr(auth_token(com["id"]))).text
    assert "clave" not in perfil
    wa = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"}).json()["wa_link"]
    assert clave not in wa and nueva not in wa


# ──────────────────────────────────────── el enlace de WhatsApp y el parser
def test_el_enlace_precarga_para_que_es_y_el_webhook_lo_reconoce(client, repo):
    from urllib.parse import parse_qs, urlparse

    repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).json()
    texto = parse_qs(urlparse(r["wa_link"]).query)["text"][0]
    assert texto == f"CONFIRMAR-{r['codigo']} para entrar a Mi comercio de URUKU"
    # El webhook confirma con ESE texto exacto.
    res = ingest.handle_message({"event": "message", "session": "obs@c.us",
                                 "payload": {"id": "wa-x", "from": "59170123456@c.us", "fromMe": False,
                                             "body": texto, "type": "text", "timestamp": 1700000000}}, repo)
    assert res["confirmado"] is True

    u = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()
    texto_u = parse_qs(urlparse(u["wa_link"]).query)["text"][0]
    assert texto_u == f"CONFIRMAR-{u['codigo']} para entrar a URUKU"


@pytest.mark.parametrize("cuerpo,vale", [
    ("CONFIRMAR-123456", True),
    ("confirmar-123456 para entrar a Mi comercio de URUKU", True),
    ("  CONFIRMAR-123456 para entrar a URUKU\n", True),
    ("CONFIRMAR-123456.", True),
    ("CONFIRMAR-1234567 para entrar", False),
    ("CONFIRMAR-12345 para entrar", False),
    ("hola CONFIRMAR-123456", False),
    ("CONFIRMAR-123456abc", False),
])
def test_el_parser_de_confirmar_acepta_el_texto_alrededor(cuerpo, vale):
    m = ingest._RE_CONFIRMAR.match(cuerpo)
    assert bool(m) is vale
    if vale:
        assert m.group(1) == "123456"


# ──────────────────────────────────────── criterio 13: el comprador
def test_criterio_13_el_comprador_recibe_su_clave_al_confirmar_y_despues_entra_sin_whatsapp(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    _confirmar_por_webhook(repo, "59170000001", codigo)
    v = client.post("/auth/usuario/verificar", json={"whatsapp": "70000001", "codigo": codigo})
    assert v.status_code == 200, v.text
    clave = v.json()["clave_nueva"]
    assert re.fullmatch(r"\d{6}", clave)
    (u,) = repo.compradores.values()
    assert u["clave_hash"].startswith("pbkdf2_sha256$") and clave not in u["clave_hash"]

    # Entra con celular + clave, SIN pasar por el webhook.
    i = client.post("/auth/usuario/ingresar", json={"whatsapp": "+591 7000-0001", "clave": clave})
    assert i.status_code == 200, i.text
    assert set(i.json()) == {"access_token", "usuario"}
    assert i.json()["usuario"] == {"id": u["id"], "whatsapp": "59170000001"}
    assert client.get("/usuario/favoritos", headers=_hdr(i.json()["access_token"])).status_code == 200


def test_el_comprador_con_clave_mala_da_401_y_a_los_cinco_fallos_429(client, repo):
    u = repo.crear_usuario("70000001")
    u["clave_hash"] = claves.hash_clave("123456")
    for _ in range(5):
        r = client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "654321"})
        assert r.status_code == 401 and r.json()["detail"] == "Celular o clave incorrectos"
    r = client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "123456"})
    assert r.status_code == 429 and r.json()["detail"] == "Demasiados intentos. Probá de nuevo en 15 minutos."


def test_un_comprador_sin_cuenta_ni_clave_no_entra_y_no_se_crea(client, repo):
    r = client.post("/auth/usuario/ingresar", json={"whatsapp": "70000009", "clave": "123456"})
    assert r.status_code == 401 and repo.compradores == {}


def test_cada_confirmacion_del_comprador_genera_una_clave_nueva(client, repo):
    vistas = []
    for n in range(2):
        codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
        _confirmar_por_webhook(repo, "59170000001", codigo, wamid=f"wa-c{n}")
        vistas.append(client.post("/auth/usuario/verificar",
                                  json={"whatsapp": "70000001", "codigo": codigo}).json()["clave_nueva"])
    vieja, nueva = vistas
    assert client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": nueva}).status_code == 200
    if vieja != nueva:
        assert client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": vieja}).status_code == 401


def test_al_verificar_una_fila_vieja_sin_591_se_normaliza_su_numero(client, repo):
    repo.compradores["viejo"] = {"id": "viejo", "whatsapp": "70000001", "activo": True,
                                 "reset_code": "111222", "reset_code_expira": "2099-01-01T00:00:00+00:00"}
    assert _confirmar_por_webhook(repo, "59170000001", "111222")["confirmado"] is True
    r = client.post("/auth/usuario/verificar", json={"whatsapp": "70000001", "codigo": "111222"})
    assert r.status_code == 200
    assert repo.compradores["viejo"]["whatsapp"] == "59170000001"
    assert r.json()["usuario"]["whatsapp"] == "59170000001"


def test_al_verificar_no_se_normaliza_si_choca_con_otra_fila(client, repo):
    repo.compradores["viejo"] = {"id": "viejo", "whatsapp": "70000001", "activo": True,
                                 "reset_code": "111222", "reset_code_expira": "2099-01-01T00:00:00+00:00",
                                 "reset_code_confirmado_at": "2026-10-06T00:00:00+00:00"}
    repo.compradores["otro"] = {"id": "otro", "whatsapp": "59170000001", "activo": False}   # unique: choca
    r = client.post("/auth/usuario/verificar", json={"whatsapp": "70000001", "codigo": "111222"})
    assert r.status_code == 200
    assert repo.compradores["viejo"]["whatsapp"] == "70000001"


# ──────────────────────────────────────── fantasmas viejos y números de URUKU
def test_un_comercio_apagado_ya_no_junta_publicaciones_por_su_jid(repo):
    """Los fantasmas viejos («Comercio 1234», apagados) conservan su `wa_jid`."""
    repo.seed_comercio(id="com-f", nombre="Comercio 1234", wa_jid="59170005555@c.us", activo=False)
    assert repo.get_comercio_by_jid("59170005555@c.us") is None
    res = ingest.handle_message({"event": "message", "session": "obs@c.us",
                                 "payload": {"id": "wa-f", "from": "59170005555@c.us", "fromMe": False,
                                             "body": "oferta zapatillas Bs 100", "type": "text",
                                             "timestamp": 1700000000}}, repo)
    assert repo.publicaciones == [] and res.get("publicada") is False


def test_el_confirmar_desde_un_numero_de_uruku_no_confirma_nada(repo, monkeypatch):
    from app.core import config as cfg
    monkeypatch.setattr(settings, "wa_numeros_propios", "59170000099", raising=False)
    cfg._numeros_propios.cache_clear()
    try:
        u = repo.crear_usuario("70000099")
        repo.set_reset_code_usuario(u["id"], "111222", "2099-01-01T00:00:00+00:00")
        assert _confirmar_por_webhook(repo, "59170000099", "111222")["confirmado"] is False
        assert not u.get("reset_code_confirmado_at")
    finally:
        cfg._numeros_propios.cache_clear()


# ──────────────────────────────────────── la IA y el ref
def test_la_ia_no_aprueba_lo_del_explorador_ni_por_identidad_origen(monkeypatch):
    from app.services import revision_ia

    v = {"veredicto": "aprobar", "confianza": 0.99}
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    assert revision_ia._auto_aprueba(v, {"origen": "whatsapp"}) is True
    assert revision_ia._auto_aprueba(v, {"origen": "explorador"}) is False
    assert revision_ia._auto_aprueba(v, {"origen": "whatsapp", "identidad_origen": "explorador"}) is False
    with pytest.raises(TypeError):
        revision_ia._auto_aprueba(v)            # `pub` es obligatorio


def test_visita_y_lead_limpian_el_ref_con_la_misma_funcion(client, repo):
    from app.core.text import limpiar_ref

    ref = "Grupo:Sol/ñandú_1.x"
    client.post("/visita", json={"ruta": "/", "sesion": "sesion-aaa111", "origen": ref})
    client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp", "origen": ref})
    assert repo.visitas[-1]["origen"] == repo.leads[-1]["origen"] == limpiar_ref(ref) == "gruposoland_1.x"


def test_el_metodo_de_pago_otro_se_acepta(client, repo):
    repo.seed_comercio(id="com-1", slug="x", nombre="X", activo=True)
    for metodo in ("transferencia", "efectivo", "otro"):
        r = client.post("/comercio/pago", headers=_hdr(auth_token("com-1")), data={"monto": "100", "metodo": metodo})
        assert r.status_code == 200, (metodo, r.text)
    assert client.post("/comercio/pago", headers=_hdr(auth_token("com-1")),
                       data={"monto": "100", "metodo": "bitcoin"}).status_code == 400


# ──────────────────────────────────────── la migración 0137, segunda ronda
def _sql_sin_comentarios(nombre="supabase/migrations/0137_limpieza_de_circuitos.sql"):
    return "\n".join(l for l in _sql(nombre).splitlines() if not l.strip().startswith("--")).lower()


def test_la_0137_agrega_las_columnas_de_la_clave_con_comentario_e_idempotente():
    sql = _sql_sin_comentarios()
    for tabla in ("comercio_usuarios", "usuarios"):
        col = "clave_hash"
        assert f"alter table {tabla} add column if not exists {col}" in sql, (tabla, col)
        assert f"comment on column {tabla}.{col} is" in sql, (tabla, col)
        # El contador ya no son columnas: son filas de `clave_fallos` (tercera ronda).
        assert f"{tabla} add column if not exists clave_intentos" not in sql
        assert f"{tabla} add column if not exists clave_bloqueada_hasta" not in sql
    assert "update public.comercios" in sql and "is distinct from" in sql        # idempotente


def test_el_hash_de_la_clave_no_esta_en_comercios_ni_se_abre_a_anon_en_ninguna_migracion():
    """El sitio lee `comercios` con la llave pública (`select *`): la clave NO puede
    estar ahí. Y `usuarios` / `comercio_usuarios` no tienen grants ni policies para
    anon/authenticated en ninguna migración, así que las columnas nuevas tampoco."""
    raiz = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
    for f in sorted(raiz.glob("*.sql")):
        sql = "\n".join(l for l in f.read_text(encoding="utf-8").splitlines()
                        if not l.strip().startswith("--")).lower()
        assert not re.search(r"alter table (public\.)?comercios\s+add column[^;]*clave_", sql), f.name
        for tabla in ("usuarios", "comercio_usuarios"):
            assert not re.search(rf"grant [^;]*on (table )?(public\.)?{tabla}\b[^;]*to [^;]*\b(anon|authenticated)\b", sql), (f.name, tabla)
            assert not re.search(rf"create policy[^;]*on (public\.)?{tabla}\b[^;]*\b(anon|authenticated)\b", sql), (f.name, tabla)
    sql = _sql_sin_comentarios()
    assert "alter table usuarios enable row level security" in sql
    assert "alter table comercio_usuarios enable row level security" in sql


# ═══════════════════════════════════════════════════════════════════════════════
# TERCERA RONDA (6/10/2026): seguridad del ingreso con clave
# Cada caso de ataque de la prueba de concepto de la revisión de seguridad
# (criterios 14 a 18) queda acá como regresión: el ataque ya NO funciona.
# ═══════════════════════════════════════════════════════════════════════════════
import time
from datetime import timedelta

DETALLE_409 = ("Ese número ya tiene un negocio en URUKU. Entrá con tu WhatsApp; "
               "si es otro local tuyo, escribinos.")
DETALLE_ANULADA = "Por seguridad tu clave se anuló. Entrá con tu WhatsApp para recibir una nueva."


def _victima(client, repo, whatsapp="59170123456"):
    v = repo.seed_comercio(id="victima", nombre="Ferreteria", slug="ferr", whatsapp=whatsapp, activo=True)
    repo.crear_comercio_usuario({"comercio_id": v["id"], "nombre": v["nombre"]})
    clave = client.post("/comercio/clave", headers=_hdr(auth_token("victima"))).json()["clave"]
    return v, clave


def _alta_campo(client, whatsapp, nombre="Puesto"):
    token = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com",
                                                   "password": "campo1234"}).json()["access_token"]
    return client.post("/campo/comercio", headers=_hdr(token), files=_foto(),
                       data={"nombre": nombre, "whatsapp": whatsapp, "modalidad": "minorista",
                             "lat": "-22.7361", "lng": "-64.3433"})


# ---- criterios 14 y 16: la PoC 1 (reset del bloqueo con un comercio colgado del número)
def test_criterio_16_el_autoregistro_con_un_numero_que_ya_tiene_negocio_da_409(client, repo):
    _victima(client, repo)
    r = client.post("/auth/comercio/registro", files=_foto(),
                    data={"nombre": "Falso", "whatsapp": "70123456", "lat": "-22.7", "lng": "-64.3"})
    assert r.status_code == 409, r.text           # la PoC esperaba 200 y la clave del atacante
    assert r.json()["detail"] == DETALLE_409
    assert list(repo.comercios) == ["victima"]    # no se creó nada


@pytest.mark.parametrize("tipeado", ["70123456", "+591 7012-3456", "591-7012-3456", " 7012 3456 "])
def test_el_409_vale_para_cualquier_forma_de_escribir_el_numero(client, repo, tipeado):
    _victima(client, repo)
    r = client.post("/auth/comercio/registro", files=_foto(),
                    data={"nombre": "Falso", "whatsapp": tipeado, "lat": "-22.7", "lng": "-64.3"})
    assert r.status_code == 409, tipeado


def test_un_comercio_apagado_no_bloquea_el_autoregistro_y_el_alta_de_campo_no_se_frena(client, repo):
    repo.seed_comercio(id="viejo", nombre="Cerrado", slug="cerrado", whatsapp="59170123456", activo=False)
    r = client.post("/auth/comercio/registro", files=_foto(),
                    data={"nombre": "Nuevo", "whatsapp": "70123456", "lat": "-22.7", "lng": "-64.3"})
    assert r.status_code == 200, r.text
    # El agente puede cargar dos puestos de un mismo dueño (mismo número).
    assert _alta_campo(client, "70999111", "Puesto 1").status_code == 200
    assert _alta_campo(client, "70999111", "Puesto 2").status_code == 200


def test_criterio_14_con_un_comercio_propio_en_el_numero_de_la_victima_12_claves_malas_bloquean(client, repo):
    """La PoC de la revisión, con el comercio del atacante ya colgado del número (dato
    viejo: antes el autoregistro lo permitía). Entrar con SU clave en el medio ya no
    pone el contador en cero."""
    _v, clave_victima = _victima(client, repo)
    a = repo.seed_comercio(id="atacante", nombre="Falso", slug="falso", whatsapp="70123456", activo=True)
    repo.crear_comercio_usuario({"comercio_id": a["id"], "nombre": a["nombre"]})
    k_atacante = client.post("/comercio/clave", headers=_hdr(auth_token("atacante"))).json()["clave"]
    assert k_atacante != clave_victima

    malas = [f"{i:06d}" for i in range(1000) if f"{i:06d}" not in (clave_victima, k_atacante)]
    estados, n = [], 0
    for _ciclo in range(3):
        for _ in range(4):
            estados.append(_ingresar(client, "70123456", malas[n]).status_code)
            n += 1
        # Entra con SU clave (si no está bloqueado ya): NO resetea nada.
        estados.append(_ingresar(client, "70123456", k_atacante).status_code)
    assert n == 12
    assert 429 in estados, estados                             # la PoC nunca veía un 429
    assert len(_fallos(repo)) <= 5                             # y no probó más de 5 claves
    # El número queda bloqueado: ni la clave correcta de la víctima pasa mientras dure.
    assert _ingresar(client, "70123456", clave_victima).status_code == 429


# ---- criterio 15: 10 fallos en 24 horas anulan la clave
def test_criterio_15_diez_fallos_en_24_horas_anulan_la_clave_y_solo_se_entra_por_whatsapp(client, repo):
    _c, cuenta, clave = _comercio_con_clave(client, repo)
    for _ in range(2):                               # 8 fallos en dos tandas de 4
        for _ in range(4):
            assert _ingresar(client, "70123456", _mala(clave)).status_code == 401
        _correr_el_reloj(repo, minutes=16)
    assert _ingresar(client, "70123456", _mala(clave)).json()["detail"] == "Celular o clave incorrectos"   # el 9º
    assert cuenta["clave_hash"]
    r = _ingresar(client, "70123456", _mala(clave))                                                       # el 10º
    assert r.status_code == 401 and r.json()["detail"] == DETALLE_ANULADA
    assert cuenta["clave_hash"] is None                                                                   # anulada
    # Ni siquiera la clave que era correcta entra.
    r = _ingresar(client, "70123456", clave)
    assert r.status_code == 401 and r.json()["detail"] == DETALLE_ANULADA
    # Por WhatsApp sí, y ahí recibe una clave nueva que funciona.
    _codigo, conf = _recuperar_y_confirmar(client, repo, "70123456", "59170123456")
    assert conf.status_code == 200, conf.text
    assert _ingresar(client, "70123456", conf.json()["clave_nueva"]).status_code == 200


def test_el_comprador_tambien_anula_la_clave_con_10_fallos_en_24_horas(client, repo):
    u = repo.crear_usuario("70000001")
    u["clave_hash"] = claves.hash_clave("123456")

    def entrar(clave):
        return client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": clave})

    for _ in range(2):
        for _ in range(4):
            assert entrar("654321").status_code == 401
        _correr_el_reloj(repo, minutes=16)
    assert entrar("654321").status_code == 401
    r = entrar("654321")
    assert r.status_code == 401 and r.json()["detail"] == DETALLE_ANULADA and u["clave_hash"] is None
    assert entrar("123456").status_code == 401
    # Confirma por WhatsApp: clave nueva, y entra.
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    _confirmar_por_webhook(repo, "59170000001", codigo)
    nueva = client.post("/auth/usuario/verificar", json={"whatsapp": "70000001", "codigo": codigo}).json()["clave_nueva"]
    assert entrar(nueva).status_code == 200


def test_el_comprador_tampoco_resetea_el_contador_al_entrar_bien(client, repo):
    u = repo.crear_usuario("70000001")
    u["clave_hash"] = claves.hash_clave("123456")
    for _ in range(4):
        client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "654321"})
    assert client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "123456"}).status_code == 200
    assert client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "654321"}).status_code == 401
    assert client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "123456"}).status_code == 429


def test_confirmar_por_whatsapp_deja_obsoletos_los_fallos_pero_pedir_clave_adentro_no(client, repo):
    c, _u, clave = _comercio_con_clave(client, repo)
    for _ in range(5):
        _ingresar(client, "70123456", _mala(clave))
    assert _ingresar(client, "70123456", clave).status_code == 429
    # Pedir otra clave desde adentro (token) NO borra los fallos: si no, quien comparte el
    # número se limpiaría el contador.
    client.post("/comercio/clave", headers=_hdr(auth_token(c["id"])))
    assert len(_fallos(repo)) == 5
    # Probar el número por WhatsApp sí: el bloqueo no le queda a la clave nueva.
    _codigo, conf = _recuperar_y_confirmar(client, repo, "70123456", "59170123456")
    assert conf.status_code == 200
    assert len(_fallos(repo)) == 0 and len(_fallos(repo, "obsoleto")) == 5
    assert _ingresar(client, "70123456", conf.json()["clave_nueva"]).status_code == 200


# ---- límite por IP, con la IP real
def test_la_ip_real_es_el_ultimo_valor_de_x_forwarded_for():
    from types import SimpleNamespace

    from app.core.ip import ip_cliente

    def req(*lineas, host="10.0.0.1"):
        return SimpleNamespace(headers=SimpleNamespace(getlist=lambda _n: list(lineas)),
                               client=SimpleNamespace(host=host))

    assert ip_cliente(req("1.1.1.1, 2.2.2.2, 9.9.9.9")) == "9.9.9.9"      # el que agrega el proxy
    assert ip_cliente(req("6.6.6.6", "9.9.9.9")) == "9.9.9.9"             # dos encabezados
    assert ip_cliente(req("9.9.9.9, ")) == "9.9.9.9"
    assert ip_cliente(req()) == "10.0.0.1"                                # sin proxy: la conexión
    assert ip_cliente(req("", host="10.0.0.1")) == "10.0.0.1"


def test_20_fallos_por_hora_desde_una_ip_la_bloquean_y_el_primer_valor_inventado_no_la_salva(client, repo):
    _c, _u, clave = _comercio_con_clave(client, repo)
    for i in range(20):                                    # fallos previos de esa IP, en otros números
        repo.registrar_intento_clave("comercio_usuarios", f"5917000{i:04d}", [], "9.9.9.9")
    spoof = {"X-Forwarded-For": "1.2.3.4, 9.9.9.9"}        # el cliente inventa el primero; el proxy agrega el último
    r = client.post("/auth/comercio/ingresar", json={"whatsapp": "70123456", "clave": clave}, headers=spoof)
    assert r.status_code == 429                            # ni con la clave correcta
    otra_ip = {"X-Forwarded-For": "9.9.9.9, 4.4.4.4"}      # poner la IP bloqueada al principio no sirve: manda la última
    assert client.post("/auth/comercio/ingresar", json={"whatsapp": "70123456", "clave": clave},
                       headers=otra_ip).status_code == 200


def test_19_fallos_por_ip_todavia_dejan_pasar(client, repo):
    _c, _u, clave = _comercio_con_clave(client, repo)
    for i in range(19):
        repo.registrar_intento_clave("comercio_usuarios", f"5917000{i:04d}", [], "9.9.9.9")
    r = client.post("/auth/comercio/ingresar", json={"whatsapp": "70123456", "clave": clave},
                    headers={"X-Forwarded-For": "9.9.9.9"})
    assert r.status_code == 200


def test_el_limite_de_pedidos_de_main_usa_el_ultimo_valor_y_no_el_primero(client, repo):
    """Cambiar el primer valor en cada pedido ya no esquiva el límite de 20 por minuto."""
    estados = [client.post("/auth/comercio/recuperar", json={"whatsapp": "70000999"},
                           headers={"X-Forwarded-For": f"10.0.0.{i}, 7.7.7.7"}).status_code
               for i in range(21)]
    assert estados[:20] == [404] * 20 and estados[20] == 429


def test_los_buckets_vacios_o_vencidos_del_limitador_se_limpian():
    from collections import deque

    from app.main import _BUCKETS, _RL_WINDOW, _barrer_buckets

    ahora = time.time()
    _BUCKETS["/auth/:1.1.1.1"] = deque()                          # vacío
    _BUCKETS["/auth/:2.2.2.2"] = deque([ahora - _RL_WINDOW - 5])    # vencido
    _BUCKETS["/auth/:3.3.3.3"] = deque([ahora])                   # vigente
    _barrer_buckets(ahora)
    assert list(_BUCKETS) == ["/auth/:3.3.3.3"]


# ---- criterio 17: el WhatsApp ya no se edita desde Mi comercio (la PoC 2)
def test_criterio_17_put_perfil_no_cambia_el_whatsapp(client, repo):
    v, _clave = _victima(client, repo)
    t = auth_token("victima")
    for valor in ("71111111", None, "59170123456"):
        r = client.put("/comercio/perfil", headers=_hdr(t), json={"whatsapp": valor})
        assert r.status_code == 400, valor
        assert r.json()["detail"] == 'El número se cambia desde "Cambié de número"'
    assert v["whatsapp"] == "59170123456"
    # El dueño sigue pudiendo recuperar con su número, y el resto de la ficha se edita igual.
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).status_code == 200
    r = client.put("/comercio/perfil", headers=_hdr(t), json={"descripcion": "Herramientas"})
    assert r.status_code == 200 and r.json()["descripcion"] == "Herramientas"
    # Con el WhatsApp mezclado con otros campos, tampoco se guarda nada.
    r = client.put("/comercio/perfil", headers=_hdr(t), json={"descripcion": "X", "whatsapp": "71111111"})
    assert r.status_code == 400 and v["descripcion"] == "Herramientas"


def test_el_admin_si_puede_cambiar_el_whatsapp(client, repo, admin_token):
    repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="59170123456", activo=True)
    r = client.put("/admin/comercio/com-a", headers=_hdr(admin_token), json={"whatsapp": "71111111"})
    assert r.status_code == 200 and repo.comercios["com-a"]["whatsapp"] == "59171111111"


# ---- criterio 18 / punto 5: la clave sólo en la raíz, y con no-store
def test_clave_inicial_va_solo_en_la_raiz_del_autoregistro_y_del_alta_de_campo(client, repo):
    r = client.post("/auth/comercio/registro", files=_foto(),
                    data={"nombre": "Mi Tienda", "whatsapp": "70001111", "lat": "-22.7", "lng": "-64.3"})
    assert r.status_code == 200
    assert re.fullmatch(r"\d{6}", r.json()["clave_inicial"])
    assert "clave_inicial" not in r.json()["comercio"]
    r = _alta_campo(client, "70002222")
    assert r.status_code == 200
    assert re.fullmatch(r"\d{6}", r.json()["clave_inicial"])
    assert "clave_inicial" not in r.json()["comercio"]


def test_toda_respuesta_con_una_clave_lleva_cache_control_no_store(client, repo):
    nuevo = client.post("/auth/comercio/registro", files=_foto(),
                        data={"nombre": "Mi Tienda", "whatsapp": "70001111", "lat": "-22.7", "lng": "-64.3"})
    campo = _alta_campo(client, "70002222")
    c, _u, clave = _comercio_con_clave(client, repo, whatsapp="59170123456", slug="ferre")
    nueva = client.post("/comercio/clave", headers=_hdr(auth_token(c["id"])))
    ingreso = _ingresar(client, "70123456", nueva.json()["clave"])
    _codigo, conf = _recuperar_y_confirmar(client, repo, "70123456", "59170123456")
    codigo_u = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    _confirmar_por_webhook(repo, "59170000001", codigo_u)
    verif = client.post("/auth/usuario/verificar", json={"whatsapp": "70000001", "codigo": codigo_u})
    ing_u = client.post("/auth/usuario/ingresar",
                        json={"whatsapp": "70000001", "clave": verif.json()["clave_nueva"]})
    for nombre, r in {"registro": nuevo, "campo": campo, "clave": nueva, "ingresar": ingreso,
                      "confirmar": conf, "verificar": verif, "ingresar_usuario": ing_u}.items():
        assert r.status_code == 200, (nombre, r.text)
        assert r.headers.get("cache-control") == "no-store", nombre


# ---- punto 6: POST /comercio/clave, máximo 3 por hora por comercio
def test_post_comercio_clave_admite_3_por_hora_por_comercio_y_el_cuarto_da_429(client, repo):
    a = repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="59170123456", activo=True)
    b = repo.seed_comercio(id="com-b", slug="b", nombre="B", whatsapp="59170999888", activo=True)
    estados = [client.post("/comercio/clave", headers=_hdr(auth_token(a["id"]))).status_code for _ in range(4)]
    assert estados == [200, 200, 200, 429]
    assert client.post("/comercio/clave", headers=_hdr(auth_token(b["id"]))).status_code == 200   # otro comercio


# ---- punto 6: el consentimiento del comprador cuenta recién al verificar el número
def test_el_consentimiento_pendiente_no_lo_hereda_quien_confirma_otro_pedido_sin_tilde(client, repo):
    """Alguien tilda el consentimiento con el número de otro; el dueño del número pide su
    propio código SIN tilde y confirma: no consintió nada."""
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001", "consentimiento": True})
    (u,) = repo.compradores.values()
    assert u["consentimiento_pendiente"] is True and u["consentimiento_en"] is None
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    assert u["consentimiento_pendiente"] is False
    _confirmar_por_webhook(repo, "59170000001", codigo)
    assert u["consentimiento_en"] is None and u["consentimiento_ofertas"] is False


def test_sin_confirmar_el_numero_el_consentimiento_nunca_se_llena(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001", "consentimiento": True})
    (u,) = repo.compradores.values()
    assert u["consentimiento_en"] is None and u["consentimiento_ofertas"] is False


# ---- punto 6: logs de ingreso con quién, cómo y desde dónde; nunca la clave ni el número
def test_los_logs_de_ingreso_llevan_id_metodo_e_ip_y_ni_la_clave_ni_el_numero(client, repo, capfd):
    c, _u, clave = _comercio_con_clave(client, repo)
    _ingresar(client, "70123456", clave)
    _ingresar(client, "70123456", _mala(clave))
    _recuperar_y_confirmar(client, repo, "70123456", "59170123456")
    uc = repo.crear_usuario("70000001")
    uc["clave_hash"] = claves.hash_clave("123456")
    client.post("/auth/usuario/ingresar", json={"whatsapp": "70000001", "clave": "123456"},
                headers={"X-Forwarded-For": "8.8.8.8, 5.5.5.5"})
    salida = capfd.readouterr()
    todo = salida.out + salida.err
    ok = next(l for l in todo.splitlines() if "comercio.ingresar.ok" in l)
    assert f"comercio_id={c['id']}" in ok and "metodo=clave" in ok and "ip=testclient" in ok
    conf = next(l for l in todo.splitlines() if "comercio.recuperar.confirmado" in l)
    assert f"comercio_id={c['id']}" in conf and "metodo=whatsapp" in conf and "ip=" in conf
    u_ok = next(l for l in todo.splitlines() if "usuario.ingresar.ok" in l)
    assert f"usuario_id={uc['id']}" in u_ok and "metodo=clave" in u_ok and "ip=5.5.5.5" in u_ok
    # (El log del webhook `ingest.confirmacion` trae el teléfono: es de la ingesta, no del ingreso.)
    de_ingreso = "\n".join(l for l in todo.splitlines() if "ingest." not in l)
    assert not re.search(r"(?<!\d)(70123456|59170123456|70000001|59170000001)(?!\d)", de_ingreso), "el número apareció en un log"
    assert not re.search(rf"(?<!\d){clave}(?!\d)", todo), "la clave apareció en un log"


# ---- la migración 0137, tercera ronda
def test_la_0137_crea_clave_fallos_con_rls_grants_solo_service_role_y_la_funcion_atomica():
    sql = _sql_sin_comentarios()
    assert "create table if not exists public.clave_fallos" in sql
    assert "create index if not exists idx_clave_fallos_numero" in sql
    assert "create index if not exists idx_clave_fallos_ip" in sql
    assert "alter table clave_fallos enable row level security" in sql
    assert "grant all on public.clave_fallos to service_role" in sql
    assert "revoke all on public.clave_fallos from public, anon, authenticated" in sql
    # Una función que inserta y cuenta en una transacción, bajo lock por número.
    assert "create or replace function public.registrar_intento_clave" in sql
    assert "pg_advisory_xact_lock" in sql and "insert into public.clave_fallos" in sql
    assert "interval '15 minutes'" in sql and "interval '24 hours'" in sql and "interval '1 hour'" in sql
    # Las funciones nacen ejecutables por PUBLIC: se les quita y sólo las usa el backend.
    assert "revoke all on function public.registrar_intento_clave" in sql
    assert "grant execute on function public.registrar_intento_clave" in sql and "to service_role" in sql
    assert "consentimiento_pendiente" in sql


def test_el_fake_repo_cuenta_como_la_funcion_sql(repo):
    """El FakeRepo es el equivalente de `registrar_intento_clave`: cuenta CON el intento
    nuevo; los ok/bloqueados no suman; los obsoletos suman sólo a la IP."""
    r1 = repo.registrar_intento_clave("comercio_usuarios", "59170123456", ["c1"], "1.1.1.1")
    assert (r1["fallos_15m"], r1["fallos_24h"], r1["fallos_ip_1h"]) == (1, 1, 1)
    repo.resolver_intento_clave(r1["id"], "ok")
    r2 = repo.registrar_intento_clave("comercio_usuarios", "59170123456", ["c1"], "1.1.1.1")
    assert (r2["fallos_15m"], r2["fallos_ip_1h"]) == (1, 1)            # el 'ok' no cuenta
    repo.reiniciar_fallos_clave("comercio_usuarios", "59170123456")
    r3 = repo.registrar_intento_clave("comercio_usuarios", "59170123456", ["c1"], "1.1.1.1")
    assert r3["fallos_15m"] == 1 and r3["fallos_ip_1h"] == 2           # obsoleto: no al número, sí a la IP
    otra = repo.registrar_intento_clave("usuarios", "59170123456", [], "2.2.2.2")
    assert otra["fallos_15m"] == 1                                      # la tabla de compradores es aparte


# ══════════════════════════════════════ CAMBIOS DE NÚMERO (re-revisión de seguridad)
#
# Con el número en la mano se entra a Mi comercio. Todo cambio del WhatsApp de
# un comercio que ya existe pasa por la misma regla: no puede ser de otro
# comercio activo, y la clave se anula.

def _h_cambio(token):
    return {"Authorization": f"Bearer {token}"}


def _ficha_con_cuenta(repo, whatsapp="59170123456"):
    ciudad = repo.get_ciudad_id("bermejo")
    v = repo.seed_comercio(id="victima", nombre="Ferreteria", slug="ferr", whatsapp=whatsapp,
                           activo=True, ciudad_id=ciudad, cargado_por=None)
    cuenta = repo.crear_comercio_usuario({"comercio_id": v["id"], "nombre": v["nombre"]})
    return v, cuenta


def test_el_agente_no_puede_cambiar_un_whatsapp_ya_cargado(client, repo):
    """El ataque de la re-revisión: el agente ponía su número, entraba por
    WhatsApp, se llevaba la clave y volvía a poner el original."""
    from app.core import auth
    _ficha_con_cuenta(repo)
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.patch("/campo/mis-comercios/victima", headers=_h_cambio(t), json={"whatsapp": "79999999"})
    assert r.status_code == 400
    assert repo.comercios["victima"]["whatsapp"] == "59170123456"


def test_el_agente_puede_reescribir_el_mismo_numero_en_otro_formato(client, repo):
    from app.core import auth
    _ficha_con_cuenta(repo)
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.patch("/campo/mis-comercios/victima", headers=_h_cambio(t), json={"whatsapp": "7012 3456"})
    assert r.status_code == 200, r.text
    assert repo.comercios["victima"]["whatsapp"] == "59170123456"


def test_el_agente_completa_un_whatsapp_vacio_normalizado(client, repo):
    from app.core import auth
    _ficha_con_cuenta(repo, whatsapp=None)
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.patch("/campo/mis-comercios/victima", headers=_h_cambio(t), json={"whatsapp": "+591 7012-3456"})
    assert r.status_code == 200, r.text
    assert repo.comercios["victima"]["whatsapp"] == "59170123456"


def test_el_admin_que_cambia_el_numero_anula_la_clave(client, repo, admin_token):
    _, cuenta = _ficha_con_cuenta(repo)
    repo.set_clave_comercio(cuenta["id"], "hash-de-la-clave-vieja")
    r = client.put("/admin/comercio/victima", headers=_h_cambio(admin_token), json={"whatsapp": "70009999"})
    assert r.status_code == 200, r.text
    assert repo.comercios["victima"]["whatsapp"] == "59170009999"
    assert repo.usuarios[cuenta["id"]]["clave_hash"] is None


def test_el_admin_no_puede_poner_el_numero_de_otro_comercio(client, repo, admin_token):
    _ficha_con_cuenta(repo)
    repo.seed_comercio(id="otro", nombre="Otro", slug="otro", whatsapp="59170005555", activo=True)
    r = client.put("/admin/comercio/victima", headers=_h_cambio(admin_token), json={"whatsapp": "70005555"})
    assert r.status_code == 409
    assert repo.comercios["victima"]["whatsapp"] == "59170123456"


def test_el_admin_que_no_cambia_el_numero_no_anula_la_clave(client, repo, admin_token):
    _, cuenta = _ficha_con_cuenta(repo)
    repo.set_clave_comercio(cuenta["id"], "hash")
    r = client.put("/admin/comercio/victima", headers=_h_cambio(admin_token),
                   json={"whatsapp": "+591 7012-3456", "horario": "Lun-Sáb 9-19"})
    assert r.status_code == 200, r.text
    assert repo.usuarios[cuenta["id"]]["clave_hash"] == "hash"


def test_aprobar_un_cambio_de_numero_anula_la_clave(client, repo, admin_token):
    _, cuenta = _ficha_con_cuenta(repo)
    repo.set_clave_comercio(cuenta["id"], "hash")
    sol = repo.crear_solicitud_cambio_numero({"comercio_id": "victima", "whatsapp_nuevo": "70004444",
                                              "lat": -22.7, "lng": -64.3})
    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/aprobar", headers=_h_cambio(admin_token))
    assert r.status_code == 200, r.text
    assert repo.usuarios[cuenta["id"]]["clave_hash"] is None


def test_aprobar_un_numero_que_ya_es_de_otro_comercio_da_409(client, repo, admin_token):
    _ficha_con_cuenta(repo)
    repo.seed_comercio(id="otro", nombre="Otro", slug="otro", whatsapp="59170005555", activo=True)
    sol = repo.crear_solicitud_cambio_numero({"comercio_id": "victima", "whatsapp_nuevo": "70005555",
                                              "lat": -22.7, "lng": -64.3})
    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/aprobar", headers=_h_cambio(admin_token))
    assert r.status_code == 409
    assert repo.comercios["victima"]["whatsapp"] == "59170123456"


# ══════════════════════════════════════ el agente carga el horario

def test_el_agente_carga_el_horario_y_deja_de_ser_estimado(client, repo):
    """El filtro «Sin horario» de la app del agente llevaba a un editor que no
    podía cargarlo: el PATCH de campo ni siquiera aceptaba el campo."""
    from app.core import auth
    _ficha_con_cuenta(repo)
    repo.comercios["victima"]["horario_estimado"] = True
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.patch("/campo/mis-comercios/victima", headers=_h_cambio(t),
                     json={"horario": "  Lun-Sáb 8:00-12:00 y 14:30-20:00 "})
    assert r.status_code == 200, r.text
    assert repo.comercios["victima"]["horario"] == "Lun-Sáb 8:00-12:00 y 14:30-20:00"
    assert repo.comercios["victima"]["horario_estimado"] is False


def test_el_agente_puede_borrar_un_horario_mal_cargado(client, repo):
    from app.core import auth
    _ficha_con_cuenta(repo)
    repo.comercios["victima"]["horario"] = "Lun 9-10"
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.patch("/campo/mis-comercios/victima", headers=_h_cambio(t), json={"horario": ""})
    assert r.status_code == 200, r.text
    assert not repo.comercios["victima"]["horario"]


# ══════════════════════════════════════ un solo comercio, para el final del alta

def test_el_agente_pide_un_comercio_de_su_ciudad(client, repo):
    """«Completar comercio» tras el alta pedía la ciudad entera y, con la señal
    de la calle, fallaba: ahora pide ese comercio solo."""
    from app.core import auth
    _ficha_con_cuenta(repo)
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.get("/campo/mis-comercios/victima", headers=_h_cambio(t))
    assert r.status_code == 200, r.text
    assert r.json()["comercio"]["id"] == "victima"


def test_el_agente_no_ve_un_comercio_de_otra_ciudad(client, repo):
    from app.core import auth
    _ficha_con_cuenta(repo)
    t = auth.make_agente_token("otro@x.com", ciudad_slug="ciudad-que-no-es")
    r = client.get("/campo/mis-comercios/victima", headers=_h_cambio(t))
    assert r.status_code == 404


def test_un_comercio_dado_de_baja_no_se_abre(client, repo):
    from app.core import auth
    _ficha_con_cuenta(repo)
    repo.comercios["victima"]["activo"] = False
    t = auth.make_agente_token("agente@x.com", ciudad_slug="bermejo")
    r = client.get("/campo/mis-comercios/victima", headers=_h_cambio(t))
    assert r.status_code == 404
