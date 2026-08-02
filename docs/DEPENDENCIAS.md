# Inventario de dependencias externas

Referencia única de qué herramientas y servicios externos usa IA CENTRAL, en qué versión, dónde viven y qué depende de cada uno. Ver ADR-019.

Criterio de inclusión: de qué depende el sistema para funcionar, no qué está instalado en el VPS.

**Mantenimiento**: actualizar en el mismo commit que se agregue, cambie de versión, o se retire cualquier dependencia de esta lista.

| Herramienta | Versión / pin | Dónde vive | ADR de origen | Actualización | Qué depende de ella |
|---|---|---|---|---|---|
| Docker / Docker Compose | Versión del SO del VPS, no pineada por el proyecto | Sistema operativo del VPS | ADR-002 | Manual, junto con mantenimiento del SO | Todo el stack |
| PostgreSQL (+ pgvector cuando se agregue) | Imagen de `docker-compose.yml` | Servicio `db` de Docker Compose | ADR-002 | Manual, pinear versión mayor | `web`, backups (ADR-004) |
| Nginx | Paquete del SO (`apt`) | Sistema operativo del VPS, fuera de Docker | ADR-003 | Manual (`apt upgrade`) | Borde HTTPS de `aicentral.network` y `ntfy.aicentral.network` |
| Certbot | Paquete del SO (`apt`) | Sistema operativo del VPS, fuera de Docker | ADR-003 | Renovación de certificados automática vía su propio timer; el paquete se actualiza manual | Nginx (TLS) |
| Spaceship (registrador + DNS) | N/A (servicio, no versionado) | Externo: panel de Spaceship, nameservers propios de Spaceship | ADR-003, ADR-018 | Renovación del dominio según config de la cuenta — verificar que no expire | `aicentral.network` (ADR-003) y `ntfy.aicentral.network` (ADR-018) |
| rclone | Binario standalone en `~/.local/bin` | Fuera de Docker, usuario `fernando` | ADR-005 | Manual; riesgo conocido de client_id compartido retirándose durante 2026 | `scripts/backup_postgres.sh` |
| LiteLLM | Imagen pineada (`ghcr.io/berriai/litellm:v1.83.14-stable`) | Servicio `litellm` de Docker Compose | ADR-012 | Manual, pinear versión exacta (nunca `latest`) | Orquestador (Fase 3; fuera del camino real por ADR-016) |
| Claude Agent SDK / CLI de Claude Code | Según lo instalado en VPS y local | Dependencia de librería del orquestador + binario `claude` | ADR-012, ADR-017 | Manual | Orquestador, `scripts/memory_audit.sh`, `scripts/adr_audit.sh` |
| ntfy | Imagen pineada (`binwiederhier/ntfy:v2.26.3`) | Servicio `ntfy` de Docker Compose | ADR-018 | Manual, pinear versión exacta (nunca `latest`) | `scripts/adr_audit.sh`; reutilizable por cualquier mecanismo futuro que necesite avisar a Fernando |
| Django | `>=5.0,<6.0` (`requirements.txt`) | Dependencia de `web`, instalada vía `requirements.txt` | ADR-002 | Manual | `web` |
| psycopg[binary] | `>=3.1,<4.0` (`requirements.txt`) | Dependencia de `web`, instalada vía `requirements.txt` | ADR-002 | Manual | `web` |
| python-dotenv | `>=1.0,<2.0` (`requirements.txt`) | Dependencia de `web`, instalada vía `requirements.txt` | ADR-002 | Manual | `web` |
| mcp | `==1.29.0` (pin exacto, línea v1 madura — no la v2.0.0 recién publicada) | `mcp_servers/django_project/requirements.txt` | ADR-020 | Manual, pinear versión exacta (nunca `latest` ni rango) | El MCP server del proyecto Django (`mcp_servers/django_project/`) |
