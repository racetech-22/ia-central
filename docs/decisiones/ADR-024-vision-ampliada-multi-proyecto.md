# ADR-024 - Visión ampliada de IA CENTRAL: cinco pilares y orden de prioridad

Fecha: 2026-08-03
Estado: Aceptada

## Contexto

Al planificar el conector MCP/SSH hacia la estación local y otros servidores de Fernando (el siguiente pendiente de Fase 3 según `mcp_servers/README.md`), surgió en conversación con Fernando (Cowork) que la visión real de IA CENTRAL es mucho más amplia que "un conector más" al estilo de `mcp_servers/django_project`: IA CENTRAL como "el Cerebro" que programa, orquesta, administra y configura todos los proyectos futuros de Fernando — en este VPS, en otros servidores, en su máquina local — con autonomía otorgada por Fernando y limitada a sus decisiones.

Verificado en esa conversación: hoy no hay ningún camino de red del VPS hacia la máquina local de Fernando — la conectividad existente es al revés (Fernando se conecta de su PC al VPS, nunca el VPS a su PC). Implementar el conector MCP/SSH hacia la estación local, tal como estaba esbozado, requiere resolver esa conectividad (VPN/túnel) antes que nada — decisión aparte, no resuelta hoy, y programarlo ahora bajo el alcance acotado original habría significado rehacerlo pronto bajo el modelo de confianza que se describe más abajo.

Esta ADR fija la **visión y el orden de prioridad**, no el diseño técnico de cada pieza — eso es trabajo aparte, futuro, para cuando le toque el turno a cada pilar. Nada de lo que sigue está construido todavía; toda afirmación va marcada explícitamente como pendiente, con la fase que corresponda (convención de ADR-014).

## Decisión

Se confirman cinco pilares de la visión ampliada:

1. **Memoria y contexto compartido**: ya esbozado en ARQUITECTURA.md §2 ("Capa de conocimiento", RAG vectorial sobre pgvector) — se confirma como pilar central, no un detalle. Los dos roles del punto 4 deben compartir el mismo contexto de cada proyecto, no operar con memoria aislada cada uno. Tiene dos capas con ritmos distintos: una **memoria básica** (historial de conversación persistido, ADR-013) que arranca **junto con** la sala de discusión del punto 4, no después — una sala sin memoria de conversaciones anteriores reproduce el mismo problema que se busca resolver (pérdida de contexto entre sesiones), solo que dentro de una sola interfaz, y persistir un chat ya requiere ese modelo de datos, es la primera capa de memoria, no una pieza aparte que pueda esperar; y una **memoria profunda** (RAG vectorial, recuperación semántica, ingesta del conocimiento ya estructurado del repo — ADRs/CHANGELOG/ARQUITECTURA.md/CLAUDE.md/DEPENDENCIAS.md vía GitHub) que se sofistica después, creciendo en paralelo sin bloquear nada (ver orden de prioridad más abajo).

2. **Todo lo configurable vive en el panel administrativo, nunca enyesado en archivos de código versionado.** Principio general de diseño de acá en adelante, no solo para permisos: cualquier variable que pueda cambiar según caso/situación/proyecto debe administrarse desde una pestaña del panel (Fase 5, ADR-013), no requerir un commit para cambiarla.

3. **Motor de confianza/permisos por niveles, editable desde el panel** — no un archivo tipo `.claude/settings.json`. Modelo de referencia: el mismo patrón ya en uso hoy en este proyecto en dos lugares distintos (allow/ask/deny de Claude Code en `.claude/settings.json`; catálogo fijo de tools MCP como política de seguridad, ADR-015) — se propone unificarlo en un solo motor, configurable por proyecto/servidor, con niveles de riesgo (ejemplo discutido, no definitivo: autónomo siempre / autónomo reversible / requiere confirmación / nunca automático). Esta ADR solo establece que debe existir y ser panel-configurable — su esquema final es diseño técnico pendiente, separado.

4. **Arquitectura de dos roles conversando en una interfaz persistida dentro de IA CENTRAL**: un rol planificador (conversacional, similar al uso actual de Cowork) y un rol ejecutor, con Fernando como decisor final — los tres en una misma ventana de chat persistida en Django/Postgres (ADR-013). Formaliza dentro de IA CENTRAL el patrón que hoy requiere que Fernando relaye manualmente entre Cowork y la sesión `iac` de Claude Code.

   **Corrección explícita sobre el rol ejecutor** (surgida al preguntar Fernando directamente si la sala permitiría, como mínimo, las mismas capacidades que el método actual — esta misma conversación de Cowork más la sesión `iac` de Claude Code con shell completo — y la respuesta honesta con la redacción original de este punto era que no): el rol ejecutor de la sala **debe ser el mismo Claude Code que ya corre hoy en la sesión `iac`**, reusando su modelo de permisos actual (`allow`/`ask`/`deny` de `.claude/settings.json`) — con la diferencia de que esas aprobaciones aparecen dentro de la ventana de la sala, no en una terminal. **No** es el orquestador angosto de ADR-021/ADR-022/ADR-023 (5 tools fijas, sin shell, deliberadamente mucho menos capaz que Claude Code): usar ese orquestador como único ejecutor de la sala sería un paso atrás en capacidad, no una migración. Ese orquestador angosto sigue existiendo aparte, para lo que sea seguro dejar 100% autónomo (Nivel 1 del futuro motor de permisos del punto 3) — pero no es el único brazo ejecutor de la sala, y no reemplaza a Claude Code.

5. **Orquestación multi-modelo inteligente, incluyendo posible debate entre modelos** para llegar a decisiones óptimas — ya tenía lugar en la hoja de ruta (Fase 4, "Capa multi-IA"), se confirma y no cambia de lugar.

**Orden de prioridad acordado, con justificación**:

1. **Punto 4, en su forma mínima (sala de discusión de a tres, con el puente a Claude Code real corregido arriba) + memoria básica del punto 1 (historial de conversación persistido en Postgres, ADR-013)** — un solo bloque de trabajo, no en secuencia: una sala de discusión sin memoria de conversaciones anteriores reproduce el mismo problema que se busca resolver (pérdida de contexto entre sesiones), solo que dentro de una sola interfaz; persistir un chat ya requiere un modelo de datos para los mensajes, eso es la primera capa de memoria, no algo que tenga sentido dejar para después. Sin esperar al motor de permisos (punto 3): el modelo de permisos actual de Claude Code (`.claude/settings.json`) alcanza para arrancar, reusado tal cual dentro de la sala. El puente real entre la sala y el proceso de Claude Code sigue siendo una pieza técnica nueva, todavía sin diseñar (ver Consecuencias) — el orquestador angosto de ADR-020/ADR-022/ADR-023 ayuda para lo que se pueda dejar autónomo, pero no resuelve ese puente por sí solo.
2. **Punto 3** (motor de permisos) — cuando llegue el momento de ampliar lo que el rol ejecutor puede hacer más allá de las tools/permisos de hoy, no antes: hoy el catálogo fijo ya actúa como límite seguro (ADR-015), no hace falta el motor todavía.
3. **Punto 1, memoria PROFUNDA** (RAG vectorial, recuperación semántica, ingesta del conocimiento ya estructurado del repo) — creciendo en paralelo desde que arranca el bloque 1º, sofisticándose con el tiempo, sin bloquear nada. No confundir con la memoria básica del bloque 1º, que no espera a este punto.
4. **Punto 2** (panel completo) — naciendo pantalla por pantalla a medida que cada pieza de atrás lo necesite, no construir el panel entero de antemano.
5. **Punto 5** (multi-modelo con debate) — al final, deliberadamente: es la pieza más compleja de las cinco.

## Alternativas descartadas

- **Implementar el conector MCP/SSH original (hacia estación local y otros servidores) tal como estaba esbozado en `mcp_servers/README.md`, de forma acotada y de solo lectura**: descartado como próximo paso — la visión real de Fernando excede largamente ese alcance, y programar esa pieza ahora habría significado tener que rehacerla pronto bajo el modelo de confianza nuevo (punto 3).
- **Diseñar el motor de permisos configurable antes que la sala de discusión**: descartado — no es necesario todavía, porque el catálogo fijo de tools de hoy ya es un límite de seguridad suficiente para la sala de discusión en su forma mínima.
- **Empezar por la orquestación multi-modelo con debate**: descartado por complejidad — es la pieza más difícil de las cinco, se prioriza al final.

## Consecuencias

- El diseño técnico detallado de cada uno de los cinco pilares (esquema del motor de permisos, modelo de datos de la memoria compartida, estructura exacta de la sala de discusión, pantallas del panel, protocolo de debate multi-modelo) es **trabajo futuro y separado** — esta ADR fija la visión y el orden, no la implementación. Cada pilar, al tocarle el turno, amerita su propia ADR de diseño.
- El conector MCP/SSH hacia la estación local y otros servidores de Fernando (mencionado en `mcp_servers/README.md` como "todavía no implementado") queda explícitamente en suspenso, no descartado — su diseño depende de resolver primero la conectividad VPN/túnel (no resuelta hoy) y de encajar en el modelo de confianza del punto 3, en vez de construirse de forma acotada por separado.
- La sala de discusión de a tres (punto 4, forma mínima) puede arrancar en Fase 3 con parte de la infraestructura ya construida (orquestador angosto para lo autónomo, tools de `mcp_servers/django_project`) — su forma final, persistida en Django/Postgres dentro del panel, depende de la capa de interfaz/persistencia de Fase 5 (ADR-013).
- **El puente real entre la sala y el proceso de Claude Code es la pieza técnica crítica pendiente de diseño del primer bloque de trabajo (sala + memoria), no un detalle menor.** Necesita invocar programáticamente al mismo Claude Code de la sesión `iac` (no una instancia aparte ni el orquestador angosto) y traer sus prompts de aprobación (`allow`/`ask`/`deny` de `.claude/settings.json`) a la interfaz de chat de la sala, en vez de a una terminal tmux. No se diseña a fondo en esta ADR — queda anotado como el trabajo técnico central a resolver antes de que la sala en su forma mínima sea real, no una decisión ya tomada.
- ARQUITECTURA.md se actualiza en el mismo commit (§1, §2, §5, §6) para reflejar esta decisión — ver CHANGELOG.md.

## Enmienda 2026-08-03: recursos del `claude-agent-sdk` relevantes para los cinco pilares

Investigación (Cowork), verificada contra el código fuente real del SDK (`anthropics/claude-agent-sdk-python`, tag `v0.2.128`, commit `f8b9ec92`, `src/claude_agent_sdk/__init__.py` y `types.py` — cada símbolo listado abajo se confirmó presente en el `__all__` real de ese commit, no asumido). **Esto no es una decisión de diseño todavía — es catálogo de recursos disponibles, para cuando le toque el turno de diseño en detalle a cada pilar (ver Consecuencias de esta ADR: cada pilar amerita su propia ADR).** No se implementa nada de esto ahora.

Organizado por pilar, con los símbolos exportados relevantes (nombres exactos, para ubicarlos fácil en la fuente cuando corresponda):

- **Pilar 1 (memoria)**: el SDK ya trae gestión de sesiones — `list_sessions`, `get_session_info`, `get_session_messages`, `fork_session`, `rename_session`, `tag_session`, `delete_session`, y una interfaz `SessionStore` (con `InMemorySessionStore` de referencia) más `import_session_to_store`. Candidato: implementar un `SessionStore` propio respaldado en Postgres en vez de diseñar persistencia de conversación desde cero.

- **Pilar 4 (sala, roles planificador/ejecutor)**: soporte nativo de sub-agentes — `AgentDefinition`, `agent_id` en `ToolPermissionContext` (confirmado en `types.py`: `agent_id: str | None = None`, "If running within the context of a sub-agent, the sub-agent's ID"), `list_subagents`, `get_subagent_messages`, hooks `SubagentStartHookInput`/`SubagentStopHookInput`. Candidato a evaluar antes de diseñar el puente (ver Consecuencias más arriba): si planificador y ejecutor pueden modelarse como dos sub-agentes dentro de una misma sesión del SDK, en vez de dos procesos separados puenteados a mano.

- **Pilar 3 (motor de permisos)**: además de `CanUseTool` (ya confirmado antes de esta enmienda, ver ADR-021), el SDK expone un sistema de hooks más amplio — `PreToolUseHookInput`, `PostToolUseHookInput`, `PostToolUseFailureHookInput`, `UserPromptSubmitHookInput`, `StopHookInput`, `PreCompactHookInput`, `NotificationHookInput`. El hook de `Notification` es candidato directo a integrarse con el `ntfy` ya montado (ADR-018).

- **Pilar 5 (multi-modelo, elección por costo/necesidad)**: soporte de esfuerzo de razonamiento adaptativo (`ThinkingConfig`, `EffortLevel`, `ThinkingConfigAdaptive`/`ThinkingConfigEnabled`/`ThinkingConfigDisabled`) y tracking nativo de uso/costo (`TaskBudget`, `TaskUsage`, `ModelUsage`, `RateLimitEvent`, `RateLimitInfo`, `RateLimitStatus`). No haría falta instrumentar medición de costo/uso a mano — el SDK ya lo expone.

- **Pilar 2 (panel/dashboard)**: mensajes de progreso de tareas ya estructurados (`TaskStartedMessage`, `TaskProgressMessage`, `TaskUpdatedMessage`, `TaskNotificationMessage`) y uso de contexto (`ContextUsageResponse`) — datos listos para alimentar pantallas del panel sin instrumentación propia.

- **Bonus, fuera de los cinco pilares pero relevante para tools futuras**: `create_sdk_mcp_server`/`tool` (decorador) permite tools MCP en el mismo proceso de Python (sin subproceso stdio, acceso directo al estado de la app) — más simple que el patrón de subproceso stdio usado en ADR-020 para `mcp_servers/django_project`. Candidato a reconsiderar en la próxima tanda de tools nuevas, no una corrección a lo ya construido.

- **Bonus, relacionado con el gap de ADR-006**: el SDK tiene soporte de sandbox (`SandboxSettings`, `SandboxNetworkConfig`, `SandboxIgnoreViolations`) — condicionado a que el VPS tenga `bwrap` instalado (confirmado en ADR-006 que hoy no lo tiene). Anotar como candidato a revisar si algún día se instala `bwrap`.

Ninguno de estos hallazgos es una decisión tomada — son recursos identificados para cuando se diseñe cada pilar en detalle, con su propia ADR, como ya estableció esta ADR más arriba.
