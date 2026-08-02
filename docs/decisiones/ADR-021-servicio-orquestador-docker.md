# ADR-021 - Servicio del orquestador en Docker Compose: cableado mínimo, sin lógica de negocio

Fecha: 2026-08-03
Estado: Aceptada

## Contexto

ADR-015 decide que el orquestador corre como servicio de `docker-compose.yml`, sin shell arbitrario, con toda capacidad expuesta como tools MCP discretas. ADR-016 deja pendiente, para Fase 3, verificar la autenticación por suscripción desde un servicio real (lo probado hasta ahí fue un contenedor de test descartable, ver ADR-017). ADR-017 condiciona el montaje del credencial a que ninguna tool MCP permita lectura de rutas arbitrarias — condición hoy vacía porque no existía ningún orquestador real corriendo (confirmado en la auditoría de solo lectura del 2026-08-02).

Este ADR cierra ambos pendientes con el primer cableado real: un servicio `orchestrator` en `docker-compose.yml` que se autentica por suscripción y llama a las tools de `mcp_servers/django_project` (ADR-020). Deliberadamente sin lógica de negocio, sin cron, sin scheduler, sin ningún disparador automático — se invoca a mano. `run_migrations`/`restart_web`/`run_tests` siguen fuera de alcance.

## Decisión

**Paquete y versión**: `claude-agent-sdk==0.2.89` (pin exacto, no la última — `0.2.128` al momento de esta decisión — mismo criterio conservador que `mcp==1.29.0` en ADR-020). Verificado contra el tag `v0.2.89` real del repo oficial (`anthropics/claude-agent-sdk-python`, commit `f2fe254e`, release no yankeada en PyPI, subida 2026-06-03).

**`orchestrator/Dockerfile`**: imagen `python:3.12-slim` + `git` (lo necesita `git_status` cuando corre como subproceso dentro de este mismo contenedor). Usuario no-root creado en build time con UID parametrizado vía `ARG ORCHESTRATOR_UID` (default `1001`, el UID real de `fernando` en este VPS) — **nunca cableado a un número fijo en el código**, porque migrar de servidor (ADR-002) puede cambiar ese UID. `docker-compose.yml` lo pasa como build arg desde la variable de entorno `ORCHESTRATOR_UID`.

**Montajes del servicio `orchestrator`**:
- `${HOME}/.claude/.credentials.json:/home/orchestrator/.claude/.credentials.json:ro` — mismo archivo, mismo patrón de solo lectura que ADR-017 ya probó en un contenedor descartable. Verificado que el SDK no reimplementa autenticación: lanza el mismo binario `claude` real como subproceso y hereda el entorno del proceso Python (confirmado leyendo `_internal/transport/subprocess_cli.py` del SDK) — la autenticación es idéntica a la de la CLI directa.
- `.:/app:ro` — el repo completo, solo lectura. Es lo único que necesita `mcp_servers/django_project` para que `git_status`/`read_file` funcionen. Nada de socket de Docker, nada de escritura.
- Sin `ports:` — no expone nada.

**Conexión al MCP server**: vía subproceso stdio, patrón oficial de `claude-agent-sdk==0.2.89` (confirmado contra el README y `types.py` del SDK, no asumido):
```python
mcp_servers={
    "django_project": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "mcp_servers.django_project.server"],
        "env": {"PYTHONPATH": "/app"},
    }
}
```
Las tools se exponen al modelo con el nombre `mcp__django_project__git_status` / `mcp__django_project__read_file` (patrón `mcp__<server>__<tool>`, verbatim del README del SDK).

**`tools=[]`, no una lista negra de nombres**: `ClaudeAgentOptions.tools` restringe la base de tools built-in de Claude Code a una lista explícita — `[]` deshabilita Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch y el resto del set interactivo completo (~29 tools confirmadas empíricamente en el `SystemMessage` de una sesión sin restringir nada). Se prefiere esto a mantener una lista negra en `disallowed_tools`, que sería frágil y no exhaustiva por diseño (mismo problema ya documentado en ADR-006/ADR-007 para otros mecanismos de este proyecto). Las únicas tools con las que el modelo puede actuar son las dos del MCP, listadas en `allowed_tools`.

**`strict_mcp_config=True`**: necesario y no opcional — verificado en la práctica que sin este flag, el SDK no se limita al `mcp_servers` configurado acá: también carga conectores de la cuenta real asociada al credencial de suscripción (apareció `"claude.ai Google Drive"`, que este proyecto nunca configuró para el orquestador). Con el flag, `get_mcp_status()` confirma que el único MCP server presente es `django_project`.

**Polling explícito de `get_mcp_status()` antes de consultar al modelo**: verificado en la práctica que usar `query()` de una sola pasada fallaba — el primer turno respondía con el MCP todavía en estado `pending` y el modelo contestaba como si la tool no existiera (probado con `git_status`: el modelo dijo textualmente no tener esa tool disponible). Se reemplazó por `ClaudeSDKClient`, con un polling determinista de `get_mcp_status()` (cada 300ms, timeout 15s) antes de mandar el prompt — cableado, no una decisión del modelo. Se descartó depender de que el modelo mismo esperara la conexión (vía alguna tool tipo `WaitForMcpServers`) porque, aun listándola explícitamente en `tools=[...]`, no apareció disponible en la sesión — no se investigó más a fondo por qué, dado que el polling explícito resuelve el problema de forma determinista y sin depender de comportamiento no documentado del modelo.

**Hallazgo residual, no resuelto, documentado explícitamente**: incluso con `tools=[]`, cuatro tools (`DesignSync`, `Monitor`, `PushNotification`, `RemoteTrigger`) siguen apareciendo en el `SystemMessage` de toda sesión probada, sin importar el valor de `tools`. Ninguna de las cuatro da acceso a filesystem ni shell (a diferencia de Bash/Read/Write/Edit, que sí se confirmó que `tools=[]` elimina por completo), así que no viola la condición central de ADR-015 ("nunca shell arbitrario"), pero no es una lista vacía real — parecen tools de plataforma/cuenta no filtrables vía `tools`, similar al comportamiento documentado para `EndConversation` en la documentación oficial de Claude Code. Queda anotado como pendiente de investigación futura, no bloqueante para esta entrega.

## Alternativas descartadas

- **`disallowed_tools` con lista explícita de ~29 nombres**: descartado por `tools=[]`, más robusto y no atado a mantener una lista sincronizada con cada versión del CLI.
- **Confiar en que el modelo espere la conexión del MCP por su cuenta** (vía alguna tool de espera): descartado tras comprobar que no aparece disponible aunque se la liste explícitamente; se prefirió el polling determinista de `get_mcp_status()`.
- **UID fijo en el Dockerfile**: descartado — ADR-017 ya estableció que el UID tiene que ser parametrizable, no cableado, por el contrato de portabilidad de servidor (ADR-002).
- **Montar el socket de Docker o dar acceso de escritura al repo**: no hace falta para las dos tools de solo lectura de ADR-020; descartado por superficie de riesgo innecesaria.

## Consecuencias

- Cierra el pendiente de Fase 3 de ADR-016 (verificación en un servicio real, no un contenedor descartable) y la condición de ADR-017 (ya no está vacía: hay una tool MCP real, de solo lectura, corriendo).
- `orchestrator/requirements.txt` instala tanto `claude-agent-sdk==0.2.89` como `mcp==1.29.0` — este último porque el subproceso stdio que lanza la tool de `mcp_servers/django_project` corre dentro de este mismo contenedor, con su mismo entorno Python.
- Verificado end-to-end: `docker compose exec orchestrator python -c "from orchestrator import run; print(run(...))"` con tres prompts distintos (PONG puro, `git_status`, `read_file`) — los tres devolvieron el resultado esperado, incluyendo el estado real del repo vía `git_status` sin ningún error de autenticación ni de conexión al MCP.
- Sin lógica de negocio ni disparador automático: el proceso principal del contenedor es `sleep infinity` — el servicio existe para ser invocado a mano, no para actuar por su cuenta.
- El hallazgo residual de `DesignSync`/`Monitor`/`PushNotification`/`RemoteTrigger` queda documentado como no resuelto — no bloquea esta entrega, pero es candidato a revisar antes de que el orquestador tenga lógica de negocio real.
- `run_migrations`, `restart_web`, `run_tests` siguen explícitamente fuera de alcance (ADR-020), para una decisión posterior y deliberada.
