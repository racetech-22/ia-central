# mcp_servers

Conectores MCP propios de IA CENTRAL (capa de ejecución, ver ARQUITECTURA.md §2):

- `django_project/`: MCP server del propio proyecto Django, para que la IA pueda leer/modificar su propio código.
  - Primera entrega (ADR-020): dos tools de solo lectura, cero efectos secundarios — `git_status` y `read_file`.
  - Segunda entrega (ADR-022): `restart_web` — reinicia el contenedor `web` vía un proxy de la API de Docker (`tecnativa/docker-socket-proxy`, servicio `docker-proxy` de `docker-compose.yml`), nunca con el socket real montado directo. `run_migrations` y `run_tests` (que necesitarían `exec` dentro del contenedor) quedan deliberadamente afuera: el proxy no tiene forma de aislar `exec` de crear/borrar contenedores nuevos (ver ADR-022) — necesitan un mecanismo distinto, todavía sin decidir.
- MCP/SSH hacia la estación local de Fernando — todavía no implementado.
- MCP/SSH de solo lectura por defecto hacia los otros servidores existentes de Fernando — todavía no implementado.

Conectado al servicio real `orchestrator` de `docker-compose.yml` (ver ADR-021) — corre como subproceso stdio dentro de ese contenedor, con acceso al repo (solo lectura) y al proxy de Docker (a través de `DOCKER_HOST`).
