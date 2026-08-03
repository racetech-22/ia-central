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
import urllib.error
import urllib.request

import anyio
import docker
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from mcp_servers.django_project import tools
from mcp_servers.django_project.security import PathSecurityError
from mcp_servers.django_project.server import mcp

# Nombre de un contenedor descartable, creado FUERA de este proceso de test
# (desde el host, con acceso real al socket de Docker) antes de correr esta
# suite, y borrado después — ver docs de ADR-022. El proxy deliberadamente no
# permite crear contenedores desde acá (CONTAINERS deshabilitado), así que
# pytest no puede crearlo por su cuenta; probar restart_web() contra el
# `ia-central-web-1` real reiniciaría el servicio de verdad durante un test.
RESTART_TEST_CONTAINER_NAME = "ia-central-test-restart-target"


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


def test_restart_web_reinicia_un_contenedor_real(monkeypatch):
    """Contra un contenedor descartable (ver RESTART_TEST_CONTAINER_NAME),
    nunca contra `ia-central-web-1` — este test no debe reiniciar el web
    real. Vía protocolo MCP real, igual que git_status/read_file, para
    confirmar que la tool está correctamente registrada e invocable.
    """
    monkeypatch.setattr(tools, "WEB_CONTAINER_NAME", RESTART_TEST_CONTAINER_NAME)

    async def run():
        async with create_connected_server_and_client_session(mcp) as session:
            return await session.call_tool("restart_web", {})

    result = anyio.run(run)

    assert not result.isError
    assert RESTART_TEST_CONTAINER_NAME in result.content[0].text


def test_proxy_rechaza_listar_y_crear_contenedores():
    """Adversarial, mismo espíritu que los 5 casos de security.py en ADR-020
    — pero acá el "código bajo prueba" es la configuración del proxy
    (docker-proxy en docker-compose.yml, ver ADR-022), no una función de
    este repo. Confirma en vivo que `CONTAINERS` sigue deshabilitado: si
    este test empieza a fallar, alguien habilitó más de lo que ADR-022
    autoriza (solo POST + ALLOW_RESTARTS).
    """
    client = docker.from_env()

    with pytest.raises(docker.errors.APIError) as list_exc:
        client.containers.list()
    assert list_exc.value.response.status_code == 403

    with pytest.raises(docker.errors.APIError) as create_exc:
        client.containers.create("alpine", "true")
    assert create_exc.value.response.status_code == 403


def test_admin_tasks_rechaza_sin_token_correcto():
    """Adversarial, mismo espíritu que los de arriba — pero acá el "código
    bajo prueba" es el sidecar `admin-tasks` (ver ADR-023), no una función
    de este repo. Habla directo con el sidecar (urllib, sin pasar por
    tools._call_admin_tasks) para no depender de que ADMIN_TASKS_TOKEN esté
    seteado en este proceso — el punto es probar el rechazo del lado del
    servidor con un token deliberadamente incorrecto, no el flujo feliz.
    """
    request = urllib.request.Request(
        "http://admin-tasks:8100/run-migrations",
        method="POST",
        headers={"Authorization": "Bearer token-incorrecto-a-proposito"},
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(request, timeout=10)
    assert exc.value.code == 401


def test_run_migrations_corre_contra_la_base_real():
    """Contra la base de desarrollo real (no destructivo: reaplicar
    migraciones ya aplicadas es un no-op de Django). Vía protocolo MCP real.
    """

    async def run():
        async with create_connected_server_and_client_session(mcp) as session:
            return await session.call_tool("run_migrations", {})

    result = anyio.run(run)

    assert not result.isError
    text = result.content[0].text
    assert "EXIT_CODE=0" in text


def test_run_tests_corre_y_devuelve_salida_coherente():
    """Hoy no hay tests propios de la app Django todavía — confirma que el
    comando corre limpio ("0 tests"), no que falle por un error real. Vía
    protocolo MCP real.
    """

    async def run():
        async with create_connected_server_and_client_session(mcp) as session:
            return await session.call_tool("run_tests", {})

    result = anyio.run(run)

    assert not result.isError
    text = result.content[0].text
    assert "EXIT_CODE=0" in text
    assert "0 tests" in text.lower() or "no tests ran" in text.lower()
