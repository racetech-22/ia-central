# ADR-034 - Historial del Ejecutor y esquema de SolicitudPermiso sobre ACP v1

Fecha: 2026-08-08
Estado: Aceptada

## Contexto

ADR-033 cerró la estructura de Chat y sesiones, y dejó dos cosas explícitamente fuera de alcance por depender de verificar ACP v1 en vivo: dónde se persiste el historial de conversación del Ejecutor, y el rediseño de `SolicitudPermiso` sobre los campos reales de `session/request_permission` (decisión abierta `esquema_solicitud_permiso_v1`). Esta ADR cierra las dos.

Verificado el 2026-08-08 contra `https://agentclientprotocol.com/protocol/v1/tool-calls.md` y `https://agentclientprotocol.com/protocol/v1/prompt-turn.md`, no contra las notas del 2026-08-06. Lo registrado entonces sobre la forma de `session/request_permission` (`sessionId`, referencia al `toolCall`, lista de `options` con `optionId`/`name`/`kind`) sigue siendo correcto. Tres hechos que aquellas notas no capturaron y que sí cambian el diseño:

1. **La respuesta no es una aprobación, es la elección de una opción.** Verbatim del resultado: `{"outcome": {"outcome": "selected", "optionId": "allow-once"}}`. El agente ofrece N opciones y el Cliente devuelve cuál eligió el usuario. Un booleano aprobado/denegado no representa eso.

2. **El pedido de permiso no transporta los detalles de la operación.** Solo el `toolCallId`. El `title`, el `kind` y el `content` de esa operación llegaron antes por `session/update`, y sus actualizaciones son parciales — verbatim: *"All fields except `toolCallId` are optional in updates."* Sin haber ido acumulando esos updates, la sala no tiene con qué mostrarle al Director qué está autorizando.

3. **`cancelled` es obligación del Cliente, y no es lo mismo que caducar.** Verbatim: *"The Client **MUST** respond to all pending `session/request_permission` requests with the `cancelled` outcome"* al cancelar un turno. El timeout de ADR-025 §9.4 y el reciclado del Ejecutor de ADR-030 son causas distintas de la cancelación de un turno.

Confirmado de paso que `usage_update` existe y transporta `used`/`size` y un `cost` opcional con `amount` y `currency` — el dato que ADR-027 daba por disponible para comparar combinaciones agente+modelo.

## Decisión

1. **`ActualizacionSesion`: log append-only de las notificaciones `session/update` del Ejecutor**, con el `payload` guardado tal cual y el discriminador `sessionUpdate` en un campo de texto libre, no en un conjunto cerrado de valores. Mismo criterio que ADR-025 punto 7 aplicó al Consultor: no se le inventa un esquema de "Mensaje" a algo que el protocolo ya define, y un tipo de update nuevo en la especificación no puede romper la ingesta.

2. **`LlamadaHerramienta`: proyección mutable de los tool calls**, con constraint de unicidad por `(sesion, tool_call_id)`. Existe además del log por dos razones del punto 2 del Contexto: los tool calls cambian de estado a lo largo de su vida y sus updates son parciales, y la solicitud de permiso los referencia por `toolCallId` sin traer sus datos. Reconstruir el estado actual de una llamada reproduciendo el log en cada pantalla de aprobación sería frágil y lento justo en el momento en que el Director tiene que decidir.

3. **`SolicitudPermiso` se reescribe y cuelga de la llamada, no del Chat.** Guarda las `opciones` ofrecidas por el agente tal como llegaron y la `opcion_elegida`, en vez de un estado aprobado/denegado. Se eliminan `tool_name`, `tool_input`, `title`, `display_name`, `description` y `agent_id`: los cuatro primeros quedan cubiertos por `LlamadaHerramienta` y los dos últimos venían de `ToolPermissionContext` del SDK, que la enmienda 2026-08-06 a ADR-025 dio de baja. Los estados `cancelada` y `caducada` se mantienen separados por el punto 3 del Contexto, y `motivo_cierre` existe para que el Director vea por qué se cerró una solicitud en vez de encontrarse con una zombi — mismo criterio que ADR-025 §9.4.

4. **La sala muestra todas las opciones que ofrece el agente, incluidas `allow_always` y `reject_always`, con tres condiciones.**

   Esto **corrige** la posición inicial del Consultor en esta misma sesión, que proponía ocultarlas. El argumento era evitar un segundo lugar donde se otorgan permisos; es incorrecto, porque ese lugar ya existe: el prompt de terminal de Claude Code ya ofrece "no preguntar de nuevo" y se usa a diario. La sala **reemplaza** ese prompt (ADR-025 punto 1), no agrega una superficie nueva, y quitarle la opción sería degradar el flujo actual. El costo de aprobar cada repetición no es neutro: lleva a aprobar sin leer, que es peor que el riesgo que se quería evitar.

   Las tres condiciones:

   - **El alcance otorgado se muestra siempre.** Lo que hace segura la opción de Claude Code no es la opción, es que dice exactamente qué alcanza (`git pull *`, no "todo"). Un "siempre" sin alcance visible sí queda prohibido.
   - **Lo recordado vive en la configuración del propio agente, nunca en una tabla de la sala.** Un solo lugar donde consultar qué está permitido; la sala transmite la decisión, no lleva memoria paralela de permisos.
   - **El hook de ADR-007 es piso.** Ningún "siempre" puede levantar un bloqueo determinista del hook.

## Alcance

Cierra `esquema_solicitud_permiso_v1` y el historial del Ejecutor. **No cierra** `verificacion_permisos_por_agente` (ADR-025), que además de lo que ya listaba gana un punto nuevo: verificar, por cada agente del catálogo, si persiste realmente el `allow_always` en su propia configuración o lo guarda en memoria y lo pierde al reiniciar. Para Claude Code se sabe que escribe en su archivo de permisos; para el resto del catálogo no se verificó.

No decide la pantalla de aprobación en sí (Fase 5 / `pilar1_sala_navegador`), solo qué datos tiene disponibles para dibujarla.

## Alternativas descartadas

- **Guardar solo el log append-only, sin proyección de tool calls**: descartada por el punto 2 — obligaría a reproducir el log para saber el estado de una llamada en el momento exacto en que hay que mostrar una aprobación.
- **Guardar solo la proyección, sin log**: descartada — se perdería todo lo que no es tool call (`agent_message_chunk`, `plan`, `usage_update`) y cualquier tipo de update que la especificación agregue después.
- **Mantener `aprobado`/`denegado` como estados y mapear las opciones a uno de los dos**: descartada por el punto 1 del Contexto — el agente puede ofrecer opciones que no caen limpio en ese binario, y el mapeo perdería qué se ofreció realmente.
- **Ocultar `allow_always`/`reject_always`**: descartada, ver punto 4 — es la corrección de la propuesta inicial del Consultor.
- **Un conjunto cerrado de valores para el tipo de update**: descartada por el punto 1 — ataría la ingesta a la versión de la especificación leída hoy.

## Consecuencias

- **`SolicitudPermiso` deja de servir al Consultor.** Cuelga de una llamada del Ejecutor, y el Consultor corre sobre `orchestrator.run(...)`, cuya política de seguridad es su lista fija de tools (ADR-015): no necesita aprobaciones interactivas. Si algún día el Consultor gana capacidades más anchas, esta decisión hay que revisarla — queda dicho, no implícito.
- **Volumen de escritura**: el log append-only crece con cada notificación, incluidos los chunks de texto en streaming. No se define acá política de retención ni de poda; es un pendiente real que va a aparecer con el uso.
- **Nada de esto está conectado todavía.** Son tablas: no hay cliente ACP que las escriba (ADR-031, pendiente), ni pantalla que las lea (`pilar1_sala_navegador`, pendiente). Se construyen ahora porque el diseño ya está verificado y porque ADR-033 las dejó como la pieza que faltaba del modelo.
- **Sobre `usage_update`**: `ActualizacionSesion` ya lo va a guardar sin trabajo adicional, lo que deja materia prima para `metrica_comparacion_agente_modelo` (ADR-027) sin haberla diseñado todavía.
- **Construido, no pendiente**, mismo criterio que ADR-032 y ADR-033: se acepta junto con su implementación y su verificación. Si la verificación no pasa, no se commitea.
