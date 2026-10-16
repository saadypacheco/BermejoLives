"""Entorno de DEMO local de URUKU, con datos ficticios, para manuales y videos.

    python scripts/demo/demo.py up          # levanta todo (y siembra si la base es nueva)
    python scripts/demo/demo.py status      # qué está corriendo
    python scripts/demo/demo.py seed        # vuelve a correr la semilla (idempotente)
    python scripts/demo/demo.py down        # baja backend y frontend (por PID)
    python scripts/demo/demo.py down --docker   # además detiene los contenedores demo-manual-* (la base queda)
    python scripts/demo/demo.py down --borrar   # además borra los contenedores (base incluida)
    python scripts/demo/demo.py reset       # base de cero: borra contenedores y vuelve a levantar

Piezas (todas en 127.0.0.1, puertos propios para no chocar con nada):

    demo-manual-pg     Postgres 16 con selfhost/postgres-init aplicado    :5999
    demo-manual-rest   PostgREST v12.2.3 (como producción)                (sólo red interna)
    demo-manual-gw     nginx que agrega el prefijo /rest/v1 de Supabase    :3999
    demo-manual-tiles  caché de teselas de OSM (selfhost/tiles/nginx.conf)  :3998
    backend            uvicorn app.main:app                                :8990
    frontend           next dev (compila en frontend/.next-demo)           :3990

El backend corre con un `.env` de demo que se escribe en scripts/demo/.run/ (ignorado por
git): secretos de juguete, WhatsApp/IA/difusión apagados. No toca backend/.env ni
frontend/.env.local (las variables del proceso les ganan a los archivos).

Nada de esto apunta a producción: no hay una sola URL ni clave real en este archivo.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
RUN = AQUI / ".run"
PIDS = RUN / "pids.json"
INIT = RAIZ / "selfhost" / "postgres-init"

PG, REST, GW, RED = "demo-manual-pg", "demo-manual-rest", "demo-manual-gw", "demo-manual-net"
TILES = "demo-manual-tiles"
PUERTO_PG, PUERTO_GW, PUERTO_BACK, PUERTO_FRONT, PUERTO_TILES = 5999, 3999, 8990, 3990, 3998

# Secretos DE JUGUETE. Sólo valen para esta demo local.
PG_PASS = "demo"
PGRST_SECRET = "demo-manual-postgrest-secreto-de-juguete-0001"
JWT_SECRET = "demo-manual-backend-secreto-de-juguete-0001"
CLAVE_PEPPER = "demo-manual-pepper-de-juguete"

# Migraciones que fallan en un Postgres vanilla (las mismas que documentan los tests con
# URUKU_PG_TEST_CONTAINER). Lo que crean lo rehacen migraciones posteriores.
FALLAN_EN_VANILLA = {"0049", "0069", "0070"}
# 0092 cambia el tipo que devuelve una función: en vanilla hay que borrarla antes.
ARREGLOS = {"0092": "drop function if exists rubros_a_revisar(text, int);\n"}

BACK_URL = f"http://localhost:{PUERTO_BACK}"
FRONT_URL = f"http://localhost:{PUERTO_FRONT}"
REST_URL = f"http://localhost:{PUERTO_GW}"
TILES_URL = f"http://localhost:{PUERTO_TILES}/{{z}}/{{x}}/{{y}}.png"


# ───────────────────────────────────────────────────────────── utilidades
def _jwt(rol: str) -> str:
    import jwt  # pyjwt, ya es dependencia del backend
    return jwt.encode({"role": rol, "iss": "uruku-demo", "iat": 1760000000, "exp": 2000000000},
                      PGRST_SECRET, algorithm="HS256")


def sh(args: list[str], check: bool = True, entrada: str | None = None) -> subprocess.CompletedProcess:
    # En bytes: en modo texto Windows convierte \n en \r\n y el `sh` del contenedor no lo entiende.
    b = subprocess.run(args, input=entrada.encode("utf-8") if entrada is not None else None, capture_output=True)
    p = subprocess.CompletedProcess(args, b.returncode, b.stdout.decode("utf-8", "replace").replace("\r\n", "\n"),
                                    b.stderr.decode("utf-8", "replace").replace("\r\n", "\n"))
    if check and p.returncode != 0:
        raise SystemExit(f"Falló: {' '.join(args)}\n{p.stderr or p.stdout}")
    return p


def psql(sql: str, check: bool = True) -> subprocess.CompletedProcess:
    return sh(["docker", "exec", "-i", PG, "psql", "-U", "postgres", "-d", "postgres",
               "-v", "ON_ERROR_STOP=1", "-q", "-At", "-f", "-"], check=check, entrada=sql)


def contenedor(nombre: str) -> str | None:
    """'running', 'exited', … o None si no existe."""
    p = sh(["docker", "inspect", "-f", "{{.State.Status}}", nombre], check=False)
    return p.stdout.strip() if p.returncode == 0 else None


def puerto_ocupado(puerto: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def esperar_http(url: str, segundos: int, nombre: str) -> None:
    fin = time.time() + segundos
    while time.time() < fin:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status < 500:
                    print(f"  {nombre} listo ({url})")
                    return
        except Exception:
            pass
        time.sleep(1.5)
    raise SystemExit(f"{nombre} no contestó en {segundos}s ({url}). Mirá {RUN}")


def entorno_backend() -> dict[str, str]:
    """El .env de demo (también va al entorno del proceso, que le gana a cualquier .env)."""
    fotos = RUN / "fotos"
    return {
        "ENVIRONMENT": "development",
        "SUPABASE_URL": REST_URL,
        "SUPABASE_PUBLIC_URL": REST_URL,
        "SUPABASE_SERVICE_ROLE_KEY": _jwt("service_role"),
        "JWT_SECRET": JWT_SECRET,
        "CLAVE_PEPPER": CLAVE_PEPPER,
        # Las llaves de emergencia del .env: inventadas, para que no valgan las de fábrica.
        "ADMIN_EMAIL": "emergencia-admin@demo.test", "ADMIN_PASSWORD": "no-usar-demo-0001",
        "AGENTE_EMAIL": "emergencia-agente@demo.test", "AGENTE_PASSWORD": "no-usar-demo-0002",
        "PUBLICADOR_EMAIL": "emergencia-publicador@demo.test", "PUBLICADOR_PASSWORD": "no-usar-demo-0003",
        "FRONTEND_URL": FRONT_URL,
        "SITIO_URL": FRONT_URL,
        "FOTOS_DIR": str(fotos),
        "FOTOS_PUBLIC_BASE_URL": f"{BACK_URL}/fotos",
        # Todo lo que sale a internet o a WhatsApp, apagado.
        "WAHA_BASE_URL": "http://127.0.0.1:9", "WAHA_API_KEY": "", "WEBHOOK_SECRET": "demo-webhook",
        "BOT_WHATSAPP_NUMERO": "59170000999",
        "WA_SOLO_LECTURA": "true", "WA_SESION_VIGILAR": "false",
        "CLIMA_WORKER": "false", "DIFUSION_WORKER": "false", "IA_REVISION_WORKER": "false",
        "GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "TIENDA_API_URL": "", "TIENDA_API_SECRET": "",
        "ADMIN_SYNC_SECRET": "", "FACEBOOK_PAGE_TOKEN": "", "WA_CANAL_ID": "",
    }


def escribir_env() -> dict[str, str]:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "fotos").mkdir(exist_ok=True)
    env = entorno_backend()
    (RUN / ".env").write_text("".join(f"{k}={v}\n" for k, v in env.items()), encoding="utf-8")
    return env


def env_proceso_backend() -> dict[str, str]:
    env = {**os.environ, **escribir_env()}
    env["PYTHONPATH"] = str(RAIZ / "backend")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    return env


def leer_pids() -> dict:
    try:
        return json.loads(PIDS.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_pids(pids: dict) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    PIDS.write_text(json.dumps(pids, indent=2), encoding="utf-8")


def pid_vivo(pid: int) -> bool:
    if os.name == "nt":
        p = sh(["tasklist", "/FI", f"PID eq {pid}", "/NH"], check=False)
        return str(pid) in p.stdout
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def lanzar(nombre: str, args: list[str], cwd: Path, env: dict[str, str]) -> int:
    log = open(RUN / f"{nombre}.log", "ab")
    kw: dict = {"cwd": str(cwd), "env": env, "stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name == "nt":
        kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS
    else:
        kw["start_new_session"] = True
    return subprocess.Popen(args, **kw).pid


def matar(pid: int) -> None:
    """Sólo por PID (y su árbol: next dev levanta un hijo)."""
    if os.name == "nt":
        sh(["taskkill", "/PID", str(pid), "/T", "/F"], check=False)
    else:
        import signal
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            pass


# ───────────────────────────────────────────────────────────── docker
def aplicadas() -> set[str] | None:
    """Las migraciones ya aplicadas a la base de la demo (None = base sin migrar).

    Se anotan en el esquema `demo` (PostgREST sólo expone `public`): así un `up`
    posterior aplica sólo las nuevas, sin rehacer la base."""
    p = psql("select nombre from demo.migraciones;", check=False)
    return set(p.stdout.split()) if p.returncode == 0 else None


def migrar(ya: set[str] | None = None) -> None:
    ya = ya or set()
    pendientes = [f.name for f in sorted(INIT.glob("*.sql")) if f.name not in ya]
    if not pendientes:
        return
    print(f"Aplicando {len(pendientes)} de selfhost/postgres-init en orden…")
    # Se copian al contenedor y se corren adentro, una por una (cada archivo con
    # ON_ERROR_STOP): un `docker exec` por archivo tardaba minutos.
    sh(["docker", "exec", PG, "rm", "-rf", "/demo-init"])
    sh(["docker", "cp", str(INIT), f"{PG}:/demo-init"])
    arreglos = "".join(
        f"  {num}_*) printf '%s' \"{sql.strip()}\" | psql -U postgres -q >/dev/null 2>&1;;\n" for num, sql in ARREGLOS.items())
    script = (
        "cd /demo-init\n"
        f"for f in {' '.join(pendientes)}; do\n"
        f"  case \"$f\" in\n{arreglos}  esac\n"
        "  if ! out=$(psql -U postgres -d postgres -v ON_ERROR_STOP=1 -q -f \"$f\" 2>&1 >/dev/null); then\n"
        "    echo \"FAIL|$f|$(echo \"$out\" | grep ERROR | head -1)\"\n"
        "  fi\n"
        "done\n")
    p = sh(["docker", "exec", "-i", PG, "sh", "-s"], entrada=script, check=False)
    fallas = [tuple(l.split("|", 2)[1:]) for l in p.stdout.splitlines() if l.startswith("FAIL|")]
    for nombre, err in fallas:
        conocida = nombre.split("_")[0] in FALLAN_EN_VANILLA
        print(f"  {'(conocida) ' if conocida else 'ATENCIÓN '}{nombre}: {err}")
    valores = ",".join(f"('{n}')" for n in pendientes)
    psql("create schema if not exists demo; create table if not exists demo.migraciones "
         "(nombre text primary key, aplicada_en timestamptz not null default now());"
         f"insert into demo.migraciones (nombre) values {valores} on conflict do nothing;"
         "notify pgrst, 'reload schema';")
    inesperadas = [n for n, _ in fallas if n.split("_")[0] not in FALLAN_EN_VANILLA]
    if inesperadas:
        print(f"  ATENCIÓN: fallaron migraciones que no se esperaba: {inesperadas}")
    print(f"  {len(pendientes)} aplicadas; con error: {len(fallas)} ({len(fallas) - len(inesperadas)} conocidas en vanilla)")


def docker_up() -> bool:
    """Levanta los contenedores. Devuelve True si la base se creó recién (hay que sembrar)."""
    if not shutil.which("docker"):
        raise SystemExit("No encuentro `docker`. ¿Está Docker Desktop abierto?")
    if sh(["docker", "info"], check=False).returncode != 0:
        raise SystemExit("Docker no contesta (¿Docker Desktop/WSL apagado?).")
    if sh(["docker", "network", "inspect", RED], check=False).returncode != 0:
        sh(["docker", "network", "create", RED])

    nueva = False
    estado = contenedor(PG)
    if estado is None:
        print(f"Creando {PG}…")
        sh(["docker", "run", "-d", "--name", PG, "--network", RED, "-p", f"127.0.0.1:{PUERTO_PG}:5432",
            "-e", f"POSTGRES_PASSWORD={PG_PASS}", "-e", f"AUTHENTICATOR_PASSWORD={PG_PASS}",
            "postgres:16-alpine"])
    elif estado != "running":
        sh(["docker", "start", PG])
    for _ in range(60):
        if sh(["docker", "exec", PG, "pg_isready", "-U", "postgres"], check=False).returncode == 0 \
                and psql("select 1;", check=False).returncode == 0:
            break
        time.sleep(1)
    else:
        raise SystemExit("Postgres no arrancó")
    ya = aplicadas()
    nueva = ya is None
    migrar(ya)

    estado = contenedor(REST)
    if estado is None:
        sh(["docker", "run", "-d", "--name", REST, "--network", RED,
            "-e", f"PGRST_DB_URI=postgres://authenticator:{PG_PASS}@{PG}:5432/postgres",
            "-e", "PGRST_DB_SCHEMAS=public", "-e", "PGRST_DB_ANON_ROLE=anon",
            "-e", f"PGRST_JWT_SECRET={PGRST_SECRET}", "-e", "PGRST_DB_MAX_ROWS=1000",
            "postgrest/postgrest:v12.2.3"])
    elif estado != "running":
        sh(["docker", "start", REST])

    estado = contenedor(GW)
    if estado is None:
        sh(["docker", "run", "-d", "--name", GW, "--network", RED, "-p", f"127.0.0.1:{PUERTO_GW}:80",
            "-v", f"{(AQUI / 'nginx.conf').as_posix()}:/etc/nginx/conf.d/default.conf:ro", "nginx:1.27-alpine"])
    elif estado != "running":
        sh(["docker", "start", GW])

    # El caché de teselas de producción (selfhost/tiles/nginx.conf), tal cual: pide a OSM
    # con el User-Agent de URUKU y guarda. Sin él, el navegador headless le pega a OSM
    # directo y las teselas no siempre vuelven (el mapa sale gris).
    estado = contenedor(TILES)
    if estado is None:
        sh(["docker", "run", "-d", "--name", TILES, "--network", RED, "-p", f"127.0.0.1:{PUERTO_TILES}:80",
            "-v", f"{(RAIZ / 'selfhost/tiles/nginx.conf').as_posix()}:/etc/nginx/conf.d/default.conf:ro",
            "nginx:1.27-alpine"])
    elif estado != "running":
        sh(["docker", "start", TILES])
    esperar_http(f"{REST_URL}/rest/v1/ciudades?select=slug&limit=1", 60, "PostgREST")
    esperar_http(f"http://localhost:{PUERTO_TILES}/healthz", 30, "Teselas")
    return nueva


def docker_down(borrar: bool = False) -> None:
    """Detiene los contenedores (la base queda para el próximo `up`); con `borrar`, los elimina."""
    for c in (TILES, GW, REST, PG):
        if contenedor(c) is not None:
            sh(["docker", "rm", "-f", c] if borrar else ["docker", "stop", c], check=False)
            print(f"  {'borrado' if borrar else 'detenido'} {c}")
    if borrar:
        sh(["docker", "network", "rm", RED], check=False)


# ───────────────────────────────────────────────────────────── procesos
def sembrar() -> None:
    print("Sembrando datos ficticios…")
    p = subprocess.run([sys.executable, str(AQUI / "seed.py")], env=env_proceso_backend(), cwd=str(RUN))
    if p.returncode != 0:
        raise SystemExit("La semilla falló (ver arriba).")


def backend_up(pids: dict) -> None:
    if pids.get("backend") and pid_vivo(pids["backend"]):
        print(f"  backend ya corre (PID {pids['backend']})")
        return
    if puerto_ocupado(PUERTO_BACK):
        raise SystemExit(f"El puerto {PUERTO_BACK} está ocupado por otro proceso.")
    pids["backend"] = lanzar("backend", [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                         "--port", str(PUERTO_BACK)], RUN, env_proceso_backend())
    guardar_pids(pids)
    esperar_http(f"{BACK_URL}/health", 90, "Backend")


def frontend_up(pids: dict) -> None:
    if pids.get("frontend") and pid_vivo(pids["frontend"]):
        print(f"  frontend ya corre (PID {pids['frontend']})")
        return
    if puerto_ocupado(PUERTO_FRONT):
        raise SystemExit(f"El puerto {PUERTO_FRONT} está ocupado por otro proceso.")
    front = RAIZ / "frontend"
    env = {**os.environ,
           "NEXT_DIST_DIR": ".next-demo",
           "NEXT_PUBLIC_SUPABASE_URL": REST_URL,
           "NEXT_PUBLIC_SUPABASE_ANON_KEY": _jwt("anon"),
           "NEXT_PUBLIC_API_URL": BACK_URL,
           "NEXT_PUBLIC_MODO_CAPTURA": "0",
           "NEXT_PUBLIC_TILES_URL": TILES_URL,
           "NEXT_TELEMETRY_DISABLED": "1"}
    for k in ("SUPABASE_INTERNAL_URL", "APP_ENV"):
        env.pop(k, None)
    next_bin = front / "node_modules" / "next" / "dist" / "bin" / "next"
    pids["frontend"] = lanzar("frontend", ["node", str(next_bin), "dev", "-p", str(PUERTO_FRONT)], front, env)
    guardar_pids(pids)
    esperar_http(f"{FRONT_URL}/api/health", 180, "Frontend")


def up(args) -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    nueva = docker_up()
    escribir_env()
    if nueva or args.sembrar:
        sembrar()
    pids = leer_pids()
    backend_up(pids)
    if not args.sin_front:
        frontend_up(pids)
    status(None)


def down(args) -> None:
    pids = leer_pids()
    for nombre in ("frontend", "backend"):
        pid = pids.pop(nombre, None)
        if pid and pid_vivo(pid):
            matar(pid)
            print(f"  {nombre} detenido (PID {pid})")
    guardar_pids(pids)
    if args.docker or getattr(args, "borrar", False):
        docker_down(borrar=getattr(args, "borrar", False))


def status(_args) -> None:
    pids = leer_pids()
    print("\nDemo de URUKU:")
    for c in (PG, REST, GW, TILES):
        print(f"  {c:18} {contenedor(c) or 'no existe'}")
    for nombre, url in (("backend", BACK_URL), ("frontend", FRONT_URL)):
        pid = pids.get(nombre)
        vivo = bool(pid) and pid_vivo(pid)
        print(f"  {nombre:18} {'corriendo PID ' + str(pid) if vivo else 'apagado'}  {url}")
    print(f"  PostgREST (gw)     {REST_URL}/rest/v1/\n  Usuarios y claves: scripts/demo/README.md")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Entorno de demo local de URUKU (datos ficticios)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("up")
    p.add_argument("--sembrar", action="store_true", help="correr la semilla aunque la base ya exista")
    p.add_argument("--sin-front", action="store_true", help="no levantar next dev")
    p.set_defaults(fn=up)
    p = sub.add_parser("down")
    p.add_argument("--docker", action="store_true", help="también detener los contenedores demo-manual-* (la base queda)")
    p.add_argument("--borrar", action="store_true", help="también borrar los contenedores demo-manual-* (base incluida)")
    p.set_defaults(fn=down)
    sub.add_parser("status").set_defaults(fn=status)
    sub.add_parser("seed").set_defaults(fn=lambda a: (docker_up(), escribir_env(), sembrar()))

    def reset(a):
        down(argparse.Namespace(docker=True, borrar=True))
        up(argparse.Namespace(sembrar=True, sin_front=False))
    sub.add_parser("reset").set_defaults(fn=reset)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
