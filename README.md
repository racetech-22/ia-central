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
    ├── ARQUITECTURA.md          (documento maestro de arquitectura, fuente de verdad)
    ├── CHANGELOG.md             (historial de cambios relevantes del proyecto)
    ├── docs/
    │   └── decisiones/          (ADRs, una por decisión importante)
    ├── docker-compose.yml
    ├── env.example
    ├── .gitignore
    ├── requirements.txt
    ├── manage.py
    ├── core/                    (proyecto Django: settings, urls raíz)
    ├── apps/                    (apps Django del propio IA CENTRAL)
    └── mcp_servers/             (conectores MCP propios: Django, servidores, local)

## Cómo mantener el contexto entre conversaciones

Este repositorio es la fuente de verdad versionada. Además, cada vez que ARQUITECTURA.md o las ADRs se actualicen, la versión vigente debe subirse también a los archivos del proyecto "IA CENTRAL" en Claude, para que cualquier conversación futura arranque con el contexto completo sin necesidad de reexplicarlo.

## Estado actual

Skeleton de Django creado y funcionando sobre Docker (Fase 2 en marcha). Ver CHANGELOG.md para el detalle de avances.

## Cómo correrlo en local

    cp env.example .env      # completar SECRET_KEY/POSTGRES_PASSWORD reales
    docker compose up

La app queda disponible en http://localhost:8000. Ver CLAUDE.md para el resto de comandos comunes (migraciones, tests, superusuario).
