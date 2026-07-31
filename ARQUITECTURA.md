# Arquitectura de IA CENTRAL

Documento maestro. Se actualiza cada vez que se toma una decisión relevante. Cualquier conversación nueva sobre este proyecto debe partir de este documento.

## 1. Principio rector

Todo lo que se construya debe cumplir dos condiciones simultáneas:

1. Portable: transferible por completo a otro servidor sin perder base de conocimiento ni funcionalidad.
2. Verificable: el conocimiento que el sistema acumula por sí mismo (auto-aprendizaje) solo se considera válido cuando pasa por un proceso explícito de verificación, nunca por defecto.

## 2. Arquitectura en tres capas

### Capa de orquestación
El agente que decide qué hacer y a qué IA/herramienta delegar cada tarea. Construida sobre el Claude Agent SDK, corriendo como proceso persistente en el VPS.

### Capa de conocimiento
Memoria de largo plazo del sistema, independiente del servidor físico donde corre la orquestación. Compuesta por:
- Base de datos vectorial para RAG (pgvector sobre Postgres, o Qdrant si se separa).
- Log de decisiones (ADRs) y documento maestro versionados en Git.
- Pipeline de verificación: captura, verificación (cruce de fuentes o confirmación de Fernando), promoción a conocimiento confirmado. Nada entra a la base de conocimiento "confirmado" sin pasar por este proceso.

### Capa de ejecución
Los conectores que le dan al agente poder real sobre el mundo:
- MCP server propio del proyecto Django (para que la IA Central pueda leer/modificar su propio código).
- MCP / acceso SSH hacia la estación local de Fernando (vía Tailscale o WireGuard).
- MCP / acceso SSH de solo lectura por defecto hacia los otros servidores existentes de Fernando (no se escribe ahí hasta que se decida explícitamente lo contrario).
- Claude Code como motor de desarrollo de código, tanto para IA CENTRAL como para los demás proyectos.
- Router de modelos (LiteLLM u OpenRouter) para poder usar Claude, modelos locales (Ollama) u otras IAs de pago sin acoplar el core a un proveedor específico.

## 3. Infraestructura

- Hosting: VPS nuevo y dedicado en Contabo (no se reutiliza ninguno de los VPS existentes de Fernando, que ya tienen otros proyectos corriendo). Ver ADR-002.
- Especificación inicial: Cloud VPS 6, 6 vCPU, 12GB RAM, 200GB SSD NVMe, región EU, Ubuntu 24.04, Auto Backup activado.
- Empaquetado: Docker + Docker Compose para todo el stack, de forma que migrar de servidor sea un docker compose up más restore de datos.
- Repositorio: GitHub privado, clonado igual en el VPS y en la máquina local de Fernando (mismo contenido, sincronizado por Git). Ver ADR-002.
- Borde HTTPS: Nginx + Certbot corren directamente en el sistema operativo del VPS (fuera de Docker), como excepción puntual al empaquetado Docker de todo lo demás, por consistencia con los otros servidores de Fernando. Nginx hace de reverse proxy hacia el contenedor `web` (`aicentral.network` → `127.0.0.1:8000`) y Certbot gestiona el certificado TLS con renovación automática. Ver ADR-003.
- Backup: `pg_dump` diario vía cron (usuario `fernando`, sin sudo) a `/home/fernando/backups/postgres/` con 14 días de retención, además del Auto Backup de VM de Contabo. Ver ADR-004. Copia adicional fuera del VPS vía `rclone` a Google Drive — **implementación interina**, ver ADR-005: el destino/credenciales de backup deben migrar a configuración gestionada desde el panel administrativo en Fase 5.
- Sync de documentación: GitHub Action (`.github/workflows/sync-drive.yml`) que en cada push a `master` sube README.md/CLAUDE.md/ARQUITECTURA.md/CHANGELOG.md/`docs/**` a la carpeta de Drive `ia-central-backups`, autenticado con OAuth2 de la cuenta personal (no cuenta de servicio, ver justificación en ADR-010). Ver ADR-010.

## 4. Panel administrativo

Empieza como un dashboard ligero (artifact que consulta vía MCP: costos, modelos activos, salud de conectores). Se migra a un panel Django completo solo cuando el número de proyectos/conectores conectados lo justifique.

Cuando exista el panel real, la configuración de destino/credenciales de backup (hoy: `rclone` + Google Drive fijo en script/cron, ver ADR-005) debe migrar a ser gestionada ahí, no quedar fija en el filesystem del VPS.

## 5. Hoja de ruta por fases

- Fase 0: Memoria y contexto (este documento, ADRs, changelog, proyecto de Claude como ancla).
- Fase 1: Cerrar decisiones de arquitectura antes de programar.
- Fase 2: Infraestructura base (VPS, Docker, repo, Django skeleton).
- Fase 3: Conectores activos desde el inicio (MCP Django, MCP local, Agent SDK, Claude Code).
- Fase 4: Capa multi-IA (router de modelos, modelo local opcional).
- Fase 5: Panel administrativo.

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
