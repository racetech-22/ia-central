"""Test de la condición de ADR-012: el Claude Agent SDK (paquete PyPI
claude-agent-sdk, import claude_agent_sdk — verificado en la ronda de
verificación de ADR-020) no debe importarse desde ningún módulo de este
repo salvo la interfaz interna del orquestador (`orchestrator.run(...)`, ver
ARQUITECTURA.md §2, implementada en ADR-021).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Rutas (relativas a REPO_ROOT, formato posix) donde SÍ se permite importar
# claude_agent_sdk directamente — hoy, únicamente la interfaz interna del
# orquestador (ADR-021). No reemplazar por un patrón laxo (ej. "cualquier
# archivo bajo orchestrator/"): si se agrega otro módulo ahí que no deba
# tocar el SDK, listarlo acá sería un error silencioso.
ALLOWED_SDK_IMPORT_PATHS: set[str] = {"orchestrator/orchestrator.py"}

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
