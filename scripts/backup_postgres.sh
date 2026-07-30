#!/usr/bin/env bash
# Backup diario de Postgres (pg_dump) para IA CENTRAL. Ver ADR-004.
#
# El destino remoto (rclone/Google Drive) es una implementación interina —
# ver ADR-005. Migra a configuración gestionada desde el panel
# administrativo en Fase 5 (ARQUITECTURA.md §4), no debe quedar fijo acá
# para siempre.
#
# Códigos de salida: 0 = todo OK (local + remoto). 1 = falló el backup
# local (pg_dump/gzip) o algo inesperado — CRÍTICO. 2 = el backup local
# quedó OK pero el sync a Drive falló — degradado, no crítico.
set -euo pipefail

# cron no carga ~/.bashrc, así que ~/.local/bin (donde vive rclone) no
# está en el PATH por defecto salvo que lo agreguemos acá explícitamente.
export PATH="$HOME/.local/bin:$PATH"

log() {
    echo "$(date -Iseconds) $1"
}

trap 'log "BACKUP_STATUS=FAILED error inesperado en línea $LINENO"' ERR

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
if docker compose exec -T db bash -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$TMP_FILE"; then
    mv "$TMP_FILE" "$DUMP_FILE"
else
    rm -f "$TMP_FILE"
    log "BACKUP_STATUS=FAILED pg_dump/gzip falló, ver salida arriba"
    exit 1
fi

# La limpieza de retención es mantenimiento, no crítico: si falla no debe
# hacer que el script reporte el backup entero como fallido.
find "$BACKUP_DIR" -name "ia_central_*.sql.gz" -mtime "+${RETENTION_DAYS}" -delete \
    || log "WARNING: no se pudo limpiar backups viejos (retención ${RETENTION_DAYS}d)"

SIZE="$(du -h "$DUMP_FILE" 2>/dev/null | cut -f1 || echo "?")"
log "BACKUP_STATUS=OK file=$DUMP_FILE size=$SIZE"

# rclone copy (no sync): nunca borra en el remoto, aunque la retención local
# sí borre dumps viejos acá. El backup local ya está a salvo si esto falla;
# se refleja como degradado (exit 2), no crítico (exit 1).
if command -v rclone >/dev/null 2>&1; then
    if rclone copy "$DUMP_FILE" "$RCLONE_REMOTE" 2>&1; then
        log "RCLONE_STATUS=OK remote=$RCLONE_REMOTE"
    else
        log "RCLONE_STATUS=FAILED remote=$RCLONE_REMOTE revisar token/cuota"
        exit 2
    fi
else
    log "RCLONE_STATUS=SKIPPED rclone no instalado"
fi

exit 0
