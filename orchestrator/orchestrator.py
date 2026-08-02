"""Interfaz interna del orquestador (ver ADR-012, ADR-021).

Única función pública: run(prompt) -> str. Es la interfaz que menciona
ADR-012 — nada más en el repo debería importar `claude_agent_sdk`
directamente (ver mcp_servers/django_project/tests/test_sdk_boundary.py).

Sin lógica de negocio ni disparador automático (cron, scheduler): este
servicio existe para probar el cableado (servicio de Docker Compose,
autenticación por suscripción, conexión al MCP server de
mcp_servers/django_project), no para correr tareas por su cuenta. Se invoca
manualmente, ej.:
    docker compose exec orchestrator python -c "from orchestrator import run; print(run('...'))"

`tools=[]` restringe la BASE de tools built-in de Claude Code (Bash, Read,
Write, Edit, Glob, Grep, WebFetch, WebSearch, etc.) a una lista vacía, en vez
de una lista negra de nombres (frágil, cambia entre versiones del CLI) — la
lista de tools ES la política de seguridad (ADR-015). Se probó listar acá
`WaitForMcpServers` (para que el modelo esperara la conexión del MCP por su
cuenta) pero no apareció disponible en la sesión aunque se la nombrara
explícitamente; se resuelve en cambio con el polling determinista de
`_wait_for_mcp_ready()` más abajo, cableado en Python, no una decisión del
modelo. Hallazgo residual sin resolver (ver ADR-021): incluso con `tools=[]`,
cuatro tools de plataforma (`DesignSync`, `Monitor`, `PushNotification`,
`RemoteTrigger`) siguen apareciendo disponibles — ninguna da acceso a
filesystem ni shell.

`strict_mcp_config=True` es necesario porque, verificado en la práctica, sin
este flag el SDK no se limita al `mcp_servers` de acá abajo — también carga
conectores de la cuenta real asociada al credencial de suscripción (se vio
aparecer "claude.ai Google Drive", que este proyecto nunca configuró para el
orquestador). Con `strict_mcp_config=True`, el único MCP server disponible
es exactamente el de mcp_servers/django_project.
"""

from __future__ import annotations

import anyio
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient, ResultMessage

MCP_SERVER_NAME = "django_project"
REPO_ROOT = "/app"
MCP_READY_TIMEOUT_S = 15.0

_OPTIONS = ClaudeAgentOptions(
    tools=[],
    strict_mcp_config=True,
    mcp_servers={
        MCP_SERVER_NAME: {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "mcp_servers.django_project.server"],
            "env": {"PYTHONPATH": REPO_ROOT},
        }
    },
    allowed_tools=[
        f"mcp__{MCP_SERVER_NAME}__git_status",
        f"mcp__{MCP_SERVER_NAME}__read_file",
    ],
    cwd=REPO_ROOT,
)


async def _wait_for_mcp_ready(client: ClaudeSDKClient) -> None:
    """Espera a que `django_project` quede `connected` antes de mandar el prompt.

    Verificado en la práctica (ver ADR-021): sin esto, `query()` de una sola
    pasada respondía en el primer turno con el MCP todavía en estado
    `pending`, y el modelo contestaba como si la tool no existiera. Este
    polling con `get_mcp_status()` es cableado determinista, no una decisión
    del modelo — evita depender de que el modelo decida esperar.
    """
    deadline = anyio.current_time() + MCP_READY_TIMEOUT_S

    while True:
        status = await client.get_mcp_status()
        server = next(
            (s for s in status["mcpServers"] if s["name"] == MCP_SERVER_NAME),
            None,
        )
        current = server["status"] if server else None

        if current == "connected":
            return
        if current in ("failed", "needs-auth", "disabled"):
            error = server.get("error") if server else None
            raise RuntimeError(
                f"MCP server '{MCP_SERVER_NAME}' quedó en estado '{current}'"
                + (f": {error}" if error else "")
            )
        if anyio.current_time() > deadline:
            raise RuntimeError(
                f"MCP server '{MCP_SERVER_NAME}' no llegó a 'connected' dentro de "
                f"{MCP_READY_TIMEOUT_S}s (último estado: {current!r})"
            )
        await anyio.sleep(0.3)


async def _run_async(prompt: str) -> str:
    result_text: str | None = None

    async with ClaudeSDKClient(options=_OPTIONS) as client:
        await _wait_for_mcp_ready(client)

        await client.query(prompt)
        async for message in client.receive_response():
            if isinstance(message, ResultMessage):
                if message.is_error:
                    raise RuntimeError(f"query terminó con error: {message.result!r}")
                result_text = message.result

    if result_text is None:
        raise RuntimeError("query no devolvió ningún ResultMessage con resultado")

    return result_text


def run(prompt: str) -> str:
    """Consulta al modelo con las tools del MCP server de mcp_servers/django_project disponibles."""
    return anyio.run(_run_async, prompt)
