#!/usr/bin/env bash
# Chequeo del sistema vivo desplegado (ADR-037) — a diferencia de los
# chequeos de archivos del repo (INDEX.md en ADR-018, docs/estado.yml en
# ADR-029, ARQUITECTURA.md §6 en ADR-032), este golpea el sitio real desde
# afuera para confirmar que lo que corre coincide con lo que dice el repo
# y que los servicios vivos (Postgres, el channel layer de Redis) responden
# de verdad, no solo que existen archivos consistentes entre sí.
#
# Notifica por ntfy (ADR-018) solo si algo falla; si todo pasa, no
# notifica nada — mismo criterio silencioso que backup_postgres.sh y
# adr_audit.sh.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Overridable solo para pruebas adversariales (ver ADR-037) — en cron
# siempre pega contra el dominio real, desde afuera.
SITIO="${SITIO_CHEQUEO_DESPLIEGUE:-https://aicentral.network}"
LOG_FILE="${CHEQUEO_DESPLIEGUE_LOG:-/home/fernando/chequeo-despliegue.log}"

cd "$PROJECT_DIR"

log() {
    echo "$(date -Iseconds) $1" | tee -a "$LOG_FILE"
}

fallas=()

log "===== chequeo de despliegue ====="

# --- 1. /salud/ responde 200, con sha/db/redis sanos ---
salud_tmp="$(mktemp)"
trap 'rm -f "$salud_tmp"' EXIT
http_code="$(curl -s -o "$salud_tmp" -w '%{http_code}' --max-time 15 "$SITIO/salud/" 2>/dev/null)"

if [ "$http_code" != "200" ]; then
    fallas+=("/salud/ devolvió HTTP $http_code (esperado 200) — cuerpo: $(head -c 300 "$salud_tmp" 2>/dev/null)")
else
    sha_local="$(grep -oP '"sha":\s*"\K[^"]+' "$salud_tmp" 2>/dev/null || echo "")"
    db_ok="$(grep -oP '"db":\s*\K(true|false)' "$salud_tmp" 2>/dev/null || echo "")"
    redis_ok="$(grep -oP '"redis":\s*\K(true|false)' "$salud_tmp" 2>/dev/null || echo "")"

    if [ "$db_ok" != "true" ]; then
        fallas+=("/salud/ reporta db=${db_ok:-<vacío>}")
    fi
    if [ "$redis_ok" != "true" ]; then
        fallas+=("/salud/ reporta redis=${redis_ok:-<vacío>}")
    fi

    # --- 2. SHA desplegado vs origin/master ---
    # API de GitHub por HTTPS anónima, no "git ls-remote": origin es un
    # remoto SSH (git@github.com:...) y cron puede no tener la clave
    # cargada — mismo protocolo de verificación de ADR-011 (anclado a SHA
    # real de origin/master vía api.github.com, no al nombre de rama).
    sha_origin="$(curl -fsS --max-time 15 https://api.github.com/repos/racetech-22/ia-central/commits/master 2>/dev/null \
        | grep -oP '"sha":\s*"\K[^"]+' | head -1 || echo "")"

    if [ "$sha_local" = "desconocido" ] || [ -z "$sha_local" ]; then
        fallas+=("sha desplegado es '${sha_local:-<vacío>}' — la imagen se construyó sin GIT_SHA")
    elif [ -z "$sha_origin" ]; then
        fallas+=("no se pudo obtener el sha de origin/master desde api.github.com")
    elif [ "$sha_local" != "$sha_origin" ]; then
        fallas+=("sha desplegado ($sha_local) no coincide con origin/master ($sha_origin)")
    fi
fi

# --- 3. verificar_canal (ADR-037) dentro del contenedor web: prueba el
# channel layer REAL, no el de memoria que usa la suite de tests ---
canal_tmp="$(mktemp)"
if ! docker compose exec -T web python manage.py verificar_canal >"$canal_tmp" 2>&1; then
    fallas+=("verificar_canal falló: $(tail -3 "$canal_tmp" | tr '\n' ' ')")
fi
rm -f "$canal_tmp"

# --- 4. /admin/login/ y /mapa/ responden lo esperado ---
admin_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$SITIO/admin/login/" 2>/dev/null)"
if [ "$admin_code" != "200" ]; then
    fallas+=("/admin/login/ devolvió HTTP $admin_code (esperado 200)")
fi

mapa_code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$SITIO/mapa/" 2>/dev/null)"
if [ "$mapa_code" != "302" ]; then
    fallas+=("/mapa/ devolvió HTTP $mapa_code (esperado 302, redirige a login sin autenticar)")
fi

# --- resultado ---
if [ "${#fallas[@]}" -eq 0 ]; then
    log "CHEQUEO_DESPLIEGUE_STATUS=OK"
    exit 0
fi

log "CHEQUEO_DESPLIEGUE_STATUS=FAILED"
for f in "${fallas[@]}"; do
    log "  - $f"
done

msg="IA CENTRAL: chequeo de despliegue encontró $(printf '%s; ' "${fallas[@]}")"
NTFY_URL="$(grep -E '^NTFY_URL=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
NTFY_TOPIC="$(grep -E '^NTFY_TOPIC=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
NTFY_TOKEN="$(grep -E '^NTFY_TOKEN=' "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2- || true)"
if [ -n "$NTFY_URL" ] && [ -n "$NTFY_TOPIC" ] && [ -n "$NTFY_TOKEN" ]; then
    curl -fsS -H "Authorization: Bearer $NTFY_TOKEN" -H "Title: IA CENTRAL - chequeo de despliegue" -d "$msg" "$NTFY_URL/$NTFY_TOPIC" >/dev/null 2>&1 || true
fi

exit 1
