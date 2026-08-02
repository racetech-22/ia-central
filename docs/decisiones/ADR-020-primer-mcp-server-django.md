# ADR-020 - Primer MCP server: `mcp_servers/django_project/`, dos tools de solo lectura

Fecha: 2026-08-02
Estado: Aceptada

## Contexto

`mcp_servers/` existía desde el skeleton inicial sin ninguna tool implementada (la auditoría de solo lectura del 2026-08-02 lo señaló como discrepancia entre ARQUITECTURA.md §2, redactado en presente, y el repo real). ADR-015 establece que el LLM del orquestador nunca tiene shell arbitrario — toda capacidad se expone como tools MCP discretas y nombradas, y la lista de tools disponibles ES la política de seguridad. ADR-017 condiciona el montaje del credencial de suscripción en el futuro contenedor del orquestador a que "ninguna tool MCP permita lectura de rutas arbitrarias del filesystem".

No hay todavía ningún orquestador corriendo (confirmado en la misma auditoría): no hay servicio en `docker-compose.yml`, no hay código de orquestador, el Claude Agent SDK no es una dependencia declarada en ningún `requirements.txt`. Esta primera pieza de `mcp_servers/` se construye y se prueba de forma standalone, sin wiring a ningún servicio real.

## Decisión

Se agrega `mcp_servers/django_project/`, con exactamente dos tools, ambas de solo lectura y cero efectos secundarios:

- `git_status()`: corre `git status --porcelain` con `cwd` fijo en la raíz del repo, vía `subprocess` con lista de argumentos (nunca `shell=True`). Sin parámetros de entrada — no hay superficie de inyección posible.
- `read_file(path: str)`: devuelve el contenido de un archivo dentro del repo, truncando (con aviso explícito) si supera 200KB.

**Por qué solo estas dos.** Mismo criterio que ADR-015: agregar capacidades de a una, no todas de entrada. `run_migrations`, `restart_web` y `run_tests` — las otras tres tools mencionadas en ARQUITECTURA.md §2 — tienen efectos reales sobre el sistema (modifican la base de datos, reinician un servicio, ejecutan código arbitrario de tests) y ameritan una decisión aparte y deliberada sobre su propio diseño de seguridad, no arrastrarse por default junto con las de solo lectura.

**`security.py` como autoridad única de la condición de ADR-017.** Toda tool que acepte una ruta pasa por `security.resolve_safe_path(path, allowed_root)`, que:
1. Resuelve la ruta solicitada a absoluta real (`Path.resolve()`, sigue symlinks).
2. Rechaza (`PathSecurityError`, nunca un `None` silencioso) si la ruta resuelta no queda estrictamente dentro de la raíz permitida — cubre `../` y symlinks que escapen, porque `resolve()` ya sigue el symlink hasta su destino final antes de comparar.
3. Rechaza además, aunque quede dentro de la raíz, cualquier archivo que matchee `.env` o `.env.*` — mismo patrón que `.claude/settings.json` (ADR-006), como defensa en profundidad, no una única capa.

Verificado con `tests/test_security.py`, cinco casos adversariales explícitos (no agregados en un solo test): traversal clásico (`../../../etc/passwd`), ruta absoluta fuera de la raíz (`/etc/passwd`), un symlink real creado dentro de la raíz apuntando afuera, `.env` y `.env.local` dentro de la raíz — los cinco rechazados — más un caso feliz que confirma que una ruta legítima sí se acepta. Los diez tests del paquete (incluidos estos cinco) corrieron en verde antes de este commit.

**Verificación de la frontera de ADR-012.** `tests/test_sdk_boundary.py` recorre todos los `.py` del repo buscando imports de `claude_agent_sdk` (paquete `claude-agent-sdk`) fuera de una lista explícita de rutas permitidas (`ALLOWED_SDK_IMPORT_PATHS`, vacía hoy a propósito, porque la interfaz interna del orquestador — `orchestrator.run(...)` — todavía no existe). El test pasa en verde ahora mismo y queda como red para el día que se construya el orquestador: la ruta exacta de esa interfaz se agrega explícitamente a la lista, no se relaja la búsqueda con un patrón laxo.

**Decisión de versión: `mcp==1.29.0`, no `2.0.0`.** Se evaluaron ambas, verificadas contra fuentes oficiales (PyPI JSON API, tags de Git del repo `modelcontextprotocol/python-sdk`, código fuente real de los ejemplos oficiales pineado a cada commit exacto):
- `mcp==2.0.0`: real, publicada el 2026-07-28, no yankeada. Es un rework mayor de la API — la clase `MCPServer` (`from mcp.server.mcpserver import MCPServer`) reemplaza a `FastMCP`.
- `mcp==1.29.0`: también publicada el 2026-07-28 (última de la línea v1). API confirmada contra el código fuente real de `examples/fastmcp/*.py` en el tag `v1.29.0`: `from mcp.server.fastmcp import FastMCP`, `mcp = FastMCP("nombre")`, `@mcp.tool()`, entrypoint `if __name__ == "__main__": mcp.run()`. Mecanismo de test en memoria confirmado en `src/mcp/shared/memory.py` de ese mismo commit: `create_connected_server_and_client_session(server)`, que acepta un `FastMCP` (o `Server` de bajo nivel) y devuelve una `ClientSession` conectada vía streams de memoria de `anyio`, sin transporte real — es lo que usa `tests/test_tools.py`.

Se elige `1.29.0` para esta primera pieza de infraestructura sensible (una tool que ya toca el filesystem del proyecto) por ser la línea madura con soporte de parches de seguridad activo, en vez de una API con 5 días de antigüedad. Reevaluar el salto a v2 más adelante es una decisión aparte y deliberada, no automática.

## Alternativas descartadas

- **Sumar `run_migrations`/`restart_web`/`run_tests` en esta misma entrega**: descartado por el mismo criterio de ADR-015 (capacidades de a una) — mezclar tools de solo lectura con tools de efectos reales en el mismo commit diluye la revisión de seguridad de estas últimas.
- **`mcp==2.0.0`**: descartado para esta entrega por ser una API con 5 días de antigüedad al momento de esta decisión, sin trayectoria de parches de seguridad propia todavía. No descartado para siempre — candidato a reevaluar cuando la línea v2 madure.
- **Reimplementar la validación de rutas dentro de cada tool en vez de un módulo compartido**: descartado — es exactamente el patrón que ya se evitó en `.claude/settings.json`/ADR-006 (una sola capa, fácil de olvidar al agregar la próxima tool). `security.py` es la única autoridad, y cualquier tool nueva que toque filesystem tiene que pasar por ahí.
- **Probar `read_file`/`git_status` llamando las funciones de Python directo, sin pasar por el protocolo MCP**: se usa igual para el caso de "propaga el error" en `read_file` (ver más abajo), pero para los casos felices se prefirió probar a través de `create_connected_server_and_client_session` — así queda demostrado que las tools están correctamente registradas y son invocables como tools MCP, no solo que las funciones sueltas de Python funcionan.

## Consecuencias

- `mcp_servers/django_project/requirements.txt` es una capa de dependencias separada del `requirements.txt` de la raíz (ese es de `web`/Django) — no se mezclan.
- No se modificó `docker-compose.yml`: este MCP server no tiene wiring a ningún servicio, se prueba de forma standalone.
- `read_file()` sobre una ruta bloqueada por `security.py` se prueba llamando la función de Python directo (`tools.read_file(...)`), no a través del protocolo MCP: FastMCP atrapa cualquier excepción de una tool y la convierte en `CallToolResult(isError=True)` en vez de volver a lanzarla del lado del cliente — a ese nivel no se distinguiría "propaga el error real" de "un catch silencioso que devuelve `isError` sin motivo". La propagación real de `PathSecurityError` se prueba directo contra la función, donde un catch agregado por error sí haría fallar el test.
- Quedan explícitamente fuera de esta entrega, para una decisión posterior y deliberada (no un olvido): `run_migrations`, `restart_web`, `run_tests` — las tres tienen efectos reales sobre el sistema.
- El día que exista `orchestrator.run(...)`, agregar su ruta exacta a `ALLOWED_SDK_IMPORT_PATHS` en `test_sdk_boundary.py` — no relajar la búsqueda en sí.
