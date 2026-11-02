"""Visitas que llegan desde asistentes de IA (docs/visibilidad-buscadores-ia.md §3.11).

La visita guarda dos pistas: `referido` (el host de la página de donde viene) y
`origen` (el `?ref=` / `?utm_source=` de la URL). ChatGPT agrega
`utm_source=chatgpt.com`; Perplexity y otros mandan referrer. Se mira `origen`
primero y después `referido`.

Límites que el panel tiene que decir: los AI Overviews y el AI Mode de Google llegan
como `google.com` (no se distinguen del Google normal) y ChatGPT a veces no manda
nada y cae como «directo».
"""
from __future__ import annotations

import re
from collections import Counter

#: fuente -> hosts (sufijo de host) o `host/ruta` (prefijo de ruta, para los que
#: comparten dominio con un buscador común: Bing, DuckDuckGo, X).
AI_SOURCES: dict[str, list[str]] = {
    "chatgpt": ["chatgpt.com", "chat.openai.com"],
    "perplexity": ["perplexity.ai"],
    "gemini": ["gemini.google.com", "bard.google.com"],
    "copilot": ["copilot.microsoft.com", "copilot.com", "bing.com/chat"],
    "claude": ["claude.ai"],
    "meta_ai": ["meta.ai"],
    "grok": ["grok.com", "x.ai", "x.com/i/grok"],
    "deepseek": ["deepseek.com"],
    "mistral": ["chat.mistral.ai"],
    "you": ["you.com"],
    "phind": ["phind.com"],
    "duckduckgo_ai": ["duck.ai", "duckduckgo.com/chat"],
}

#: Valores sueltos de `utm_source` que no son un host («chatgpt», «perplexity»).
_ALIAS_UTM: dict[str, str] = {
    "chatgpt": "chatgpt", "openai": "chatgpt",
    "perplexity": "perplexity",
    "gemini": "gemini", "bard": "gemini",
    "copilot": "copilot",
    "claude": "claude",
    "meta_ai": "meta_ai", "metaai": "meta_ai", "meta-ai": "meta_ai",
    "grok": "grok",
    "deepseek": "deepseek",
    "mistral": "mistral",
    "phind": "phind",
    "duck.ai": "duckduckgo_ai",
}

_ESQUEMA = re.compile(r"^[a-z][a-z0-9+.-]*://")


def _normalizar(valor: str | None) -> str:
    """`https://WWW.ChatGPT.com/c/1?x=1` -> `chatgpt.com/c/1`."""
    v = (valor or "").strip().lower()
    v = _ESQUEMA.sub("", v)
    v = v.split("?", 1)[0].split("#", 1)[0]
    if v.startswith("www."):
        v = v[4:]
    return v.strip("/ ")


def _coincide(valor: str, patron: str) -> bool:
    host, _, ruta = patron.partition("/")
    v_host, _, v_ruta = valor.partition("/")
    if not (v_host == host or v_host.endswith("." + host)):
        return False
    return not ruta or v_ruta == ruta or v_ruta.startswith(ruta + "/")


def _fuente_de(valor: str | None) -> str | None:
    v = _normalizar(valor)
    if not v:
        return None
    if v in _ALIAS_UTM:
        return _ALIAS_UTM[v]
    for fuente, patrones in AI_SOURCES.items():
        if any(_coincide(v, p) for p in patrones):
            return fuente
    return None


def classify_ai_source(origen: str | None, referido: str | None) -> str | None:
    """La fuente de IA de una visita, o None si no viene de un asistente.
    `origen` (utm_source / ref) manda sobre `referido` (host del referrer)."""
    return _fuente_de(origen) or _fuente_de(referido)


def summarize_ai_sources(filas: list[dict], top_rutas: int = 3) -> list[dict]:
    """`[{source, visits, people, business_views, top_routes}]` sobre las filas de
    `visitas` (con `ruta`, `sesion`, `origen`, `referido`). Ordenado por visitas.
    `business_views` = visitas a fichas de comercio (`/comercios/…`)."""
    visitas: Counter = Counter()
    gente: dict[str, set] = {}
    fichas: Counter = Counter()
    rutas: dict[str, Counter] = {}
    for v in filas:
        fuente = classify_ai_source(v.get("origen"), v.get("referido"))
        if not fuente:
            continue
        ruta = v.get("ruta") or "/"
        visitas[fuente] += 1
        gente.setdefault(fuente, set()).add(v.get("sesion"))
        if ruta.startswith("/comercios/"):
            fichas[fuente] += 1
        rutas.setdefault(fuente, Counter())[ruta] += 1
    return [
        {
            "source": f,
            "visits": n,
            "people": len(gente[f]),
            "business_views": fichas[f],
            "top_routes": [{"ruta": r, "n": c} for r, c in rutas[f].most_common(top_rutas)],
        }
        for f, n in sorted(visitas.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
