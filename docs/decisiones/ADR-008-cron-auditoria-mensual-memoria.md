# ADR-008 - Cron mensual de auditoría de la auto-memoria vía `claude -p`

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

Se agregó una regla en CLAUDE.md (sección "Memoria entre sesiones") para guardar en memoria preferencias/límites descubiertos al cerrar cada tarea, sin esperar a que se pida explícitamente. Con eso, la auto-memoria del proyecto va a ir creciendo con el tiempo — y nada garantiza que quede al día: una entrada puede quedar duplicada, contradecir una decisión posterior documentada en una ADR nueva, o simplemente dejar de ser relevante.

Hacía falta una revisión periódica. Las rutinas de sesión de Claude Code (`CronCreate`) no sirven para esto porque viven solo en memoria del proceso — se pierden en cuanto termina la sesión que las creó (confirmado en la práctica: se usaron rutinas de sesión para los recordatorios de un solo uso del backup, y quedó documentado explícitamente que no sobreviven a un reinicio del proceso). Para algo que tiene que repetirse mes a mes de forma confiable, hace falta un cron del sistema operativo, igual que `scripts/backup_postgres.sh` (ADR-004).

## Decisión

Se agrega `scripts/memory_audit.sh`, programado por `crontab` del usuario `fernando` (sin sudo) el día 1 de cada mes a las 04:15 — después del backup diario de las 03:00, para no competir por recursos. El script:

- Corre `claude -p "<prompt>"` en modo no interactivo, con `--allowedTools "Read,Glob,Grep"` — deliberadamente sin acceso a `Bash`, `Write` ni `Edit`. La auditoría **solo lee**, nunca modifica ni borra memoria por sí sola; cualquier cambio a la memoria a partir de sus hallazgos lo decide Fernando.
- Le pide a Claude que revise las entradas de memoria del proyecto, verifique si hay algo duplicado, contradictorio, o desactualizado respecto al estado actual del repo (CLAUDE.md/ARQUITECTURA.md/ADRs), y deje un resumen en texto plano.
- Envuelve la llamada con `timeout 300` (5 minutos) para que un cron desatendido no quede colgado indefinidamente si algo falla.
- Deja el resultado en `/home/fernando/memory-audit.log`, con un separador de timestamp por corrida y una marca `AUDIT_STATUS=OK|FAILED` al final, siguiendo el mismo patrón auto-verificable que `backup_postgres.sh` (ADR-004).

Se probó corriéndolo manualmente antes de dejarlo solo en cron: encontró las 3 entradas de memoria existentes, las cruzó correctamente contra el repo (confirmó que el dominio en la memoria de referencia coincide con `git remote -v` y con ADR-003), no encontró duplicados ni desactualizaciones, y de paso señaló — correctamente — que el propio `scripts/memory_audit.sh` todavía no estaba documentado ni commiteado en ese momento.

## Alternativas descartadas

- **Rutina de sesión (`CronCreate`)**: descartada explícitamente por el pedido — se pierde si la sesión/proceso termina, y una auditoría mensual necesita sobrevivir semanas sin que haya una sesión de Claude Code corriendo.
- **Dar acceso completo de herramientas (`--dangerously-skip-permissions` o sin restringir `--allowedTools`)**: innecesario para una tarea de solo lectura, y peligroso para un cron desatendido — si el prompt en algún momento se ve influenciado por contenido inesperado en los archivos de memoria (auto-inyección de instrucciones), un scope de herramientas amplio le daría más superficie para actuar. Restringir a `Read,Glob,Grep` acota el daño posible al mínimo.
- **Que el propio script de backup (ADR-004) también dispare la auditoría de memoria**: se mantienen separados porque tienen cadencias distintas (diario vs. mensual) y objetivos distintos (integridad de datos vs. higiene de memoria) — juntarlos complicaría la lectura de `backup.log` sin necesidad.

## Consecuencias

- Igual que el backup (ADR-004), si se migra el proyecto a otro servidor (ADR-002) hay que recrear la entrada de `crontab` — `scripts/memory_audit.sh` sí viaja versionado con el repo.
- El log (`/home/fernando/memory-audit.log`) vive fuera del repositorio y no se sincroniza a ningún lado (a diferencia de los backups de Postgres, que sí van a Google Drive vía ADR-005) — si se pierde, se pierde el historial de auditorías, pero no hay pérdida de datos reales asociada, así que no se consideró necesario replicarlo.
- El costo de las llamadas mensuales a `claude -p` es marginal (una corrida corta, herramientas de solo lectura), pero es un consumo real de la cuenta de Fernando — vale la pena que lo tenga presente si en algún momento audita gastos.
