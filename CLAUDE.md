# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado del proyecto

Skeleton de Django creado (arranque de Fase 2 de la hoja de ruta, ver ARQUITECTURA.md §5): proyecto `core/` funcional, empaquetado con Docker, corriendo contra Postgres. Primera app propia bajo `apps/`: `adminpanel` (branding del admin de Django + `StatusNote` como modelo mínimo de ejemplo) — el panel administrativo real de ARQUITECTURA.md §4 es Fase 5, no confundir con esta app placeholder. Todavía no hay conectores en `mcp_servers/` (eso es Fase 3). No hay entorno virtual local ni Django instalado fuera de Docker — todo el desarrollo se hace vía `docker compose`.

Apps nuevas van en `apps/<nombre>/` y se registran en `INSTALLED_APPS` de `core/settings.py` como `"apps.<nombre>"` (ver `apps.adminpanel` como referencia).

### Comandos comunes

```bash
cp env.example .env          # solo la primera vez; completar SECRET_KEY/POSTGRES_PASSWORD reales
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

En el VPS de producción, `.env` (no versionado) tiene `DJANGO_DEBUG=False` y valores reales de `DJANGO_SECRET_KEY`/`POSTGRES_PASSWORD` — nunca copiar `env.example` tal cual encima del `.env` de producción.

No hay todavía un linter/formatter configurado (ni pre-commit, ni ruff/black en requirements.txt) — si se agrega uno, actualizar esta sección con el comando exacto.

### Rutina de mantenimiento (cron del sistema, no rutinas de sesión)

Los tres jobs son cron del sistema operativo (`crontab -l` del usuario `fernando`, sin sudo) — a propósito, no rutinas de sesión de Claude Code (`CronCreate`), que se pierden en cuanto termina la sesión que las creó.

- **Diario, 03:00** — `scripts/backup_postgres.sh` (ver ADR-004): `pg_dump` + gzip a `/home/fernando/backups/postgres/` (fuera del repo, 14 días de retención) y sync a Google Drive vía `rclone` (implementación **interina**, ver ADR-005 — a reemplazar cuando exista el panel administrativo de Fase 5). Deja marcas `BACKUP_STATUS=OK|FAILED` / `RCLONE_STATUS=OK|FAILED|SKIPPED` en `backup.log`, exit code 0/1/2 según qué falló.
- **Mensual, día 1 a las 04:15** — `scripts/memory_audit.sh`: corre `claude -p` en modo no interactivo (`--allowedTools "Read,Glob,Grep"`, sin permiso de escritura — solo lee, nunca modifica ni borra memoria) pidiéndole que revise la auto-memoria de este proyecto (qué hay guardado, si algo está duplicado o desactualizado respecto al repo) y deja el resultado en `/home/fernando/memory-audit.log`, con `AUDIT_STATUS=OK|FAILED` al final de cada corrida.
- **Semanal, domingos a las 04:45** — `scripts/adr_audit.sh` (ver ADR-014): corre `claude -p` en modo no interactivo (`--allowedTools "Read,Glob,Grep"`, sin permiso de escritura — solo lee, nunca modifica ni borra nada) verificando que las `docs/decisiones/ADR-*.md` digan la verdad sobre el estado real del repo, que `docs/decisiones/INDEX.md` coincida con los archivos reales, y que cada ADR sea internamente coherente consigo misma (referencias "punto N"/"§N"/"ADR-NNN" y conteos en palabras que describan listas propias del mismo documento). Deja el resultado en `/home/fernando/adr-audit.log`, con `ADR_AUDIT_STATUS=OK|FAILED` (si la llamada a `claude -p` corrió sin error) y `ADR_CONTENT_STATUS=CLEAN|DISCREPANCIES_FOUND` (si encontró algo) al final de cada corrida.

Para correr cualquiera de los tres a mano: `bash scripts/backup_postgres.sh`, `bash scripts/memory_audit.sh` o `bash scripts/adr_audit.sh` desde la raíz del repo.

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
  - `Read(./.env)` / `Read(./.env.*)`: la tool `Read` no puede abrir `.env` ni variantes (`.env.local`, `.env.production`, etc.). La plantilla de ejemplo se llama `env.example` (sin punto inicial, ver ADR-006) precisamente para no matchear este wildcard ni el de `Bash(cat *.env*)` — es pública (el repo es público desde ADR-011) y no tiene ningún secreto real, así que bloquear su lectura no protegía nada y solo generaba fricción.
  - `Bash(cat *.env*)`: bloquea específicamente el comando `cat` sobre rutas que contengan `.env`.

**Verificado el 2026-07-31 intentando leer los secretos reales** (ver también CHANGELOG.md):
- `Read` sobre `.env` → bloqueado correctamente ("File is in a directory that is denied by your permission settings").
- `Bash: cat .env` → bloqueado correctamente.
- `Bash: head -1 .env` → también bloqueado.
- **Una invocación alternativa de shell fuera del patrón bloqueado → NO bloqueada**, imprimió el contenido real completo de `.env` (incluyendo las credenciales) en la conversación de esa verificación.

Conclusión importante (documentada en detalle en ADR-006): las reglas `deny` de tipo `Bash(cat *.env*)` bloquean patrones de comando literales, no el acceso al archivo en sí — cualquier otra forma de leerlo por shell que no matchee ese patrón exacto (una invocación alternativa fuera del patrón bloqueado) puede saltárselo. El bloqueo verdaderamente "imposible" (a nivel de sandbox de filesystem, no de patrón de comando) requeriría `sandbox.credentials.files` con `mode: "deny"` y `sandbox.enabled: true` — pero esta VPS no tiene `bwrap` (bubblewrap) instalado, que es requisito para el sandbox de filesystem en Linux, así que esa vía no está disponible sin instalarlo primero. Por ahora, `deny` en este archivo es una mitigación parcial (bloquea la tool `Read` por completo, y el intento más obvio por Bash), no una garantía absoluta contra todo comando de shell posible — la defensa real hoy es que solo Fernando tiene acceso SSH a este VPS.

**Otro gap del mismo tipo, encontrado el 2026-08-04 (ver también CHANGELOG.md)**: `docker compose config` (y en general cualquier comando que interpole variables de entorno para mostrar su resultado — no solo de `.env`, sino cualquier secreto que Docker Compose sustituya) puede volcar secretos reales en texto plano en su salida, sin que ningún `deny` actual de este archivo lo cubra (esas reglas apuntan a `.env`/`cat`, no a comandos que interpolan y muestran valores ya resueltos). Pasó en vivo: un `docker compose config` seguido de un `tail` sobre su salida imprimió `POSTGRES_PASSWORD` en texto plano en la conversación, motivando una rotación de esa credencial. Regla a partir de ahora: la salida de `docker compose config` (o cualquier comando equivalente que interpole entorno) se redirige siempre a un archivo, nunca se muestra completa (nada de `cat`/`tail`/`head` sin filtrar sobre ella) — para inspeccionarla, filtrar con `grep` por lo que no sea el valor (nombre de servicio, presencia/ausencia de una variable, cantidad de líneas que matchean un patrón), o limitarse a reportar el exit code.

### Hook `PreToolUse` contra comandos destructivos (`.claude/hooks/block-destructive-db.sh`)

`.claude/settings.json` también registra un hook `PreToolUse` (matcher `Bash`) que corre `.claude/hooks/block-destructive-db.sh` antes de cada comando Bash. A diferencia del `deny` de arriba, esto sí es un bloqueo determinista de verdad (exit 2 aborta el tool call) — ver ADR-007. Bloquea:

- `docker compose down` con `-v`/`--volumes` (borra el volumen de Postgres).
- `docker volume rm`/`docker volume prune` mencionando el volumen de Postgres (`ia-central_postgres_data`/`postgres_data`).
- `DROP DATABASE` / `DROP TABLE` en cualquier parte del comando.
- `rm` apuntando a `/home/fernando/backups` (o `~/backups`).

Probado con casos sintéticos (pipe directo al script) y en vivo con tool calls reales de Bash (`docker volume rm ia-central_postgres_data` y `docker compose down -v`, ambos abortados antes de ejecutarse). Como con ADR-006, la lista de patrones no es exhaustiva por diseño — si aparece una nueva forma de borrar el volumen o la base, hay que agregar la regla al script.

### Hook de pre-commit de Git para integridad de `docs/decisiones/INDEX.md` (`.githooks/pre-commit`)

A diferencia del hook `PreToolUse` de arriba (que solo corre dentro de Claude Code), este es un hook nativo de Git — bloquea cualquier commit, de cualquier origen, que toque `docs/decisiones/` si `INDEX.md` no coincide exactamente con los archivos `ADR-*.md` reales. Ver ADR-018.

Requiere activación manual una vez por clon (no viaja con `git clone`): `git config core.hooksPath .githooks`. Si un commit sobre `docs/decisiones/` no se bloquea cuando debería, o se bloquea inesperadamente en un clon nuevo (VPS o máquina local), lo primero a revisar es si este paso se corrió ahí.

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
- Repo GitHub público (`ia-central`, era privado hasta el 2026-07-31 — ver ADR-011), clonado en el VPS y sincronizado por Git — es la fuente de verdad versionada. No se mantiene un clon adicional en la máquina local de Fernando (ver enmienda 2026-08-02 a ADR-002): GitHub + VPS ya son dos copias completas con historia íntegra, y un clon local sin disciplina de `git pull` regular sería un riesgo de desactualización silenciosa, no una protección real.
- Acceso a los demás servidores de Fernando: solo lectura por defecto vía MCP/SSH; no se otorga escritura sin decisión explícita.

## Cómo mantener la documentación (importante para cualquier tarea en este repo)

- `ARQUITECTURA.md` es el documento maestro y fuente de verdad: se actualiza cada vez que se toma una decisión de arquitectura relevante.
- Toda decisión importante se registra además como ADR individual en `docs/decisiones/` (formato: Contexto / Decisión / Alternativas descartadas / Consecuencias), no solo como una línea en ARQUITECTURA.md.
- `CHANGELOG.md` registra en orden cronológico todas las decisiones y avances relevantes.
- Cuando cambies ARQUITECTURA.md o agregues/edites una ADR, también hay que actualizar CHANGELOG.md en el mismo cambio. **No hace falta subir nada a los archivos del proyecto "IA CENTRAL" en Claude**: ADR-011 estableció que esas copias estáticas se desactualizan en cada commit y que toda sesión debe leer en vivo desde GitHub. Esta instrucción decía lo contrario hasta el 2026-08-06, anterior a ADR-011 y nunca actualizada — si una sesión futura encuentra una copia en Knowledge o en Drive, es un artefacto viejo, no una fuente.
- No dupliques contenido entre README.md, ARQUITECTURA.md y las ADRs: el README es el punto de entrada, ARQUITECTURA.md es la fuente de verdad completa, y las ADRs contienen el razonamiento detrás de cada decisión puntual.
- **Convención de tiempo verbal en las ADR** (ver ADR-014): el presente ("se agrega", "existe", "corre") se reserva para artefactos que ya existen en el repo en el momento de escribir la ADR — algo verificable ahí mismo. Cualquier afirmación sobre un artefacto que todavía no está implementado debe marcarse explícitamente como pendiente y con la fase que corresponde, ej. `**Pendiente (Fase 3):** agregar LiteLLM a docker-compose.yml`. Esto es lo que distingue una ADR verificable de una que afirma cosas no hechas — el problema detectado dos veces el 2026-08-01 (ADR-011 con una instrucción que nunca se agregó a CLAUDE.md, y ADR-012 con LiteLLM en `docker-compose.yml` descrito en presente sin estar implementado).
- `docs/DEPENDENCIAS.md` (ver ADR-019) se actualiza en el mismo commit que se agregue, cambie de versión, o se retire cualquier herramienta o servicio externo del que dependa el sistema — incluidos los que no son software instalado en el VPS (registrador, DNS).
- `docs/estado.yml` (fuente estructurada del mapa de ruta, ver ADR-029; renderizada en `/mapa/` para superusuarios por `apps/adminpanel/views.py` + `apps/adminpanel/templates/adminpanel/mapa.html`, que ya no se editan a mano) se actualiza en el mismo commit que cualquier cambio que altere el estado de una pieza — igual que ARQUITECTURA.md y CHANGELOG.md. `.githooks/pre-commit` bloquea el commit si el esquema no cierra, si alguna ADR referenciada no existe, o si a una pieza `construido` le falta algún artefacto declarado. Es un resumen estructurado, no una fuente de verdad: si contradice a ARQUITECTURA.md o a una ADR, manda la ADR y hay que corregir `docs/estado.yml`.

## Memoria entre sesiones

Al cerrar cada tarea o fase de trabajo, evalúa brevemente si algo de lo ocurrido (una preferencia expresada, un límite operativo descubierto) vale la pena guardar en memoria antes de seguir — no esperes a que se pida explícitamente con `/memory`.

## Fuente de verdad en vivo desde GitHub (ADR-011)

Cualquier sesión con acceso a fetch web o shell (Cowork, claude.ai con búsqueda, Claude Code) debe leer en vivo `README.md`/`CLAUDE.md`/`ARQUITECTURA.md`/`CHANGELOG.md`/`docs/decisiones/ADR-*.md`/`docs/decisiones/INDEX.md`/`docs/estado.yml`, en vez de depender de Knowledge/Files subidos a mano o copias en Drive (se desactualizan en cada commit).

**`docs/estado.yml` (ADR-029) reemplaza reconstruir el estado leyendo ADR una por una — la práctica de antes de esa ADR.** Da, en un solo archivo, el estado de cada pieza (construido/disenado/pendiente) y las decisiones abiertas. Piso mínimo al arrancar una sesión: ese archivo más solo las ADR del tema puntual de la tarea — queda permitido de forma expresa no abrir el resto, no hace falta un recorrido general.

**Excepción que no se relaja: ARQUITECTURA.md §6 (el resumen de una línea por ADR) se lee siempre, esté o no la tarea relacionada con arquitectura.** Es el único índice barato de conexiones cruzadas entre decisiones — lo que permite detectar que algo nuevo rompe una condición de una ADR vieja de tema aparentemente ajeno. No es redundante con `docs/estado.yml`: ese archivo da estado de piezas, no las condiciones/cláusulas de invalidación que cruzan ADR entre sí.

**Al introducir un actor, capacidad o componente nuevo, revisar las ADR cuya línea de §6 mencione una condición o una cláusula de invalidación** — una ADR puede quedar invalidada por algo que no es su tema. Evidencia real: el 2026-08-07, ADR-028 (Ejecutor) disparó la cláusula de invalidación del punto 3 de ADR-017 (condicionada a que ninguna tool permita lectura arbitraria del filesystem), conexión que ya era visible en la propia línea de ADR-017 en §6.

**Protocolo de dos pasos, anclado a un SHA — no a `?v=` sobre la rama** (ver enmienda 2026-08-03 a ADR-011; el `?v=` quedó reemplazado, no complementado: el CDN de GitHub puede ignorar el query string para su cache key y fallar en silencio):

1. Pedir `https://api.github.com/repos/racetech-22/ia-central/commits/master` para el SHA real del HEAD.
2. Pedir cada archivo vía `https://raw.githubusercontent.com/racetech-22/ia-central/<SHA>/<path>`, con ese SHA exacto — nunca el nombre de rama. El contenido de un SHA fijo es inmutable, no hace falta cache-busting adicional.

**Los nombres de archivo de las ADR no son deducibles** (`ADR-NNN.md` es incorrecto, cada una lleva slug — ver ADR-011 enmienda 2026-08-02). Resolver el nombre real primero en `docs/decisiones/INDEX.md`, con el mismo protocolo. Sin navegador y sin poder leer `INDEX.md`, no asumir un nombre — reportar el bloqueo.

**Cowork no puede ejecutar el paso 1 en solitario** (`api.github.com` le devuelve vacío, ver ADR-011 enmiendas 2026-08-06/2026-08-07). Si Claude Code corre en paralelo en la misma sesión, este sí alcanza `api.github.com`: le pasa el SHA completo a Cowork, que ancla directo a `raw.githubusercontent.com/<SHA>/<path>` sin nada más — reemplaza la mitigación de abajo, no se suma a ella. Solo con Cowork aislado (sin Claude Code disponible): releer cada archivo con un query string distinto antes de confiar en una ADR con estado "En progreso" o enmiendas recientes — mitigación imperfecta, no garantía.

## Metodología de trabajo con Fernando (cualquier sesión: Cowork, Claude Desktop, Claude Code)

- Antes de responder cualquier pregunta o iteración, indicar explícitamente qué modelo de Claude (Sonnet 5 / Opus 5 / Fable 5) es el más adecuado para esa respuesta.
- Trabajar en iteraciones de un solo paso: proponer o ejecutar una sola cosa a la vez y esperar el comentario/confirmación de Fernando antes de continuar con la siguiente — no solo en infraestructura, sino en cualquier tipo de tarea o decisión.
- Ser proactivo dando opiniones y sugerencias técnicas propias e independientes en cada iteración, incluso cuando contradigan la idea inicial de Fernando o no vayan a agradarle — nunca responder de forma evasiva tipo "depende".
- Aplicar por defecto, en cualquier tarea (de esta o cualquier sesión) y sin esperar a que se pida, esta lógica: al cerrar un gap de verificación o automatización, revisar si ese mismo tipo de gap se repite en otro lado del proyecto — mecanismos que dependen de que alguien se acuerde de mirar un log, convenciones documentadas pero no forzadas por código, marcas de estado que miden "el proceso corrió" en vez de "el resultado es el esperado", dependencias externas no registradas en ningún lado. Señalarlo explícitamente aunque no se haya pedido, y resolverlo si es de bajo riesgo; si no, dejarlo anotado como pendiente concreto, no como duda genérica.
