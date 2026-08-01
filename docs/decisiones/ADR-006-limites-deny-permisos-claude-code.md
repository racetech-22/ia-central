# ADR-006 - Límites del `deny` por patrón de comando en `.claude/settings.json`

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

Se agregó `.claude/settings.json` (ver commit correspondiente) con reglas `deny` para bloquear la lectura de `.env`/`.env.*` por parte de Claude Code: `Read(./.env)`, `Read(./.env.*)` y `Bash(cat *.env*)`. La intención explícita era que fuera imposible leer los secretos reales, sin depender del criterio de Claude en cada sesión.

Al verificarlo intentando activamente leer `.env` por distintas vías:

- `Read` sobre `.env` → bloqueado correctamente.
- `Bash: cat .env` → bloqueado correctamente.
- `Bash: head -1 .env` → también bloqueado.
- Una invocación alternativa de shell fuera del patrón bloqueado → **no bloqueada**. Imprimió el contenido real de `.env` (incluyendo las credenciales) en la conversación durante la propia verificación (que luego se rotaron, ver commit posterior).

## Decisión

Se documenta explícitamente que las reglas `deny` de tipo `Bash(patrón)` en `.claude/settings.json` son un bloqueo de **patrón de texto del comando**, no un bloqueo de acceso al archivo en sí. Cualquier comando que no matchee literalmente el patrón configurado puede leer igual el contenido del archivo mediante una invocación alternativa de shell. Ampliar la lista de patrones bloqueados no cierra el problema de fondo: es una lista de denegación de comandos, inherentemente incompleta contra la superficie arbitraria de un shell.

La protección que sí sería hermética (`sandbox.credentials.files` con `mode: "deny"`, que opera a nivel de sandbox de filesystem del proceso, no de texto del comando) requiere `bwrap` (bubblewrap) instalado en el VPS — no está instalado, y agregarlo implica habilitar sandboxing de Bash para todo el proyecto, un cambio de alcance mayor que agregar una regla a `settings.json`.

Se acepta esta limitación por ahora. La defensa real contra la exposición de `.env` no es el `deny` de `settings.json` (que es una mitigación parcial y honesta, no una garantía), sino que **solo Fernando tiene acceso SSH a este VPS**. Mientras esa condición se mantenga, el riesgo de que estos secretos se filtren fuera de una sesión de Claude Code (que ya corre con el mismo usuario del sistema y podría en principio leer cualquier archivo al que ese usuario tenga acceso) es bajo — el `deny` reduce la probabilidad de una lectura accidental/rutinaria, no la hace matemáticamente imposible.

## Alternativas descartadas

- **Ampliar `Bash(deny)` con más patrones**: reduce la superficie pero no la cierra — sigue siendo una lista incompleta contra cualquier construcción de shell no anticipada. Se descarta como solución, aunque no hay nada malo en agregar patrones puntuales si se quiere subir el costo de un desvío accidental.
- **Instalar `bwrap` y habilitar `sandbox.enabled` + `sandbox.credentials.files`**: es la solución técnicamente correcta, pero es un cambio de infraestructura de mayor alcance (afecta cómo corren todos los comandos Bash del proyecto, no solo el acceso a `.env`) que no se implementa en esta ADR. Queda como opción futura si se decide invertir en sandboxing real.
- **No documentar el hallazgo y confiar en que no vuelva a pasar**: descartado — el punto de este proyecto (ADR-001, principio de verificación) es no tratar como resuelto algo que no se verificó. Ya se verificó, y el resultado real es que es una mitigación parcial.

## Consecuencias

- `.claude/settings.json` se mantiene tal cual (no se amplía el `deny` como parte de esta ADR): sigue bloqueando la tool `Read` (esto sí es efectivo) y el patrón `cat` más obvio por Bash, sin pretender ser una garantía absoluta.
- La seguridad real de `.env` en este VPS depende de que el acceso SSH quede limitado a Fernando. Si en algún momento se agrega otro usuario/colaborador con acceso al VPS, esta ADR queda obsoleta y hay que revisar si conviene invertir en `bwrap`/sandboxing real en ese momento.
- Si se quiere subir el nivel de protección sin esperar a Fase 5, la opción más barata es ampliar la lista de patrones `Bash(deny)` (mitigación parcial adicional); la opción robusta es instalar `bwrap` y habilitar sandboxing de filesystem.

## Enmienda (2026-08-01): `.env.example` renombrado a `env.example`, no excepción en el `deny`

El wildcard `Read(./.env.*)` también matchea `.env.example` (que no tiene ningún secreto real, solo placeholders) — esto obligaba a escribir en ese archivo a ciegas, sin poder leerlo antes con la tool `Read` (necesaria para usar `Edit`), con el riesgo de duplicar secciones o romper el formato sin detectarlo. Además, desde ADR-011 el repo es público: `.env.example` está versionado y es legible por cualquiera en GitHub, así que bloquear su lectura local no protegía nada — beneficio de seguridad cero por ese costo operativo.

Se evaluó (y se descartó) estrechar el `deny` a una lista explícita de variantes de `.env` con secretos reales (`.env.local`, `.env.production`, etc.), dejando `.env.example` fuera. Se descartó porque convierte un wildcard general en una lista de denegación no exhaustiva — exactamente la misma clase de limitación que esta ADR ya documentó como problema para `Bash(deny)`: cualquier variante `.env.<algo>` futura no anticipada en la lista quedaría sin cubrir.

**Decisión final: renombrar el archivo de `.env.example` a `env.example`** (sin punto inicial). La cadena `"env.example"` no contiene `".env"` como subcadena, así que deja de matchear tanto `Read(./.env.*)` como `Bash(cat *.env*)` — ambos wildcards quedan intactos y siguen cubriendo cualquier `.env.<algo>` futuro sin necesidad de anticiparlo ni mantener una lista. Un solo cambio resuelve las dos reglas.

**Costo aceptado**: se pierde la convención de nombre habitual del ecosistema `dotenv` (`.env.example`). Se actualizaron las referencias existentes (README.md, CLAUDE.md, `core/settings.py`, y la excepción `!.env.example` en `.gitignore`, que quedó sin sentido y se eliminó). Verificado con `grep` en todo el repo que no quedó ninguna referencia colgante al nombre anterior en documentación o código vivo (las menciones en CHANGELOG.md anteriores a este cambio se dejan tal cual, como registro histórico de lo que se hizo en su momento).
