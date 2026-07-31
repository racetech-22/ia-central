# ADR-006 - Límites del `deny` por patrón de comando en `.claude/settings.json`

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

Se agregó `.claude/settings.json` (ver commit correspondiente) con reglas `deny` para bloquear la lectura de `.env`/`.env.*` por parte de Claude Code: `Read(./.env)`, `Read(./.env.*)` y `Bash(cat *.env*)`. La intención explícita era que fuera imposible leer los secretos reales, sin depender del criterio de Claude en cada sesión.

Al verificarlo intentando activamente leer `.env` por distintas vías:

- `Read` sobre `.env` → bloqueado correctamente.
- `Bash: cat .env` → bloqueado correctamente.
- `Bash: head -1 .env` → también bloqueado.
- `Bash: python3 -c "print(open('.env').read())"` → **no bloqueado**. Imprimió `DJANGO_SECRET_KEY` y `POSTGRES_PASSWORD` reales en la conversación durante la propia verificación (que luego se rotaron, ver commit posterior).

## Decisión

Se documenta explícitamente que las reglas `deny` de tipo `Bash(patrón)` en `.claude/settings.json` son un bloqueo de **patrón de texto del comando**, no un bloqueo de acceso al archivo en sí. Cualquier comando que no matchee literalmente el patrón configurado (`python3`, `node`, `less`, `grep`, `awk`, `sed`, `od`, `base64`, etc.) puede leer igual el contenido del archivo. Ampliar la lista de patrones bloqueados no cierra el problema de fondo: es una lista de denegación de comandos, inherentemente incompleta contra la superficie arbitraria de un shell.

La protección que sí sería hermética (`sandbox.credentials.files` con `mode: "deny"`, que opera a nivel de sandbox de filesystem del proceso, no de texto del comando) requiere `bwrap` (bubblewrap) instalado en el VPS — no está instalado, y agregarlo implica habilitar sandboxing de Bash para todo el proyecto, un cambio de alcance mayor que agregar una regla a `settings.json`.

Se acepta esta limitación por ahora. La defensa real contra la exposición de `.env` no es el `deny` de `settings.json` (que es una mitigación parcial y honesta, no una garantía), sino que **solo Fernando tiene acceso SSH a este VPS**. Mientras esa condición se mantenga, el riesgo de que estos secretos se filtren fuera de una sesión de Claude Code (que ya corre con el mismo usuario del sistema y podría en principio leer cualquier archivo al que ese usuario tenga acceso) es bajo — el `deny` reduce la probabilidad de una lectura accidental/rutinaria, no la hace matemáticamente imposible.

## Alternativas descartadas

- **Ampliar `Bash(deny)` con más patrones** (`head`, `less`, `grep`, `python3 -c *`, `node -e *`, etc.): reduce la superficie pero no la cierra — sigue siendo una lista incompleta contra cualquier construcción de shell no anticipada (`dd`, `exec 3<`, heredocs, etc.). Se descarta como solución, aunque no hay nada malo en agregar patrones puntuales si se quiere subir el costo de un desvío accidental.
- **Instalar `bwrap` y habilitar `sandbox.enabled` + `sandbox.credentials.files`**: es la solución técnicamente correcta, pero es un cambio de infraestructura de mayor alcance (afecta cómo corren todos los comandos Bash del proyecto, no solo el acceso a `.env`) que no se implementa en esta ADR. Queda como opción futura si se decide invertir en sandboxing real.
- **No documentar el hallazgo y confiar en que no vuelva a pasar**: descartado — el punto de este proyecto (ADR-001, principio de verificación) es no tratar como resuelto algo que no se verificó. Ya se verificó, y el resultado real es que es una mitigación parcial.

## Consecuencias

- `.claude/settings.json` se mantiene tal cual (no se amplía el `deny` como parte de esta ADR): sigue bloqueando la tool `Read` (esto sí es efectivo) y el patrón `cat` más obvio por Bash, sin pretender ser una garantía absoluta.
- La seguridad real de `.env` en este VPS depende de que el acceso SSH quede limitado a Fernando. Si en algún momento se agrega otro usuario/colaborador con acceso al VPS, esta ADR queda obsoleta y hay que revisar si conviene invertir en `bwrap`/sandboxing real en ese momento.
- Si se quiere subir el nivel de protección sin esperar a Fase 5, la opción más barata es ampliar la lista de patrones `Bash(deny)` (mitigación parcial adicional); la opción robusta es instalar `bwrap` y habilitar sandboxing de filesystem.
