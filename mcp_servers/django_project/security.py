"""Verificación de límites de rutas para las tools MCP del proyecto Django.

Este módulo es la ÚNICA autoridad de la condición de ADR-017 ("ninguna tool
MCP permite lectura de rutas arbitrarias del filesystem"). Cualquier tool
nueva que reciba una ruta y toque el filesystem tiene que validarla acá antes
de abrir nada — no reimplementar esta lógica en cada tool.
"""

from __future__ import annotations

from pathlib import Path


class PathSecurityError(Exception):
    """La ruta solicitada no pasa la verificación de límites de este módulo."""


def _is_blocked_env_file(resolved: Path) -> bool:
    name = resolved.name
    return name == ".env" or name.startswith(".env.")


def resolve_safe_path(requested_path: str, allowed_root: Path) -> Path:
    """Resuelve `requested_path` a una ruta absoluta real y la valida.

    - Resuelve símbolicamente (Path.resolve(), sigue symlinks) tanto la raíz
      permitida como la ruta solicitada, para comparar rutas reales finales.
    - Rechaza (PathSecurityError) si la ruta resuelta no queda estrictamente
      dentro de `allowed_root` — cubre "../" y symlinks que escapen, porque
      resolve() ya siguió el symlink hasta su destino real.
    - Rechaza además, aunque quede dentro de la raíz, cualquier archivo que
      matchee `.env` o `.env.*` — mismo patrón que `.claude/settings.json`
      (ADR-006), como defensa en profundidad, no una única capa.
    """
    root = allowed_root.resolve()
    candidate = Path(requested_path)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(root)
    except ValueError:
        raise PathSecurityError(
            f"ruta fuera de la raíz permitida ({root}): {requested_path!r} -> {resolved}"
        ) from None

    if _is_blocked_env_file(resolved):
        raise PathSecurityError(f"acceso a archivo .env bloqueado: {resolved.name!r}")

    return resolved
