# mcp_servers

Conectores MCP propios de IA CENTRAL (capa de ejecución, ver ARQUITECTURA.md §2):

- `django_project/`: MCP server del propio proyecto Django, para que la IA pueda leer/modificar su propio código. Primera entrega (ver ADR-020): dos tools de solo lectura, cero efectos secundarios — `git_status` y `read_file`. Deliberadamente afuera de esta entrega, para una tanda posterior: `run_migrations`, `restart_web`, `run_tests` (tools con efectos reales, requieren una decisión aparte, ver ADR-015).
- MCP/SSH hacia la estación local de Fernando — todavía no implementado.
- MCP/SSH de solo lectura por defecto hacia los otros servidores existentes de Fernando — todavía no implementado.

Standalone por ahora: no hay ningún orquestador corriendo (ver ARQUITECTURA.md §2 y la auditoría de solo lectura del 2026-08-02), así que `django_project/` se construye y se prueba de forma aislada, sin wiring a ningún servicio real. Se implementa completamente en la Fase 3 de la hoja de ruta (ver ARQUITECTURA.md §5).
