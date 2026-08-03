# mcp_servers

Conectores MCP propios de IA CENTRAL (capa de ejecución, ver ARQUITECTURA.md §2):

- `django_project/`: MCP server del propio proyecto Django, para que la IA pueda leer/modificar su propio código. Cinco tools, entregadas en tres tandas:
  - Primera entrega (ADR-020): dos de solo lectura, cero efectos secundarios — `git_status` y `read_file`.
  - Segunda entrega (ADR-022): `restart_web` — reinicia el contenedor `web` vía un proxy de la API de Docker (`tecnativa/docker-socket-proxy`, servicio `docker-proxy` de `docker-compose.yml`), nunca con el socket real montado directo.
  - Tercera entrega (ADR-023): `run_migrations`/`run_tests` — corren contra un sidecar propio (`admin-tasks`, servicio nuevo con la misma imagen que `web`, sin `ports:`) que no toca Docker en absoluto, solo corre comandos fijos de Django management contra la base real. Se eligió este camino en vez de `exec` vía el proxy de ADR-022 porque ese proxy no puede aislar `exec` de crear/borrar contenedores nuevos.
- MCP/SSH hacia la estación local de Fernando — todavía no implementado. Su diseño queda en suspenso, no descartado: depende de resolver primero la conectividad VPN/túnel (hoy no hay ningún camino de red del VPS hacia la máquina local — la conectividad existente es al revés) y de encajar en el modelo de confianza unificado de ADR-024, en vez de construirse acotado por separado.
- MCP/SSH de solo lectura por defecto hacia los otros servidores existentes de Fernando — todavía no implementado. Mismo motivo que el punto anterior: en suspenso hasta el modelo de confianza de ADR-024, no descartado.

Conectado al servicio real `orchestrator` de `docker-compose.yml` (ver ADR-021) — corre como subproceso stdio dentro de ese contenedor, con acceso al repo (solo lectura), al proxy de Docker (`DOCKER_HOST`) y al sidecar `admin-tasks` (`ADMIN_TASKS_TOKEN`).
