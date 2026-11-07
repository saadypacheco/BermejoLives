#!/usr/bin/env bash
# Verificación después de cada deploy: todo lo que se puede comprobar SIN una persona.
#
#   QA:    cd /docker/buscadonde && DOMINIO=encontralo.store bash scripts/verificar.sh
#   Prod:  cd /docker/uruku && bash scripts/verificar.sh                (DOMINIO = uruku.bo)
#
#   Opciones:
#     --solo-web      sólo lo que se ve desde afuera (curl). Es lo que corre solo en una PC sin Docker.
#     --con-bloqueo   además prueba el bloqueo del login del panel (6 intentos con un correo inventado).
#                     Escribe filas de «intento fallido» en la base (no toca datos reales); ver docs/verificacion.md.
#     --ayuda         muestra esto.
#
#   Variables (todas opcionales):
#     DOMINIO            uruku.bo por defecto
#     COMMIT_ESPERADO    commit que debería estar corriendo (por defecto, `git rev-parse --short HEAD`)
#     MIGRACIONES_DESDE  primera migración a comprobar (por defecto 0180)
#     TIMEOUT            segundos por pedido (por defecto 30)
#
# NO ES DESTRUCTIVO. No escribe datos reales, no manda WhatsApp, no llama a APIs que cobran
# (Gemini, OpenAI) ni publica en redes. Las pruebas de permisos de la base corren dentro de una
# transacción que se deshace. No imprime nunca ningún valor de los .env: sólo largo o presencia.
#
# `set -e` NO va a propósito: un chequeo que falla no puede frenar a los demás.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2

SOLO_WEB=0
CON_BLOQUEO=0
for a in "$@"; do
  case "$a" in
    --solo-web) SOLO_WEB=1 ;;
    --con-bloqueo) CON_BLOQUEO=1 ;;
    -h|--ayuda|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opción desconocida: $a (probá --ayuda)"; exit 2 ;;
  esac
done

DOMINIO="${DOMINIO:-uruku.bo}"
TIMEOUT="${TIMEOUT:-30}"
MIGRACIONES_DESDE="${MIGRACIONES_DESDE:-0180}"
WEB="https://$DOMINIO"
API="https://api.$DOMINIO"
TILES="https://tiles.$DOMINIO"
UA_NAVEGADOR="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36"
UA_VERIFICAR="verificar-uruku/1.0 (curl)"

C_PG="buscadonde-postgres"
C_BACK="buscadonde-backend"
C_FRONT="buscadonde-frontend"
C_WAHA="buscadonde-waha"
C_REELS="buscadonde-reels"
C_TILES="uruku-tiles"
C_REST="buscadonde-postgrest"

T="$(mktemp -d 2>/dev/null || echo "/tmp/verificar.$$")"
mkdir -p "$T"
trap 'rm -rf "$T"' EXIT

# ── salida ────────────────────────────────────────────────────────────────────
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  V=$'\033[32m'; R=$'\033[31m'; A=$'\033[33m'; G=$'\033[90m'; N=$'\033[0m'; B=$'\033[1m'
else
  V=""; R=""; A=""; G=""; N=""; B=""
fi
N_OK=0; N_FALLA=0; N_AVISO=0; N_SALT=0
LISTA_FALLAS=()

ok()      { N_OK=$((N_OK+1));       printf '  %s[ OK     ]%s %s\n' "$V" "$N" "$1"; }
falla()   { N_FALLA=$((N_FALLA+1)); LISTA_FALLAS+=("$1"); printf '  %s[ FALLA  ]%s %s\n' "$R" "$N" "$1"; [ -n "${2:-}" ] && printf '             %s%s%s\n' "$G" "$2" "$N"; return 0; }
aviso()   { N_AVISO=$((N_AVISO+1)); printf '  %s[ AVISO  ]%s %s\n' "$A" "$N" "$1"; [ -n "${2:-}" ] && printf '             %s%s%s\n' "$G" "$2" "$N"; return 0; }
salteado(){ N_SALT=$((N_SALT+1));   printf '  %s[ SALTEADO ]%s %s\n' "$G" "$N" "$1"; }
titulo()  { printf '\n%s== %s ==%s\n' "$B" "$1" "$N"; }
primera_linea() { printf '%s' "$1" | tr -d '\r' | grep -v '^[[:space:]]*$' | head -n1 | cut -c1-200; }

# ── ayudantes ─────────────────────────────────────────────────────────────────
# fetch URL [args de curl...]  →  deja CODE, CTYPE, ERR; el cuerpo en $T/body y los encabezados en $T/hdr.
CODE=000; CTYPE=""; ERR=""
fetch() {
  local url="$1"; shift
  local out rc
  : > "$T/body"; : > "$T/hdr"
  out=$(curl -sS -m "$TIMEOUT" -A "$UA_VERIFICAR" -o "$T/body" -D "$T/hdr" -w '%{http_code} %{content_type}' "$@" "$url" 2>"$T/err")
  rc=$?
  CODE="${out%% *}"; CTYPE="${out#* }"
  [ -z "$CODE" ] && CODE=000
  ERR=""
  if [ "$rc" -ne 0 ] || [ "$CODE" = "000" ]; then
    CODE=000
    ERR="$(primera_linea "$(cat "$T/err" 2>/dev/null)")"
    [ -z "$ERR" ] && ERR="curl terminó con el código $rc"
  fi
}

# Igual que fetch, pero si no da 200 espera un poco y reintenta una vez (Traefik tarda en registrar un contenedor nuevo).
fetch_200() {
  fetch "$@"
  if [ "$CODE" != "200" ]; then sleep 3; fetch "$@"; fi
}

tiene_header() { grep -qi "^$1:" "$T/hdr"; }

# sql "consulta" → SQL_OUT, SQL_RC. Sólo lecturas, o pruebas dentro de una transacción que se deshace.
SQL_OUT=""; SQL_RC=0
sql() {
  SQL_OUT=$(docker exec "$C_PG" psql -U postgres -d postgres -X -q -A -t -c "$1" 2>&1)
  SQL_RC=$?
  SQL_OUT=$(printf '%s' "$SQL_OUT" | tr -d '\r')
}

json_campo() { # json_campo campo  (lee $T/body; valores string)
  sed -n 's/.*"'"$1"'" *: *"\([^"]*\)".*/\1/p' "$T/body" | head -n1
}

mismo_commit() { # los dos no vacíos y uno es prefijo del otro (el sha corto cambia de largo)
  [ -n "$1" ] && [ -n "$2" ] && { [ "${1#"$2"}" != "$1" ] || [ "${2#"$1"}" != "$2" ]; }
}

# ── ¿hay Docker del VPS? ──────────────────────────────────────────────────────
HAY_DOCKER=0
MOTIVO_SIN_DOCKER=""
if [ "$SOLO_WEB" = "1" ]; then
  MOTIVO_SIN_DOCKER="se pidió --solo-web"
elif ! command -v docker >/dev/null 2>&1; then
  MOTIVO_SIN_DOCKER="esta máquina no tiene docker"
elif ! docker ps >/dev/null 2>&1; then
  MOTIVO_SIN_DOCKER="docker no responde (¿apagado o sin permisos?)"
elif ! { docker inspect "$C_PG" >/dev/null 2>&1 || docker inspect "$C_BACK" >/dev/null 2>&1 || docker inspect "$C_FRONT" >/dev/null 2>&1; }; then
  MOTIVO_SIN_DOCKER="no es el VPS: no existen los contenedores buscadonde-*"
else
  HAY_DOCKER=1
fi

# ── ambiente y commit esperado ────────────────────────────────────────────────
if [ "$DOMINIO" = "uruku.bo" ]; then AMBIENTE_DEF="prod"; else AMBIENTE_DEF="qa"; fi
AMBIENTE="$AMBIENTE_DEF"
ESPERADO="${COMMIT_ESPERADO:-}"
[ -z "$ESPERADO" ] && ESPERADO="$(git rev-parse --short HEAD 2>/dev/null || true)"

printf '%sVerificación de URUKU%s  ·  %s  ·  %s\n' "$B" "$N" "$DOMINIO" "$(date '+%Y-%m-%d %H:%M')"
[ "$HAY_DOCKER" = "0" ] && printf '%sSin chequeos internos (%s): sólo lo que se ve desde afuera.%s\n' "$G" "$MOTIVO_SIN_DOCKER" "$N"

# ════════════════════════════════════════════════════════════════════════════
titulo "1. Contenedores"
if [ "$HAY_DOCKER" = "1" ]; then
  revisar_contenedor() { # nombre obligatorio(1/0)
    local n="$1" oblig="$2" e st hl rs
    e=$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}|{{.State.Restarting}}' "$n" 2>/dev/null) || e=""
    if [ -z "$e" ]; then
      if [ "$oblig" = "1" ]; then falla "$n no existe (no está creado)"; else salteado "$n no está creado (opcional)"; fi
      return
    fi
    st="${e%%|*}"; hl="${e#*|}"; hl="${hl%%|*}"; rs="${e##*|}"
    if [ "$st" != "running" ]; then falla "$n no está corriendo (estado: $st)"; return; fi
    if [ "$rs" = "true" ]; then falla "$n se reinicia en bucle"; return; fi
    case "$hl" in
      unhealthy) falla "$n está corriendo pero «unhealthy» (el healthcheck falla)" ;;
      starting)  aviso "$n todavía está arrancando (healthcheck «starting»); volvé a correr en un minuto" ;;
      healthy)   ok "$n corriendo y healthy" ;;
      *)         ok "$n corriendo" ;;
    esac
  }
  for c in "$C_FRONT" "$C_BACK" "$C_PG" "$C_REST" "$C_WAHA" "$C_TILES"; do revisar_contenedor "$c" 1; done
  revisar_contenedor "$C_REELS" 0
else
  salteado "Contenedores: $MOTIVO_SIN_DOCKER"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "2. Versión (qué código corre)"
FRONT_COMMIT=""; BACK_COMMIT=""
fetch_200 "$WEB/version"
if [ "$CODE" = "200" ]; then
  FRONT_COMMIT="$(json_campo commit)"
  VENV="$(json_campo env)"
  [ -n "$VENV" ] && AMBIENTE="$VENV"
  ok "$WEB/version contesta: commit ${FRONT_COMMIT:-?}, ambiente ${VENV:-sin etiqueta (se asume $AMBIENTE_DEF)}"
else
  falla "$WEB/version no contesta 200 (código $CODE)" "$ERR"
fi
fetch_200 "$API/health"
if [ "$CODE" = "200" ]; then
  BACK_COMMIT="$(json_campo commit)"
  BASE="$(json_campo base)"
  ok "$API/health contesta: commit ${BACK_COMMIT:-?}"
  if [ "$BASE" = "connected" ] && grep -q '"status" *: *"ok"' "$T/body"; then
    ok "El backend dice que la base está conectada (status ok)"
  else
    falla "El backend no ve la base: status/base = «$(tr -d '\r\n' < "$T/body" | cut -c1-160)»"
  fi
else
  falla "$API/health no contesta 200 (código $CODE)" "$ERR"
fi
if [ -n "$FRONT_COMMIT" ] && [ -n "$BACK_COMMIT" ]; then
  if [ "$FRONT_COMMIT" = "dev" ] || [ "$BACK_COMMIT" = "dev" ]; then
    falla "El build no recibió GIT_SHA (commit «dev»): se deployó sin pasar GIT_SHA=\$(git rev-parse --short HEAD)"
  elif mismo_commit "$FRONT_COMMIT" "$BACK_COMMIT"; then
    ok "Frontend y backend corren el mismo commit ($FRONT_COMMIT)"
  else
    falla "Frontend y backend corren commits DISTINTOS" "frontend=$FRONT_COMMIT  backend=$BACK_COMMIT (¿se reconstruyó sólo uno?)"
  fi
  if [ -n "$ESPERADO" ] && [ "$FRONT_COMMIT" != "dev" ]; then
    if mismo_commit "$FRONT_COMMIT" "$ESPERADO" && mismo_commit "$BACK_COMMIT" "$ESPERADO"; then
      ok "Coincide con el commit del repositorio ($ESPERADO)"
    else
      falla "No coincide con el commit esperado $ESPERADO" "frontend=$FRONT_COMMIT  backend=$BACK_COMMIT (¿falta el build o el git pull?)"
    fi
  else
    [ -z "$ESPERADO" ] && aviso "No se pudo saber el commit esperado (no es un repo git y no se pasó COMMIT_ESPERADO)"
  fi
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "3. Páginas públicas"
printf '  %sAmbiente detectado: %s%s\n' "$G" "$AMBIENTE" "$N"

fetch_200 "$WEB/"
if [ "$CODE" = "200" ]; then
  if grep -q "Muy pronto — URUKU" "$T/body"; then
    falla "/ muestra «Muy pronto»: el sitio está en MODO CAPTURA (MODO_CAPTURA=1 en el build)"
  else
    ok "/ responde 200 con el sitio real"
  fi
else
  falla "/ no responde 200 (código $CODE)" "$ERR"
fi

for p in /buscar /planes /que-es-uruku /comprar-en-bermejo /bermejo /terminos /privacidad /agentes /pagar /ofertas /novedades; do
  fetch_200 "$WEB$p"
  if [ "$CODE" = "200" ]; then ok "$p responde 200"; else falla "$p no responde 200 (código $CODE)" "$ERR"; fi
done

fetch_200 "$WEB/buscar?q=farmacia"
if [ "$CODE" != "200" ]; then
  falla "/buscar?q=farmacia no responde 200 (código $CODE)" "$ERR"
elif grep -q 'href="/comercios/' "$T/body"; then
  N_LINKS=$(grep -o 'href="/comercios/[^"]*"' "$T/body" | sort -u | wc -l | tr -d ' ')
  ok "/buscar?q=farmacia trae resultados en el HTML del servidor ($N_LINKS fichas distintas)"
  SLUG_BUSQUEDA="$(grep -o 'href="/comercios/[^"#?]*' "$T/body" | head -n1 | sed 's#href="/comercios/##')"
else
  falla "/buscar?q=farmacia responde 200 pero sin ningún link a una ficha" "el buscador no trajo resultados en el HTML (¿falla la lectura de la base o no hay farmacias?)"
fi

fetch_200 "$WEB/mapa" -L
if [ "$CODE" = "200" ]; then ok "/mapa responde 200 (después de redirigir)"; else falla "/mapa no responde 200 (código $CODE)" "$ERR"; fi
fetch_200 "$WEB/buscar?vista=mapa"
if [ "$CODE" = "200" ]; then ok "/buscar?vista=mapa responde 200"; else falla "/buscar?vista=mapa no responde 200 (código $CODE)" "$ERR"; fi

# Una ficha real y activa: de la base si se puede; si no, la primera de la búsqueda.
SLUG=""
if [ "$HAY_DOCKER" = "1" ]; then
  sql "select slug from public.comercios where activo and slug is not null and slug !~ '^comercio-[0-9]+\$' limit 1"
  [ "$SQL_RC" -eq 0 ] && SLUG="$(primera_linea "$SQL_OUT")"
  printf '%s' "$SLUG" | grep -qE '^[a-z0-9-]+$' || SLUG=""
fi
[ -z "$SLUG" ] && SLUG="${SLUG_BUSQUEDA:-}"
if [ -n "$SLUG" ]; then
  fetch_200 "$WEB/comercios/$SLUG"
  if [ "$CODE" = "200" ]; then ok "Ficha de un comercio real (/comercios/$SLUG) responde 200"; else falla "Ficha /comercios/$SLUG no responde 200 (código $CODE)" "$ERR"; fi
else
  falla "No se pudo elegir un comercio activo para probar su ficha" "ni la base ni la búsqueda dieron un slug"
fi

# robots.txt y sitemap.xml: en prod se indexa; en QA no (y el sitemap sale vacío a propósito).
fetch_200 "$WEB/robots.txt"
if [ "$CODE" != "200" ]; then
  falla "/robots.txt no responde 200 (código $CODE)" "$ERR"
else
  # Sólo importa el grupo «User-agent: *» (en prod otros grupos, como los scrapers abusivos, sí llevan «Disallow: /»).
  ROBOTS_ASTERISCO=$(awk 'BEGIN { RS = ""; FS = "\n" }
    { t = tolower($0); if (t ~ /user-agent: *\*/) { if (t ~ /\ndisallow: \/[ \t\r]*(\n|$)/ && t !~ /\nallow: \/[ \t\r]*(\n|$)/) bad = 1; vio = 1 } }
    END { print (bad ? "BLOQUEA" : (vio ? "PERMITE" : "SIN_GRUPO")) }' "$T/body")
  if [ "$AMBIENTE" = "prod" ]; then
    if [ "$ROBOTS_ASTERISCO" = "PERMITE" ] && grep -qi '^sitemap:' "$T/body"; then
      ok "/robots.txt de producción: permite rastrear y declara el sitemap"
    else
      falla "/robots.txt de PRODUCCIÓN bloquea todo o no declara el sitemap (grupo *: $ROBOTS_ASTERISCO)" "$(head -c 160 "$T/body" | tr '\r\n' '  ')"
    fi
  else
    if [ "$ROBOTS_ASTERISCO" = "BLOQUEA" ]; then ok "/robots.txt de QA bloquea todo (correcto: QA no se indexa)"; else falla "/robots.txt de QA NO bloquea el rastreo (grupo *: $ROBOTS_ASTERISCO)" "$(head -c 160 "$T/body" | tr '\r\n' '  ')"; fi
  fi
fi
fetch_200 "$WEB/sitemap.xml"
if [ "$CODE" != "200" ]; then
  falla "/sitemap.xml no responde 200 (código $CODE)" "$ERR"
else
  N_LOC=$(grep -o '<loc>' "$T/body" | wc -l | tr -d ' ')
  if [ "$AMBIENTE" = "prod" ]; then
    if [ "$N_LOC" -gt 1000 ]; then ok "/sitemap.xml de producción lista $N_LOC direcciones"; else falla "/sitemap.xml de PRODUCCIÓN lista sólo $N_LOC direcciones (se esperan más de 1000)" "si es 0 o muy bajo, el sitemap no pudo leer la base"; fi
  else
    if [ "$N_LOC" -le 5 ]; then ok "/sitemap.xml de QA casi vacío ($N_LOC direcciones; esperado: QA no se indexa)"; else aviso "/sitemap.xml de QA lista $N_LOC direcciones (se esperaba casi vacío)"; fi
  fi
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "4. Mapa (tiles)"
fetch "$TILES/0/0/0.png"
if [ "$CODE" = "200" ] && printf '%s' "$CTYPE" | grep -qi '^image/'; then
  ok "$TILES/0/0/0.png devuelve una imagen (${CTYPE%%;*})"
elif [ "$CODE" = "000" ]; then
  falla "tiles.$DOMINIO no responde" "$ERR"
else
  falla "$TILES/0/0/0.png devolvió código $CODE, tipo «$CTYPE» (se esperaba 200 image/png)"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "5. Seguridad"
# 5.1 La base no se ve desde internet
fetch "https://db.$DOMINIO/rest/v1/"
case "$CODE" in
  200) falla "https://db.$DOMINIO/rest/v1/ RESPONDE 200: la base está expuesta a internet" ;;
  000) ok "db.$DOMINIO no es alcanzable desde internet (sin respuesta: correcto)" ;;
  *)   ok "db.$DOMINIO/rest/v1/ no responde 200 (código $CODE: correcto)" ;;
esac

# 5.2 WAHA: el compose no lo publica por ningún hostname; el puerto va sólo a 127.0.0.1
WAHA_EXPUESTO=""
for h in waha whatsapp wa; do
  fetch "https://$h.$DOMINIO/"
  [ "$CODE" = "200" ] && WAHA_EXPUESTO="$WAHA_EXPUESTO $h.$DOMINIO"
done
if [ -n "$WAHA_EXPUESTO" ]; then
  falla "El dashboard de WAHA responde 200 en un hostname público:$WAHA_EXPUESTO" "cualquiera podría re-vincular el número de WhatsApp"
else
  ok "WAHA no responde 200 en waha./whatsapp./wa.$DOMINIO"
fi
if [ "$HAY_DOCKER" = "1" ]; then
  PUBLICADOS=""
  for c in "$C_WAHA" "$C_PG" "$C_REST" "$C_BACK" "$C_FRONT" "$C_TILES"; do
    # `docker port` imprime «3000/tcp -> 127.0.0.1:3010»; algo distinto de 127.0.0.1 = abierto a todos.
    while IFS= read -r l; do
      [ -z "$l" ] && continue
      case "$l" in *"-> 127.0.0.1:"*|*"-> [::1]:"*) ;; *) PUBLICADOS="$PUBLICADOS $c($l)";; esac
    done < <(docker port "$c" 2>/dev/null)
  done
  if [ -z "$PUBLICADOS" ]; then ok "Ningún contenedor publica puertos fuera de 127.0.0.1 (WAHA, Postgres, PostgREST, backend, frontend, tiles)"; else falla "Hay puertos publicados a todas las interfaces:$PUBLICADOS"; fi
else
  salteado "Puertos publicados por los contenedores: $MOTIVO_SIN_DOCKER"
fi

# 5.3 Permisos de la base: anon no puede escribir ni leer lo privado (transacción que se deshace)
anon_denegado() { # descripción  sentencia
  sql "begin; set local role anon; $2; rollback;"
  if printf '%s' "$SQL_OUT" | grep -qiE 'permission denied|permiso denegado'; then
    ok "anon NO puede $1 (permission denied)"
  else
    falla "anon NO fue rechazado al intentar $1" "respuesta de la base: $(primera_linea "$SQL_OUT")"
  fi
}
if [ "$HAY_DOCKER" = "1" ]; then
  anon_denegado "insertar en visitas"        "insert into public.visitas default values"
  anon_denegado "insertar en leads"          "insert into public.leads default values"
  anon_denegado "insertar en site_events"    "insert into public.site_events default values"
  anon_denegado "leer leads"                 "select count(*) from public.leads"
  anon_denegado "leer el correo de comercios" "select email from public.comercios limit 1"
else
  salteado "Permisos de anon en la base: $MOTIVO_SIN_DOCKER"
fi

# 5.4 Encabezados de seguridad de la home
if curl -sS -m "$TIMEOUT" -A "$UA_VERIFICAR" -D "$T/hdr" -o /dev/null "$WEB/" 2>/dev/null; then
  FALTAN=""
  for h in strict-transport-security x-frame-options content-security-policy-report-only; do
    tiene_header "$h" || FALTAN="$FALTAN $h"
  done
  if [ -z "$FALTAN" ]; then ok "La home trae strict-transport-security, x-frame-options y content-security-policy-report-only"; else falla "A la home le faltan encabezados de seguridad:$FALTAN" "los pone Traefik (compose) y Next (next.config.mjs)"; fi
  if [ "$AMBIENTE" = "prod" ]; then
    if tiene_header x-robots-tag && grep -i '^x-robots-tag:' "$T/hdr" | grep -qi 'noindex'; then falla "La home de PRODUCCIÓN manda X-Robots-Tag noindex: los buscadores NO la van a indexar" "revisá APP_ENV=prod en el build del frontend"; else ok "La home de producción no manda noindex"; fi
  else
    if grep -i '^x-robots-tag:' "$T/hdr" | grep -qi 'noindex'; then ok "La home de QA manda X-Robots-Tag noindex (correcto)"; else falla "La home de QA NO manda noindex: se podría indexar con datos reales"; fi
  fi
else
  falla "No se pudo pedir la home para revisar encabezados" "$(primera_linea "$(curl -sS -m 10 -o /dev/null "$WEB/" 2>&1)")"
fi

# 5.5 El bundle del navegador no trae nada de la base (rest/v1, JWT, la anon key real)
fetch_200 "$WEB/"
if [ "$CODE" = "200" ]; then
  cp "$T/body" "$T/home.html"
  fetch "$WEB/buscar" ; [ "$CODE" = "200" ] && cp "$T/body" "$T/buscar.html"
  # Los .js que referencia el HTML: <script src="/_next/static/...js"> y, dentro del payload de Next, "static/chunks/...js".
  cat "$T/home.html" "$T/buscar.html" 2>/dev/null | grep -oE 'static/[A-Za-z0-9_./%()~\[-]+\.js' | sed 's#^#/_next/#' | sort -u | head -n 150 > "$T/js.lista"
  N_JS=$(wc -l < "$T/js.lista" | tr -d ' ')
  if [ "$N_JS" -eq 0 ]; then
    aviso "No se encontraron archivos JS en el HTML de la home (¿cambió el formato?); no se pudo revisar el bundle"
  else
    mkdir -p "$T/js"; i=0
    while IFS= read -r u; do
      i=$((i+1))
      curl -sS -m "$TIMEOUT" -o "$T/js/$i.js" "$WEB$u" 2>/dev/null &
      while [ "$(jobs -r | wc -l)" -ge 8 ]; do sleep 0.2; done
    done < "$T/js.lista"
    wait
    cat "$T/home.html" > "$T/js/_home.html"
    BAD=""
    grep -lF 'rest/v1' "$T"/js/* >/dev/null 2>&1 && BAD="$BAD «rest/v1»"
    grep -lE 'eyJhbGciOi[A-Za-z0-9_-]{10,}\.eyJ' "$T"/js/* >/dev/null 2>&1 && BAD="$BAD «JWT (eyJ...)»"
    if [ "$HAY_DOCKER" = "1" ]; then
      # La anon key REAL del frontend, sin imprimirla: va a un archivo temporal sólo para el grep.
      docker exec "$C_FRONT" printenv SUPABASE_ANON_KEY 2>/dev/null | tr -d '\r\n' > "$T/key.txt"
      if [ "$(wc -c < "$T/key.txt" | tr -d ' ')" -ge 20 ]; then
        printf '\n' >> "$T/key.txt"
        grep -lF -f "$T/key.txt" "$T"/js/* >/dev/null 2>&1 && BAD="$BAD «la anon key real»"
      fi
      rm -f "$T/key.txt"
    fi
    if [ -z "$BAD" ]; then ok "El bundle del navegador ($N_JS archivos JS + HTML) no trae rest/v1 ni claves JWT"; else falla "El bundle del navegador trae:$BAD" "el navegador no debe hablar con la base (AGENTS.md regla 7); corré «npm run check:bundle» en el build"; fi
  fi
else
  falla "No se pudo bajar la home para revisar el bundle (código $CODE)" "$ERR"
fi

# 5.6 Bloqueo del login del panel (opcional)
if [ "$CON_BLOQUEO" = "1" ]; then
  FAKE="verificar-$(date +%s)$RANDOM@example.invalid"
  CODIGOS=""
  for n in 1 2 3 4 5 6; do
    fetch "$API/auth/login" -X POST -H 'Content-Type: application/json' -H "Origin: $WEB" -H "User-Agent: $UA_NAVEGADOR" \
      --data-binary "{\"email\":\"$FAKE\",\"password\":\"clave-inventada-$RANDOM\"}"
    CODIGOS="$CODIGOS $CODE"
  done
  set -- $CODIGOS
  if [ "$1$2$3$4$5" = "401401401401401" ] && [ "$6" = "429" ]; then
    ok "Login del panel: 5 intentos con clave mala dan 401 y el 6.º queda bloqueado (429)"
  else
    falla "Login del panel: la secuencia de códigos no fue 401×5 y 429" "obtenido:$CODIGOS (si empieza en 429, esta IP ya estaba bloqueada: 20 fallos por hora)"
  fi
else
  salteado "Bloqueo del login del panel (opcional: agregá --con-bloqueo; escribe 6 intentos fallidos con un correo inventado)"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "6. Medición"
fetch "$API/collect" -X POST -H 'Content-Type: text/plain;charset=UTF-8' -H "Origin: $WEB" -H "User-Agent: $UA_NAVEGADOR" \
  --data-binary '{"t":"pv","path":"/admin/verificar","session":"verificar0123456789","first":true}'
if [ "$CODE" = "204" ]; then
  ok "POST /collect contesta 204 (se manda a una ruta interna: no se guarda ninguna visita)"
else
  falla "POST /collect devolvió $CODE (se esperaba 204)" "$ERR"
fi
fetch_200 "$API/public/measurement-config"
if [ "$CODE" = "200" ] && grep -q '"internal" *: *true' "$T/body"; then
  ok "GET /public/measurement-config dice internal:true"
else
  falla "GET /public/measurement-config: código $CODE, cuerpo «$(tr -d '\r\n' < "$T/body" | cut -c1-120)»" "se esperaba {\"internal\":true,...}"
fi
fetch "$API/lead" -X POST -H 'Content-Type: application/json' -H "Origin: $WEB" -H "User-Agent: $UA_NAVEGADOR" \
  --data-binary '{"comercio_id":"00000000-0000-4000-8000-000000000000","tipo":"whatsapp"}'
if [ "$CODE" = "200" ] && grep -q '"ok" *: *false' "$T/body"; then
  ok "POST /lead con un comercio que no existe contesta {ok:false} (no se guarda nada)"
else
  falla "POST /lead con un comercio inexistente: código $CODE, cuerpo «$(tr -d '\r\n' < "$T/body" | cut -c1-120)»" "se esperaba {\"ok\":false}; si guarda la fila se «envenena» el lote de leads"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "7. Datos de los planes"
if [ "$HAY_DOCKER" = "1" ]; then
  sql "select slug || '=' || coalesce(fotos_max::text,'NULL') from public.planes where slug in ('gratis','publica','destacado','pro','empleado_ia') order by slug"
  if [ "$SQL_RC" -ne 0 ]; then
    falla "No se pudo leer la tabla planes" "$(primera_linea "$SQL_OUT")"
  else
    MAL=""
    for par in gratis=0 publica=60 destacado=130 pro=310 empleado_ia=510; do
      printf '%s\n' "$SQL_OUT" | grep -qx "$par" || MAL="$MAL ${par%%=*}(esperado ${par#*=}, hay: $(printf '%s\n' "$SQL_OUT" | grep "^${par%%=*}=" | head -n1 | cut -d= -f2))"
    done
    if [ -z "$MAL" ]; then ok "fotos_max correcto: gratis 0 · publica 60 · destacado 130 · pro 310 · empleado_ia 510"; else falla "fotos_max no coincide:$MAL" "falta aplicar la migración 0188_fotos_por_plan_v2.sql"; fi
  fi
  sql "select count(*) from public.planes where slug = 'gratis' and descripcion ilike '%Despu%s segu%s%'"
  if [ "$SQL_RC" -ne 0 ]; then
    falla "No se pudo leer la descripción del plan gratis" "$(primera_linea "$SQL_OUT")"
  elif [ "$(primera_linea "$SQL_OUT")" = "0" ]; then
    ok "La descripción del plan gratis no dice «Después seguís»"
  else
    falla "La descripción del plan gratis todavía dice «Después seguís…»" "falta aplicar 0189_plan_gratis_texto.sql"
  fi
else
  salteado "Datos de planes: $MOTIVO_SIN_DOCKER"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "8. Migraciones aplicadas"
if [ "$HAY_DOCKER" = "1" ]; then
  if ! ls supabase/migrations/*.sql >/dev/null 2>&1; then
    falla "No se encuentra supabase/migrations/ (¿se corrió desde la carpeta del compose?)"
  else
    # De cada archivo ≥ MIGRACIONES_DESDE se sacan las tablas, vistas, funciones y columnas que crea,
    # y se comprueba que existan. Así la lista se arma sola cuando se suman migraciones.
    for f in supabase/migrations/*.sql; do
      b="$(basename "$f")"; num="${b%%_*}"
      case "$num" in ''|*[!0-9]*) continue ;; esac
      [ "$num" \< "$MIGRACIONES_DESDE" ] && continue
      awk -v mig="$num" '
        { l = tolower($0); sub(/--.*/, "", l) }
        match(l, /^[ \t]*create[ \t]+(or[ \t]+replace[ \t]+)?(materialized[ \t]+)?(table|view)[ \t]+(if[ \t]+not[ \t]+exists[ \t]+)?(public\.)?[a-z_][a-z_0-9]*/) {
          t = substr(l, RSTART, RLENGTH); n = split(t, p, /[ \t]+/); s = p[n]; sub(/^public\./, "", s)
          print "rel|" s "||" mig
        }
        match(l, /^[ \t]*create[ \t]+(or[ \t]+replace[ \t]+)?function[ \t]+(public\.)?[a-z_][a-z_0-9]*/) {
          t = substr(l, RSTART, RLENGTH); n = split(t, p, /[ \t]+/); s = p[n]; sub(/^public\./, "", s)
          print "fn|" s "||" mig
        }
        match(l, /alter[ \t]+table[ \t]+(if[ \t]+exists[ \t]+)?(only[ \t]+)?(public\.)?[a-z_][a-z_0-9]*/) {
          t = substr(l, RSTART, RLENGTH); n = split(t, p, /[ \t]+/); tabla = p[n]; sub(/^public\./, "", tabla)
        }
        tabla != "" && match(l, /add[ \t]+column[ \t]+(if[ \t]+not[ \t]+exists[ \t]+)?[a-z_][a-z_0-9]*/) {
          t = substr(l, RSTART, RLENGTH); n = split(t, p, /[ \t]+/)
          print "col|" p[n] "|" tabla "|" mig
        }
        index(l, ";") { tabla = "" }
      ' "$f"
    done | sort -u > "$T/objetos.txt"
    N_OBJ=$(wc -l < "$T/objetos.txt" | tr -d ' ')
    N_MIG=$(cut -d'|' -f4 "$T/objetos.txt" | sort -u | wc -l | tr -d ' ')
    if [ "$N_OBJ" -eq 0 ]; then
      aviso "No se encontró ningún objeto para comprobar en las migraciones ≥ $MIGRACIONES_DESDE"
    else
      VALORES=$(awk -F'|' '{ printf "%s('"'"'%s'"'"','"'"'%s'"'"','"'"'%s'"'"','"'"'%s'"'"')", (NR>1?",":""), $1, $2, $3, $4 }' "$T/objetos.txt")
      sql "with q(tipo, nombre, tabla, mig) as (values $VALORES)
           select mig || ' ' || tipo || ' ' || case when tabla <> '' then tabla || '.' else '' end || nombre
           from q where not (case tipo
             when 'rel' then to_regclass('public.' || nombre) is not null
             when 'fn'  then exists (select 1 from pg_proc p join pg_namespace n on n.oid = p.pronamespace where n.nspname = 'public' and p.proname = nombre)
             when 'col' then exists (select 1 from information_schema.columns where table_schema = 'public' and table_name = tabla and column_name = nombre)
           end) order by 1"
      if [ "$SQL_RC" -ne 0 ]; then
        falla "No se pudieron comprobar las migraciones" "$(primera_linea "$SQL_OUT")"
      elif [ -z "$SQL_OUT" ]; then
        ok "Migraciones $MIGRACIONES_DESDE en adelante: los $N_OBJ objetos de $N_MIG migraciones existen en la base"
      else
        printf '%s\n' "$SQL_OUT" | cut -d' ' -f1 | sort -u > "$T/faltan.txt"
        FALTAN_MIG="$(tr '\n' ' ' < "$T/faltan.txt")"
        falla "Falta aplicar migraciones: $FALTAN_MIG"
        printf '%s\n' "$SQL_OUT" | while IFS= read -r l; do printf '             %sfalta: %s%s\n' "$G" "$l" "$N"; done
        printf '             %sSe aplican con: bash scripts/deploy-prod.sh --sql supabase/migrations/<archivo>.sql frontend%s\n' "$G" "$N"
      fi
    fi
  fi
else
  salteado "Migraciones: $MOTIVO_SIN_DOCKER"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "9. Interruptores de costo"
if [ "$HAY_DOCKER" = "1" ]; then
  sql "select key || '=' || case when enabled then 'ENCENDIDO' else 'apagado' end || ' (' || updated_by || ', ' || to_char(updated_at, 'YYYY-MM-DD') || ')' from public.cost_switches order by key"
  if [ "$SQL_RC" -ne 0 ]; then
    falla "No se pudo leer cost_switches" "$(primera_linea "$SQL_OUT")"
  elif [ -z "$SQL_OUT" ]; then
    ok "cost_switches sin filas: todo apagado (sin fila = apagado)"
  else
    printf '%s\n' "$SQL_OUT" | while IFS= read -r l; do printf '             %s%s%s\n' "$G" "$l" "$N"; done
    if printf '%s\n' "$SQL_OUT" | grep -q 'ENCENDIDO'; then
      aviso "Hay interruptores de costo ENCENDIDOS (gastan plata): confirmá que es a propósito"
    else
      ok "Todos los interruptores de costo están apagados"
    fi
  fi
else
  salteado "Interruptores de costo: $MOTIVO_SIN_DOCKER"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "10. WhatsApp (sesión de WAHA)"
if [ "$HAY_DOCKER" = "1" ]; then
  # Se llama a WAHA desde el backend, con su misma clave (que no se imprime).
  SES=$(docker exec -i "$C_BACK" python - 2>&1 <<'PY'
import os, json, urllib.request
base = os.environ.get("WAHA_BASE_URL", "http://buscadonde-waha:3000").rstrip("/")
clave = os.environ.get("WAHA_API_KEY", "")
if not clave:
    print("SIN_CLAVE"); raise SystemExit(0)
req = urllib.request.Request(base + "/api/sessions?all=true", headers={"X-Api-Key": clave})
try:
    datos = json.load(urllib.request.urlopen(req, timeout=8))
except Exception as e:
    print("ERROR " + e.__class__.__name__); raise SystemExit(0)
print(" ".join("%s=%s" % (s.get("name"), s.get("status")) for s in datos) or "SIN_SESIONES")
PY
  )
  SES="$(primera_linea "$SES")"
  case "$SES" in
    SIN_CLAVE)     falla "El backend no tiene WAHA_API_KEY: no puede hablar con WAHA" ;;
    ERROR*)        falla "El backend no logra hablar con WAHA ($SES)" "¿está caído buscadonde-waha?" ;;
    SIN_SESIONES)  falla "WAHA no tiene ninguna sesión: no entra ningún mensaje de WhatsApp" "hay que escanear el QR por túnel SSH (ver docker-compose.prod.yml)" ;;
    "")            falla "No hubo respuesta del backend al consultar WAHA" ;;
    *)
      MALAS=""
      for par in $SES; do [ "${par#*=}" = "WORKING" ] || MALAS="$MALAS $par"; done
      if [ -z "$MALAS" ]; then ok "Sesión(es) de WhatsApp en WORKING: $SES"; else falla "Sesión de WhatsApp que NO está en WORKING:$MALAS" "no entra ninguna oferta por WhatsApp hasta que vuelva a WORKING"; fi ;;
  esac
else
  salteado "Sesión de WAHA: $MOTIVO_SIN_DOCKER"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "11. Procesos de fondo (workers)"
if [ "$HAY_DOCKER" = "1" ]; then
  # Sólo booleanos (no son secretos). «env» = está escrito en el .env; «defecto» = vale lo que trae el código.
  WK=$(docker exec -i "$C_BACK" python - 2>&1 <<'PY'
import os
try:
    from app.core.config import settings as s
except Exception as e:
    print("ERROR " + e.__class__.__name__); raise SystemExit(0)
pares = [("DIFUSION_WORKER", "difusion_worker"), ("INDEXNOW_WORKER", "indexnow_worker"),
         ("IA_REVISION_WORKER", "ia_revision_worker"), ("INTEGRACION_DIFUSION", "integracion_difusion"),
         ("CONTENT_PLANNER_WORKER", "content_planner_worker"), ("CONTENT_RENDER_WORKER", "content_render_worker"),
         ("TELEFONOS_FOTO_WORKER", "telefonos_foto_worker")]
for env, attr in pares:
    print("%s %s %s" % (env, str(getattr(s, attr, "?")).lower(), "env" if os.environ.get(env) is not None else "defecto"))
PY
  )
  if printf '%s' "$WK" | grep -q '^ERROR'; then
    falla "No se pudo leer la configuración del backend" "$(primera_linea "$WK")"
  else
    printf '%s\n' "$WK" | while read -r nombre valor origen; do
      [ -z "$nombre" ] && continue
      printf '             %s%-24s %-5s (%s)%s\n' "$G" "$nombre" "$valor" "$origen" "$N"
    done
    ok "Configuración de los workers leída (compará con lo que querés: DIFUSION/INDEXNOW/IA_REVISION/INTEGRACION_DIFUSION y los de contenido)"
  fi
else
  salteado "Workers: $MOTIVO_SIN_DOCKER"
fi

# ════════════════════════════════════════════════════════════════════════════
titulo "12. Disco y memoria del servidor"
if [ "$HAY_DOCKER" = "1" ]; then
  USO=$(df -P / 2>/dev/null | awk 'NR==2{gsub(/%/,"",$5); print $5}')
  if [ -n "$USO" ]; then
    if ! [ "$USO" -ge 0 ] 2>/dev/null || [ "$USO" -gt 100 ]; then salteado "Disco: df devolvió un valor raro ($USO)"
    elif [ "$USO" -lt 85 ]; then ok "Disco: ${USO}% usado (menos de 85%)"; else aviso "Disco: ${USO}% usado (85% o más)" "liberá espacio (imágenes viejas de docker: docker image prune) antes de que se llene"; fi
  else
    salteado "Disco: no se pudo leer df"
  fi
  DISP=$(free -m 2>/dev/null | awk '/^Mem:/{print $7}')
  if [ -n "$DISP" ]; then
    if [ "$DISP" -gt 1000 ]; then ok "Memoria disponible: ${DISP} MB (más de 1000)"; else aviso "Memoria disponible: ${DISP} MB (1000 o menos)" "el servidor anda justo; mirá qué contenedor consume más con docker stats --no-stream"; fi
  else
    salteado "Memoria: no se pudo leer free"
  fi
else
  salteado "Disco y memoria (son del servidor): $MOTIVO_SIN_DOCKER"
fi

# ── resumen ───────────────────────────────────────────────────────────────────
printf '\n%s=======================================================%s\n' "$B" "$N"
printf '%sRESUMEN  %s  (%s)%s\n' "$B" "$DOMINIO" "$AMBIENTE" "$N"
printf '  %sOK: %d%s   %sFALLA: %d%s   %sAVISO: %d%s   SALTEADO: %d\n' "$V" "$N_OK" "$N" "$R" "$N_FALLA" "$N" "$A" "$N_AVISO" "$N" "$N_SALT"
if [ "$N_FALLA" -gt 0 ]; then
  printf '\n%sHAY FALLAS:%s\n' "$R" "$N"
  for f in "${LISTA_FALLAS[@]}"; do printf '  - %s\n' "$f"; done
  printf '\nMandale TODA esta salida a Claude para que lo revise.\n'
  exit 1
fi
if [ "$N_AVISO" -gt 0 ]; then
  printf '\n%sSin fallas, pero revisá los AVISOS de arriba.%s\n' "$A" "$N"
else
  printf '\n%sTODO BIEN.%s\n' "$V" "$N"
fi
exit 0
