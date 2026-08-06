# Arquitectura de IA CENTRAL

Documento maestro. Se actualiza cada vez que se toma una decisión relevante. Cualquier conversación nueva sobre este proyecto debe partir de este documento.

## 1. Principio rector

Todo lo que se construya debe cumplir tres condiciones simultáneas:

1. Portable: transferible por completo a otro servidor sin perder base de conocimiento ni funcionalidad.
2. Verificable: el conocimiento que el sistema acumula por sí mismo (auto-aprendizaje) solo se considera válido cuando pasa por un proceso explícito de verificación, nunca por defecto.
3. **Configurable desde el panel, nunca enyesado en archivos de código versionado** (ver ADR-024): cualquier variable que pueda cambiar según caso/situación/proyecto debe administrarse desde una pestaña del panel administrativo (Fase 5, ADR-013), no requerir un commit para cambiarla. **Pendiente (Fase 5):** el panel todavía no existe; el principio aplica de acá en adelante a todo lo que se construya, no solo a permisos.

El punto 1 cubre **portabilidad de servidor** (ADR-001: mover todo a otro VPS sin perder conocimiento). **Portabilidad de proveedor** — no quedar acoplado a un único proveedor de modelos — es un requisito distinto, resuelto en ADR-012 (gateway LiteLLM + framework de agente como capa reemplazable detrás de una interfaz interna).

## 2. Arquitectura en tres capas

### Capa de orquestación
El servicio `orchestrator` corre en `docker-compose.yml` (`restart: always`), junto a `web` y `db` — no como servicio systemd ni sesión de tmux, para no salirse del contrato de portabilidad de ADR-002. Ver ADR-015, ADR-021. Implementado con el Claude Agent SDK (`claude-agent-sdk==0.2.89`) como motor del bucle, expuesto al resto del sistema únicamente vía una interfaz interna propia (`orchestrator.run(prompt) -> str`, en `orchestrator/orchestrator.py`) — el SDK es un detalle de implementación reemplazable, nunca se llama directamente desde fuera de esa interfaz (verificado con `mcp_servers/django_project/tests/test_sdk_boundary.py`). Se enrutará a través de un gateway LiteLLM autohospedado, no directo a la API de Anthropic (ver ADR-012) — aunque mientras Fase 3 use autenticación por suscripción en vez de clave de API, el gateway queda montado y sano sin estar en el camino real de esas llamadas. Ver ADR-016. **Todavía sin lógica de negocio ni disparador automático** (cron, scheduler): el proceso principal del contenedor es `sleep infinity`, se invoca a mano vía `docker compose exec orchestrator`. Las tres tools con efectos reales originalmente previstas en ADR-020 (`restart_web`, `run_migrations`, `run_tests`) ya existen — ver ADR-022, ADR-023.

El LLM que corre en el orquestador nunca tiene shell arbitrario: `ClaudeAgentOptions(tools=[])` deshabilita todas las tools built-in de Claude Code (Bash, Read, Write, Edit, Glob, Grep, WebFetch, WebSearch, etc.) y `disallowed_tools` saca además cuatro tools de plataforma/cuenta que `tools=[]` no toca (`DesignSync`, `Monitor`, `PushNotification`, `RemoteTrigger` — ver enmienda 2026-08-03 a ADR-021, lista no garantizada exhaustiva a futuro). La única capacidad real son las cinco tools MCP de `mcp_servers/django_project` (`git_status`, `read_file` de ADR-020; `restart_web` de ADR-022; `run_migrations`, `run_tests` de ADR-023) conectadas por subproceso stdio — la lista de tools disponibles ES la política de seguridad del agente autónomo, a diferencia de Claude Code (sesión `iac`, supervisada por Fernando), que sí tiene shell completo bajo `.claude/settings.json` y el hook de ADR-007. Ver ADR-015, ADR-021, ADR-022, ADR-023. `restart_web` reinicia el contenedor `web` vía un proxy de la API de Docker (`tecnativa/docker-socket-proxy`, servicio `docker-proxy`), nunca con el socket real montado en `orchestrator`. `run_migrations`/`run_tests` corren contra el sidecar `admin-tasks` (misma imagen que `web`, sin `ports:`), que nunca toca Docker en absoluto — se eligió ese camino en vez de `exec` vía el proxy porque este último no puede aislar `exec` de crear/borrar contenedores nuevos, ver ADR-023.

Para autenticar (ver ADR-016), el contenedor del orquestador monta el credencial de suscripción de `~/.claude/.credentials.json` en solo lectura, corriendo con el UID del propietario del archivo en el host (parametrizado vía `ORCHESTRATOR_UID`, nunca cableado) — condicionado a que ninguna tool MCP permita lectura de rutas arbitrarias del filesystem, ya que el credencial es entorno de ejecución del proceso, no una capacidad invocable por el agente. Si esa condición deja de cumplirse, la decisión queda invalidada y hay que pasar a clave de API dedicada. Ver ADR-017. Verificado end-to-end en el servicio real (no un contenedor descartable): `docker compose exec orchestrator python -c "from orchestrator import run; print(run('responde solo PONG'))"` devolvió `PONG`, y una consulta que forzó el uso de `git_status` devolvió el estado real del repo, sin error de autenticación ni de conexión al MCP. Ver ADR-021.

### Capa de conocimiento
Memoria de largo plazo del sistema, independiente del servidor físico donde corre la orquestación. Compuesta por:
- Base de datos vectorial para RAG (pgvector sobre Postgres, o Qdrant si se separa).
- Log de decisiones (ADRs) y documento maestro versionados en Git.
- Pipeline de verificación: captura, verificación (cruce de fuentes o confirmación de Fernando), promoción a conocimiento confirmado. Nada entra a la base de conocimiento "confirmado" sin pasar por este proceso.

Pilar central de la visión ampliada de ADR-024, no un detalle: los dos roles de la sala de discusión (ver más abajo) deben compartir esta misma memoria por proyecto, no operar cada uno con contexto aislado. Tiene dos capas con ritmos distintos (ver ADR-024): una **memoria básica** (historial de conversación persistido en Postgres, ADR-013) que arranca junto con la sala de discusión, no después — persistir un chat ya requiere ese modelo de datos, es la primera capa de memoria; y una **memoria profunda** (RAG vectorial, ingesta del conocimiento ya estructurado del repo) que se sofistica después, en paralelo, sin bloquear nada. **Pendiente (Fase 3):** hoy no existe ni el historial de conversación en Postgres ni la base vectorial.

### Sala de discusión: planificador + ejecutor + Fernando (ADR-024)
**Pendiente (forma mínima: Fase 3 — con memoria básica de conversación desde el arranque, ver ADR-024; forma final: Fase 5 — integrada dentro del panel, ver ADR-013).** Arquitectura de dos roles conversando, con Fernando como decisor final: un rol planificador (conversacional, similar al uso actual de Cowork) y un rol ejecutor, los tres en una misma ventana de chat. Formaliza dentro de IA CENTRAL el patrón que hoy requiere que Fernando relaye manualmente entre Cowork y la sesión `iac` de Claude Code.

**El rol ejecutor es el mismo Claude Code que ya corre hoy en la sesión `iac`** (con shell completo bajo `.claude/settings.json`, sus aprobaciones `allow`/`ask`/`deny` apareciendo dentro de la ventana de la sala en vez de en una terminal) — **no** el orquestador angosto de ADR-021/ADR-022/ADR-023 (5 tools fijas, sin shell, deliberadamente mucho menos capaz). Ese orquestador angosto sigue existiendo aparte, para lo que sea seguro dejar 100% autónomo (Nivel 1 del futuro motor de confianza/permisos), pero no es el único brazo ejecutor de la sala ni reemplaza a Claude Code — usarlo como único ejecutor sería un paso atrás en capacidad respecto al método actual, no una migración. Ver ADR-024.

Primer pilar en el orden de prioridad de ADR-024 — la pieza con más base ya construida de las cinco (persistencia de conversación de ADR-013 casi gratis, orquestador angosto para lo autónomo), pero no toda: el puente real entre la sala y el proceso de Claude Code (para que el rol ejecutor sea Claude Code de verdad, no una simulación) ya tiene diseño (ADR-025) — mecanismo de permisos confirmado (`can_use_tool` + `ToolPermissionContext`) y, para destinos externos, protocolo completo de conexión saliente (tres capas, fail-closed), ninguno implementado todavía. Puede arrancar sin esperar al motor de confianza/permisos unificado (segundo pilar en prioridad) porque reusa el modelo de permisos ya existente de Claude Code tal cual.

### Capa de ejecución
Los conectores que le dan al agente poder real sobre el mundo:
- MCP server propio del proyecto Django (para que la IA Central pueda leer/modificar su propio código), expuesto como tools nombradas y deterministas (`git_status`, `read_file`, `restart_web`, `run_migrations`, `run_tests`), nunca como shell abierto al modelo. Ver ADR-015, ADR-020, ADR-022, ADR-023.
- MCP / acceso SSH hacia la estación local de Fernando (vía Tailscale o WireGuard).
- MCP / acceso SSH de solo lectura por defecto hacia los otros servidores existentes de Fernando (no se escribe ahí hasta que se decida explícitamente lo contrario).
- Claude Code como motor de desarrollo de código, tanto para IA CENTRAL como para los demás proyectos.
- Router de modelos: LiteLLM autohospedado (no OpenRouter — se descartó por ser servicio de terceros con comisión, ver ADR-012), montado desde el inicio de Fase 3 aunque todo el tráfico vaya a Claude al principio. Permite usar Claude, modelos locales (Ollama) u otras IAs de pago sin acoplar el core a un proveedor específico ni reescribir el motor de orquestación. Ver ADR-012.

## 3. Infraestructura

- Hosting: VPS nuevo y dedicado en Contabo (no se reutiliza ninguno de los VPS existentes de Fernando, que ya tienen otros proyectos corriendo). Ver ADR-002.
- Especificación inicial: Cloud VPS 6, 6 vCPU, 12GB RAM, 200GB SSD NVMe, región EU, Ubuntu 24.04, Auto Backup activado.
- Empaquetado: Docker + Docker Compose para todo el stack, de forma que migrar de servidor sea un docker compose up más restore de datos.
- Repositorio: GitHub público (era privado hasta el 2026-07-31, ver ADR-011), clonado en el VPS. GitHub y el VPS son las dos copias completas (historia de Git íntegra); no se mantiene un clon adicional en la máquina local de Fernando — ver enmienda 2026-08-02 a ADR-002. Ver ADR-002.
- Borde HTTPS: Nginx + Certbot corren directamente en el sistema operativo del VPS (fuera de Docker), como excepción puntual al empaquetado Docker de todo lo demás, por consistencia con los otros servidores de Fernando. Nginx hace de reverse proxy hacia el contenedor `web` (`aicentral.network` → `127.0.0.1:8000`) y Certbot gestiona el certificado TLS con renovación automática. Ver ADR-003.
- Backup: `pg_dump` diario vía cron (usuario `fernando`, sin sudo) a `/home/fernando/backups/postgres/` con 14 días de retención, además del Auto Backup de VM de Contabo. Ver ADR-004. Copia adicional fuera del VPS vía `rclone` a Google Drive — **implementación interina**, ver ADR-005: el destino/credenciales de backup deben migrar a configuración gestionada desde el panel administrativo en Fase 5.
- Sync de documentación: GitHub Action (`.github/workflows/sync-drive.yml`) que en cada push a `master` sube README.md/CLAUDE.md/ARQUITECTURA.md/CHANGELOG.md/`docs/**` a la carpeta de Drive `ia-central-backups`, autenticado con OAuth2 de la cuenta personal (no cuenta de servicio, ver justificación en ADR-010). Ver ADR-010.

## 4. Panel administrativo

Empieza como un dashboard ligero (artifact que consulta vía MCP: costos, modelos activos, salud de conectores). Se migra a un panel Django completo solo cuando el número de proyectos/conectores conectados lo justifique.

Cuando exista el panel real, la configuración de destino/credenciales de backup (hoy: `rclone` + Google Drive fijo en script/cron, ver ADR-005) debe migrar a ser gestionada ahí, no quedar fija en el filesystem del VPS.

El panel administrativo es un panel de control (costos, modelos activos, salud de conectores, tareas en curso, cola de verificación de conocimiento) — no un segundo cliente de chat. La interfaz conversacional y su persistencia (conversaciones, mensajes, memoria) son una capa aparte, nativa en Django/Postgres cuando se construya, diferida a Fase 5. Ver ADR-013.

## 5. Hoja de ruta por fases

- Fase 0: Memoria y contexto (este documento, ADRs, changelog, proyecto de Claude como ancla).
- Fase 1: Cerrar decisiones de arquitectura antes de programar.
- Fase 2: Infraestructura base (VPS, Docker, repo, Django skeleton).
- Fase 3: Conectores activos desde el inicio (MCP Django, MCP local, Agent SDK detrás de un gateway LiteLLM, Claude Code). Ver ADR-012.
- Fase 4: Capa multi-IA (elección de modelo por defecto y política de enrutamiento sobre el gateway LiteLLM ya montado en Fase 3, modelo local opcional).
- Fase 5: Panel administrativo. Incluye, de forma nativa en Django/Postgres, la capa de interfaz y persistencia (conversaciones, mensajes, memoria) — diferida a esta fase, ver ADR-013.

Fase 3 y 4 corren headless: conectores MCP + orquestador, sin interfaz web propia. La interfaz de trabajo en esas fases es Claude Code en la sesión tmux `iac` (ver CLAUDE.md), más logs y marcas de estado — no producen nada visible en el navegador, y eso es esperado, no un síntoma de que no avanza. Ver ADR-013.

**Orden de prioridad de la visión ampliada (ADR-024)**, dentro de las fases ya existentes, sin renumerarlas:

1. Sala de discusión de a tres, forma mínima, **junto con** la memoria básica (historial de conversación en Postgres) (§2) — Fase 3, un solo bloque de trabajo, no en secuencia: una sala sin memoria de conversaciones anteriores reproduce el mismo problema que se busca resolver, solo que dentro de una interfaz. El rol ejecutor es Claude Code real (sesión `iac`), no el orquestador angosto — el puente entre la sala y ese proceso ya tiene diseño (ADR-025): mecanismo de permisos confirmado (`can_use_tool` + `ToolPermissionContext`) y, para destinos externos, protocolo completo de conexión saliente, ninguno implementado todavía.
2. Motor de confianza/permisos unificado — sin fase fija todavía: se dispara cuando haga falta ir más allá del modelo de permisos actual de Claude Code (reusado tal cual por la sala) y del catálogo fijo del orquestador angosto (ADR-020/022/023), no antes.
3. Memoria PROFUNDA/RAG (§2) — creciendo en paralelo desde que arranca el bloque 1º, sofisticándose con el tiempo, sin bloquear nada. No confundir con la memoria básica del bloque 1º, que no espera a este punto.
4. Panel administrativo completo (§4) — Fase 5, naciendo pantalla por pantalla a medida que cada pilar de arriba lo necesite, no de antemano.
5. Orquestación multi-modelo con debate — Fase 4, al final deliberadamente: la pieza más compleja de las cinco.

Ver ADR-024 para el contexto y la justificación completa de este orden.

## 6. Registro de decisiones

Cada decisión importante se documenta como una ADR en docs/decisiones/, no solo en este archivo.

- ADR-001: Arquitectura en tres capas y principio de portabilidad/verificación.
- ADR-002: Repositorio en GitHub y VPS dedicado nuevo en Contabo.
- ADR-003: Nginx y Certbot fuera de Docker para TLS de borde (excepción puntual a ADR-002).
- ADR-004: Backup diario de Postgres vía pg_dump.
- ADR-005: Sync de backups a Google Drive vía rclone (interina, a reemplazar en Fase 5).
- ADR-006: Límites del `deny` por patrón de comando en `.claude/settings.json` — no es hermético, la defensa real hoy es el acceso SSH restringido a Fernando.
- ADR-007: Hook `PreToolUse` que bloquea de forma determinista comandos destructivos contra la base de datos (`docker compose down -v`, `docker volume rm/prune` del volumen de Postgres, `DROP DATABASE`/`DROP TABLE`, `rm` sobre la carpeta de backups).
- ADR-008: Cron mensual (sistema, no rutina de sesión) que corre `claude -p` de solo lectura para auditar la auto-memoria del proyecto.
- ADR-009: El agente de Cowork no puede alcanzar la red del VPS (sandbox con allowlist de dominios) — confirma que la ejecución autónoma de Fase 3 debe vivir como proceso nativo en el VPS, no como acceso remoto desde Cowork.
- ADR-010: Sync automático de la documentación a Google Drive vía GitHub Actions, con OAuth2 de cuenta personal en vez de cuenta de servicio (sin cuota de almacenamiento propia sin Google Workspace).
- ADR-011: La fuente de verdad se consulta en vivo desde GitHub (`raw.githubusercontent.com`), no vía Knowledge/Drive estático — requiere que el repo sea público.
- ADR-012: Independencia de proveedor vía gateway LiteLLM (desde el inicio de Fase 3) y el Claude Agent SDK como capa reemplazable detrás de una interfaz interna (`orchestrator.run(...)`).
- ADR-013: Interfaz y persistencia propias en Django/Postgres (no productos de Anthropic), diferidas a Fase 5. Fase 3/4 corren headless.
- ADR-014: Auditoría semanal (`claude -p` de solo lectura, cron del sistema, domingos 04:45) que verifica que las ADR digan la verdad sobre el estado real del repo. Establece la convención de marcar como pendiente (con fase) toda afirmación sobre algo no implementado todavía.
- ADR-015: El orquestador corre como servicio de `docker-compose.yml` (no systemd ni tmux). El LLM nunca tiene shell arbitrario — toda capacidad se expone como tools MCP discretas y nombradas; la lista de tools es la política de seguridad.
- ADR-016: Fase 3 arranca con autenticación por suscripción, no con clave de API — el gateway LiteLLM de ADR-012 queda montado pero fuera del camino real de las llamadas a Claude mientras dure esta vía.
- ADR-017: El orquestador autentica montando el credencial de suscripción en solo lectura con UID alineado, condicionado a que ninguna tool MCP permita lectura de rutas arbitrarias — si esa condición se rompe, la decisión queda invalidada.
- ADR-018: Hook de pre-commit de Git que bloquea si `docs/decisiones/INDEX.md` no coincide con los archivos reales, y notificación push (ntfy autohospedado) si la auditoría semanal de ADR-014 encuentra discrepancias, falla, o no devuelve el marcador esperado.
- ADR-019: Inventario versionado de herramientas y servicios externos del proyecto (`docs/DEPENDENCIAS.md`), sin actualización automática.
- ADR-020: Primer MCP server (`mcp_servers/django_project/`), con dos tools de solo lectura (`git_status`, `read_file`) y `security.py` como autoridad única de la condición de ADR-017. `run_migrations`/`restart_web`/`run_tests` quedan deliberadamente afuera de esta entrega.
- ADR-021: Servicio `orchestrator` real en `docker-compose.yml` — cableado mínimo, sin lógica de negocio ni disparador automático. Autentica por suscripción (cierra el pendiente de ADR-016) y conecta al MCP server de ADR-020 por subproceso stdio (cierra la condición de ADR-017). `tools=[]` como política de seguridad, `strict_mcp_config=True` para no heredar conectores de la cuenta real, `disallowed_tools` como capa aparte para tools de plataforma que `tools=[]` no cubre.
- ADR-022: Segunda tanda de tools con efectos reales — `restart_web`, vía proxy de la API de Docker (`tecnativa/docker-socket-proxy`) en vez de montar el socket directo. `run_migrations`/`run_tests` quedan fuera: el proxy no puede aislar `exec` de crear/borrar contenedores nuevos.
- ADR-023: Tercera tanda — `run_migrations`/`run_tests`, vía un sidecar propio (`admin-tasks`, misma imagen que `web`) que no toca Docker en absoluto, en vez de forzar `exec` a través del proxy de ADR-022.
- ADR-024: Visión ampliada de IA CENTRAL — cinco pilares (memoria compartida, panel-configurable-siempre, motor de permisos unificado, sala de discusión planificador/ejecutor/Fernando, multi-modelo con debate) y su orden de prioridad. Documento de visión y orden, no de diseño técnico — cada pilar amerita su propia ADR al tocarle el turno.
- ADR-025: Diseño técnico inicial de la sala de discusión (pilar 4 de ADR-024) — **en progreso**, no una decisión cerrada. Reconciliada con ADR-027 el 2026-08-06 (ver enmienda de esa fecha en la propia ADR, con diagnóstico de sus nueve puntos). Sobreviven sin cambios: autenticación por proyecto vía Workspaces de Anthropic (ahora como un caso, no el único — depende de la combinación agente+modelo), cifrado de credenciales de proyecto (campo propio sobre `cryptography`), flujo de "conectar proyecto nuevo", y el protocolo de conexión saliente del agente remoto (tres capas, WebSocket sobre TLS primario con long-polling degradado, fail-closed en el ciclo de vida de permisos, tras evaluar y descartar self-hosted sandboxes de Claude Managed Agents) — este último gana peso, porque al no haber garantía a nivel de protocolo en ACP es la única capa donde IA CENTRAL controla algo real sobre un destino externo. Se reescriben: el puente de permisos (`can_use_tool` del SDK no tiene equivalente estructural en ACP), el modelo de sesión (el Ejecutor deja de ser sub-agente del SDK: Consultor y Ejecutor pasan a ser piezas separadas), el esquema de SolicitudPermiso (sus campos venían de `ToolPermissionContext`, que no existe en ACP), y la capa 3 del protocolo saliente. Sin resolver: modelo de datos de Chat con los dos roles separados, esquema real de SolicitudPermiso sobre `session/request_permission`, diseño del aislamiento de proceso por Ejecutor, verificación por agente del catálogo, y la pantalla del panel para conectar un proyecto.
- ADR-026: Servidor ASGI de IA CENTRAL — `daphne==4.2.3`, por ser el servidor oficial que mantiene la misma organización que Channels y `channels_redis`, el único con configuración documentada en Channels, y por auto-negociar HTTP y WebSocket en un solo proceso. Uvicorn queda como plan B, sin cambios de código de aplicación.
- ADR-027: Interfaz del rol ejecutor de la sala — **en progreso**, no una decisión cerrada. Dirección encaminada, no implementada: Agent Client Protocol (ACP), estándar abierto tipo LSP para agentes de código, en vez de un envoltorio propio — resuelve que Claude Code solo funciona con modelos Claude (verificado), lo que chocaba con la independencia de proveedor de ADR-012. Evaluados y no elegidos: OpenHands (su propio modo headless "always approves", sin bloqueo duro en el analizador de seguridad — retroceso frente al hook de ADR-007) y Goose como interfaz (buena implementación de referencia, pero adoptarlo en vez de ACP cambiaría una dependencia por otra). **Límite central, verificado el 2026-08-06 y corregido respecto de lo que afirmaba la enmienda del mismo día (commit `381a7fc`): ACP no da garantía estructural de permisos para agentes locales** — `session/request_permission` es `MAY` y no `MUST`, y `fs/*`/`terminal/*` son capability opcional del Cliente, no una restricción sobre cómo el agente accede al disco (ACP v2 elimina esa superficie citando adopción real nula). Se suma que el hook `PreToolUse` de ADR-007 es específico de Claude Code, sin base para asumir equivalente en Goose/Qwen Code/Kimi CLI. Es la misma categoría de riesgo que ADR-006 ya aceptó, generalizada de una implementación a N. Candidato registrado, no decidido: aislamiento a nivel de sistema operativo por proceso de Ejecutor, extendiendo el patrón de `admin-tasks` (ADR-023) y `orchestrator` (ADR-015). Otras advertencias vigentes: soporte remoto de ACP todavía incompleto, providers ACP de Goose sin reanudar ni bifurcar sesión (limitación de Goose, no del estándar: `session/resume` es estable, el fork sigue sin estabilizar en ambos niveles), y librería de Python todavía pre-1.0.
