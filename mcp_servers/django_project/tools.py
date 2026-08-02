"""Tools MCP de solo lectura para el proyecto Django de IA CENTRAL.

Alcance de esta primera entrega (ver ADR-020, y el principio de ADR-015 de
agregar capacidades de a una): solo dos tools de solo lectura, cero efectos
secundarios. run_migrations/restart_web/run_tests quedan deliberadamente
afuera, para una entrega posterior y una decisión aparte.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mcp_servers.django_project import security

REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_READ_BYTES = 200_000


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
