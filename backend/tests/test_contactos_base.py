"""La base de compradores: números normalizados, sin repetir, y conteos —
nunca listas de números— con el cruce contra los que ya usan URUKU."""
from app.services.contactos import normalizar_telefono, preparar_filas, slug_grupo


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_los_numeros_quedan_con_pais_como_los_usa_whatsapp():
    assert normalizar_telefono("+54 9 387 512-3456") == ("5493875123456", True)
    assert normalizar_telefono("0387 15 512 3456") == ("5493875123456", True)
    assert normalizar_telefono("011 15 4444 5555") == ("5491144445555", True)
    assert normalizar_telefono("71234567") == ("59171234567", True)
    assert normalizar_telefono("+591 7 123 4567") == ("59171234567", True)
    # Con un dígito de menos no se inventa: queda marcado.
    assert normalizar_telefono("549387512345") == ("549387512345", False)
    assert normalizar_telefono("") == ("", False)
    assert slug_grupo("Tours Salta – Compras Bermejo") == "tours-salta-compras-bermejo"


def test_se_deduplica_por_telefono_y_grupo():
    filas = [
        {"telefono": "387 5123456", "grupo": "Salta Tours"},
        {"telefono": "+54 9 387 512 3456", "grupo": "salta tours"},   # el mismo, escrito distinto
        {"telefono": "387 5123456", "grupo": "Jujuy"},                # otro grupo: vale
        {"telefono": "", "grupo": "Jujuy"},
        {"telefono": "12", "grupo": "Jujuy"},
    ]
    buenas, malas = preparar_filas(filas, "prueba.xlsx")
    assert [(b["telefono"], b["grupo_slug"]) for b in buenas] == [
        ("5493875123456", "salta-tours"), ("5493875123456", "jujuy"), ("12", "jujuy")]
    assert buenas[2]["valido"] is False
    assert [m["motivo"] for m in malas] == ["sin número", "número que no se entiende"]


def test_importar_y_resumen_desde_el_admin(client, repo, admin_token):
    repo.crear_usuario("5493875123456")     # uno de la base ya entró a URUKU
    r = client.post("/admin/contactos/importar", headers=_h(admin_token), json={
        "origen": "compradores.xlsx",
        "filas": [
            {"telefono": "387 5123456", "grupo": "Salta Tours", "ciudad": "Salta"},
            {"telefono": "387 5550000", "grupo": "Salta Tours"},
            {"telefono": "388 4441111", "grupo": "Jujuy Compras"},
            {"telefono": "387 5123456", "grupo": "Salta Tours"},   # repetido en el mismo archivo
        ]})
    assert r.status_code == 200 and r.json()["nuevos"] == 3 and r.json()["repetidos"] == 0
    # Otra vez el mismo archivo: nada nuevo.
    r2 = client.post("/admin/contactos/importar", headers=_h(admin_token), json={
        "filas": [{"telefono": "387 5123456", "grupo": "Salta Tours"}]})
    assert r2.json()["nuevos"] == 0 and r2.json()["repetidos"] == 1
    res = client.get("/admin/contactos/resumen", headers=_h(admin_token)).json()
    assert res["total"] == 3 and res["telefonos_distintos"] == 3 and res["en_uruku"] == 1
    assert res["grupos"][0] == {"grupo": "Salta Tours", "slug": "salta-tours", "contactos": 2, "en_uruku": 1}
    # Sin ser admin, no.
    assert client.get("/admin/contactos/resumen").status_code in (401, 403)
