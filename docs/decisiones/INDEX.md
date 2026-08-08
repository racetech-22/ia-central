# Índice de ADR

Manifiesto en ruta fija de los nombres de archivo reales de cada ADR — necesario porque `raw.githubusercontent.com` no soporta listar directorio ni glob, y el fallback obvio (`api.github.com/repos/.../contents/...`) devuelve vacío desde herramientas de fetch como la de Cowork (ver ADR-011). Cualquier sesión que solo tenga fetch web (sin shell ni navegador) debe leer este archivo primero para resolver la URL exacta de cada ADR antes de pedirla.

**Mantenimiento**: cada vez que se agregue una ADR nueva, agregar su línea acá en el mismo commit — es el mismo hábito que ya exige CLAUDE.md para ARQUITECTURA.md §6 y CHANGELOG.md, no una tarea nueva.

| ADR | Archivo |
|-----|---------|
| ADR-001 | ADR-001-arquitectura-base.md |
| ADR-002 | ADR-002-repo-y-vps.md |
| ADR-003 | ADR-003-nginx-certbot-fuera-de-docker.md |
| ADR-004 | ADR-004-backup-postgres.md |
| ADR-005 | ADR-005-rclone-google-drive-interino.md |
| ADR-006 | ADR-006-limites-deny-permisos-claude-code.md |
| ADR-007 | ADR-007-hook-bloqueo-comandos-destructivos-db.md |
| ADR-008 | ADR-008-cron-auditoria-mensual-memoria.md |
| ADR-009 | ADR-009-cowork-no-alcanza-red-vps.md |
| ADR-010 | ADR-010-sync-docs-a-drive.md |
| ADR-011 | ADR-011-fuente-de-verdad-en-vivo.md |
| ADR-012 | ADR-012-independencia-proveedor-litellm.md |
| ADR-013 | ADR-013-interfaz-y-persistencia-propias.md |
| ADR-014 | ADR-014-auditoria-semanal-veracidad-adr.md |
| ADR-015 | ADR-015-orquestador-docker-superficie-cerrada.md |
| ADR-016 | ADR-016-autenticacion-por-suscripcion.md |
| ADR-017 | ADR-017-credencial-suscripcion-en-contenedor.md |
| ADR-018 | ADR-018-hook-precommit-index-y-notificacion.md |
| ADR-019 | ADR-019-inventario-dependencias-externas.md |
| ADR-020 | ADR-020-primer-mcp-server-django.md |
| ADR-021 | ADR-021-servicio-orquestador-docker.md |
| ADR-022 | ADR-022-segunda-tanda-mcp-docker-proxy.md |
| ADR-023 | ADR-023-sidecar-admin-tasks.md |
| ADR-024 | ADR-024-vision-ampliada-multi-proyecto.md |
| ADR-025 | ADR-025-diseno-sala-discusion.md |
| ADR-026 | ADR-026-servidor-asgi-daphne.md |
| ADR-027 | ADR-027-interfaz-ejecutor-acp.md |
| ADR-028 | ADR-028-aislamiento-proceso-ejecutor.md |
| ADR-029 | ADR-029-mapa-de-ruta-desde-estado-versionado.md |
| ADR-030 | ADR-030-granularidad-ciclo-vida-ejecutor.md |
| ADR-031 | ADR-031-ubicacion-cliente-acp.md |
| ADR-032 | ADR-032-verificacion-arquitectura-seccion-6.md |
| ADR-033 | ADR-033-modelo-datos-chat-consultor-ejecutor.md |
| ADR-034 | ADR-034-historial-ejecutor-y-solicitud-permiso-acp.md |
| ADR-035 | ADR-035-rutas-websocket-sala.md |
| ADR-036 | ADR-036-principio-maxima-capacidad-operador-unico.md |
| ADR-037 | ADR-037-chequeo-sistema-vivo-desplegado.md |
