"""Ayudas de los tests del contenido para redes: fotos, comercios suscriptores, bancos y piezas sembradas."""
from __future__ import annotations

import random
from datetime import timedelta
from io import BytesIO

from PIL import Image, ImageChops, ImageDraw

from app.services import cargas, content_storage

AGENTE = "agente@bermejolive.com"


def jpg(w: int = 1600, h: int = 1200, seed: int = 1, exif: bool = False) -> bytes:
    """Una foto de prueba: degradé con ruido (distinta por `seed`, para que no sea un duplicado)."""
    rnd = random.Random(seed)
    base = Image.linear_gradient("L").resize((w, h))
    im = Image.merge("RGB", [base, ImageChops.invert(base), base.transpose(Image.FLIP_LEFT_RIGHT)])
    d = ImageDraw.Draw(im)
    for _ in range(12):
        x, y, r = rnd.randrange(w), rnd.randrange(h), rnd.randrange(20, 120)
        d.ellipse([x, y, x + r, y + r], fill=tuple(rnd.randrange(256) for _ in range(3)))
    im = Image.blend(im, Image.effect_noise((w, h), 30).convert("RGB"), 0.2)
    buf = BytesIO()
    if exif:
        e = Image.Exif()
        e[271] = "CamaraSecreta"          # Make
        im.save(buf, format="JPEG", quality=85, exif=e)
    else:
        im.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def hoy():
    return cargas.hoy_bolivia()


def comercio(repo, cid="com-1", **kw):
    """Un comercio suscriptor al día (plan publica, paga_hasta en 20 días) y completo."""
    base = {"id": cid, "slug": f"local-{cid}", "nombre": f"Local {cid}", "activo": True, "plan": "publica",
            "plan_cortesia": False, "suspendido": False, "paga_hasta": (hoy() + timedelta(days=20)).isoformat(),
            "ciudad_id": "ciu-1", "whatsapp": "59170000001", "calle": "Calle Barrientos",
            "horario": "Lunes a sábado de 8 a 19", "rubros": {"nombre": "👕 Vidriería", "slug": "vidrios"},
            "lat": -22.7, "lng": -64.3, "cargado_por": AGENTE, "portada_url": None}
    base.update(kw)
    return repo.seed_comercio(**base)


def autorizar(crepo, cid, granted=True, via="admin"):
    return crepo.add_consent({"comercio_id": cid, "granted": granted, "via": via, "recorded_by": "admin@x"})


def banco(crepo, cid, n=5, w=1600, h=1200, uploaded_by="admin@x", **extra):
    """n fotos reales en el banco (archivo bajo CONTENT_DIR y su fila)."""
    out = []
    for i in range(n):
        proc = content_storage.procesar_foto(jpg(w, h, seed=hash((cid, i, w)) % 10_000))
        aid = content_storage.nuevo_id()
        rel_foto, rel_thumb = content_storage.guardar_foto(cid, aid, proc)
        out.append(crepo.insert_asset({"id": aid, "comercio_id": cid, "kind": "photo", "source": "admin_upload",
                                       "file_path": rel_foto, "thumb_path": rel_thumb, "sha256": proc["sha256"],
                                       "width": proc["width"], "height": proc["height"], "bytes": proc["bytes"],
                                       "uploaded_by": uploaded_by, **extra}))
    return out


def pieza(crepo, comercio_id="com-1", dia=None, pilar="comercio_del_dia", status="ready_for_review", **kw):
    dia = dia or (hoy() + timedelta(days=1))
    lunes = dia - timedelta(days=dia.weekday())
    facts = kw.pop("facts", {"pillar": pilar, "nombre": "Local com-1", "slug": "local-com-1", "ciudad": "Bermejo",
                             "hashtags_allowed": ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"], "allowed_numbers": []})
    fila = {"week_start": lunes.isoformat(), "scheduled_for": dia.isoformat(), "pillar": pilar,
            "comercio_id": comercio_id if pilar == "comercio_del_dia" else None, "status": status, "facts": facts,
            "template": pilar, "caption_tiktok": "Local com-1 en Bermejo. Búsquelo en uruku.bo",
            "caption_ig": "Local com-1 en Bermejo. Búsquelo en uruku.bo", "caption_channel": "Local com-1. Búsquelo en uruku.bo",
            "hashtags": ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"], "caption_engine": "template", "caption_checks": [],
            "created_by": "selector", **kw}
    return crepo.insert_piece(fila)


def h(token):
    return {"Authorization": f"Bearer {token}"}


def gemini_on(crepo):
    """Prende el interruptor de costo `gemini_content` (§17.2): por defecto está apagado y nada llama a Gemini."""
    from app.services import cost_switches
    cost_switches.set(crepo, cost_switches.GEMINI_CONTENT, True, "test@uruku.bo")
