#!/usr/bin/env bash
# Auditoría semanal de veracidad de las ADR contra el repo, vía cron del
# sistema (no una rutina de sesión, esas se pierden). Ver ADR-014, su
# enmienda del 2026-08-02 (verificación (d), INDEX.md) y ADR-018
# (marca de estado de contenido + notificación push vía ntfy autohospedado).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${ADR_AUDIT_LOG:-/home/fernando/adr-audit.log}"
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"

cd "$PROJECT_DIR"

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

echo "===== $(date -Iseconds) adr audit =====" >> "$LOG_FILE"

timeout 600 "$CLAUDE_BIN" -p "Revisá todos los archivos docs/decisiones/ADR-*.md de este repo y verificá que digan la verdad sobre el estado real del repositorio, aplicando esta convención de redacción (ver CLAUDE.md, sección 'Cómo mantener la documentación'): el presente ('se agrega', 'existe', 'corre', 'queda configurado') se reserva para artefactos que ya existen en el repo al momento de escribir la ADR. Una afirmación sobre algo NO implementado todavía debe estar marcada explícitamente como pendiente (ej. 'Pendiente (Fase 3): ...') o expresada en futuro/condicional con una fase explícita (ej. 'se migrará en Fase 5', 'deben migrar a Fase 5').

Para cada afirmación de tipo 'se agrega/crea/modifica/existe X' (un archivo, una sección de código, una configuración) en cualquier ADR, clasificala en una de estas tres categorías:

1. DISCREPANCIA: redactada en presente, como si X ya existiera, pero verificaste que X no existe o no coincide con lo descrito, y NO está marcada como pendiente ni con fase futura explícita. Es lo único que hay que reportar en detalle.
2. CORRECTO: marcada explícitamente como pendiente o en futuro/condicional con fase explícita, y efectivamente el artefacto no existe todavía — coincide lo que dice con lo que hay. No reportar en detalle, alcanza con contarlas.
3. AMBIGÜEDAD: en presente sobre algo que no existe todavía en el repo, pero SIN marca de pendiente ni fase explícita — no es una discrepancia flagrante (no confunde a un lector atento) pero viola la convención y convendría corregirla.

También verificá: (b) que ARQUITECTURA.md §6 (Registro de decisiones) liste todas las ADR que existen en docs/decisiones/, sin que falte ninguna; (c) que CHANGELOG.md tenga al menos una entrada correspondiente a cada ADR.

También verificá (d), la integridad de docs/decisiones/INDEX.md contra el estado real del directorio docs/decisiones/: listá con Glob los archivos reales que matchean docs/decisiones/ADR-*.md, leé docs/decisiones/INDEX.md, y compará ambos conjuntos. Reportá como discrepancia de nomenclatura cualquiera de estos tres casos: (d1) un archivo ADR-*.md real que no tiene entrada en INDEX.md; (d2) una entrada de INDEX.md cuyo nombre de archivo no existe tal cual en el directorio (posible renombre no reflejado, o typo); (d3) un número de ADR que aparece más de una vez en INDEX.md o que falta en la secuencia sin que el hueco esté explicado en otro lado. No asumas que un nombre 'parecido' es el mismo archivo — la comparación es por nombre exacto.

También verificá (e), la coherencia interna de cada ADR consigo misma — no contra el repo, sino contra el propio documento: (e1) toda referencia interna del tipo 'punto N', 'paso N', '§N', 'sección N' debe apuntar a un elemento que exista con ese número dentro del mismo documento; reportá la que apunte a algo inexistente, citando la frase exacta y diciendo cuántos elementos tiene realmente esa lista. (e2) toda referencia a otra ADR ('ver ADR-NNN') debe corresponder a un archivo que exista en docs/decisiones/. (e3) todo conteo escrito en palabras o cifras que describa una lista del mismo documento ('cinco decisiones', 'tres razones', 'cuatro piezas', 'dos tramas') debe coincidir con la cantidad real de elementos de esa lista; reportá el que no cuadre, con el número que dice y el que corresponde. Estas tres son verificaciones sobre el texto, no sobre el repo: no requieren que ningún artefacto exista. Cuando reportes un conteo desactualizado (e3), recomendá por defecto ELIMINAR el número en vez de actualizarlo — una ADR que crece por enmiendas vuelve a desactualizar cualquier cantidad hardcodeada, y actualizarla solo mueve el problema a la próxima enmienda. Reportá un caso solo si podés citar la frase exacta y mostrar el conteo real; ante la duda, no lo reportes.

No modifiques ni borres nada. Terminá con un resumen en texto plano, en este orden: primero las DISCREPANCIAS reales de contenido (si hay alguna), con el ADR, la afirmación exacta, y qué encontraste en el repo en su lugar. Después, un bloque aparte para las discrepancias de INDEX.md (d1/d2/d3) si las hay, con la misma prioridad que las discrepancias de contenido — un INDEX.md desactualizado también es una fuente de verdad rota. Después, un bloque aparte para las discrepancias de coherencia interna (e1/e2/e3) si las hay, con la misma prioridad que las anteriores — una referencia interna rota o un conteo desactualizado es tan una fuente de verdad rota como las anteriores. Después, aparte y con menor énfasis, las AMBIGÜEDADES. Si no hay discrepancias, decilo explícitamente. No detalles los casos CORRECTOS uno por uno, mencionalos de forma agregada (cuántos, cuáles ADR).

Además de ese resumen en texto plano, terminá tu respuesta con una última línea, sola, exactamente 'ADR_CONTENT_STATUS=CLEAN' si no encontraste ninguna DISCREPANCIA de contenido, ni discrepancia de INDEX.md (d1/d2/d3), ni de coherencia interna (e1/e2/e3), o exactamente 'ADR_CONTENT_STATUS=DISCREPANCIES_FOUND' si encontraste al menos una de cualquiera de esos tres tipos. Las AMBIGÜEDADES por sí solas, sin ninguna DISCREPANCIA real, no cuentan para este marcador — dejalo en CLEAN si sólo hay ambigüedades. Esta línea tiene que aparecer literalmente, sin texto adicional en la misma línea, porque un proceso automático la va a buscar con grep." \
    --allowedTools "Read,Glob,Grep" \
    > "$output_file" 2>&1
status=$?

cat "$output_file" >> "$LOG_FILE"

if [ "$status" -ne 0 ]; then
    echo "ADR_AUDIT_STATUS=FAILED exit_code=$status" >> "$LOG_FILE"
else
    echo "ADR_AUDIT_STATUS=OK" >> "$LOG_FILE"
fi
echo "===== fin =====" >> "$LOG_FILE"
echo >> "$LOG_FILE"

content_status="UNKNOWN"
if grep -q '^ADR_CONTENT_STATUS=DISCREPANCIES_FOUND' "$output_file"; then
    content_status="DISCREPANCIES_FOUND"
elif grep -q '^ADR_CONTENT_STATUS=CLEAN' "$output_file"; then
    content_status="CLEAN"
fi

if [ "$status" -ne 0 ] || [ "$content_status" = "DISCREPANCIES_FOUND" ] || [ "$content_status" = "UNKNOWN" ]; then
    if [ "$status" -ne 0 ]; then
        msg="IA CENTRAL: adr_audit.sh fallo (exit $status). Ver adr-audit.log."
    elif [ "$content_status" = "UNKNOWN" ]; then
        msg="IA CENTRAL: adr_audit.sh no devolvio ADR_CONTENT_STATUS esperado. Revisar adr-audit.log."
    else
        msg="IA CENTRAL: auditoria semanal de ADR encontro discrepancias. Ver adr-audit.log."
    fi
    NTFY_URL="$(grep -E '^NTFY_URL=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
    NTFY_TOPIC="$(grep -E '^NTFY_TOPIC=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
    NTFY_TOKEN="$(grep -E '^NTFY_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
    if [ -n "$NTFY_URL" ] && [ -n "$NTFY_TOPIC" ] && [ -n "$NTFY_TOKEN" ]; then
        curl -fsS -H "Authorization: Bearer $NTFY_TOKEN" -H "Title: IA CENTRAL - auditoria ADR" -d "$msg" "$NTFY_URL/$NTFY_TOPIC" >/dev/null 2>&1 || true
    fi
fi
