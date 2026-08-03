# ADR-025 - Diseño técnico inicial de la sala de discusión (pilar 4 de ADR-024)

Fecha: 2026-08-03
Estado: **En progreso** (diseño en curso, no una decisión cerrada — a diferencia del resto de las ADR de este repo, que documentan decisiones ya tomadas)

## Contexto

ADR-024 estableció que la sala de discusión (planificador + ejecutor + Fernando), junto con la memoria básica de conversación, es el primer bloque de trabajo de la visión ampliada. Esta ADR baja ese pilar a diseño técnico concreto, en conversación con Fernando (Cowork), verificando cada afirmación técnica contra el código fuente real de `claude-agent-sdk` (tag `v0.2.128`, commit `f8b9ec92`) antes de asumir nada — mismo criterio de todo el proyecto (ver, por ejemplo, ADR-020, ADR-022, la enmienda de ADR-024 sobre recursos del SDK).

Nada de lo que sigue está construido todavía. Se marca explícitamente qué quedó decidido/encaminado (con evidencia verbatim del SDK) vs. qué sigue abierto y sin resolver — no se inventan detalles que no se hayan discutido con Fernando.

## Decisión / dirección encaminada

1. **Puente de permisos**: confirmado que `ClaudeAgentOptions.can_use_tool` es el mecanismo real para reemplazar el prompt de terminal por una UI propia. Verbatim de `types.py` (commit `f8b9ec92`): *"Custom permission handler for tool calls that would otherwise prompt the user... it is the SDK replacement for the interactive permission prompt."* `ToolPermissionContext` trae campos ya pensados para una UI de aprobación — `title` ("Full permission prompt sentence... use this as the primary prompt text"), `display_name` ("Short noun phrase for the tool action... suitable for button labels"), `description` ("Human-readable subtitle for the permission UI") — y `agent_id` ("If running within the context of a sub-agent, the sub-agent's ID") para distinguir de qué agente vino el pedido.

2. **Modelo de sesión para proyectos nativos** (en el propio VPS de IA CENTRAL): una sola sesión del SDK, con el rol planificador como agente principal (conversa con Fernando) y el rol ejecutor como sub-agente definido vía `ClaudeAgentOptions.agents: dict[str, AgentDefinition]`. Verbatim de `types.py`: *"Programmatically define custom subagents invokable via the Agent tool. Keys are agent names, values are agent definitions."* Un solo `can_use_tool` maneja los pedidos de permiso de ambos roles, distinguiéndolos por `agent_id`.

3. **Modelo para proyectos en destino externo** (servidor externo o PC local de Fernando): verificado — buscado explícitamente `ssh`/`remote host` en `types.py` y `__init__.py` — que el SDK **no tiene transporte remoto/SSH nativo**; la única mención de "SSH" en todo `types.py` es sobre permitir que un proceso sandboxeado acceda a un *SSH agent socket* local, no un mecanismo de conexión remota del SDK. El SDK siempre lanza `claude` como subproceso local. Consecuencia directa: cada destino externo necesita su propio agente instalado ahí (Claude Code real + conexión saliente hacia IA CENTRAL) — el proceso no puede correr centralizado en el VPS de IA CENTRAL y tocar archivos de otra máquina. La conexión es **siempre saliente desde el destino hacia IA CENTRAL, nunca al revés** — evita tener que exponer la PC local de Fernando a conexiones entrantes (coherente con lo ya verificado en ADR-024: hoy no hay ningún camino de red del VPS hacia la máquina local).

4. **Modelo de datos**: proyecto = destino registrado (nativo, o externo con su agente) + puede tener varios chats independientes contra ese mismo destino. Candidato de implementación: un `SessionStore` propio respaldado en Postgres, reusando la interfaz que el SDK ya expone (`SessionStore`, `InMemorySessionStore` de referencia, `list_sessions`/`fork_session`/`tag_session`/etc. — ver enmienda de ADR-024 sobre recursos del SDK) en vez de diseñar el modelo de conversación desde cero.

5. **Cómo se conecta un proyecto nuevo**: no se automatiza la creación de la cuenta de Claude ni la creación del servidor — eso lo sigue haciendo Fernando manualmente, fuera de IA CENTRAL, como siempre. Lo que sí se automatiza: una herramienta/pantalla en el panel ("conectar proyecto nuevo") donde Fernando completa las credenciales necesarias (clave SSH, host, clave de API, etc.) y la herramienta arma la conexión — instala el agente remoto si hace falta, registra el proyecto — sin pasos manuales de terminal de por medio.

## Alternativas descartadas

- **Centralizar la ejecución en el VPS de IA CENTRAL y acceder a proyectos externos por SSH/API directo, sin agente propio en cada destino**: descartado — el SDK no tiene transporte remoto nativo (verificado, punto 3), y un mecanismo de acceso remoto genérico construido a mano reabriría exactamente el tipo de superficie de riesgo que ADR-015/ADR-022 evitaron con cuidado para el orquestador local.
- **Conexión entrante hacia la PC local de Fernando (VPN/túnel con el VPS iniciando la conexión)**: descartado — expondría la PC local a conexiones entrantes; la conexión saliente desde cada destino resuelve lo mismo sin ese riesgo.
- **Automatizar también la creación de cuenta/servidor para un proyecto nuevo**: descartado por ahora — fuera del alcance de lo que Fernando pidió automatizar; sigue siendo un paso manual suyo.

## Consecuencias

- Este documento es una ADR **en progreso**: no cierra el diseño de la sala, deja avanzada la dirección técnica de cinco decisiones concretas y deja explícitamente abiertos los puntos de abajo. Se espera revisarla/completarla en próximas conversaciones antes de empezar a construir.
- El puente de permisos (punto 1) es la pieza técnica crítica que ADR-024 ya había señalado como pendiente — queda con mecanismo confirmado (`can_use_tool` + `ToolPermissionContext`), pero sin implementar.
- El requisito de "agente propio por destino externo" (punto 3) tiene una consecuencia práctica real: conectar un proyecto en un servidor externo o en la PC de Fernando implica instalar y correr un Claude Code real ahí, no solo registrar credenciales — el alcance de "conectar proyecto nuevo" (punto 5) incluye ese paso de instalación remota.

## Abierto, no resuelto

- **Autenticación por proyecto/agente remoto**: ¿cada agente remoto usa la misma suscripción de Fernando (riesgo de cupo compartido, ya advertido en ADR-016) o clave de API propia vía el gateway LiteLLM de ADR-012 (una clave por proyecto, sin ese riesgo)? Ninguna decisión tomada. Candidato a investigar: si Anthropic permite generar claves de API de forma programática desde su Consola — **no verificado todavía, no asumir que sí**.
- Protocolo exacto de conexión saliente del agente remoto hacia IA CENTRAL (websocket, polling, algo del propio SDK) — no diseñado.
- Esquema exacto de base de datos para proyectos/chats/sesiones — no diseñado, solo la idea general (`SessionStore` propio sobre Postgres).
- Pantalla exacta del panel para "conectar proyecto nuevo" — no diseñada.
- Si el modelo de sub-agente (punto 2) sigue siendo válido para proyectos nativos una vez que se sume el motor de permisos configurable (pilar 3 de ADR-024) — no re-evaluado todavía.
