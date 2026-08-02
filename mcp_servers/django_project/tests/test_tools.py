"""Casos felices de las tools MCP.

git_status() y read_file() se prueban invocándolas a través del protocolo
MCP real, con el mecanismo de sesión en memoria de mcp==1.29.0
(mcp.shared.memory.create_connected_server_and_client_session, verificado
contra el código fuente oficial en el paso 0 de ADR-020) conectado al mismo
objeto `mcp` de server.py — así queda probado que ambas tools están
correctamente registradas y son invocables como tools MCP, no solo que las
funciones de Python funcionan sueltas.
"""

from __future__ import annotations

import subprocess

import anyio
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.django_project import tools
from mcp_servers.django_project.security import PathSecurityError
from mcp_servers.django_project.server import mcp


def test_git_status_coherente_con_el_repo(tmp_path, monkeypatch):
    # Repo de test real y aislado (no el repo de IA CENTRAL): así no
    # depende de su estado real ni escribe nada ahí.
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "nuevo.txt").write_text("archivo sin trackear\n")

    monkeypatch.setattr(tools, "REPO_ROOT", tmp_path)

    async def run():
        async with create_connected_server_and_client_session(mcp) as session:
            return await session.call_tool("git_status", {})

    result = anyio.run(run)

    assert not result.isError
    text = result.content[0].text
    assert "nuevo.txt" in text
    assert text.startswith("??")


def test_read_file_devuelve_contenido_esperado(tmp_path, monkeypatch):
    (tmp_path / "conocido.txt").write_text("contenido de referencia\n")
    monkeypatch.setattr(tools, "REPO_ROOT", tmp_path)

    async def run():
        async with create_connected_server_and_client_session(mcp) as session:
            return await session.call_tool("read_file", {"path": "conocido.txt"})

    result = anyio.run(run)

    assert not result.isError
    assert result.content[0].text == "contenido de referencia\n"


def test_read_file_bloqueado_propaga_error_no_contenido_parcial(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=no-deberia-salir\n")
    monkeypatch.setattr(tools, "REPO_ROOT", tmp_path)

    # Deliberadamente NO se prueba esto a través del protocolo MCP: FastMCP
    # atrapa cualquier excepción de una tool y la convierte en
    # CallToolResult(isError=True) en vez de volver a lanzarla del lado del
    # cliente (comportamiento estándar del SDK) — a ese nivel no se
    # distinguiría "propaga el error de security.py" de "un catch silencioso
    # que devuelve isError sin motivo real". La propagación real se prueba
    # directo contra tools.read_file(), donde un catch silencioso agregado
    # por error sí haría fallar este test.
    with pytest.raises(PathSecurityError):
        tools.read_file(".env")
