# ADR-009 - El agente de Cowork no puede alcanzar la red del VPS

Fecha: 2026-07-31
Estado: Aceptada

## Contexto

Al evaluar cómo arrancar la Fase 3 (conectores activos: MCP Django, MCP local, Agent SDK, Claude Code — ver ARQUITECTURA.md §5), surgió la pregunta de si el agente de Cowork (Claude en el navegador/desktop, en su modo Cowork) podía operar directamente sobre el VPS de IA CENTRAL vía acceso remoto (SSH), como una forma rápida de tener ejecución "autónoma" sin todavía haber construido la capa de orquestación descrita en ARQUITECTURA.md §2.

Para probarlo se creó un usuario `claude-agent` en el VPS específicamente para este test, y se intentó alcanzar el servidor desde el sandbox de ejecución de Cowork por varias vías: SSH, y `curl` directo a la IP pública del VPS en los puertos 22 y 443. Todos los intentos fallaron, con errores de tipo "Network is unreachable" o "blocked-by-allowlist".

## Decisión

Se confirma que el sandbox de ejecución de Cowork corre detrás de un proxy con allowlist de dominios: bloquea cualquier conexión a una IP o puerto arbitrario que no esté en esa lista permitida, incluyendo SSH (puerto 22) y HTTPS directo a una IP (puerto 443) en vez de un dominio. No hay ninguna forma de que ese agente alcance la red del VPS de esta manera.

Como consecuencia directa, se descarta darle acceso directo al VPS al agente de Cowork. El usuario `claude-agent` creado para la prueba se eliminó del VPS.

Se decide que la ejecución autónoma real de Fase 3 tiene que vivir como proceso nativo *dentro* del VPS — el agente construido sobre el Claude Agent SDK corriendo persistente en el servidor mismo, con sus conectores MCP propios (ver ARQUITECTURA.md §2, capa de orquestación) — y no como acceso remoto disparado desde el sandbox de Cowork. Cowork puede seguir siendo útil para tareas puntuales que sí caen dentro de lo que su sandbox permite (por ejemplo, trabajar contra el repo en GitHub), pero no como mecanismo de ejecución continua sobre la infraestructura de IA CENTRAL.

## Alternativas descartadas

- **Agregar el dominio/IP del VPS a alguna allowlist configurable de Cowork**: no hay control de ese lado — el propio VPS no tiene forma de "pedir" que Cowork lo agregue a su allowlist; es una restricción del lado del sandbox de Cowork, no del servidor. Descartado por no ser algo que se pueda resolver desde IA CENTRAL.
- **Exponer el VPS de otra forma que sí pase por dominio/HTTPS** (por ejemplo, un endpoint HTTP en `aicentral.network` que Cowork sí pudiera alcanzar, en vez de SSH directo): no se probó a fondo, pero aunque funcionara, seguiría siendo acceso remoto disparado desde un sandbox ajeno con su propio ciclo de vida (se pierde entre sesiones, como ya se documentó para las rutinas de Cowork/sesión en general) — no resuelve el problema de fondo de necesitar un proceso persistente. Se prioriza directamente la arquitectura ya decidida en ARQUITECTURA.md §2.
- **No documentar el hallazgo porque "ya se sabía" que la arquitectura iba a ser un proceso en el VPS**: descartado — el punto de probarlo fue justamente verificar si había un atajo viable antes de invertir en construir el proceso nativo, y vale la pena dejar registrado que se probó y no funcionó, para no repetir la prueba más adelante sin memoria de por qué se descartó.

## Consecuencias

- Fase 3 arranca sin atajos: hay que construir el proceso de orquestación (Claude Agent SDK) corriendo en el propio VPS, con sus conectores MCP, tal como ya establece ARQUITECTURA.md §2 — esta ADR no cambia esa arquitectura, la confirma después de haber probado la alternativa más simple y descartarla.
- No queda ningún usuario ni credencial de la prueba en el VPS (el usuario `claude-agent` se eliminó); no hay limpieza pendiente de este experimento.
- Si en el futuro cambia el comportamiento del sandbox de Cowork (por ejemplo, si Anthropic agrega soporte para acceso a redes arbitrarias), esta ADR quedaría obsoleta y valdría la pena reevaluar — pero no hay que asumir eso por defecto.
