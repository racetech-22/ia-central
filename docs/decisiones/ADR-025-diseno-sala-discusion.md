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

6. **Autenticación por proyecto — resuelto: Workspaces de Anthropic, uno por proyecto.** Verificado contra la documentación oficial vigente: "Organize API keys, manage team access, and control costs with workspaces" y explícitamente "Project-based organization: Create workspaces for specific projects or products to track usage and costs separately." Cada workspace tiene su propia clave de API (encerrada a los recursos de ese workspace), su propio límite de gasto mensual, su propio límite de tasa, y métricas de uso/costo consultables por separado vía `workspace_id`.

   Flujo acordado: Fernando crea el workspace y la clave de API a mano en la Consola de Anthropic (Settings > Workspaces > Create workspace, con su límite de gasto) — nada de esto se automatiza. Esa clave es la que se pega en la herramienta de "conectar proyecto nuevo" de la sala (ver punto 5 de las decisiones encaminadas). El orquestador de IA CENTRAL en el propio VPS sigue con autenticación por suscripción por ahora (ADR-016) — no se fuerza la migración de lo ya construido, esto aplica a los proyectos nuevos que se sumen desde la sala.

   Esto también resuelve, de paso, el aislamiento de cupo que ADR-016 ya había advertido como riesgo: cada proyecto nuevo queda con su propio límite de gasto, sin competir por la suscripción personal de Fernando ni por el cupo de otros proyectos. Y da, sin trabajo adicional, la base para la visibilidad de costos por proyecto de la visión original de IA CENTRAL (README.md): la API de Uso y Costo de Anthropic ya permite filtrar por `workspace_id`.

7. **Esquema de datos mínimo, cuatro piezas**: **Proyecto** (nombre, tipo de destino — nativo / externo-servidor / externo-PC-local —, workspace de Anthropic asociado, ver punto 6, campo de credencial de conexión cifrado, ver punto 8, estado); identificador: el `project_key` del SDK, confirmado en `SessionKey` (`types.py`, tag `v0.2.128`): *"Caller-defined scope. Default: sanitized cwd. Multi-tenant deployments should set this to a tenant ID or project name."* **Chat** (FK a Proyecto, puede haber varios por proyecto, según lo pedido por Fernando); identificador: el `session_id` del SDK. **Tabla espejo del `SessionStore`** (memoria básica real, no un esquema de "Mensaje" inventado): implementa el `Protocol` real del SDK — `project_key`, `session_id`, `subpath` (vacío para el planificador, con valor tipo `subagents/agent-{id}` para el ejecutor sub-agente, mismo formato confirmado en `SessionKey`), `uuid`, el blob JSON de la entrada (`SessionStoreEntry` — verbatim: *"a minimal structural supertype — adapters should treat entries as pass-through blobs"*, no interpretarlas), `mtime`. Los dos únicos métodos obligatorios del `Protocol` (el resto son opcionales, probados en runtime por presencia, nunca por `isinstance`) son `append(key, entries)` y `load(key)`. **SolicitudPermiso** (la tabla del puente `can_use_tool` del punto 1, no viene del SDK): FK a Chat, `tool_name`, `tool_input` (JSON), `title`/`display_name`/`description` (de `ToolPermissionContext`), `agent_id`, estado (pendiente/aprobado/denegado), quién decidió, cuándo.

8. **Cifrado de credenciales de proyecto**: motivo — `scripts/backup_postgres.sh` (ADR-004) hace dump diario de toda la base, sincronizado a Google Drive vía `rclone` (ADR-005); credenciales de proyecto en texto plano en Postgres significarían claves SSH/API sin cifrar en cada backup diario en Drive. Decisión: no usar un wrapper de Django de terceros para campos cifrados — verificados en PyPI tres candidatos (`django-cryptography-django5`, última versión `2.2` de junio 2024, sin actualizar desde entonces; `django-fernet-fields-v2`, última `0.9` de agosto 2023; `django-encrypted-model-fields`, última `0.6.5` de febrero 2022) y los tres están abandonados o casi. En su lugar: un campo cifrado propio (subclase de `TextField`, implementación chica) sobre `cryptography==50.0.0` (pin exacto — librería base de PyCA, confirmada activamente mantenida, versión más reciente en PyPI, subida días antes de esta decisión), con una clave de cifrado nueva y separada de `DJANGO_SECRET_KEY` (`CREDENTIALS_ENCRYPTION_KEY` en `.env`). Límite explícito: protege contra exposición de backups/dumps de la base, no contra acceso SSH completo al VPS — mismo límite de confianza ya aceptado en ADR-006.

9. **Protocolo de conexión saliente — resuelto**

   Pendiente (Fase 3): nada de este protocolo está implementado. Lo que sigue fija el diseño, no describe código existente.

   **9.0 Alternativa evaluada y descartada: Managed Agents self-hosted**

   Antes de diseñar nada propio se evaluó adoptar self-hosted sandboxes de Claude Managed Agents (beta `managed-agents-2026-04-01`), que resuelve exactamente este problema y está operado por Anthropic: el entorno `self_hosted` actúa como cola de trabajo (*"acts as a work queue"*), un worker en la máquina destino reclama trabajo por polling y necesita *"only outbound HTTPS"*. Trae además credencial propia acotada a la cola (`ANTHROPIC_ENVIRONMENT_KEY`, distinta de la clave de organización), `reclaim_older_than_ms` para re-reclamar trabajo de un worker caído, `workers_polling` como señal de vida, y `work.stop` con `force` para parada limpia vs. interrupción.

   Se verificó explícitamente — en vez de asumirlo — que sí soporta aprobación humana en vivo: la política `always_ask` hace que *"the session pauses and waits for your approval"*, emite `session.status_idle` con `stop_reason: requires_action`, y la aplicación responde con un evento `user.tool_confirmation` (allow/deny, con `deny_message`).

   Se descarta igual, por tres razones ancladas en decisiones ya cerradas de este repo:

   1. El ejecutor dejaría de ser Claude Code con `.claude/settings.json` — que es exactamente la corrección que ADR-024 incorporó antes del merge. Managed Agents corre `agent_toolset_20260401` (bash, read, write, edit, glob, grep) con solo dos niveles de permiso (`always_allow` / `always_ask`) y override por tool, sin matching por patrón de argumento. Hoy `Bash(docker compose *)` corre sin preguntar y `Bash(git push *)` pregunta; eso no es expresable ahí — o bash entero pregunta siempre, o nunca. Además quedaría afuera el hook `PreToolUse` de ADR-007.
   2. Persistencia del lado de Anthropic (*"Event history is persisted server-side"*), en colisión directa con ADR-013 (conversaciones y memoria nativas en Django/Postgres) y con la capa reemplazable de ADR-012 — Managed Agents está mucho más acoplado que el SDK, sin equivalente al swap de LiteLLM. Se suma que *"Memory is not currently supported with self-hosted sandboxes"*.
   3. Es beta, con *"behaviors may be refined between releases"*, para la pieza central del pilar 1.

   No queda descartado para siempre: es buen candidato para trabajo 100% autónomo (Nivel 1 del futuro motor de permisos) y para *scheduled deployments*, donde no hay `.claude/settings.json` que preservar ni aprobación interactiva que perder.

   También se descartó MCP tunnels: resuelve el problema inverso (que Anthropic alcance servidores MCP dentro de una red privada), es research preview provisto *"as-is"* sin compromiso de continuidad, y depende de Cloudflare como tercero.

   De la evaluación sí se adoptan las semánticas del protocolo de Anthropic (cola durable, lease con reclaim, vida por heartbeat reciente, `stop` distinto de interrupción), reimplementadas acá.

   **9.1 Estructura en tres capas**

   El protocolo se define en tres capas explícitamente separadas, para que el transporte sea reemplazable sin tocar la semántica:

   - **Capa 1 — Transporte**: WebSocket sobre TLS (primario) o long-polling HTTP (degradado, para destinos detrás de proxies que rompen WebSocket). Única obligación: entregar tramas en orden en ambos sentidos y avisar la desconexión. Ningún componente de capa 2 o 3 puede asumir cuál está en uso.
   - **Capa 2 — Sesión**: tramas, correlación por identificador, heartbeat, reanudación.
   - **Capa 3 — Semántica de agente**: traducción de tramas a llamadas de `ClaudeSDKClient` y al `can_use_tool` del punto 1 de esta ADR.

   Definir la capa 2 sin atarla a WebSocket desde el arranque cuesta poco; retrofitear el transporte degradado después sería caro. El long-polling queda como plan B, no como arquitectura.

   **9.2 Superficie de fiabilidad reducida a dos tramas**

   Decisión de diseño central: no todo viaja por el socket.

   - Lo durable (entradas del `SessionStore` del punto 7, resultados finales) viaja por POST HTTP idempotente con reintento, fuera del socket. Consecuencia: una caída de la conexión no puede perder historial, solo pausa la interacción.
   - Lo cosmético (streaming de texto parcial para pintar la sala en vivo) viaja por el socket sin garantía de entrega: si se pierde, la historia real se reconstruye desde las entradas del `SessionStore`.
   - Solo dos tipos de trama exigen entrega confiable: `prompt` (bajada) y `permission_request` (subida). Todo el trabajo de reanudación se concentra ahí.

   **9.3 Tramas**

   Envoltorio común (JSON, un objeto por trama): `v` (versión de protocolo, entero), `type`, `frame_id` (UUID), `chat_id`, `ts`.

   Subida (destino → IA CENTRAL): `hello` (autenticación, versión del agente, `project_key`, `session_epoch`, último `frame_id` de bajada recibido), `heartbeat`, `stream`, `permission_request`, `turn_done`, `error`.

   Bajada (IA CENTRAL → destino): `hello_ack` (`session_epoch` aceptado, desde dónde reanudar), `prompt`, `permission_response`, `interrupt`, `stop` (`graceful` | `force`).

   `permission_request` transporta: `request_id`, `tool_name`, `tool_input`, y los campos que `ToolPermissionContext` ya expone para UI (`title`, `display_name`, `description`) más `agent_id`. `permission_response` transporta: `request_id`, `decision` (`allow` | `deny`), `updated_input` opcional, `message` opcional.

   **9.4 Ciclo de vida de una solicitud de permiso**

   Es la parte del protocolo donde se decide si el sistema es confiable o no.

   1. En el destino se dispara `can_use_tool`. Genera `request_id`, emite `permission_request` y queda esperando con timeout.
   2. IA CENTRAL, al recibirla, primero persiste la fila SolicitudPermiso en estado pendiente, y recién después la empuja al navegador de Fernando. El orden importa: persistir antes de notificar es lo que hace que el paso 5 funcione.
   3. Fernando decide. La fila pasa a aprobado/denegado con quién y cuándo, y recién entonces se emite `permission_response`.
   4. El destino resuelve la espera y devuelve el resultado a `can_use_tool`.

   Modos de falla, cada uno con comportamiento definido:

   | Falla | Comportamiento |
   |---|---|
   | Se cae el socket antes de la respuesta | Al reconectar, el destino reenvía las `permission_request` que sigue teniendo pendientes. IA CENTRAL deduplica por `request_id`; si ya se decidió mientras estaba caído, responde de inmediato con la decisión almacenada. |
   | Muere el proceso del destino | La espera muere con él y la sesión de Claude Code también. Al reconectar el agente anuncia un `session_epoch` nuevo; IA CENTRAL marca como caducado todo lo que quedó pendiente del epoch anterior. Fernando ve por qué caducó, no una solicitud zombi. |
   | Fernando nunca responde | Timeout del lado del destino (configurable desde el panel por el principio rector §1.3; por defecto 30 min) que devuelve denegado con mensaje. Nunca auto-aprobar. La fila pasa a caducado. |
   | Llega una respuesta duplicada | Idempotente por `request_id`: la segunda se ignora. |
   | Llega una respuesta con `request_id` desconocido | El destino la descarta y la registra. Puede pasar legítimamente tras un cambio de epoch. |

   Principio explícito: fail-closed. Ninguna combinación de fallas puede terminar en una tool ejecutada sin decisión afirmativa de Fernando. La única salida por defecto es denegar.

   **9.5 Reconexión y vida**

   - Reconexión con backoff exponencial y jitter (1 s, 2 s, 4 s… tope 60 s). El destino siempre reintenta; IA CENTRAL nunca inicia conexión.
   - `heartbeat` cada 20 s desde el destino. IA CENTRAL da la conexión por muerta a los 60 s (tres perdidos). La vida se mide por heartbeat reciente, no por "el socket parece abierto".
   - Cola durable de bajada: si no hay agente conectado, un `prompt` queda encolado en Postgres y espera, no falla. Semántica tomada de Managed Agents.
   - Reanudación de bajada: `hello` informa el último `frame_id` recibido; IA CENTRAL reenvía lo posterior desde un buffer acotado.

   **9.6 Autenticación del canal**

   Dos credenciales, nunca confundidas:

   - **Token de conexión**, emitido por IA CENTRAL al registrar el proyecto (punto 5), acotado a un proyecto, presentado en `hello`. En el destino vive en archivo modo 600; en IA CENTRAL se guarda hasheado (no cifrado reversible: no hace falta volver a mostrarlo, y si se pierde se rota). Rotable desde el panel sin reinstalar el agente.
   - **Credencial de modelo**: la clave de API del Workspace de Anthropic del punto 6, que vive en el destino porque es ahí donde corre Claude Code.

   Sobre la segunda queda un límite explícito, análogo al que ADR-017 aceptó para el credencial de suscripción: la clave del Workspace es entorno de ejecución del proceso, alcanzable por el agente que corre en esa máquina. Se acepta porque el Workspace acota el radio de daño (límite de gasto y de tasa propios, punto 6). Nunca debe colocarse ahí una clave de alcance organizacional — la propia documentación de Anthropic advierte que hacerlo *"exposes an organization-scoped credential to agent tool calls"*.

   Transporte: WSS obligatorio sobre el Nginx + Certbot ya existente (ADR-003). Se rechaza cualquier conexión no TLS.

   **9.7 Cambios de infraestructura que esto implica**

   Pendiente (Fase 3):

   - `web` pasa de WSGI a ASGI (servidor ASGI a elegir y pinear con el criterio conservador de ADR-020).
   - `channels` (`4.3.2` al momento de escribir esto) y `channels_redis`, ambos con pin exacto.
   - Servicio `redis` nuevo en `docker-compose.yml`: imagen pineada, sin `ports:`, solo red interna de Docker — mismo criterio que corrigió la exposición de `db`/`web` (enmienda 2026-08-02 a ADR-003).
   - Nginx: cabeceras `Upgrade`/`Connection` y `proxy_read_timeout` mayor al intervalo de heartbeat.
   - Alta de `channels`, `channels_redis`, el servidor ASGI y `redis` en `docs/DEPENDENCIAS.md` (ADR-019).

   Propiedad que se preserva a propósito: en Redis no vive nada durable, solo ruteo de conexiones vivas. Perderlo entero corta conexiones en curso pero no pierde datos, y no agrega nada al alcance del backup de ADR-004 — el contrato de portabilidad de ADR-002 queda intacto.

   Nota: `channels` no exige canal compartido (*"Channel layers are an entirely optional part of Channels"*). Redis hace falta por este diseño, porque la solicitud de permiso entra por el consumer del agente remoto y tiene que salir por el consumer del navegador de Fernando. Se descarta `InMemoryChannelLayer` porque su propia documentación dice *"Do Not Use In Production"*, y `channels_redis` es *"the only official Django-maintained channel layer supported for production use"* — el mismo criterio de mantenimiento que descartó los wrappers de campos cifrados en el punto 8.

   **9.8 Qué NO hace este protocolo**

   - No transporta archivos ni entregables.
   - No instala el agente en el destino: eso es alcance del punto 5 ("conectar proyecto nuevo").
   - No reemplaza el modelo de permisos de Claude Code; lo transporta.

   **9.9 Riesgo residual aceptado**

   Un destino comprometido puede mentirle a IA CENTRAL sobre qué tool va a ejecutar, porque es el propio destino quien arma la `permission_request`. No hay mitigación real dentro de este protocolo: el modelo de confianza es que la máquina destino es de Fernando. Se documenta como límite conocido, con el mismo criterio con que ADR-006 documentó el suyo, en vez de dejarlo implícito.

   Segundo riesgo, operativo: migrar `web` a ASGI es el cambio más grande sobre ese servicio desde su creación. Pendiente (Fase 3): verificar explícitamente después de la migración que el admin de Django y `https://aicentral.network/admin/login/` siguen respondiendo como antes, con el mismo criterio de verificación end-to-end de ADR-021/022/023.

## Alternativas descartadas

- **Centralizar la ejecución en el VPS de IA CENTRAL y acceder a proyectos externos por SSH/API directo, sin agente propio en cada destino**: descartado — el SDK no tiene transporte remoto nativo (verificado, punto 3), y un mecanismo de acceso remoto genérico construido a mano reabriría exactamente el tipo de superficie de riesgo que ADR-015/ADR-022 evitaron con cuidado para el orquestador local.
- **Conexión entrante hacia la PC local de Fernando (VPN/túnel con el VPS iniciando la conexión)**: descartado — expondría la PC local a conexiones entrantes; la conexión saliente desde cada destino resuelve lo mismo sin ese riesgo.
- **Automatizar también la creación de cuenta/servidor para un proyecto nuevo**: descartado por ahora — fuera del alcance de lo que Fernando pidió automatizar; sigue siendo un paso manual suyo.
- **Managed Agents como transporte con Claude Code como ejecutado** (usar `work.poller()` para reclamar trabajo y lanzar Claude Code local en vez de correr las tools in-process): descartado. La sesión de Managed Agents es el bucle de agente de Anthropic; anidar Claude Code adentro deja dos bucles, sigue persistiendo y facturando la orquestación externa que se está puenteando, y —determinante— las aprobaciones granulares del Claude Code interno siguen sin ruta hacia la sala: lo que llegaría a la ventana sería una sola aprobación de "ejecutar Claude Code", no `git push` vs. `docker compose`.
- **Segmentar por nivel de confianza** (Managed Agents para lo autónomo, protocolo propio para lo interactivo): descartado por ahora. El único trabajo autónomo existente es el orquestador angosto, que corre sobre el VPS de IA CENTRAL — proyecto nativo, sin problema de transporte remoto que resolver. Serían dos protocolos, dos modelos de credencial y dos juegos de fallas para usar uno. Revisable cuando exista trabajo autónomo real en un destino externo.

Observación que conviene dejar asentada: el diseño ya era híbrido antes de esta enmienda — el punto 2 (nativo, sesión única del SDK con sub-agente, sin transporte remoto) y el punto 3 (externo, agente propio con conexión saliente) son dos modos conviviendo. Lo que esta enmienda resuelve es que el modo externo no se parte en dos más, pero sí es multi-transporte (§9.1).

## Consecuencias

- Este documento es una ADR **en progreso**: no cierra el diseño de la sala, deja avanzada la dirección técnica de cinco decisiones concretas y deja explícitamente abiertos los puntos de abajo. Se espera revisarla/completarla en próximas conversaciones antes de empezar a construir.
- El puente de permisos (punto 1) es la pieza técnica crítica que ADR-024 ya había señalado como pendiente — queda con mecanismo confirmado (`can_use_tool` + `ToolPermissionContext`), pero sin implementar.
- El requisito de "agente propio por destino externo" (punto 3) tiene una consecuencia práctica real: conectar un proyecto en un servidor externo o en la PC de Fernando implica instalar y correr un Claude Code real ahí, no solo registrar credenciales — el alcance de "conectar proyecto nuevo" (punto 5) incluye ese paso de instalación remota.

## Abierto, no resuelto

- Pantalla exacta del panel para "conectar proyecto nuevo" — no diseñada.
- Si el modelo de sub-agente (punto 2) sigue siendo válido para proyectos nativos una vez que exista el motor de permisos configurable (pilar 3 de ADR-024) — no re-evaluado.
