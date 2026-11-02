"""Los videos de URUKU en la home pública (docs/contenido-redes-tecnico.md §15.1).

Una pieza se ve en la home SÓLO si: ya salió en al menos una red (`content_posts.status='posted'`),
su video y su portada siguen en el disco, y TODOS los comercios que aparecen en ella están activos
y con la autorización vigente. Las mismas condiciones valen para bajar el archivo: si dejan de
cumplirse, la lista no la trae y los archivos contestan 404.

Nada acá escribe en la base.
"""
from __future__ import annotations

from app.services import content_consent, content_storage

TITULO_COMPILADO = "Ofertas de la semana"
#: Redes de las que se devuelve el link del posteo (el canal de WhatsApp no tiene link público).
REDES_CON_LINK = ("tiktok", "instagram", "facebook", "youtube")
#: Cuántas candidatas se miran como máximo por pedido (las que no cumplan se descartan).
CANDIDATAS = 100


def _posteados(posts: list[dict]) -> list[dict]:
    return [p for p in posts if p.get("status") == "posted"]


def es_publica(crepo, pieza: dict, posts: list[dict] | None = None) -> bool:
    """¿Esta pieza puede verse (y bajarse) en la home?"""
    if pieza.get("status") != "published" or not pieza.get("activo", True):
        return False
    if pieza.get("files_purged_at") or not pieza.get("video_path") or not pieza.get("cover_path"):
        return False
    if not (content_storage.esta_en_disco(pieza["video_path"]) and content_storage.esta_en_disco(pieza["cover_path"])):
        return False
    posts = crepo.list_posts([pieza["id"]]) if posts is None else posts
    if not _posteados(posts):
        return False
    return content_consent.motivo_de_comercios(crepo, pieza) is None


def network_links(posts: list[dict]) -> dict[str, str]:
    """`{red: post_url}` de cada red publicada que tiene un link web."""
    out: dict[str, str] = {}
    for p in _posteados(posts):
        url = (p.get("post_url") or "").strip()
        if p.get("network") in REDES_CON_LINK and url.lower().startswith(("https://", "http://")):
            out[p["network"]] = url
    return out


def _fecha_de_publicacion(pieza: dict, posts: list[dict]) -> str | None:
    if pieza.get("published_at"):
        return str(pieza["published_at"])
    fechas = [str(p["posted_at"]) for p in _posteados(posts) if p.get("posted_at")]
    return max(fechas) if fechas else None


def video_response(pieza: dict, posts: list[dict], slug_de_ciudad: dict[str, str]) -> dict:
    """`PublicVideoResponse` (§15.1). Las URLs de los archivos son rutas relativas estables, sin firma."""
    f = pieza.get("facts") or {}
    propio = bool(pieza.get("comercio_id")) and bool(f.get("nombre"))
    base = f"/public/videos/{pieza['id']}"
    return {
        "id": pieza["id"],
        "title": f["nombre"] if propio else TITULO_COMPILADO,
        "comercio": {"nombre": f["nombre"], "slug": f.get("slug")} if propio else None,
        "city_slug": slug_de_ciudad.get(pieza.get("ciudad_id") or ""),
        "published_at": _fecha_de_publicacion(pieza, posts),
        "duration_s": float(pieza["duration_s"]) if pieza.get("duration_s") is not None else None,
        "cover_url": f"{base}/cover",
        "video_url": f"{base}/video",
        "network_links": network_links(posts),
    }


def listar(crepo, ciudad_slug: str | None, limite: int) -> list[dict]:
    """Los videos de la home, el más nuevo primero. Ciudad desconocida: lista vacía."""
    ciudades = crepo.list_ciudades()
    slug_de = {c["id"]: c["slug"] for c in ciudades}
    ciudad_id = None
    if ciudad_slug:
        ciudad_id = next((c["id"] for c in ciudades if c["slug"] == ciudad_slug), None)
        if ciudad_id is None:
            return []
    candidatas = crepo.list_published_with_video(ciudad_id, CANDIDATAS)
    if not candidatas:
        return []
    posts = crepo.list_posts([p["id"] for p in candidatas])
    por_pieza: dict[str, list[dict]] = {}
    for x in posts:
        por_pieza.setdefault(x["piece_id"], []).append(x)
    out: list[dict] = []
    for p in candidatas:
        mias = por_pieza.get(p["id"], [])
        if es_publica(crepo, p, mias):
            out.append(video_response(p, mias, slug_de))
            if len(out) >= limite:
                break
    return out
