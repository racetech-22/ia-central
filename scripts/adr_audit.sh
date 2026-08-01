#!/usr/bin/env bash
# Auditoría semanal de veracidad de las ADR contra el repo, vía cron del
# sistema (no una rutina de sesión, esas se pierden). Ver ADR-014.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${ADR_AUDIT_LOG:-/home/fernando/adr-audit.log}"
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"

cd "$PROJECT_DIR"

{
    echo "===== $(date -Iseconds) adr audit ====="
    timeout 300 "$CLAUDE_BIN" -p "Revisá todos los archivos docs/decisiones/ADR-*.md de este repo y verificá que digan la verdad sobre el estado real del repositorio, aplicando esta convención de redacción (ver CLAUDE.md, sección 'Cómo mantener la documentación'): el presente ('se agrega', 'existe', 'corre', 'queda configurado') se reserva para artefactos que ya existen en el repo al momento de escribir la ADR. Una afirmación sobre algo NO implementado todavía debe estar marcada explícitamente como pendiente (ej. '**Pendiente (Fase 3):** ...') o expresada en futuro/condicional con una fase explícita (ej. 'se migrará en Fase 5', 'deben migrar a Fase 5').

Para cada afirmación de tipo 'se agrega/crea/modifica/existe X' (un archivo, una sección de código, una configuración) en cualquier ADR, clasificala en una de estas tres categorías:

1. DISCREPANCIA: redactada en presente, como si X ya existiera, pero verificaste que X no existe o no coincide con lo descrito, y NO está marcada como pendiente ni con fase futura explícita. Es lo único que hay que reportar en detalle.
2. CORRECTO: marcada explícitamente como pendiente o en futuro/condicional con fase explícita, y efectivamente el artefacto no existe todavía — coincide lo que dice con lo que hay. No reportar en detalle, alcanza con contarlas.
3. AMBIGÜEDAD: en presente sobre algo que no existe todavía en el repo, pero SIN marca de pendiente ni fase explícita — no es una discrepancia flagrante (no confunde a un lector atento) pero viola la convención y convendría corregirla.

También verificá: (b) que ARQUITECTURA.md §6 (Registro de decisiones) liste todas las ADR que existen en docs/decisiones/, sin que falte ninguna; (c) que CHANGELOG.md tenga al menos una entrada correspondiente a cada ADR.

No modifiques ni borres nada. Terminá con un resumen en texto plano, en este orden: primero las DISCREPANCIAS reales (si hay alguna), con el ADR, la afirmación exacta, y qué encontraste en el repo en su lugar. Después, aparte y con menor énfasis, las AMBIGÜEDADES. Si no hay discrepancias, decilo explícitamente. No detalles los casos CORRECTOS uno por uno, mencionalos de forma agregada (cuántos, cuáles ADR)." \
        --allowedTools "Read,Glob,Grep" \
        2>&1
    status=$?
    if [ "$status" -ne 0 ]; then
        echo "ADR_AUDIT_STATUS=FAILED exit_code=$status"
    else
        echo "ADR_AUDIT_STATUS=OK"
    fi
    echo "===== fin ====="
    echo
} >> "$LOG_FILE"
