# ADR-007 - Hook `PreToolUse` que bloquea comandos destructivos contra la base de datos

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

ADR-006 documentó que el `deny` por patrón de comando en `.claude/settings.json` no es hermético para lectura de secretos, pero ese mismo mecanismo de permisos (`allow`/`ask`/`deny`) tampoco cubre comandos *destructivos* específicos como borrar el volumen de Postgres o hacer `DROP TABLE`/`DROP DATABASE` — no había ninguna barrera dura contra perder datos por un comando mal tipeado o mal targeteado, más allá del backup diario (ADR-004/ADR-005).

## Decisión

Se agrega un hook `PreToolUse` con matcher `Bash` en `.claude/settings.json`, que corre `.claude/hooks/block-destructive-db.sh` antes de cualquier comando Bash. El script bloquea de forma determinista (exit 2, no una sugerencia que Claude pueda ignorar) si el comando matchea alguno de estos patrones:

- `docker compose down` combinado con `-v`/`--volumes` (borra el volumen de Postgres).
- `docker volume rm` o `docker volume prune` mencionando el volumen de Postgres (`ia-central_postgres_data` o `postgres_data`) — forma alternativa de borrar el mismo volumen sin pasar por `docker compose down -v`.
- `DROP DATABASE` o `DROP TABLE`, en cualquier parte del comando (cubre `psql -c "..."`, heredocs, etc.), case-insensitive.
- `rm` apuntando a la carpeta de backups (`/home/fernando/backups` o `~/backups`).

Un exit code 2 en un hook `PreToolUse` de tipo `command` aborta el tool call — Claude ve el mensaje de stderr como motivo, pero no puede simplemente reintentarlo o ignorarlo; el bloqueo ocurre antes de que el comando llegue a ejecutarse.

Se verificó con pruebas sintéticas (`echo '{"tool_input":{"command":"..."}}' | ./.claude/hooks/block-destructive-db.sh`) cada regla en su versión "debe bloquear" y su contraparte "no debe bloquear" (por ejemplo, `docker compose down` sin `-v` sí pasa, `docker volume ls` sí pasa, `rm /tmp/foo.txt` sí pasa). Además se probó en vivo, con un tool call real de Bash intentando `docker volume rm ia-central_postgres_data` y `docker compose down -v` — ambos fueron efectivamente abortados por el hook antes de ejecutarse (`PreToolUse:Bash hook error: ...`), y un `docker compose ps` normal después confirmó que los contenedores seguían intactos.

## Alternativas descartadas

- **Agregar estos patrones al `deny` de `permissions`** en vez de un hook: `permissions.deny` con reglas `Bash(...)` sirve para patrones de comando relativamente simples y fijos, pero acá se necesita lógica condicional (ej. "down" + "-v" en cualquier orden, o "docker volume rm/prune" *solo si* menciona el volumen de Postgres) que el formato de patrón de permisos no expresa bien. Un hook con un script permite esa lógica sin volverse una expresión regular ilegible en JSON.
- **Un hook de tipo `prompt` o `agent`** (evaluación por LLM en vez de código) en lugar de `command`: más flexible para casos ambiguos, pero es exactamente lo que el pedido original quería evitar — "código que bloquee de verdad, no una sugerencia". Un hook `command` con `exit 2` es determinista; un hook basado en LLM podría, en teoría, fallar en clasificar un caso límite.
- **Confiar en el backup diario (ADR-004/ADR-005) como única red de contención**: el backup protege contra la pérdida de datos *después* de que ocurrió el borrado (hay que restaurar), pero no evita el borrado en sí. Este hook es una capa previa, no un reemplazo del backup.

## Consecuencias

- Mismo caveat que ADR-006: esto vive en `.claude/settings.json` de este proyecto, corre con el mismo usuario del sistema que ejecuta Claude Code, y solo protege comandos que pasan por la tool `Bash` de Claude Code — no protege contra un `DROP DATABASE` tipeado directamente por Fernando en su propia terminal (no es ese el objetivo: esto es una barrera para acciones de Claude, no para el propio Fernando).
- Los patrones son necesariamente una lista finita. Si aparece una nueva forma de borrar el volumen o la base (por ejemplo, un comando de administración de Postgres distinto, o un `docker system prune` genérico que arrastre el volumen), hay que agregar la regla correspondiente al script — no es exhaustivo por diseño, igual que se documentó en ADR-006 para el `deny` de `.env`.
- Si se migra el proyecto a otro servidor (ADR-002), `.claude/hooks/block-destructive-db.sh` viaja versionado con el repo, así que el hook funciona igual sin configuración adicional (a diferencia del `deny` de `.env`, que no depende de rutas de usuario específicas tampoco).
