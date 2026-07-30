# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado del proyecto

Skeleton de Django creado (arranque de Fase 2 de la hoja de ruta, ver ARQUITECTURA.md §5): proyecto `core/` funcional, empaquetado con Docker, corriendo contra Postgres. Todavía no hay apps propias en `apps/` ni conectores en `mcp_servers/` (eso es Fase 3). No hay entorno virtual local ni Django instalado fuera de Docker — todo el desarrollo se hace vía `docker compose`.

### Comandos comunes

```bash
cp .env.example .env          # solo la primera vez; completar SECRET_KEY/POSTGRES_PASSWORD reales
docker compose build web      # reconstruir la imagen tras cambiar requirements.txt
docker compose up             # levantar db + web (http://localhost:8000)
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test              # cuando existan tests
docker compose down           # bajar los contenedores (los datos persisten en el volumen postgres_data)
```

No hay todavía un linter/formatter configurado (ni pre-commit, ni ruff/black en requirements.txt) — si se agrega uno, actualizar esta sección con el comando exacto.

## Qué es IA CENTRAL

Un agente orquestador con memoria persistente y verificada — no un chatbot — pensado para desarrollar, administrar y modificar todos los proyectos de Fernando (locales y en varios servidores), explotando múltiples IAs (Claude, modelos vía Ollama, otras de pago) según tarea/costo/disponibilidad, y aprendiendo de sus interacciones solo cuando ese conocimiento pasa por verificación explícita.

Dos condiciones no negociables guían cualquier decisión de diseño (ADR-001):

1. **Portable**: todo debe poder transferirse por completo a otro servidor sin perder base de conocimiento ni funcionalidad.
2. **Verificable**: el conocimiento auto-generado por el sistema nunca se trata como válido por defecto; debe pasar por el pipeline captura → verificación (cruce de fuentes o confirmación de Fernando) → promoción antes de considerarse "conocimiento confirmado".

## Arquitectura en tres capas (ver ARQUITECTURA.md)

- **Orquestación**: agente construido sobre el Claude Agent SDK, corriendo como proceso persistente en el VPS, decide qué hacer y a qué IA/herramienta delegar.
- **Conocimiento**: memoria de largo plazo independiente del servidor físico — base vectorial (pgvector sobre Postgres, o Qdrant) para RAG, más ADRs/documento maestro versionados en Git. Incluye el pipeline de verificación obligatorio descrito arriba.
- **Ejecución**: los conectores que dan poder real sobre el mundo — MCP server propio del proyecto Django, MCP/SSH hacia la estación local de Fernando (Tailscale/WireGuard), MCP/SSH de solo lectura por defecto hacia otros servidores existentes de Fernando (no se escribe ahí sin decisión explícita), Claude Code como motor de desarrollo, y un router de modelos (LiteLLM u OpenRouter) para no acoplar el core a un proveedor específico.

Cualquier función de auto-aprendizaje que se implemente debe cubrir las tres etapas del pipeline (captura, verificación, promoción) antes de considerarse completa — es una consecuencia directa de ADR-001, no opcional.

## Infraestructura (ver ADR-002)

- VPS nuevo y dedicado en Contabo, exclusivo para IA CENTRAL — nunca reutilizar los VPS existentes de Fernando que ya corren otros proyectos en producción.
- Todo el stack se empaqueta con Docker + Docker Compose, de forma que migrar de servidor sea `docker compose up` más restore de datos.
- Repo GitHub privado (`ia-central`), clonado igual en el VPS y en la máquina local de Fernando, sincronizado por Git — es la fuente de verdad versionada.
- Acceso a los demás servidores de Fernando: solo lectura por defecto vía MCP/SSH; no se otorga escritura sin decisión explícita.

## Cómo mantener la documentación (importante para cualquier tarea en este repo)

- `ARQUITECTURA.md` es el documento maestro y fuente de verdad: se actualiza cada vez que se toma una decisión de arquitectura relevante.
- Toda decisión importante se registra además como ADR individual en `docs/decisiones/` (formato: Contexto / Decisión / Alternativas descartadas / Consecuencias), no solo como una línea en ARQUITECTURA.md.
- `CHANGELOG.md` registra en orden cronológico todas las decisiones y avances relevantes.
- Cuando cambies ARQUITECTURA.md o agregues/edites una ADR, también hay que actualizar CHANGELOG.md en el mismo cambio, y recordarle a Fernando que debe subir la versión vigente a los archivos del proyecto "IA CENTRAL" en Claude para que conversaciones futuras arranquen con el contexto completo.
- No dupliques contenido entre README.md, ARQUITECTURA.md y las ADRs: el README es el punto de entrada, ARQUITECTURA.md es la fuente de verdad completa, y las ADRs contienen el razonamiento detrás de cada decisión puntual.
