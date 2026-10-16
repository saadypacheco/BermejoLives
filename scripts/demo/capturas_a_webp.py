"""Pasa las capturas de los manuales de PNG a WebP para el sitio.

Los PNG (frontend/public/manuales/capturas/**/*.png) salen de
scripts/capturas-manual.mjs y se quedan en la máquina: sirven para editar los
videos, pero son ~36 MB. Los manuales usan el WebP (≈ 5 veces menos, misma
nitidez a la vista), que es lo que se versiona y se despliega.

    python scripts/demo/capturas_a_webp.py
"""
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parents[2] / "frontend" / "public" / "manuales" / "capturas"

hechas = 0
antes = despues = 0
for png in sorted(RAIZ.glob("*/*.png")):
    webp = png.with_suffix(".webp")
    if webp.exists() and webp.stat().st_mtime >= png.stat().st_mtime:
        continue
    Image.open(png).save(webp, "WEBP", quality=82, method=6)
    antes += png.stat().st_size
    despues += webp.stat().st_size
    hechas += 1
print(f"{hechas} convertidas: {antes / 1e6:.1f} MB en PNG -> {despues / 1e6:.1f} MB en WebP")
