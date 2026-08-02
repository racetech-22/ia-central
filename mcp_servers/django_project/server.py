"""Entrypoint MCP del proyecto Django de IA CENTRAL (ver ADR-020).

Standalone: no hay ningún orquestador corriendo todavía (confirmado en la
auditoría de solo lectura del 2026-08-02), así que este server no tiene
wiring a ningún servicio real — se construye y se prueba de forma aislada,
vía mcp.shared.memory.create_connected_server_and_client_session (ver
tests/test_tools.py), no con un cliente MCP real.

Patrón verificado contra el código fuente oficial de mcp==1.29.0
(examples/fastmcp/*.py en el tag v1.29.0 del repo modelcontextprotocol/python-sdk).
"""

from mcp.server.fastmcp import FastMCP

from mcp_servers.django_project import tools

mcp = FastMCP("IA CENTRAL - proyecto Django")


@mcp.tool()
def git_status() -> str:
    """Estado de git del repo (`git status --porcelain`). Solo lectura, sin parámetros."""
    return tools.git_status()


@mcp.tool()
def read_file(path: str) -> str:
    """Lee un archivo dentro de la raíz del repo, validado contra security.py."""
    return tools.read_file(path)


if __name__ == "__main__":
    mcp.run()
