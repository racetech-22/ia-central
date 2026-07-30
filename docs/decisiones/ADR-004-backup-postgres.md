# ADR-004 - Backup diario de Postgres vía pg_dump

Fecha: 2026-07-30
Estado: Aceptada

## Contexto

Al revisar el VPS no había ningún backup a nivel de base de datos: ni cron, ni systemd timer, ni script de `pg_dump`. El único respaldo existente era el "Auto Backup" contratado a nivel de VM en Contabo (ver ADR-002), que no es verificable desde dentro del VPS (vive en el panel de control de Contabo) y no garantiza un dump consistente de la base mientras Postgres está corriendo. Dado que ADR-001 exige portabilidad ("transferible por completo a otro servidor sin perder base de conocimiento"), depender únicamente de un snapshot de VM no verificado es insuficiente.

## Decisión

Se agrega `scripts/backup_postgres.sh`, que corre `pg_dump` dentro del contenedor `db` (leyendo `POSTGRES_USER`/`POSTGRES_DB` del propio entorno del contenedor, no parseando `.env` en bash, porque `SECRET_KEY`/`POSTGRES_PASSWORD` pueden traer caracteres especiales de shell), comprime el resultado con `gzip` y lo guarda con timestamp en `/home/fernando/backups/postgres/` (fuera del repositorio). Se programa vía `crontab` del usuario `fernando` (no root, no necesita sudo porque `fernando` está en el grupo `docker`) todos los días a las 03:00, con retención de 14 días (los dumps más viejos se borran automáticamente).

## Alternativas descartadas

- **Confiar solo en el Auto Backup de Contabo**: no verificable desde el VPS, no necesariamente consistente a nivel de aplicación, y ata la recuperación a un único proveedor/mecanismo. Descartado como única capa, se mantiene como respaldo adicional a nivel de VM.
- **`docker volume` export completo en vez de `pg_dump`**: un dump lógico (`pg_dump`) es más portable (restaurable en cualquier versión/instancia de Postgres, no solo restaurando el volumen exacto) y más chico. Se prioriza sobre copiar el volumen entero.
- **Backup a almacenamiento remoto (S3, otro servidor) desde el inicio**: agrega una dependencia/credencial nueva sin que todavía exista ese destino decidido. Se difiere: por ahora los dumps quedan en el mismo VPS, lo cual no protege contra pérdida total del servidor. Revisar cuando se decida un destino remoto.

## Consecuencias

- Los dumps viven en `/home/fernando/backups/postgres/`, fuera del repositorio y sin sincronizar a ningún otro lugar. Si el VPS se pierde por completo, este backup se pierde con él — sigue dependiendo del Auto Backup de Contabo (o de un destino remoto futuro) como única protección contra ese escenario.
- Si se migra el proyecto a otro servidor (ADR-002), hay que recrear el cronjob (`crontab -l` de este ADR) y copiar `scripts/backup_postgres.sh`, que sí está versionado.
- Restaurar un dump: `gunzip -c ia_central_<timestamp>.sql.gz | docker compose exec -T db psql -U ia_central ia_central`.
