#!/usr/bin/env bash
# PreToolUse hook (matcher: Bash). Bloqueo determinista (exit 2) de
# comandos destructivos contra la base de datos y contra los backups.
# No es una sugerencia: el tool call se aborta, sin depender del
# criterio de Claude en esa sesión. Ver ADR-007.
set -euo pipefail

input="$(cat)"
command="$(echo "$input" | jq -r '.tool_input.command // empty')"

if [ -z "$command" ]; then
    exit 0
fi

block() {
    echo "BLOQUEADO por hook de seguridad (.claude/hooks/block-destructive-db.sh): $1" >&2
    exit 2
}

# docker compose down -v / --volumes: borra el volumen de Postgres (todos los datos).
if echo "$command" | grep -qiE 'docker[ -]compose' \
    && echo "$command" | grep -qE '(^|[[:space:]])down([[:space:]]|$)' \
    && echo "$command" | grep -qE '(^|[[:space:]])(-v|--volumes)([[:space:]]|$)'; then
    block "'docker compose down' con -v/--volumes borra el volumen de Postgres"
fi

# DROP DATABASE / DROP TABLE en cualquier parte del comando (psql -c, heredoc, etc.)
if echo "$command" | grep -qiE '\bdrop[[:space:]]+database\b'; then
    block "DROP DATABASE detectado en el comando"
fi
if echo "$command" | grep -qiE '\bdrop[[:space:]]+table\b'; then
    block "DROP TABLE detectado en el comando"
fi

# rm apuntando a la carpeta de backups.
if echo "$command" | grep -qE '\brm\b' \
    && echo "$command" | grep -qE '(/home/fernando/backups|~/backups)'; then
    block "'rm' apuntando a la carpeta de backups (/home/fernando/backups)"
fi

# docker volume rm/prune sobre el volumen de Postgres: otra forma de borrar
# los datos sin pasar por 'docker compose down -v'.
if echo "$command" | grep -qE 'docker[[:space:]]+volume[[:space:]]+(rm|prune)' \
    && echo "$command" | grep -qE '(ia-central_postgres_data|postgres_data)'; then
    block "'docker volume rm/prune' mencionando el volumen de Postgres (ia-central_postgres_data)"
fi

exit 0
