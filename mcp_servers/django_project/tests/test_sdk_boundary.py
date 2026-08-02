"""Test de la condición de ADR-012: el Claude Agent SDK (paquete PyPI
claude-agent-sdk, import claude_agent_sdk — verificado en la ronda de
verificación de ADR-020) no debe importarse desde ningún módulo de este
repo salvo la futura interfaz interna del orquestador (orchestrator.run(...),
ver ARQUITECTURA.md §2). Esa interfaz no existe todavía (confirmado en la
auditoría de solo lectura del 2026-08-02), así que este test debe pasar en
verde ahora mismo — sirve de red para cuando se construya el orquestador.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Rutas (relativas a REPO_ROOT, formato posix) donde SÍ se permite importar
# claude_agent_sdk directamente. Vacío hoy a propósito. El día que exista
# orchestrator.run(...), agregar acá su ruta exacta — no reemplazar por un
# patrón laxo (ej. "cualquier archivo bajo orchestrator/").
ALLOWED_SDK_IMPORT_PATHS: set[str] = set()

SDK_MODULE_NAME = "claude_agent_sdk"


def _imports_sdk(py_file: Path) -> bool:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.split(".")[0] == SDK_MODULE_NAME for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] == SDK_MODULE_NAME:
                return True
    return False


def test_claude_agent_sdk_no_se_importa_fuera_de_la_interfaz_del_orquestador():
    violaciones = []

    for py_file in REPO_ROOT.rglob("*.py"):
        if ".git" in py_file.parts:
            continue
        rel = py_file.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWED_SDK_IMPORT_PATHS:
            continue
        if _imports_sdk(py_file):
            violaciones.append(rel)

    assert not violaciones, (
        "claude_agent_sdk importado fuera de la interfaz interna del "
        f"orquestador (ADR-012), todavía no existe ninguna: {violaciones}"
    )
