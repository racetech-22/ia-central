#!/usr/bin/env bash
# Backup diario de Postgres (pg_dump) para IA CENTRAL. Ver ADR-004.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/home/fernando/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

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
