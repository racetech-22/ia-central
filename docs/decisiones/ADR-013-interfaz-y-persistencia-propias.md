# ADR-013 - Capa de interfaz y persistencia propia en Django, diferida a Fase 5

Fecha: 2026-08-01
Estado: Aceptada

## Contexto

Surgió la pregunta de si replicar en el VPS un sistema equivalente a Claude Desktop/claude.ai (chat, proyectos, sesiones, memoria) funcionando junto a Claude Code, y si eso requiere específicamente el Claude Agent SDK.

Clarificación técnica de partida: el Claude Agent SDK es **headless** — una librería sin interfaz alguna. No aporta nada de la capa visual. "Parecerse a Claude Desktop" se descompone en tres capas, y el SDK solo cubre una:

1. **Interfaz web**: chat con streaming, lista de conversaciones, proyectos, archivos, render de resultados. Desarrollo web convencional, sin complejidad de IA.
2. **Persistencia**: conversaciones, mensajes, proyectos, memoria. Tablas de Postgres.
3. **Bucle del agente**: ya resuelto en ADR-012.

Motivación directa, además: durante el 2026-07-31 y 08-01 se perdió una cantidad considerable de tiempo peleando con los mecanismos de sincronización de Knowledge/Files de los productos de Anthropic (ver ADR-011) — comportamiento opaco, sin errores visibles, sin forma de verificar qué se cargó realmente. La misma limitación aplica a la memoria entre conversaciones: no es inspeccionable ni versionable. Construir estas tablas en Postgres propio elimina esa clase entera de problema y convierte "memoria y contexto" en algo que se diseña, se consulta y se respalda.

## Decisión

1. La capa de interfaz y persistencia de IA CENTRAL se construye **de forma nativa en Django/Postgres**, no se delega en productos de Anthropic (claude.ai Projects, Claude Desktop, Cowork). Esos productos se usan como herramienta de desarrollo, nunca como parte de la arquitectura ni como fuente de verdad del estado del sistema.
2. Esa construcción se **difiere a Fase 5**, como ya establece ARQUITECTURA.md §5. Fase 3 se mantiene headless: conectores MCP + orquestador, sin interfaz web propia.
3. Durante Fase 3 y 4, la interfaz de trabajo sigue siendo Claude Code en la sesión tmux `iac` (ver CLAUDE.md), más los logs y marcas de estado ya existentes.

## Alternativas descartadas

- **Construir la interfaz web en Fase 3, en paralelo a los conectores**: descartado por scope creep. Serían semanas de trabajo de frontend que retrasan lo único que hace valioso al sistema en esta fase — que el agente pueda ejecutar acciones reales. Además, el diseño correcto de esa interfaz se conoce mucho mejor después de operar el orquestador un tiempo.
- **Seguir dependiendo de Claude Desktop / claude.ai Projects como interfaz y almacén de contexto**: descartado por ADR-011 (mecanismos de sync no fiables, copias estáticas) y porque contradice el principio de portabilidad de ADR-001 — el estado del sistema viviría en un producto de terceros, no exportable ni versionable.
- **Replicar la funcionalidad completa de Claude Desktop (clon de chat) al llegar Fase 5**: descartado como objetivo. La necesidad real que describe ARQUITECTURA.md §4 es un panel de control (costos, modelos activos, salud de conectores, tareas en curso, cola de verificación de conocimiento), no un segundo cliente de chat — el chat ya está cubierto por Claude Code. Si en Fase 5 aparece una necesidad genuina de interfaz conversacional propia, se decide entonces con evidencia de uso real, no por anticipado.

## Consecuencias

- **Fase 3 no produce nada visible en el navegador.** El progreso se verifica por logs, tests y comportamiento del orquestador. Conviene aceptarlo explícitamente para no confundir "no se ve nada" con "no avanza".
- Cuando llegue Fase 5, el esquema de persistencia (conversaciones, mensajes, memoria, tareas) hay que diseñarlo desde cero. Conviene ir anotando durante Fase 3 y 4 qué entidades aparecen de forma natural, para no diseñarlo a ciegas.
- Mantener el estado del sistema en Postgres propio lo incluye automáticamente en el backup diario de ADR-004 y en la migración de ADR-002 — cosa que no ocurre con nada almacenado dentro de productos de Anthropic.
- Esta ADR no impide seguir usando Cowork/claude.ai como herramienta de trabajo y consulta. Solo establece que no forman parte de la arquitectura del sistema.
