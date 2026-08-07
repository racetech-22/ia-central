# ADR-033 - Modelo de datos de Chat con Consultor y Ejecutor separados

Fecha: 2026-08-07
Estado: Aceptada

## Contexto

La enmienda 2026-08-06 a ADR-025, punto 4, dejó esto explícitamente abierto: *"falta decidir si un Chat abarca turnos de ambos roles con un identificador común, o si son sesiones/históricos separados correlacionados por Chat"*. Está registrado en `docs/estado.yml` como `modelo_datos_chat_consultor_ejecutor`.

**Hallazgo de esta sesión, que cambia la naturaleza del trabajo.** `apps/sala/models.py` se construyó el 2026-08-04 (`pilar1_modelo_datos`), dos días antes de esa enmienda, y quedó armado sobre el modelo que la enmienda da de baja: `EntradaSesion.subpath` documenta `"subagents/agent-{id}" para el ejecutor sub-agente`, `SolicitudPermiso` calca los campos de `ToolPermissionContext` del SDK, y `Chat.session_id` asume una sola sesión por chat. `docs/estado.yml` marcaba la pieza como `construido` sin ninguna salvedad.

Verificado en vivo el 2026-08-07 antes de decidir nada: `Chat`, `EntradaSesion` y `SolicitudPermiso` tienen **cero filas**; `Proyecto` tiene una sola, proveniente de la migración de siembra `0002_seed_ia_central_proyecto.py`, no de uso real. Fuera de `models.py` y las migraciones, el único archivo del repo que los referencia es `apps/sala/admin.py`. Consecuencia: se corrige sin migrar datos y sin romper nada aguas abajo.

**Corrección explícita a lo que se afirmó antes en esta misma sesión**: se dijo que `EntradaSesion` había que rehacerla. Es inexacto. La enmienda 2026-08-06 mantiene al Consultor sobre `orchestrator.run(...)` — o sea el Claude Agent SDK (ADR-012) —; el que salió del SDK es el Ejecutor. Una tabla espejo del `SessionStore` del SDK sigue siendo válida para el historial del Consultor. Lo que muere no es la tabla, es usar `subpath` para alojar al Ejecutor como sub-agente.

## Decisión

1. **Historiales separados, correlacionados por Chat — no un identificador común.** El motivo es consecuencia directa de ADR-030: el contenedor del Ejecutor se recicla (al terminar el trabajo, por inactividad, o si se cae), y cada reciclado abre una sesión nueva del agente. Un mismo Chat atraviesa entonces **N sesiones de Ejecutor y una sola conversación de Consultor**. Un identificador común no puede representar esa cardinalidad sin inventarle un mecanismo aparte. Lo que el Director ve —una sola ventana con los dos roles intercalados— se resuelve ordenando por fecha al renderizar: es presentación, no almacenamiento.

2. **`Chat`**: el campo `session_id` pasa a llamarse `consultor_session_id`. El nombre a secas era ambiguo desde el momento en que hay dos roles. Suma `agente` y `modelo` (la elección es por chat, ADR-030 punto 1, habilitada por el catálogo de ADR-027) y `rama` (el trabajo se commitea a una rama propia del chat, ADR-030 punto 6).

3. **`SesionEjecutor`, tabla nueva**: FK a Chat, `acp_session_id`, `slot` (cuál de los N Ejecutores de población fija tiene asignado, nulo mientras espera turno), `estado` (`en_cola` / `activa` / `terminada` / `caducada` — `en_cola` existe porque ADR-030 acepta explícitamente que los chats esperen turno cuando no hay slot libre), `iniciada_en`, `terminada_en`.

   **Esta tabla ES la tabla de asignaciones** que ADR-030 punto 5 y ADR-031 punto 5 dieron por existente sin definirla. No son dos tablas: asignar un Ejecutor a un chat y abrir una sesión de Ejecutor son el mismo hecho.

   Dos reglas de integridad que se declaran en la base, no se confían al código: a lo sumo una sesión `activa` por `slot`, y a lo sumo una sesión `activa` por `chat` (ADR-030 punto 1: un Ejecutor por chat).

4. **El `session_epoch` de ADR-025 §9.4 deja de ser un campo.** Ese protocolo necesitaba un epoch para caducar solicitudes de permiso pendientes cuando el proceso del destino moría. Con esta tabla, **cada fila de `SesionEjecutor` es el epoch**: al reciclarse el contenedor se cierra la fila y se abre otra, y todo lo pendiente que apunte a la fila vieja caduca por construcción. Un concepto del protocolo desaparece porque el modelo de datos lo absorbe.

5. **`EntradaSesion` se conserva** como historial del Consultor, corrigiendo el comentario de `subpath` para que deje de describir al Ejecutor como sub-agente. Ver la corrección del Contexto.

6. **`Proyecto` no se toca.** La enmienda 2026-08-06 marca sus fundamentos como sobrevivientes (puntos 5, 6 generalizado, y 8).

## Alcance

Cierra la estructura de `modelo_datos_chat_consultor_ejecutor`. **No cierra** dos cosas que dependen de verificar la especificación de ACP v1 en vivo, y que por eso van juntas en un paso aparte:

- Dónde se persiste el historial de conversación **del Ejecutor** (los mensajes del agente ACP, no los del Consultor).
- El rediseño de `SolicitudPermiso` sobre los campos reales de `session/request_permission` v1 — decisión abierta `esquema_solicitud_permiso_v1`, que sigue abierta después de esta ADR.

`SolicitudPermiso` queda por ahora tal como está, con sus campos del SDK: se lo deja explícitamente marcado como pendiente de rediseño en vez de tocarlo a medias.

## Alternativas descartadas

- **Un identificador común para los turnos de ambos roles**: descartada por el motivo del punto 1 — no expresa que un Chat atraviese varias sesiones de Ejecutor, cardinalidad que ADR-030 introdujo el mismo día.
- **Tabla de asignaciones separada de la de sesiones de Ejecutor**: descartada por el punto 3 — serían dos tablas con el mismo ciclo de vida y la misma clave, que habría que mantener sincronizadas sin ganar nada.
- **Rehacer `EntradaSesion`**: descartada tras la corrección del Contexto — el Consultor sigue sobre el SDK, la tabla sigue siendo correcta para su historial.
- **Registrar en `SesionEjecutor` con qué agente y modelo corrió realmente cada sesión**: no se agrega ahora, para no diseñar de más. Queda anotado en Consecuencias porque va a hacer falta.

## Consecuencias

- **Se corrige un desvío entre código construido y decisiones vigentes.** El código del 2026-08-04 quedó dos días después desalineado con la enmienda a ADR-025, y `docs/estado.yml` siguió marcando la pieza como `construido` sin salvedad. Se corrige en el mismo commit, sin marca de desvío intermedia, porque las tablas estaban vacías y la corrección llega en la misma sesión que el hallazgo.
- **Queda expuesto un hueco de verificación que este proyecto todavía no cubre.** Hoy hay chequeo determinista de que los archivos declarados existan (ADR-029), de que INDEX.md coincida con los archivos reales (ADR-018) y de que ARQUITECTURA.md §6 coincida con las ADR (ADR-032). **Nada verifica que el código ya construido siga coincidiendo con las decisiones vigentes**, que es exactamente cómo pasó esto. Es la misma familia de hueco, un nivel más abajo y bastante más difícil de automatizar — no se resuelve acá, se registra.
- **Falta registrar con qué agente+modelo corrió cada sesión**, que es lo que va a necesitar `metrica_comparacion_agente_modelo` (decisión abierta de ADR-027). Hoy la elección vive en `Chat`; si cambia a mitad de un chat, no queda rastro de con qué corrió cada sesión. Anotado a propósito, no omitido.
- **`apps/sala/admin.py` se actualiza** en el mismo commit: es el único consumidor existente de estos modelos.
- **Migraciones sobre tablas vacías**: no hay migración de datos. La fila sembrada de `Proyecto` debe sobrevivir intacta, y eso se verifica, no se supone.
- **Construido, no pendiente**, a diferencia de ADR-030 y ADR-031: esta ADR se acepta junto con su implementación y su verificación. Si la verificación no pasa, no se commitea.
