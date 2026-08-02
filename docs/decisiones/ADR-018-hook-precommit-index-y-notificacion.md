# ADR-018 - Hook de pre-commit para integridad de INDEX.md y notificación de fallos de auditoría vía ntfy autohospedado

Fecha: 2026-08-02
Estado: Aceptada

## Contexto

La verificación (d) agregada a `scripts/adr_audit.sh` (ver enmienda a ADR-014) detecta si `docs/decisiones/INDEX.md` queda desactualizado respecto a los archivos reales, pero solo corre una vez por semana y de forma pasiva: escribe el resultado en `/home/fernando/adr-audit.log`, un archivo que nadie monitorea activamente. Un `INDEX.md` roto podía quedar así hasta 7 días sin que nadie se enterara, y aun después de la corrida semanal la señal quedaba enterrada en un log que hay que abrir a propósito.

Además, `ADR_AUDIT_STATUS=OK|FAILED` solo refleja si la llamada a `claude -p` se ejecutó sin errores (timeout, CLI caído), no si el contenido de la auditoría encontró discrepancias reales. Una corrida que sí detecta una DISCREPANCIA terminaba igual con `ADR_AUDIT_STATUS=OK` — el hallazgo quedaba solo en el texto del resumen, sin marca grepeable que lo distinguiera de una corrida limpia.

Para la notificación se evaluó primero ntfy.sh público (sin cuenta, sin infraestructura propia) como opción interina, mismo criterio que ADR-005 usó para rclone/Google Drive. Se descartó: expone el mecanismo a un tercero cuya disponibilidad y políticas no controla el proyecto, y el tópico como único control de acceso es seguridad por oscuridad — cualquiera que lo adivine puede leer y publicar notificaciones falsas. Este proyecto ya rechazó un trade-off equivalente en ADR-012 (OpenRouter vs. LiteLLM autohospedado); se prioriza la misma consistencia acá.

## Decisión

Hook de pre-commit real a nivel de Git (`.githooks/pre-commit`, versionado, activado con `git config core.hooksPath .githooks` — un paso manual por clon): bloquea (exit 1) cualquier commit que toque `docs/decisiones/` si `INDEX.md` no coincide exactamente con los archivos `ADR-*.md` reales del directorio (archivo sin indexar, entrada sin archivo real, o ambos). A diferencia del hook `PreToolUse` de ADR-007 (que solo corre dentro de una sesión de Claude Code), este es un hook nativo de Git: se aplica a cualquier commit, sea de Claude Code, de Fernando directamente, o de cualquier otra herramienta — mismo espíritu de ADR-006, donde ya se estableció que un bloqueo atado a una sola herramienta no es hermético.

ntfy se autohospeda como servicio de `docker-compose.yml` (imagen oficial `binwiederhier/ntfy`, pineada a `v2.26.3` — no `latest`, mismo criterio que LiteLLM en ADR-012), expuesto vía Nginx+Certbot en el subdominio `ntfy.aicentral.network` (mismo patrón que ADR-003), con autenticación habilitada mediante un token dedicado de solo publicación — no depende de la oscuridad del nombre del tópico.

Marca de estado del contenido de la auditoría. `scripts/adr_audit.sh` termina su prompt pidiendo una línea grepeable adicional, `ADR_CONTENT_STATUS=CLEAN|DISCREPANCIES_FOUND`, independiente de `ADR_AUDIT_STATUS`. Si `ADR_AUDIT_STATUS=FAILED`, `ADR_CONTENT_STATUS=DISCREPANCIES_FOUND`, o la marca esperada no aparece (`UNKNOWN` — en sí mismo una falla silenciosa a señalar), se dispara una notificación autenticada a la instancia propia de ntfy. El mensaje es genérico, nunca el contenido real del hallazgo — el detalle se sigue leyendo del log.

## Alternativas descartadas

- **ntfy.sh público**: descartado por consistencia con ADR-012 y porque oscuridad no es autenticación real.
- **Email vía SMTP**: requiere cuenta/relay dedicado y más superficie de configuración para una alerta de texto corta, semanal en el peor caso. Descartado, mismo criterio que ADR-010.
- **Servir ntfy bajo un subpath de `aicentral.network` en vez de subdominio propio**: evita un registro DNS nuevo, pero el soporte de WebSocket/SSE de ntfy está pensado para dominio o subdominio raíz — agrega fragilidad de configuración para ahorrarse un registro DNS que Fernando ya controla en su registrador. Descartado por relación costo/beneficio.
- **Confiar solo en el hook `PreToolUse` de Claude Code (ADR-007) para bloquear `INDEX.md` desactualizado**: descartado por la misma razón que ADR-006 ya documentó — solo cubre comandos que pasan por la tool `Bash` de una sesión de Claude Code.
- **Bloquear el commit si `ADR_CONTENT_STATUS=DISCREPANCIES_FOUND` en vez de solo notificar**: descartado — esa auditoría mira hacia atrás, sobre estado ya commiteado; no hay nada que bloquear en ese momento, corresponde avisar y corregir en un commit posterior.

## Consecuencias

- Nueva pieza en el stack: contenedor `ntfy`, subdominio y certificado TLS adicional, token de autenticación en `.env` (no versionado).
- Requirió un registro DNS nuevo (`ntfy.aicentral.network` → IP del VPS) antes de que Certbot pudiera emitir el certificado — paso manual de Fernando en su registrador (Spaceship), no una dependencia nueva de un tercero.
- Esta pieza queda reutilizable por cualquier otro mecanismo del proyecto que necesite avisar a Fernando, no solo `adr_audit.sh` — registrada como tal en `docs/DEPENDENCIAS.md` (ADR-019).
- `git config core.hooksPath .githooks` es un paso manual por clon (VPS y máquina local de Fernando). Si un commit sobre `docs/decisiones/` no se bloquea cuando debería, lo primero a revisar es si ese paso se corrió en ese clon.
- El hook agrega fricción real y deliberada: editar `docs/decisiones/` sin actualizar `INDEX.md` bloquea el commit hasta corregirlo — mismo trade-off que ADR-007 ya aceptó.
- Mismo criterio de mantenimiento que cualquier servicio propio: la versión pineada se actualiza manual y deliberadamente (ver política general en ADR-019).
- Esta ADR no resuelve el mismo defecto de fondo en `scripts/memory_audit.sh` (ADR-008), que también solo mide si la CLI corrió, no si encontró algo relevante, y no notifica nada. Queda fuera de alcance por ahora, candidato a una decisión futura si se decide aplicar la misma lógica ahí.
- **`ntfy` sí publica un puerto** (`127.0.0.1:2586` → `80` del contenedor), a diferencia de LiteLLM (ADR-012), que no publica ninguno. La diferencia es quién necesita alcanzar cada servicio: a LiteLLM solo lo consumen otros contenedores (`web`/orquestador) por la red interna de Docker; a `ntfy` lo necesita alcanzar Nginx, que corre en el host, fuera de Docker (ADR-003), y no tiene forma de entrar a la red interna de Docker. El puerto se limita a `127.0.0.1` (no `0.0.0.0`, mismo patrón que ya usa `web`): alcanzable por Nginx en el mismo host, sin exponerse directo a la interfaz pública — el único camino desde internet sigue siendo vía Nginx con TLS.
