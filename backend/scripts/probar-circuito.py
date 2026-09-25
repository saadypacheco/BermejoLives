"""El circuito de una oferta, de punta a punta, con el backend de verdad.

No toca producción: levanta la app con el repo de prueba (el mismo de los
tests) y le manda al webhook lo que mandaría WhatsApp. Sirve para ver qué
pasa con cada mensaje ANTES de salir a crear grupos.
"""
import sys, io, json
sys.path.insert(0, r'C:\repos\proyectosClaude\Bermejo\backend')
sys.stdout.reconfigure(encoding='utf-8')

from fastapi.testclient import TestClient
from app.main import app
from app.db.repository import get_repo
from tests.conftest import FakeRepo
from app.core.config import settings
from app.core import auth

repo = FakeRepo()
app.dependency_overrides[get_repo] = lambda: repo
c = TestClient(app)

# ── el escenario: un local con su código y su grupo, como quedaría en la calle
settings.wa_numeros_propios = "59164610187,59175314737"   # Registrador y Anfitrión
settings.wa_numeros_explorador = "59167677803"            # el Explorador
com = repo.crear_comercio({"nombre": "Bazzi", "slug": "bazzi", "activo": True, "whatsapp": "59171111111",
                           "rubro_slug": "ropa", "confiable": False})
repo.comercios[com["id"]]["codigo"] = "AQP5"
otro = repo.crear_comercio({"nombre": "Zapatería Luz", "slug": "zapateria-luz", "activo": True, "rubro_slug": "calzado"})
repo.comercios[otro["id"]]["codigo"] = "B7K2"
GRUPO = "120363000@g.us"

def wa(body, de="59171111111", chat=GRUPO, tipo="chat", media=None, from_me=False, mid=None):
    """Un mensaje como los que manda WAHA."""
    payload = {"id": mid or f"wamid.{abs(hash(body + de + str(media)))%10**8}", "from": chat, "fromMe": from_me,
               "body": body, "type": tipo, "timestamp": 1758800000,
               "participant": (de + "@c.us") if chat.endswith("@g.us") else None}
    if media:
        payload["hasMedia"] = True
        payload["mediaUrl"] = media
        payload["mimetype"] = "image/jpeg"
    return c.post("/ingest/webhook", json={"event": "message", "session": "default", "payload": payload})

def estado(titulo):
    print(f"\n── {titulo}")
    for p in repo.publicaciones:
        cm = repo.comercios.get(p.get("comercio_id"), {})
        print(f"   {p.get('tipo'):8} · {p.get('estado'):10} · {cm.get('nombre','?'):14} · "
              f"{(p.get('titulo') or p.get('descripcion') or '')[:38]!r} "
              f"· precio={p.get('precio')} {p.get('moneda') or ''}")
    if not repo.publicaciones:
        print("   (nada publicado)")

print("=" * 78)
print("1. EL GRUPO TODAVÍA NO ESTÁ ATADO: llega una foto y no se sabe de quién es")
print("=" * 78)
r = wa("Campera de jean Bs 250", media="https://x/foto1.jpg", tipo="image")
print("   respuesta:", r.status_code, r.json())
estado("publicaciones")

print("\n" + "=" * 78)
print("2. SE ATA EL GRUPO: el Anfitrión manda el código adentro del grupo")
print("=" * 78)
r = wa("URUKU-AQP5", de="59175314737")          # el Anfitrión, un número propio
print("   respuesta:", r.status_code, r.json())
print("   grupo atado a:", repo.comercios.get((repo.wa_grupos.get(GRUPO) or {}).get("comercio_id"), {}).get("nombre"))

print("\n" + "=" * 78)
print("3. EL COMERCIANTE MANDA, y cada mensaje se clasifica solo")
print("=" * 78)
casos = [
    ("Campera de jean Bs 250", "image", "https://x/campera.jpg"),
    ("Llegó la colección nueva", "image", "https://x/coleccion.jpg"),   # foto, pero es novedad
    ("", "image", "https://x/cartel.jpg"),                              # foto sola: el cartel
    ("Llegó mercadería nueva", "chat", None),
    ("Oferta: 2x1 en remeras", "chat", None),
    ("Pantalón 180 bolivianos", "chat", None),
    ("Mirá el video de la tienda https://tiktok.com/@bazzi/v/1", "chat", None),
    ("Hoy cerramos a las 16", "chat", None),
]
for cuerpo, tipo, media in casos:
    antes = len(repo.publicaciones)
    r = wa(cuerpo, tipo=tipo, media=media)
    tipo_detectado = "—"
    if len(repo.publicaciones) > antes:
        tipo_detectado = list(repo.publicaciones)[-1]["tipo"]
    print(f"   {(cuerpo[:42] or '(foto sin texto)'):46}{'📷 ' if media else '   '}→ {tipo_detectado}")
estado("lo que quedó")

print("\n" + "=" * 78)
print("4. LAS GUARDAS: lo que NO tiene que publicarse")
print("=" * 78)
antes = len(repo.publicaciones)
wa("hola Juan, mandá las fotos acá", de="59164610187")          # un número de URUKU
print(f"   mensaje del Registrador en el grupo      → {'NO publicó' if len(repo.publicaciones)==antes else 'PUBLICÓ (mal)'}")
antes = len(repo.publicaciones)
wa("Campera Bs 300", de="59199999999", chat="59199999999@c.us")  # desconocido, sin código
nuevo_borrador = next((c for c in repo.comercios.values() if c.get("whatsapp") == "59199999999"), None)
print(f"   1-a-1 de un desconocido sin código        → queda en moderación, y el borrador nace "
      f"{'APAGADO (no sale en el sitio)' if nuevo_borrador and not nuevo_borrador.get('activo', True) else 'ENCENDIDO (mal)'}")
antes = len(repo.publicaciones)
wa("URUKU-B7K2 zapatilla urbana Bs 180", de="59167677803", chat="59167677803@c.us",
   tipo="image", media="https://x/zapa.jpg")                      # el Explorador, con código
nuevo = list(repo.publicaciones)[-1] if len(repo.publicaciones) > antes else None
print(f"   el Explorador con el código de OTRO local → publicó para "
      f"{repo.comercios.get(nuevo['comercio_id'],{}).get('nombre') if nuevo else 'nadie'}"
      f" · contacto={nuevo.get('contacto_whatsapp') if nuevo else '-'}")

print("\n" + "=" * 78)
print("5. LA MODERACIÓN: lo que llegó espera aprobación")
print("=" * 78)
token = auth.make_token(settings.admin_email, "admin")
h = {"Authorization": f"Bearer {token}"}
pend = c.get("/moderacion/publicaciones?estado=pendiente", headers=h).json()
print(f"   pendientes: {pend.get('total', len(pend.get('items', [])))}")
primera = (pend.get("items") or [None])[0]
if primera:
    print(f"   apruebo: {primera.get('titulo') or primera.get('descripcion')}")
    r = c.post(f"/moderacion/publicaciones/{primera['id']}", headers=h, json={"estado": "aprobado"})
    print("   →", r.status_code, "estado ahora:", next(p["estado"] for p in repo.publicaciones if p["id"]==primera["id"]))

print("\n" + "=" * 78)
print("6. ¿SALE EN EL SITIO? (lo que vería el comprador)")
print("=" * 78)
for p in repo.publicaciones:
    if p["estado"] == "aprobado" and p.get("activo", True):
        cm = repo.comercios.get(p["comercio_id"], {})
        print(f"   ✓ {cm.get('nombre')} · {p['tipo']} · {(p.get('titulo') or p.get('descripcion') or '')[:40]}"
              f" · {p.get('precio')} {p.get('moneda') or ''}")
