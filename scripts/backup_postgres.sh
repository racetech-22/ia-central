#!/usr/bin/env bash
# Backup diario de Postgres (pg_dump) para IA CENTRAL. Ver ADR-004.
#
# El destino remoto (rclone/Google Drive) es una implementación interina —
# ver ADR-005. Migra a configuración gestionada desde el panel
# administrativo en Fase 5 (ARQUITECTURA.md §4), no debe quedar fijo acá
# para siempre.
set -euo pipefail

# cron no carga ~/.bashrc, así que ~/.local/bin (donde vive rclone) no
# está en el PATH por defecto salvo que lo agreguemos acá explícitamente.
export PATH="$HOME/.local/bin:$PATH"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/home/fernando/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:ia-central-backups/postgres}"

cd "$PROJECT_DIR"
mkdir -p "$BACKUP_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DUMP_FILE="$BACKUP_DIR/ia_central_${TIMESTAMP}.sql.gz"
TMP_FILE="${DUMP_FILE}.tmp"

# POSTGRES_USER/POSTGRES_DB se leen del propio entorno del contenedor db
# (seteado por docker-compose desde .env), no se parsea .env acá porque
# SECRET_KEY/POSTGRES_PASSWORD pueden traer caracteres especiales de shell.
docker compose exec -T db bash -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$TMP_FILE"
mv "$TMP_FILE" "$DUMP_FILE"

find "$BACKUP_DIR" -name "ia_central_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete

echo "$(date -Iseconds) backup OK: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"

# rclone copy (no sync): nunca borra en el remoto, aunque la retención local
# sí borre dumps viejos acá. Si falla (red, cuota, token vencido) no aborta
# el script: el backup local ya está a salvo, esto solo agrega una copia off-VPS.
if command -v rclone >/dev/null 2>&1; then
    if rclone copy "$DUMP_FILE" "$RCLONE_REMOTE" 2>&1; then
        echo "$(date -Iseconds) rclone sync OK -> $RCLONE_REMOTE"
    else
        echo "$(date -Iseconds) WARNING: rclone sync a $RCLONE_REMOTE falló, revisar token/cuota" >&2
    fi
else
    echo "$(date -Iseconds) WARNING: rclone no instalado, se omite sync remoto" >&2
fi
