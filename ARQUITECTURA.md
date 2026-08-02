# Arquitectura de IA CENTRAL

Documento maestro. Se actualiza cada vez que se toma una decisión relevante. Cualquier conversación nueva sobre este proyecto debe partir de este documento.

## 1. Principio rector

Todo lo que se construya debe cumplir dos condiciones simultáneas:

1. Portable: transferible por completo a otro servidor sin perder base de conocimiento ni funcionalidad.
2. Verificable: el conocimiento que el sistema acumula por sí mismo (auto-aprendizaje) solo se considera válido cuando pasa por un proceso explícito de verificación, nunca por defecto.

El punto 1 cubre **portabilidad de servidor** (ADR-001: mover todo a otro VPS sin perder conocimiento). **Portabilidad de proveedor** — no quedar acoplado a un único proveedor de modelos — es un requisito distinto, resuelto en ADR-012 (gateway LiteLLM + framework de agente como capa reemplazable detrás de una interfaz interna).

## 2. Arquitectura en tres capas

### Capa de orquestación
El agente que decide qué hacer y a qué IA/herramienta delegar cada tarea, corriendo como servicio de `docker-compose.yml` (`restart: always`), junto a `web` y `db` — no como servicio systemd ni sesión de tmux, para no salirse del contrato de portabilidad de ADR-002. Ver ADR-015. Implementada con el Claude Agent SDK como motor del bucle, pero expuesta al resto del sistema (Django, MCP servers) únicamente vía una interfaz interna propia (`orchestrator.run(...)`) — el SDK es un detalle de implementación reemplazable, nunca se llama directamente desde fuera de esa interfaz. El SDK está pensado para enrutar sus llamadas a modelo a través de un gateway LiteLLM autohospedado, no directo a la API de Anthropic (ver ADR-012) — pero mientras Fase 3 use autenticación por suscripción en vez de clave de API, el gateway queda montado y sano sin estar en el camino real de esas llamadas. Ver ADR-016.

El LLM que corre en el orquestador nunca tiene shell arbitrario. Toda capacidad sobre la infraestructura (migraciones, reinicio de servicios, lectura de archivos, git) se expone como tools MCP discretas y nombradas, implementadas como código determinista en `mcp_servers/` — la lista de tools disponibles ES la política de seguridad del agente autónomo, a diferencia de Claude Code (sesión `iac`, supervisada por Fernando), que sí tiene shell completo bajo `.claude/settings.json` y el hook de ADR-007. Ver ADR-015.

Para autenticar (ver ADR-016), el contenedor del orquestador monta el credencial de suscripción de `~/.claude/.credentials.json` en solo lectura, corriendo con el UID del propietario del archivo en el host. Esto queda condicionado a que ninguna tool MCP permita lectura de rutas arbitrarias del filesystem — el credencial es entorno de ejecución del proceso, no una capacidad invocable por el agente. Si esa condición deja de cumplirse, la decisión queda invalidada y hay que pasar a clave de API dedicada. Ver ADR-017.

### Capa de conocimiento
Memoria de largo plazo del sistema, independiente del servidor físico donde corre la orquestación. Compuesta por:
- Base de datos vectorial para RAG (pgvector sobre Postgres, o Qdrant si se separa).
- Log de decisiones (ADRs) y documento maestro versionados en Git.
- Pipeline de verificación: captura, verificación (cruce de fuentes o confirmación de Fernando), promoción a conocimiento confirmado. Nada entra a la base de conocimiento "confirmado" sin pasar por este proceso.

### Capa de ejecución
Los conectores que le dan al agente poder real sobre el mundo:
- MCP server propio del proyecto Django (para que la IA Central pueda leer/modificar su propio código), expuesto como tools nombradas y deterministas (`run_migrations`, `restart_web`, `run_tests`…), nunca como shell abierto al modelo. Ver ADR-015.
- MCP / acceso SSH hacia la estación local de Fernando (vía Tailscale o WireGuard).
- MCP / acceso SSH de solo lectura por defecto hacia los otros servidores existentes de Fernando (no se escribe ahí hasta que se decida explícitamente lo contrario).
- Claude Code como motor de desarrollo de código, tanto para IA CENTRAL como para los demás proyectos.
- Router de modelos: LiteLLM autohospedado (no OpenRouter — se descartó por ser servicio de terceros con comisión, ver ADR-012), montado desde el inicio de Fase 3 aunque todo el tráfico vaya a Claude al principio. Permite usar Claude, modelos locales (Ollama) u otras IAs de pago sin acoplar el core a un proveedor específico ni reescribir el motor de orquestación. Ver ADR-012.

## 3. Infraestructura

- Hosting: VPS nuevo y dedicado en Contabo (no se reutiliza ninguno de los VPS existentes de Fernando, que ya tienen otros proyectos corriendo). Ver ADR-002.
- Especificación inicial: Cloud VPS 6, 6 vCPU, 12GB RAM, 200GB SSD NVMe, región EU, Ubuntu 24.04, Auto Backup activado.
- Empaquetado: Docker + Docker Compose para todo el stack, de forma que migrar de servidor sea un docker compose up más restore de datos.
- Repositorio: GitHub público (era privado hasta el 2026-07-31, ver ADR-011), clonado igual en el VPS y en la máquina local de Fernando (mismo contenido, sincronizado por Git). Ver ADR-002.
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
