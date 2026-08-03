# ADR-024 - Visión ampliada de IA CENTRAL: cinco pilares y orden de prioridad

Fecha: 2026-08-03
Estado: Aceptada

## Contexto

Al planificar el conector MCP/SSH hacia la estación local y otros servidores de Fernando (el siguiente pendiente de Fase 3 según `mcp_servers/README.md`), surgió en conversación con Fernando (Cowork) que la visión real de IA CENTRAL es mucho más amplia que "un conector más" al estilo de `mcp_servers/django_project`: IA CENTRAL como "el Cerebro" que programa, orquesta, administra y configura todos los proyectos futuros de Fernando — en este VPS, en otros servidores, en su máquina local — con autonomía otorgada por Fernando y limitada a sus decisiones.

Verificado en esa conversación: hoy no hay ningún camino de red del VPS hacia la máquina local de Fernando — la conectividad existente es al revés (Fernando se conecta de su PC al VPS, nunca el VPS a su PC). Implementar el conector MCP/SSH hacia la estación local, tal como estaba esbozado, requiere resolver esa conectividad (VPN/túnel) antes que nada — decisión aparte, no resuelta hoy, y programarlo ahora bajo el alcance acotado original habría significado rehacerlo pronto bajo el modelo de confianza que se describe más abajo.

Esta ADR fija la **visión y el orden de prioridad**, no el diseño técnico de cada pieza — eso es trabajo aparte, futuro, para cuando le toque el turno a cada pilar. Nada de lo que sigue está construido todavía; toda afirmación va marcada explícitamente como pendiente, con la fase que corresponda (convención de ADR-014).

## Decisión

Se confirman cinco pilares de la visión ampliada:

1. **Memoria y contexto compartido**: ya esbozado en ARQUITECTURA.md §2 ("Capa de conocimiento", RAG vectorial sobre pgvector) — se confirma como pilar central, no un detalle. Los dos roles del punto 4 deben compartir el mismo contexto de cada proyecto, no operar con memoria aislada cada uno.

2. **Todo lo configurable vive en el panel administrativo, nunca enyesado en archivos de código versionado.** Principio general de diseño de acá en adelante, no solo para permisos: cualquier variable que pueda cambiar según caso/situación/proyecto debe administrarse desde una pestaña del panel (Fase 5, ADR-013), no requerir un commit para cambiarla.

3. **Motor de confianza/permisos por niveles, editable desde el panel** — no un archivo tipo `.claude/settings.json`. Modelo de referencia: el mismo patrón ya en uso hoy en este proyecto en dos lugares distintos (allow/ask/deny de Claude Code en `.claude/settings.json`; catálogo fijo de tools MCP como política de seguridad, ADR-015) — se propone unificarlo en un solo motor, configurable por proyecto/servidor, con niveles de riesgo (ejemplo discutido, no definitivo: autónomo siempre / autónomo reversible / requiere confirmación / nunca automático). Esta ADR solo establece que debe existir y ser panel-configurable — su esquema final es diseño técnico pendiente, separado.

4. **Arquitectura de dos roles conversando en una interfaz persistida dentro de IA CENTRAL**: un rol planificador (conversacional, similar al uso actual de Cowork) y un rol ejecutor (con tools reales, equivalente a Claude Code/el orquestador de ADR-021), con Fernando como decisor final — los tres en una misma ventana de chat persistida en Django/Postgres (ADR-013). Formaliza dentro de IA CENTRAL el patrón que hoy requiere que Fernando relaye manualmente entre Cowork y la sesión `iac` de Claude Code.

5. **Orquestación multi-modelo inteligente, incluyendo posible debate entre modelos** para llegar a decisiones óptimas — ya tenía lugar en la hoja de ruta (Fase 4, "Capa multi-IA"), se confirma y no cambia de lugar.

**Orden de prioridad acordado, con justificación**:

1. **Punto 4, en su forma mínima** (sala de discusión de a tres) — usando el orquestador y las tools ya existentes hoy (ADR-020, ADR-022, ADR-023), sin esperar al motor de permisos (punto 3) ni ampliar el catálogo de tools. Es la única de las cinco piezas que ya tiene casi toda su base construida.
2. **Punto 3** (motor de permisos) — cuando llegue el momento de ampliar lo que el rol ejecutor puede hacer más allá de las tools de hoy, no antes: hoy el catálogo fijo ya actúa como límite seguro (ADR-015), no hace falta el motor todavía.
3. **Punto 1** (memoria profunda/RAG) — creciendo en paralelo, arrancando simple (historial de conversación en Postgres, ya casi gratis una vez que exista la persistencia de ADR-013).
4. **Punto 2** (panel completo) — naciendo pantalla por pantalla a medida que cada pieza de atrás lo necesite, no construir el panel entero de antemano.
5. **Punto 5** (multi-modelo con debate) — al final, deliberadamente: es la pieza más compleja de las cinco.

## Alternativas descartadas

- **Implementar el conector MCP/SSH original (hacia estación local y otros servidores) tal como estaba esbozado en `mcp_servers/README.md`, de forma acotada y de solo lectura**: descartado como próximo paso — la visión real de Fernando excede largamente ese alcance, y programar esa pieza ahora habría significado tener que rehacerla pronto bajo el modelo de confianza nuevo (punto 3).
- **Diseñar el motor de permisos configurable antes que la sala de discusión**: descartado — no es necesario todavía, porque el catálogo fijo de tools de hoy ya es un límite de seguridad suficiente para la sala de discusión en su forma mínima.
- **Empezar por la orquestación multi-modelo con debate**: descartado por complejidad — es la pieza más difícil de las cinco, se prioriza al final.

## Consecuencias

- El diseño técnico detallado de cada uno de los cinco pilares (esquema del motor de permisos, modelo de datos de la memoria compartida, estructura exacta de la sala de discusión, pantallas del panel, protocolo de debate multi-modelo) es **trabajo futuro y separado** — esta ADR fija la visión y el orden, no la implementación. Cada pilar, al tocarle el turno, amerita su propia ADR de diseño.
- El conector MCP/SSH hacia la estación local y otros servidores de Fernando (mencionado en `mcp_servers/README.md` como "todavía no implementado") queda explícitamente en suspenso, no descartado — su diseño depende de resolver primero la conectividad VPN/túnel (no resuelta hoy) y de encajar en el modelo de confianza del punto 3, en vez de construirse de forma acotada por separado.
- La sala de discusión de a tres (punto 4, forma mínima) puede arrancar en Fase 3 con la infraestructura ya construida (orquestador, tools de `mcp_servers/django_project`) — su forma final, persistida en Django/Postgres dentro del panel, depende de la capa de interfaz/persistencia de Fase 5 (ADR-013).
- ARQUITECTURA.md se actualiza en el mismo commit (§1, §2, §5, §6) para reflejar esta decisión — ver CHANGELOG.md.
