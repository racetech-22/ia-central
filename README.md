# IA CENTRAL

Asistente de IA central para el desarrollo, administración y evolución de todos los proyectos de Fernando (actuales y futuros), instalado inicialmente en un VPS de Contabo, con capacidad de operar sobre proyectos locales y en otros servidores.

## Visión

IA CENTRAL no es un chatbot: es un agente orquestador con memoria persistente y verificada, capaz de:

- Desarrollar, administrar, alterar y modificar proyectos propios (Python/Django principalmente) en el servidor donde vive, en otros servidores, y en la estación local de Fernando.
- Explotar el poder de múltiples IAs (Claude, modelos open source vía Ollama, otras de pago) según la tarea, el costo y la disponibilidad.
- Aprender de las conversaciones e iteraciones con las IAs conectadas, pero solo incorporando conocimiento verificado como real.
- Consultar a Fernando cuando encuentre dudas que no pueda resolver por sí mismo.
- Ser transferible por completo a otro servidor si es necesario, sin perder base de conocimiento ni capacidades ya desarrolladas.
- Administrar y dar visibilidad (panel administrativo) de sus propias funciones, variables, modelos y costos, así como de otros proyectos desarrollados en este servidor, en otros servidores, o en local.

Este README es un punto de entrada. La descripción completa de la arquitectura vive en ARQUITECTURA.md. Las decisiones tomadas y su razonamiento viven en docs/decisiones/.

## Estructura del repositorio

    ia-central/
    ├── README.md
    ├── CLAUDE.md                (guía para Claude Code en este repo)
    ├── ARQUITECTURA.md          (documento maestro de arquitectura, fuente de verdad)
    ├── CHANGELOG.md             (historial de cambios relevantes del proyecto)
    ├── docs/
    │   ├── DEPENDENCIAS.md      (inventario de herramientas y servicios externos)
    │   └── decisiones/          (ADRs, una por decisión importante, más INDEX.md)
    ├── .claude/                 (permisos y hooks de Claude Code)
    ├── .githooks/               (hooks de Git versionados)
    ├── .github/                 (workflows de GitHub Actions, ver ADR-010)
    ├── scripts/                 (backup, auditorías programadas por cron)
    ├── docker-compose.yml
    ├── Dockerfile
    ├── litellm/                 (config del servicio litellm, ver ADR-012)
    ├── ntfy/                    (config del servicio ntfy, ver ADR-018)
    ├── env.example
    ├── .gitignore
    ├── requirements.txt
    ├── manage.py
    ├── admin_tasks_server.py    (sidecar admin-tasks, ver ADR-023)
    ├── core/                    (proyecto Django: settings, urls raíz, asgi)
    ├── apps/                    (apps Django del propio IA CENTRAL)
    ├── orchestrator/            (interfaz interna del agente, ver ADR-012/ADR-021)
    └── mcp_servers/             (conectores MCP propios)

## Cómo mantener el contexto entre conversaciones

Este repositorio es la fuente de verdad versionada, y se consulta **en vivo** desde `https://raw.githubusercontent.com/racetech-22/ia-central/master/` — no vía copias subidas a los archivos del proyecto en Claude ni a Google Drive, que se desactualizan en cada commit. Ver ADR-011, incluidas sus enmiendas sobre caché del CDN y sobre `docs/decisiones/INDEX.md` (los nombres de archivo de las ADR llevan slug descriptivo y no son deducibles).

## Estado actual

Fase 2 completa (VPS, Docker, Django sobre Postgres, HTTPS en `aicentral.network` con Nginx + Certbot) y Fase 3 en curso: MCP server propio con tools nombradas, servicio `orchestrator` cableado, y `web` migrado a ASGI. El estado vigente y detallado vive en ARQUITECTURA.md §5 y en CHANGELOG.md — este README no lo duplica, porque una lista de avances acá se desactualiza sola.

## Cómo correrlo en local

    cp env.example .env      # completar SECRET_KEY/POSTGRES_PASSWORD reales
    docker compose up

La app queda disponible en http://localhost:8000. Ver CLAUDE.md para el resto de comandos comunes (migraciones, tests, superusuario).
