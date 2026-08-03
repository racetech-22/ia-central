"""Entrypoint MCP del proyecto Django de IA CENTRAL (ver ADR-020, ADR-021, ADR-022).

Ya conectado al servicio real `orchestrator` de docker-compose.yml (ver
ADR-021) — corre como subproceso stdio dentro de ese contenedor.

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


@mcp.tool()
def restart_web() -> str:
    """Reinicia el contenedor `web` (nombre fijo). Sin parámetros. Ver ADR-022."""
    return tools.restart_web()


if __name__ == "__main__":
    mcp.run()
