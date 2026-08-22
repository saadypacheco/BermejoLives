#!/usr/bin/env python3
"""Construye el diccionario de sinónimos y se lo aplica a los comercios YA cargados.

Responde a: "los que ya están, ¿quedan sin sinónimos?". No: se calculan ahora,
sin volver a mirar las fotos.

Los productos ya están escritos en `prod_det_ia` desde el análisis anterior, y
para saber que "campera" también se dice "casaca" alcanza la palabra. La llamada
va SIN imágenes, que es lo que la hace barata, y se pide un diccionario de
términos en vez de un análisis por comercio: entre 161 locales hay unos pocos
cientos de productos repetidos, así que se pregunta una vez por término y no una
vez por local.

Dos etapas independientes, y ese es el punto:

  1. DICCIONARIO — pregunta a la IA. Cuesta (poco) y se hace una sola vez.
  2. APLICAR     — llena comercios.sinonimos desde el diccionario. GRATIS,
                   sin red, y se puede repetir cuantas veces haga falta:
                   después de corregir términos a mano, o cuando entren
                   comercios nuevos.

    # ver qué términos hay, sin llamar a nadie
    docker compose -f docker-compose.prod.yml exec -T backend \\
        python /app/scripts/construir_sinonimos.py

    # pedir el diccionario a la IA y guardarlo
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 backend \\
        python /app/scripts/construir_sinonimos.py

    # sólo re-aplicar el diccionario existente (no gasta un centavo)
    docker compose -f docker-compose.prod.yml exec -T -e APLICAR=1 -e SOLO_APLICAR=1 \\
        backend python /app/scripts/construir_sinonimos.py
"""
import os
import sys
from collections import Counter

sys.path.insert(0, "/app")

from app.db.repository import get_repo  # noqa: E402
from app.services.sinonimos import (  # noqa: E402
    TERMINOS_POR_LOTE,
    gemini_post,
    generar_diccionario,
    sinonimos_para,
    terminos_de_comercio,
)


def main() -> int:
    aplicar = os.environ.get("APLICAR") in {"1", "true", "si"}
    solo_aplicar = os.environ.get("SOLO_APLICAR") in {"1", "true", "si"}
    repo = get_repo()

    comercios = [c for c in repo.list_todos_comercios(None, 5000) if c.get("activo", True)]

    # Se piden primero los términos más repetidos: si una corrida se corta por
    # cuota, lo que quedó cubierto es lo que más comercios beneficia.
    frecuencia: Counter[str] = Counter()
    for c in comercios:
        frecuencia.update(terminos_de_comercio(c))

    # Antes de contar nada: ¿la tabla se puede leer? Una migración sin aplicar o
    # un PostgREST con el cache viejo devuelven un diccionario vacío, que se ve
    # idéntico a "primera corrida" — y ahí se pagarían las 16 llamadas para que
    # la escritura falle recién al final.
    if not repo.sinonimos_disponibles():
        print("ERROR: no se puede leer producto_sinonimos.")
        print("")
        print("  Falta aplicar la migración, o PostgREST tiene el cache viejo:")
        print("")
        print("    docker compose -f docker-compose.prod.yml exec -T postgres \\")
        print("      psql -U postgres -d postgres -f - "
              "< supabase/migrations/0050_producto_sinonimos.sql")
        print("    docker compose -f docker-compose.prod.yml restart postgrest")
        print("")
        print("  Se corta acá a propósito: sin la tabla, el diccionario se vería")
        print("  vacío y se gastarían las llamadas a la IA para nada.")
        return 1

    conocidos = repo.get_diccionario_sinonimos()
    faltantes = [t for t, _ in frecuencia.most_common() if t not in conocidos]

    print(f"Comercios activos:            {len(comercios)}")
    print(f"Términos distintos:           {len(frecuencia)}")
    print(f"Ya en el diccionario:         {len(conocidos)}"
          + ("   (tabla vacía: primera corrida)" if not conocidos else ""))
    print(f"Faltan preguntar:             {len(faltantes)}")
    print(f"Llamadas a la IA que implica: {-(-len(faltantes) // TERMINOS_POR_LOTE)}")
    print("\nLos 20 más repetidos:")
    for termino, veces in frecuencia.most_common(20):
        marca = "ya" if termino in conocidos else "--"
        print(f"    [{marca}] {termino:30} {veces:3} comercios")

    if not aplicar:
        print("\nSimulación. APLICAR=1 pide el diccionario y escribe.")
        return 0

    # ── 1. Diccionario ────────────────────────────────────────────────────────
    if faltantes and not solo_aplicar:
        print(f"\nPidiendo sinónimos para {len(faltantes)} términos…")
        nuevos = generar_diccionario(faltantes, gemini_post)
        escritos = repo.guardar_sinonimos(nuevos, origen="ia")
        print(f"  términos con sinónimos útiles: {len(nuevos)}")
        print(f"  guardados:                     {escritos}")
        for t, v in list(nuevos.items())[:15]:
            print(f"    {t:26} -> {v}")
        conocidos = repo.get_diccionario_sinonimos()
    elif solo_aplicar:
        print("\nSOLO_APLICAR: no se llama a la IA.")

    # ── 2. Aplicar a los comercios ────────────────────────────────────────────
    print(f"\nAplicando el diccionario ({len(conocidos)} términos) a los comercios…")
    con, sin, iguales = 0, 0, 0
    for c in comercios:
        nuevo = sinonimos_para(c, conocidos)
        if not nuevo:
            sin += 1
            continue
        if (c.get("sinonimos") or "") == nuevo:
            iguales += 1
            con += 1
            continue
        repo.update_comercio(c["id"], {"sinonimos": nuevo}, None)
        con += 1

    print(f"  comercios con sinónimos: {con}  (sin cambios: {iguales})")
    print(f"  sin ningún sinónimo:     {sin}")
    if sin:
        print("  (esos no tienen productos cargados, o sus productos no tienen"
              " otra forma de decirse)")
    print("\nAPLICADO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
