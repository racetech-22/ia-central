# Changelog

Todas las decisiones y avances relevantes del proyecto quedan registradas aquí, en orden cronológico. Las decisiones con justificación completa viven además como ADR en `docs/decisiones/`.

## 2026-07-30

- Definida la descripción inicial del proyecto IA CENTRAL.
- Aceptada arquitectura en tres capas (orquestación / conocimiento / ejecución) — ver ADR-001.
- Definido el pipeline de verificación de conocimiento (captura, verificación, promoción) — ver ADR-001.
- Decidido usar GitHub privado como repositorio fuente de verdad y VPS nuevo dedicado en Contabo (8-16GB RAM, 4 vCPU, NVMe) para IA CENTRAL — ver ADR-002.
- Creada la estructura inicial del repositorio (README.md, ARQUITECTURA.md, .gitignore, ADRs).
- Creado el skeleton de Django (`core/`, `manage.py`, `apps/`, `mcp_servers/`), empaquetado con `Dockerfile` y `docker-compose.yml` (web + Postgres con pgvector), y `requirements.txt`/`.env.example`. Verificado que build, migrate y check corren correctamente contra Postgres — arranque de Fase 2 de la hoja de ruta.
- Agregada la primera app propia bajo `apps/`: `adminpanel`, que personaliza el admin integrado de Django (branding "IA CENTRAL") e incluye `StatusNote` como modelo mínimo de ejemplo (modelo + ModelAdmin) a modo de plantilla para futuras apps. El panel administrativo real (costos, modelos activos, salud de conectores de ARQUITECTURA.md §4) queda para Fase 5.
