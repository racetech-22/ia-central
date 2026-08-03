"""Tools MCP para el proyecto Django de IA CENTRAL.

ADR-020 (primera entrega): dos tools de solo lectura, cero efectos
secundarios (`git_status`, `read_file`).

ADR-022 (segunda entrega): agrega `restart_web`, la única de las tres tools
con efectos reales originalmente previstas (`run_migrations`, `restart_web`,
`run_tests`) que se pudo aislar limpio con `tecnativa/docker-socket-proxy` —
`ALLOW_RESTARTS` es una ACL independiente de `CONTAINERS` en ese proxy.
`run_migrations`/`run_tests` (que necesitan `exec` dentro del contenedor)
quedan deliberadamente afuera: el proxy no tiene forma de habilitar exec sin
habilitar también crear/borrar contenedores (`CONTAINERS` es todo-o-nada),
así que requieren un mecanismo distinto, todavía sin decidir — ver ADR-022.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import docker

from mcp_servers.django_project import security

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_READ_BYTES = 200_000

# Nombre fijo del contenedor real de docker-compose.yml (proyecto
# "ia-central", servicio "web", instancia 1) — NUNCA compuesto a partir de
# nada que venga del modelo. Ver ADR-022.
WEB_CONTAINER_NAME = "ia-central-web-1"


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
