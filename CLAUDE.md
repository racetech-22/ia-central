# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado del proyecto

Skeleton de Django creado (arranque de Fase 2 de la hoja de ruta, ver ARQUITECTURA.md §5): proyecto `core/` funcional, empaquetado con Docker, corriendo contra Postgres. Primera app propia bajo `apps/`: `adminpanel` (branding del admin de Django + `StatusNote` como modelo mínimo de ejemplo) — el panel administrativo real de ARQUITECTURA.md §4 es Fase 5, no confundir con esta app placeholder. Todavía no hay conectores en `mcp_servers/` (eso es Fase 3). No hay entorno virtual local ni Django instalado fuera de Docker — todo el desarrollo se hace vía `docker compose`.

Apps nuevas van en `apps/<nombre>/` y se registran en `INSTALLED_APPS` de `core/settings.py` como `"apps.<nombre>"` (ver `apps.adminpanel` como referencia).

### Comandos comunes

```bash
cp .env.example .env          # solo la primera vez; completar SECRET_KEY/POSTGRES_PASSWORD reales
docker compose build web      # reconstruir la imagen tras cambiar requirements.txt
docker compose up             # levantar db + web (http://localhost:8000)
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py createsuperuser
docker compose run --rm web python manage.py check
docker compose run --rm web python manage.py test              # cuando existan tests
docker compose run --rm web python manage.py collectstatic --noinput   # necesario tras cambiar estáticos; Nginx los sirve directo en prod (ver ADR-003)
docker compose down           # bajar los contenedores (los datos persisten en el volumen postgres_data)
```

En el VPS de producción, `.env` (no versionado) tiene `DJANGO_DEBUG=False` y valores reales de `DJANGO_SECRET_KEY`/`POSTGRES_PASSWORD` — nunca copiar `.env.example` tal cual encima del `.env` de producción.

No hay todavía un linter/formatter configurado (ni pre-commit, ni ruff/black en requirements.txt) — si se agrega uno, actualizar esta sección con el comando exacto.

### Rutina de mantenimiento (cron del sistema, no rutinas de sesión)

Ambos jobs son cron del sistema operativo (`crontab -l` del usuario `fernando`, sin sudo) — a propósito, no rutinas de sesión de Claude Code (`CronCreate`), que se pierden en cuanto termina la sesión que las creó.

- **Diario, 03:00** — `scripts/backup_postgres.sh` (ver ADR-004): `pg_dump` + gzip a `/home/fernando/backups/postgres/` (fuera del repo, 14 días de retención) y sync a Google Drive vía `rclone` (implementación **interina**, ver ADR-005 — a reemplazar cuando exista el panel administrativo de Fase 5). Deja marcas `BACKUP_STATUS=OK|FAILED` / `RCLONE_STATUS=OK|FAILED|SKIPPED` en `backup.log`, exit code 0/1/2 según qué falló.
- **Mensual, día 1 a las 04:15** — `scripts/memory_audit.sh`: corre `claude -p` en modo no interactivo (`--allowedTools "Read,Glob,Grep"`, sin permiso de escritura — solo lee, nunca modifica ni borra memoria) pidiéndole que revise la auto-memoria de este proyecto (qué hay guardado, si algo está duplicado o desactualizado respecto al repo) y deja el resultado en `/home/fernando/memory-audit.log`, con `AUDIT_STATUS=OK|FAILED` al final de cada corrida.

Para correr cualquiera de los dos a mano: `bash scripts/backup_postgres.sh` o `bash scripts/memory_audit.sh` desde la raíz del repo.

### Reconectar a esta sesión de trabajo en el VPS

En el VPS, el alias `iac` (definido en `~/.bashrc`) reabre o adjunta la sesión de tmux donde corre `claude --continue` dentro de `~/ia-central`:

```bash
alias iac='tmux new-session -A -s iacentral -c ~/ia-central "claude --continue"'
```

Es la forma recomendada de retomar el trabajo sin perder contexto de conversación ni tener que reexplicar el estado del proyecto.

### Permisos de Claude Code en este repo (`.claude/settings.json`)

Este archivo está versionado (a diferencia de `.claude/settings.local.json`, que es personal y no se sube) y define qué puede hacer Claude Code sin pedir confirmación, qué necesita confirmación siempre, y qué tiene bloqueado de forma dura:

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": ["Bash(docker compose *)", "Bash(docker volume ls)", "Bash(git status)", "Bash(git diff *)", "Bash(git commit -m *)"],
    "ask": ["Bash(git push *)"],
    "deny": ["Read(./.env)", "Read(./.env.*)", "Bash(cat *.env*)"]
  }
}
```

- **`$schema`**: solo referencia para autocompletar/validar en el editor, no tiene efecto en tiempo de ejecución.
- **`allow`**: operaciones que corren sin pedir permiso cada vez.
  - `Bash(docker compose *)`: cualquier subcomando de `docker compose` (`up`, `build`, `run`, `exec`, `logs`, `down`, etc.) sin preguntar.
  - `Bash(docker volume ls)`: match exacto, solo listar volúmenes (no `docker volume rm` ni otros subcomandos).
  - `Bash(git status)`: match exacto.
  - `Bash(git diff *)`: `git diff` con cualquier argumento.
  - `Bash(git commit -m *)`: crear commits con mensaje sin preguntar. Ojo: esto **no** cubre `git add` (sigue pidiendo permiso aparte) ni `git push`.
- **`ask`**: siempre pide confirmación, sin importar otras reglas.
  - `Bash(git push *)`: todo push (a cualquier rama/remoto) requiere confirmación explícita cada vez.
- **`deny`**: bloqueo duro — Claude no puede ejecutar esto ni con confirmación del usuario.
  - `Read(./.env)` / `Read(./.env.*)`: la tool `Read` no puede abrir `.env` ni variantes (`.env.local`, `.env.production`, etc.). Ojo: `.env.example` también matchea `.env.*` y queda bloqueado para `Read`, aunque solo tiene placeholders — no es un problema de seguridad, pero puede ser molesto si hace falta inspeccionarlo (usar `git show HEAD:.env.example` como alternativa).
  - `Bash(cat *.env*)`: bloquea específicamente el comando `cat` sobre rutas que contengan `.env`.

**Verificado el 2026-07-31 intentando leer los secretos reales** (ver también CHANGELOG.md):
- `Read` sobre `.env` → bloqueado correctamente ("File is in a directory that is denied by your permission settings").
- `Bash: cat .env` → bloqueado correctamente.
- `Bash: head -1 .env` → también bloqueado.
- **Una invocación alternativa de shell fuera del patrón bloqueado → NO bloqueada**, imprimió el contenido real completo de `.env` (incluyendo las credenciales) en la conversación de esa verificación.

Conclusión importante (documentada en detalle en ADR-006): las reglas `deny` de tipo `Bash(cat *.env*)` bloquean patrones de comando literales, no el acceso al archivo en sí — cualquier otra forma de leerlo por shell que no matchee ese patrón exacto (una invocación alternativa fuera del patrón bloqueado) puede saltárselo. El bloqueo verdaderamente "imposible" (a nivel de sandbox de filesystem, no de patrón de comando) requeriría `sandbox.credentials.files` con `mode: "deny"` y `sandbox.enabled: true` — pero esta VPS no tiene `bwrap` (bubblewrap) instalado, que es requisito para el sandbox de filesystem en Linux, así que esa vía no está disponible sin instalarlo primero. Por ahora, `deny` en este archivo es una mitigación parcial (bloquea la tool `Read` por completo, y el intento más obvio por Bash), no una garantía absoluta contra todo comando de shell posible — la defensa real hoy es que solo Fernando tiene acceso SSH a este VPS.

### Hook `PreToolUse` contra comandos destructivos (`.claude/hooks/block-destructive-db.sh`)

`.claude/settings.json` también registra un hook `PreToolUse` (matcher `Bash`) que corre `.claude/hooks/block-destructive-db.sh` antes de cada comando Bash. A diferencia del `deny` de arriba, esto sí es un bloqueo determinista de verdad (exit 2 aborta el tool call) — ver ADR-007. Bloquea:

- `docker compose down` con `-v`/`--volumes` (borra el volumen de Postgres).
- `docker volume rm`/`docker volume prune` mencionando el volumen de Postgres (`ia-central_postgres_data`/`postgres_data`).
- `DROP DATABASE` / `DROP TABLE` en cualquier parte del comando.
- `rm` apuntando a `/home/fernando/backups` (o `~/backups`).

Probado con casos sintéticos (pipe directo al script) y en vivo con tool calls reales de Bash (`docker volume rm ia-central_postgres_data` y `docker compose down -v`, ambos abortados antes de ejecutarse). Como con ADR-006, la lista de patrones no es exhaustiva por diseño — si aparece una nueva forma de borrar el volumen o la base, hay que agregar la regla al script.

## Qué es IA CENTRAL

Un agente orquestador con memoria persistente y verificada — no un chatbot — pensado para desarrollar, administrar y modificar todos los proyectos de Fernando (locales y en varios servidores), explotando múltiples IAs (Claude, modelos vía Ollama, otras de pago) según tarea/costo/disponibilidad, y aprendiendo de sus interacciones solo cuando ese conocimiento pasa por verificación explícita.

Dos condiciones no negociables guían cualquier decisión de diseño (ADR-001):

1. **Portable**: todo debe poder transferirse por completo a otro servidor sin perder base de conocimiento ni funcionalidad.
2. **Verificable**: el conocimiento auto-generado por el sistema nunca se trata como válido por defecto; debe pasar por el pipeline captura → verificación (cruce de fuentes o confirmación de Fernando) → promoción antes de considerarse "conocimiento confirmado".

## Arquitectura en tres capas (ver ARQUITECTURA.md)

- **Orquestación**: agente construido sobre el Claude Agent SDK, corriendo como proceso persistente en el VPS, decide qué hacer y a qué IA/herramienta delegar.
- **Conocimiento**: memoria de largo plazo independiente del servidor físico — base vectorial (pgvector sobre Postgres, o Qdrant) para RAG, más ADRs/documento maestro versionados en Git. Incluye el pipeline de verificación obligatorio descrito arriba.
- **Ejecución**: los conectores que dan poder real sobre el mundo — MCP server propio del proyecto Django, MCP/SSH hacia la estación local de Fernando (Tailscale/WireGuard), MCP/SSH de solo lectura por defecto hacia otros servidores existentes de Fernando (no se escribe ahí sin decisión explícita), Claude Code como motor de desarrollo, y un router de modelos (LiteLLM u OpenRouter) para no acoplar el core a un proveedor específico.

Cualquier función de auto-aprendizaje que se implemente debe cubrir las tres etapas del pipeline (captura, verificación, promoción) antes de considerarse completa — es una consecuencia directa de ADR-001, no opcional.

## Infraestructura (ver ADR-002)

- VPS nuevo y dedicado en Contabo, exclusivo para IA CENTRAL — nunca reutilizar los VPS existentes de Fernando que ya corren otros proyectos en producción.
- Todo el stack se empaqueta con Docker + Docker Compose, de forma que migrar de servidor sea `docker compose up` más restore de datos.
- Repo GitHub público (`ia-central`, era privado hasta el 2026-07-31 — ver ADR-011), clonado igual en el VPS y en la máquina local de Fernando, sincronizado por Git — es la fuente de verdad versionada.
- Acceso a los demás servidores de Fernando: solo lectura por defecto vía MCP/SSH; no se otorga escritura sin decisión explícita.

## Cómo mantener la documentación (importante para cualquier tarea en este repo)

- `ARQUITECTURA.md` es el documento maestro y fuente de verdad: se actualiza cada vez que se toma una decisión de arquitectura relevante.
- Toda decisión importante se registra además como ADR individual en `docs/decisiones/` (formato: Contexto / Decisión / Alternativas descartadas / Consecuencias), no solo como una línea en ARQUITECTURA.md.
- `CHANGELOG.md` registra en orden cronológico todas las decisiones y avances relevantes.
- Cuando cambies ARQUITECTURA.md o agregues/edites una ADR, también hay que actualizar CHANGELOG.md en el mismo cambio, y recordarle a Fernando que debe subir la versión vigente a los archivos del proyecto "IA CENTRAL" en Claude para que conversaciones futuras arranquen con el contexto completo.
- No dupliques contenido entre README.md, ARQUITECTURA.md y las ADRs: el README es el punto de entrada, ARQUITECTURA.md es la fuente de verdad completa, y las ADRs contienen el razonamiento detrás de cada decisión puntual.

## Memoria entre sesiones

Al cerrar cada tarea o fase de trabajo, evalúa brevemente si algo de lo ocurrido (una preferencia expresada, un límite operativo descubierto) vale la pena guardar en memoria antes de seguir — no esperes a que se pida explícitamente con `/memory`.

## Fuente de verdad en vivo desde GitHub (ADR-011)

Cualquier sesión con acceso a fetch web o shell (Cowork, claude.ai con búsqueda, Claude Code) debe leer en vivo `README.md`/`CLAUDE.md`/`ARQUITECTURA.md`/`CHANGELOG.md`/`docs/decisiones/ADR-*.md` desde `https://raw.githubusercontent.com/racetech-22/ia-central/master/<path>`, en vez de depender de Knowledge/Files subidos a mano o copias en Drive (se desactualizan en cada commit).

Dos capas de caché independientes a tener en cuenta (ver enmienda en ADR-011):
- Agregar siempre un parámetro único a la URL (`?v=<sha-del-commit-o-timestamp>`) — evita que la propia herramienta de fetch reuse una respuesta ya cacheada dentro de la sesión (verificado: al menos la de Cowork deduplica por URL exacta hasta 900s).
- Aun así, el CDN de GitHub puede tardar hasta ~5 minutos en reflejar un push recién hecho, y el query param no evita esto (verificado: el CDN ignora el query string para su propio caché). Un fetch que responde 200 no garantiza que sea el último commit — si se acaba de pushear algo, esperar un par de minutos antes de asumirlo.

## Metodología de trabajo con Fernando (cualquier sesión: Cowork, Claude Desktop, Claude Code)

- Antes de responder cualquier pregunta o iteración, indicar explícitamente qué modelo de Claude (Sonnet 5 / Opus 5 / Fable 5) es el más adecuado para esa respuesta.
- Trabajar en iteraciones de un solo paso: proponer o ejecutar una sola cosa a la vez y esperar el comentario/confirmación de Fernando antes de continuar con la siguiente — no solo en infraestructura, sino en cualquier tipo de tarea o decisión.
- Ser proactivo dando opiniones y sugerencias técnicas propias e independientes en cada iteración, incluso cuando contradigan la idea inicial de Fernando o no vayan a agradarle — nunca responder de forma evasiva tipo "depende".
