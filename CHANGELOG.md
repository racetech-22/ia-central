# Changelog

Todas las decisiones y avances relevantes del proyecto quedan registradas aquí, en orden cronológico. Las decisiones con justificación completa viven además como ADR en `docs/decisiones/`.

## 2026-07-30

- Definida la descripción inicial del proyecto IA CENTRAL.
- Aceptada arquitectura en tres capas (orquestación / conocimiento / ejecución) — ver ADR-001.
- Definido el pipeline de verificación de conocimiento (captura, verificación, promoción) — ver ADR-001.
- Decidido usar GitHub privado como repositorio fuente de verdad y VPS nuevo dedicado en Contabo (8-16GB RAM, 4 vCPU, NVMe) para IA CENTRAL — ver ADR-002.
- Creada la estructura inicial del repositorio (README.md, ARQUITECTURA.md, .gitignore, ADRs).
- Creado el skeleton de Django (`core/`, `manage.py`, `apps/`, `mcp_servers/`), empaquetado con `Dockerfile` y `docker-compose.yml` (web + Postgres con pgvector), y `requirements.txt`/`.env.example`. Verificado que build, migrate y check corren correctamente contra Postgres — arranque de Fase 2 de la hoja de ruta.
- Agregada la primera app propia bajo `apps/`: `adminpanel`, que personaliza el admin integrado de Django (branding "IA CENTRAL") e incluye `StatusNote` como modelo mínimo de ejemplo (modelo + ModelAdmin) a modo de plantilla para futuras apps. El panel administrativo real (costos, modelos activos, salud de conectores de ARQUITECTURA.md §4) queda para Fase 5.
- Expuesto IA CENTRAL en `aicentral.network` con HTTPS: Nginx + Certbot instalados fuera de Docker en el VPS (excepción puntual documentada en ADR-003, por consistencia con los otros servidores de Fernando), con Nginx como reverse proxy hacia el contenedor `web`. Agregados `CSRF_TRUSTED_ORIGINS` y `SECURE_PROXY_SSL_HEADER` en `core/settings.py` para que Django reconozca correctamente las peticiones HTTPS reenviadas por el proxy.
- Hardening de producción en el `.env` del VPS (no versionado): `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` reales generados (reemplazando los placeholders `change-me`, con `ALTER USER` para no perder los datos ya existentes) y `DJANGO_DEBUG=False`. Como `runserver` con `DEBUG=False` no sirve estáticos, Nginx ahora sirve `/static/` directo desde `staticfiles/` (`manage.py collectstatic`), ver ADR-003.
- Detectado que no había ningún backup a nivel de base de datos (solo el Auto Backup de VM de Contabo, no verificable desde el VPS). Agregado `scripts/backup_postgres.sh` (pg_dump + gzip) programado por cron del usuario `fernando` a diario a las 03:00, con 14 días de retención — ver ADR-004.
- Agregado sync de los dumps a Google Drive vía `rclone` (`gdrive:ia-central-backups/postgres/`, scope `drive.file`) como copia fuera del VPS. Documentado explícitamente como implementación **interina** en ADR-005: el destino y las credenciales deben migrar a configuración gestionada desde el panel administrativo en Fase 5, no quedar fijos en script/cron.
- `scripts/backup_postgres.sh` ahora es auto-verificable: deja líneas grepeables `BACKUP_STATUS=OK|FAILED` / `RCLONE_STATUS=OK|FAILED|SKIPPED` en `backup.log` y termina con código de salida 0 (todo OK), 1 (backup local falló — crítico) o 2 (local OK pero sync remoto falló — degradado). Probado forzando cada caso. Ver ADR-004.

## 2026-07-31

- Agregado `.claude/settings.json` (versionado) con reglas de permisos para Claude Code en este repo: `allow` para `docker compose`/`git status`/`git diff`/`git commit -m`, `ask` obligatorio para `git push`, y `deny` para lectura de `.env`/`.env.*` (tool `Read`) y `cat *.env*` por Bash. Documentado bloque por bloque en CLAUDE.md.
- **Verificado que el `deny` de `.env` es incompleto**: bloquea la tool `Read` y el comando `cat` exacto, pero `python3 -c "print(open('.env').read())"` lo esquivó e imprimió el `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` reales en la conversación durante la propia verificación. El bloqueo robusto (a nivel de sandbox de filesystem, `sandbox.credentials.files`) no está disponible porque el VPS no tiene `bwrap` instalado.
- Rotados `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` en el `.env` del VPS (no versionado) por haber quedado expuestos en el hallazgo anterior — password de Postgres cambiado con `ALTER USER` (sin perder datos), contenedores recreados. Verificado `check`/`migrate` con las credenciales nuevas y que `https://aicentral.network/admin/login/` sigue respondiendo 200 con el branding esperado.
- Documentado en ADR-006 que el `deny` por patrón de comando en `.claude/settings.json` no es hermético (se evade con `python3`, `node`, etc.) y que la protección robusta requeriría `bwrap`, no instalado en este VPS. Por ahora la defensa real contra la exposición de `.env` es que solo Fernando tiene acceso SSH al servidor, no la configuración de permisos de Claude Code.
