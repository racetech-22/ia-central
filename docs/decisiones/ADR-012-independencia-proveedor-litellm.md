# ADR-012 - Independencia de proveedor: LiteLLM como gateway y el framework de agente como capa reemplazable

Fecha: 2026-08-01
Estado: Aceptada

## Contexto

ARQUITECTURA.md §2 ya preveía un router de modelos (LiteLLM u OpenRouter) para no acoplar el core a un proveedor específico. Fase 3 arranca usando el Claude Agent SDK como motor de orquestación, lo que obliga a responder si eso introduce una dependencia dura de Anthropic.

Conviene distinguir dos requisitos que hasta ahora se confundían: ADR-001 define portabilidad como **portabilidad de servidor** (mover todo a otro VPS sin perder conocimiento). La **portabilidad de proveedor** es un requisito distinto, no cubierto por ninguna ADR previa.

Del análisis resulta que el acoplamiento real es superficial y está concentrado en una sola capa. Los MCP servers son protocolo abierto (más de 200 implementaciones públicas) y funcionan con cualquier cliente compatible; la capa de conocimiento (pgvector, ADRs versionados en Git) es neutra por completo; la documentación también. Lo único acoplado es el bucle de orquestación, que es además la pieza más delgada y reescribible del sistema.

Verificado en la documentación oficial de LiteLLM: el Claude Agent SDK puede apuntarse a un proxy LiteLLM mediante la variable `ANTHROPIC_BASE_URL`, lo que permite enrutar a cualquier modelo del config (Claude, OpenAI, modelos locales vía Ollama) sin cambiar el motor de orquestación.

## Decisión

1. **LiteLLM autohospedado se monta como gateway de modelos desde el inicio de Fase 3**, aunque al principio el 100% del tráfico vaya a Claude. El objetivo es que cambiar de proveedor sea un cambio de configuración, no una reescritura.
2. **El Claude Agent SDK se usa como motor del bucle de orquestación**, pero estrictamente como dependencia de librería (corre dentro del contenedor, no es un servicio externo) y detrás del gateway de LiteLLM.
3. **El framework de agente queda marcado explícitamente como capa reemplazable.** El resto del sistema (Django, MCP servers) llama a una interfaz interna propia (`orchestrator.run(...)`), nunca al SDK directamente. Sustituir el framework debe implicar reescribir un módulo, no el sistema.

## Alternativas descartadas

- **Stack 100% open source desde el arranque** (LangGraph o Pydantic AI + LiteLLM): plenamente viable y sin acoplamiento alguno, pero hoy implica más plumbing y menor fiabilidad en corridas agénticas largas que el SDK nativo. Se descarta para Fase 3, no de forma permanente — la frontera del punto 3 existe precisamente para poder revisar esto sin costo prohibitivo.
- **OpenRouter como router en vez de LiteLLM**: servicio hospedado de terceros, no open source, con comisión por uso. LiteLLM autohospedado cubre el mismo caso gratis y sin agregar dependencia externa. Descartado también por la política de priorizar herramientas libres/open source.
- **Escribir el bucle de agente desde cero para Fase 3**: la versión funcional son unos cientos de líneas, pero la calidad de producción (compactación de contexto, recuperación de errores de tools, fiabilidad en corridas largas, interrupción y reanudación) es donde se va el esfuerzo real. No aporta a los objetivos de Fase 3.
- **Apoyar la independencia en modelos locales**: el VPS actual (6 vCPU, 12GB RAM, sin GPU) solo corre modelos de ~7-8B cuantizados y lentos. Sirve para clasificación, embeddings o resúmenes; es inviable para codificación agéntica. La independencia real de este proyecto pasa por poder cambiar de API, no por autohospedar inferencia en este hardware.

## Consecuencias

- Implementado (2026-08-01): `docker-compose.yml` agrega el servicio `litellm` (imagen `ghcr.io/berriai/litellm:v1.83.14-stable`, pineada — no `latest`, ver ADR-002; `restart: always`; sin `ports:` publicados, solo alcanzable por la red interna de Docker), con `litellm/config.yaml` versionado (un modelo, `claude-sonnet-5`, clave por variable de entorno) y healthcheck contra `/health/liveliness`. Una pieza más que mantener y una configuración más que versionar (mapa de modelos, claves por proveedor).
- Las claves de API de todos los proveedores quedan centralizadas en la config de LiteLLM. Simplifica la rotación, pero concentra secretos en un punto — aplica lo aprendido en ADR-006: la protección real hoy es el acceso SSH restringido al VPS, no la configuración.
- **La frontera `orchestrator.run(...)` hay que sostenerla con disciplina.** Si el código de Django o los MCP servers empiezan a llamar al SDK directamente, esta decisión queda vacía sin que nadie lo note. Conviene verificarlo explícitamente en cualquier auditoría de código futura.
- Usar modelos locales vía Ollama sigue siendo posible a través de LiteLLM para tareas baratas, pero requeriría hardware adicional para el bucle principal.
- Esta ADR no decide qué modelo usar por defecto en el orquestador, solo cómo se enruta. Esa elección corresponde a Fase 4 (capa multi-IA).
