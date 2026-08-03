"""Tools MCP para el proyecto Django de IA CENTRAL.

ADR-020 (primera entrega): dos tools de solo lectura, cero efectos
secundarios (`git_status`, `read_file`).

ADR-022 (segunda entrega): agrega `restart_web`, aislada limpio con
`tecnativa/docker-socket-proxy` (`ALLOW_RESTARTS` es una ACL independiente
de `CONTAINERS` en ese proxy).

ADR-023 (tercera entrega): agrega `run_migrations`/`run_tests`, que
necesitan `exec` dentro de un contenedor — algo que el proxy de ADR-022 no
puede aislar de crear/borrar contenedores nuevos (`CONTAINERS` es
todo-o-nada). En vez de forzarlo por ahí, corren contra un sidecar propio
(`admin-tasks`, misma imagen que `web`) que nunca toca Docker en absoluto —
solo corre comandos fijos de Django management contra la base real.
"""

from __future__ import annotations

import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

import docker

from mcp_servers.django_project import security

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_READ_BYTES = 200_000

# Nombre fijo del contenedor real de docker-compose.yml (proyecto
# "ia-central", servicio "web", instancia 1) — NUNCA compuesto a partir de
# nada que venga del modelo. Ver ADR-022.
WEB_CONTAINER_NAME = "ia-central-web-1"

# Nombre de servicio (resuelto por la red interna de Docker Compose) del
# sidecar de ADR-023 — nunca publicado al host, ver docker-compose.yml.
ADMIN_TASKS_BASE_URL = "http://admin-tasks:8100"


def git_status() -> str:
    """Corre `git status --porcelain` con cwd fijo en la raíz del repo.

    Sin parámetros de entrada — no hay superficie de inyección posible.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def read_file(path: str) -> str:
    """Devuelve el contenido de `path`, validado contra security.py.

    Propaga `security.PathSecurityError` si la ruta no pasa la validación —
    nunca un catch silencioso ni contenido parcial. Trunca (con aviso
    explícito) si el archivo supera MAX_READ_BYTES.
    """
    safe_path = security.resolve_safe_path(path, REPO_ROOT)

    if not safe_path.is_file():
        raise FileNotFoundError(f"no es un archivo regular: {path!r}")

    data = safe_path.read_bytes()
    if len(data) > MAX_READ_BYTES:
        truncated = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        return (
            truncated
            + f"\n\n[TRUNCADO: archivo de {len(data)} bytes, se muestran los primeros {MAX_READ_BYTES}]"
        )

    return data.decode("utf-8", errors="replace")


def restart_web() -> str:
    """Reinicia el contenedor `web`, vía el proxy de la API de Docker.

    Sin parámetros — el nombre del contenedor es una constante fija
    (`WEB_CONTAINER_NAME`), nunca compuesto a partir de nada que venga del
    modelo. Usa `client.api.restart()` (el cliente de bajo nivel de
    docker-py), que llama directo a `POST /containers/{id}/restart` sin un
    `GET`/inspect previo — así no hace falta habilitar `CONTAINERS` en el
    proxy, solo `POST` + `ALLOW_RESTARTS` (ver ADR-022). `DOCKER_HOST` (env,
    ver docker-compose.yml) apunta al proxy, nunca al socket real.
    """
    client = docker.from_env()
    try:
        client.api.restart(WEB_CONTAINER_NAME, timeout=10)
    finally:
        client.close()

    return f"Contenedor {WEB_CONTAINER_NAME!r} reiniciado."


def _call_admin_tasks(path: str) -> str:
    """POST de solo infraestructura al sidecar `admin-tasks` (ver ADR-023).

    `path` es siempre uno de los dos valores fijos usados por
    `run_migrations`/`run_tests` acá abajo — nunca algo que el modelo pueda
    elegir. El token sale de `ADMIN_TASKS_TOKEN` (mismo valor que el
    sidecar, ver docker-compose.yml); si falta, la request igual se manda
    (el sidecar la va a rechazar con 401 — falla cerrado del lado del
    servidor, no de acá).
    """
    token = os.environ.get("ADMIN_TASKS_TOKEN", "")
    request = urllib.request.Request(
        f"{ADMIN_TASKS_BASE_URL}{path}",
        method="POST",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"admin-tasks devolvió {exc.code}: {body}") from exc


def run_migrations() -> str:
    """Corre `python manage.py migrate` contra la base real, vía `admin-tasks`.

    Sin parámetros. Ver ADR-023.
    """
    return _call_admin_tasks("/run-migrations")


def run_tests() -> str:
    """Corre `python manage.py test` (la suite del proyecto), vía `admin-tasks`.

    Sin parámetros. Ver ADR-023.
    """
    return _call_admin_tasks("/run-tests")
