#!/usr/bin/env bash
# Auditoría mensual de la auto-memoria del proyecto vía cron del sistema
# (no una rutina de sesión, esas se pierden). Ver CLAUDE.md, sección
# "Memoria entre sesiones" / rutina de mantenimiento mensual.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${MEMORY_AUDIT_LOG:-/home/fernando/memory-audit.log}"
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"

cd "$PROJECT_DIR"

{
    echo "===== $(date -Iseconds) memory audit ====="
    timeout 300 "$CLAUDE_BIN" -p "Revisá tu sistema de memoria persistente (auto-memoria) para este proyecto: qué entradas hay guardadas, si alguna parece duplicada, contradictoria o desactualizada respecto al estado actual del repo (podés confirmar contra CLAUDE.md/ARQUITECTURA.md/las ADRs si hace falta). No modifiques ni borres nada. Terminá con un resumen breve en texto plano: lista de entradas encontradas y cualquier hallazgo o recomendación." \
        --allowedTools "Read,Glob,Grep" \
        2>&1
    status=$?
    if [ "$status" -ne 0 ]; then
        echo "AUDIT_STATUS=FAILED exit_code=$status"
    else
        echo "AUDIT_STATUS=OK"
    fi
    echo "===== fin ====="
    echo
} >> "$LOG_FILE"
