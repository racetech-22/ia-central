# ADR-027 — Interfaz del rol ejecutor: Agent Client Protocol (ACP)

Fecha: 2026-08-06
Estado: **En progreso** (idea en desarrollo, no una decisión cerrada — segunda ADR del repo con ese estado, junto a ADR-025)

> **Advertencia de estado.** Este documento registra una dirección técnica que se está discutiendo en el momento de escribirlo, para que no se pierda el razonamiento ni las fuentes verificadas. **No es la decisión definitiva.** Se espera cerrarla en breve, y hasta entonces nada de acá debe tratarse como acordado ni usarse para justificar código.

## Contexto

ADR-024 fijó que el rol ejecutor de la sala es Claude Code, y ADR-025 diseñó el puente de permisos sobre `can_use_tool` del Claude Agent SDK. Al planificar la implementación surgió una pregunta de Fernando: si Claude Code puede trabajar con modelos que no sean de Anthropic.

Verificado contra la documentación oficial de Claude Code (`code.claude.com/docs/en/third-party-integrations`): **no**. Todas las vías de despliegue son modelos Claude — Anthropic directo, Amazon Bedrock, Google Cloud Agent Platform, Microsoft Foundry, Claude Platform on AWS. Lo que esa documentación llama "LLM Gateway" (`ANTHROPIC_BASE_URL` y variantes) sirve para centralizar autenticación, límites de tasa y seguimiento de costos, no para cambiar de familia de modelo; las variables de pineado son `ANTHROPIC_DEFAULT_OPUS_MODEL`, `SONNET`, `HAIKU` y `FABLE`, todas Claude.

Eso choca de frente con el principio de ADR-012 (independencia de proveedor) y con la posición expresada por Fernando de no quedar atado a ninguna empresa. ADR-012 ya resolvió ese problema para el **modelo**, dejando el SDK detrás de una interfaz interna propia (`orchestrator.run(...)`). El **ejecutor** no tiene equivalente: entraría acoplado.

## Dirección encaminada

**La interfaz del rol ejecutor debería ser el Agent Client Protocol (ACP), no un envoltorio propio.**

ACP es un estándar abierto que hace para los agentes de código lo que LSP hizo para los servidores de lenguaje. Verbatim de su documentación oficial: *"ACP solves this by providing a standardized protocol for agent-editor communication, similar to how the Language Server Protocol (LSP) standardized language server integration"*, y nombra explícitamente el problema que motivó esta ADR: *"Developer lock-in: choosing an agent often means accepting their available interfaces."*

Existen adaptadores ACP publicados para Claude Code (`claude-agent-acp`), Codex (`codex-acp`), Amp (`amp-acp`) y Pi (`pi-acp`), más un registro de agentes que implementan el protocolo. Un agente nuevo que hable ACP entraría sin tocar la sala.

Consecuencia directa sobre la sala: el selector de ejecutor y modelo por iteración se vuelve viable con tres ejes independientes — qué agente ACP, qué modelo, y con qué modo de permisos. **Pendiente (Fase 3):** nada de esto está implementado; la sala todavía no tiene ni el consumer de navegador.

## Alternativas evaluadas

- **OpenHands** (MIT, SDK Python nativo, modelos vía convención LiteLLM): descartado como interfaz principal. Su propia documentación advierte *"No hard-deny at the analyzer boundary"* — sus analizadores de seguridad clasifican riesgo pero no bloquean — y su modo headless *"always approves"*. Frente al hook `PreToolUse` de ADR-007, que aborta de forma determinista, sería un retroceso en garantías. Detrás hay además una empresa comercial: MIT protege del bloqueo legal, no de que la dirección del proyecto siga intereses de producto.
- **Goose como interfaz** (Apache 2.0, gobernanza de la Agentic AI Foundation): no descartado, pero no es la interfaz. Goose es una implementación que ya habla ACP y expone `goose serve` con endpoint `/acp` sobre TLS. Sirve como implementación de referencia y candidato de uso, no como dependencia obligatoria. Adoptar Goose *en vez de* ACP sería cambiar una dependencia por otra.
- **Envoltorio propio del ejecutor** (una interfaz interna nuestra, al estilo de `orchestrator.run(...)` de ADR-012): descartado mientras exista ACP. Escribir un protocolo propio cuando ya hay un estándar con adaptadores publicados es trabajo que después habría que mantener y reconciliar.

## Advertencias verificadas

Ninguna de estas es motivo para descartar la dirección, pero todas deben pesar en la decisión final:

- **ACP remoto está incompleto.** Su documentación dice: *"Full support for remote agents is a work in progress."* Lo maduro hoy es el modo local, como subproceso por stdio con JSON-RPC. Para proyectos externos (ADR-025 §9) esto importa y hay que reevaluarlo.
- **La integración de Goose con Claude Code por CLI está deprecada.** Su documentación marca los providers `claude-code`, `codex` y `gemini-cli` como *"kept for backward compatibility only"*, reemplazados por los providers ACP. Cualquier diseño que se apoye en la vía CLI nace obsoleto.
- **Los providers ACP de Goose todavía no soportan reanudar ni bifurcar sesión**, según su propia documentación de limitaciones. Choca con el modelo de sesiones de ADR-025 punto 7 y hay que verificarlo antes de comprometerse.
- **Cada adaptador exige su CLI instalado y autenticado** en la máquina donde corre. No elimina la dependencia de cada proveedor: la vuelve intercambiable.

## Enmienda 2026-08-06: catálogo verificado, ejes del selector, y correcciones de razonamiento

Sigue **En progreso** — esta enmienda incorpora hallazgos y decisiones parciales, no cierra la decisión. Surgió al discutir una ampliación de la idea original: que el ejecutor no sea un agente fijo sino un catálogo de agentes de código, con la sala sugiriendo cuál usar en cada iteración según complejidad y costo, y qué modelo. Todo lo que sigue se verificó en vivo contra `agentclientprotocol.com` el 2026-08-06 — ninguna afirmación de esta sección se apoya en conocimiento previo.

**Correcciones de razonamiento previo**

Van primero, y se registran como correcciones, no como hallazgos nuevos:

1. Se sostuvo que Cursor, Cline y Qoder pertenecían al rol de cliente (editores), y por lo tanto no eran candidatos a ejecutor. Es incorrecto. Los tres figuran en el registro oficial de agentes ACP con CLI en modo agente. Un producto puede ocupar los dos roles: editor para su propio usuario, y agente ACP invocable por otro cliente. Queda anotado porque el error habría recortado el catálogo sin fundamento.
2. Se planteó a Goose como coordinador del ejecutor. Es incorrecto y contradice el diseño: en ACP el coordinador es el **cliente**, rol que ocupa la sala de IA CENTRAL; Goose es un **agente**, o sea un ejecutor más. Si Goose coordinara, la sala perdería `session/request_permission`, que es método baseline del cliente y donde se apoya la garantía de ADR-006/ADR-007. Esta ADR ya había descartado a Goose como interfaz ("adoptar Goose en vez de ACP sería cambiar una dependencia por otra"); queda reafirmado.
3. Se sostuvo que, apuntados al mismo modelo vía LiteLLM, los agentes del catálogo se vuelven casi equivalentes. Es incorrecto, y lo desmiente la propia ADR-012, que ya había identificado que el esfuerzo real de un bucle de agente está en compactación de contexto, recuperación de errores de tools, fiabilidad en corridas largas, interrupción y reanudación. Los agentes difieren de forma sustantiva en andamiaje, política de edición (diff contra reescritura de archivo), estrategia de contexto del repositorio (indexación contra lectura bajo demanda) y herramientas expuestas. La objeción la planteó Fernando y era correcta.
4. Se propuso ocultar `docs/decisiones/` al ejecutor para proteger el razonamiento acumulado. Se descarta por contraproducente: el valor del repo es que el ejecutor trabaje *con* el contexto de las decisiones tomadas; uno sin acceso a las ADR va a proponer cosas que las contradicen, y ese costo es inmediato y seguro en cada iteración, mientras que el riesgo del que protegía es difuso. La propuesta fue del Consultor (ver enmienda de ADR-024) y era incorrecta.
5. Se afirmó en el punto "Principio de protección" de esta misma enmienda (commit `381a7fc`): *"Implementable con ACP sin piezas nuevas: `fs/read_text_file`, `fs/write_text_file` y los métodos de terminal son del cliente, así que la sala decide qué entrega."* Es incorrecto para agentes locales, verificado en vivo el 2026-08-06: `fs/*`/`terminal/*` son capability opcional que declara el Cliente, no una restricción sobre cómo el Agente accede al disco por su cuenta — y ACP v2 directamente elimina esa superficie, citando que *"many Agents are moving toward their own sandboxing and execution configuration instead"* (`rfds/v2/client-filesystem-terminal-capabilities.md`). Un agente local (`claude-agent-acp` incluido) puede tocar archivos y shell directamente, sin pasar por esos métodos. No hay exclusión de secretos lograble sin piezas nuevas. Análisis completo y candidato de reemplazo (aislamiento de proceso a nivel de sistema operativo) en la enmienda 2026-08-06 a ADR-025.

**Catálogo verificado**

| Propuesto | ¿En el registro oficial de ACP? | Nota |
|---|---|---|
| Cursor | Sí | CLI con modo agente ACP documentado |
| Cline | Sí | |
| Qoder | Sí | Qoder CLI |
| Kimi CLI | Sí | MoonshotAI |
| Qwen Code | Sí | |
| OpenHands | Sí | ya evaluado y no elegido como interfaz, ver más arriba |
| Goose | Sí | ya evaluado, ver más arriba |
| Devin | No | |
| Windsurf | No | |
| Aider | No | |
| DeepSeek | No aplica | es un modelo, no un agente: entra por el eje de modelo que ADR-012 ya resuelve |

El registro incluye además, entre otros: Codex CLI, Gemini CLI, GitHub Copilot en public preview, Junie de JetBrains, Augment Code, Factory Droid, OpenCode, Mistral Vibe, Kiro CLI, `cagent` de Docker y Stakpak.

Consecuencia para el diseño: el catálogo no hay que curarlo a mano contra una lista de productos conocidos. La pregunta correcta no es "¿qué agentes queremos soportar?" sino "¿qué agentes ACP están instalados y autenticados en la máquina donde corre el ejecutor?" — que es una pregunta de despliegue, no de arquitectura.

**El costo por iteración lo entrega el protocolo, no hay que instrumentarlo**

Se propuso construir telemetría propia (agente, modelo, tokens, costo, aceptación) como precondición del selector, para que la recomendación naciera de datos y no de una heurística inventada. La mitad de eso ya viene por el canal estándar. La notificación `usage_update` está estabilizada desde el 2026-06-05, y su anuncio dice verbatim: *"the current context token count and context-window size, along with optional cumulative session cost."* Es decir: contexto consumido, tamaño de ventana y costo acumulado llegan igual desde cualquier agente del catálogo, sin código específico por agente. Lo que no entrega el protocolo es la dificultad de la tarea ni si el resultado fue aceptado — eso sí queda del lado de la sala. El selector sigue debiendo nacer como registro y no como heurística, pero su parte más cara ya está resuelta aguas arriba.

**Los tres ejes son la estructura del protocolo, no una capa a inventar**

La sección "Dirección encaminada" ya anticipaba tres ejes independientes (qué agente, qué modelo, qué modo de permisos). Verificado: eso es literalmente cómo ACP está armado.

- **Modelo**: la categoría `model_config` está estabilizada desde el 2026-06-24, y su anuncio explicita que los clientes pueden agrupar esas opciones junto al selector primario de modelo *"without depending on Agent-specific option IDs"*.
- **Permisos**: `session/request_permission` es método baseline del cliente — el agente pide, el cliente decide. Relevante para la pregunta abierta sobre las garantías de ADR-006/ADR-007: la autorización es estructuralmente del lado de la sala. Falta verificar si eso alcanza para conservar el corte determinista del hook, o si un agente puede actuar sin pasar por ahí.
- **Sesiones**: `session/resume`, `session/list`, `session/delete` y `session/close` están estabilizados; el fork tiene RFD abierto ("Forking of existing sessions").

Matiz que corrige la lectura ingenua de esos ejes: el andamiaje de cada agente está afinado para su propio modelo, así que agente y modelo **no son plenamente independientes** en la práctica. La unidad de evaluación real es la combinación agente+modelo, y el selector debe registrar y comparar combinaciones, no ejes sueltos.

**Corrección a una advertencia previa de esta misma ADR**

La advertencia que dice que "los providers ACP de Goose todavía no soportan reanudar ni bifurcar sesión" mezcla dos niveles. Reanudar es parte estable del protocolo (`session/resume`); la limitación registrada es de la implementación de Goose, no de ACP. La advertencia se mantiene, pero acotada a Goose y no al estándar. El fork sí sigue sin estabilizar, en ambos niveles.

**Lo que sigue sin sostenerse**

La especialización por dominio ("este agente es mejor en frontend, este en refactors") no está documentada ni medida de forma neutral por nadie, y no puede anticiparse sin iteraciones propias registradas. Distinto de la diferencia de andamiaje del punto 3 de las correcciones de arriba, que sí es real.

**Decisiones parciales del Director**, registradas como inclinación (la ADR sigue En progreso):

1. **Debate entre agentes solo en fase de plan.** La ejecución concurrente de varios agentes sobre el mismo árbol de trabajo queda descartada por ahora: colisión de escrituras, costo multiplicado y choque con el actor único que supone ADR-007. Motivo adicional a favor: un plan son pocos tokens, así que el debate es barato justo donde más valor tiene.
2. **Se implementa contra ACP v1 estable, no contra el borrador de v2.** v1 es la que tiene SDK 1.0 y la que implementan los agentes del registro; implementar contra un borrador contradice la política de pinear todo (ADR-002), y la guía de migración publicada acota el costo de moverse después. El criterio original enunciado ("la versión más avanzada y comprobada") era contradictorio, y se resolvió a favor de comprobada.
3. **Catálogo inicial**: Claude Code vía el adaptador `claude-agent-acp` (la suscripción de ADR-016 hace su costo marginal cero), Goose (ACP nativo, gobernanza de la Agentic AI Foundation), y Qwen Code y Kimi CLI para probar combinaciones agente+modelo de familias distintas y de bajo costo. Kimi CLI está escrito en Python, el mismo stack del proyecto, lo que facilita depuración e integración sin sumar otro runtime al VPS. Gemini CLI, Cline, Codex CLI y OpenCode quedan como candidatos posteriores.
4. **No se instala el catálogo completo.** Se suma de a un agente cuando una iteración concreta lo justifique. Cada adaptador exige su CLI instalado y autenticado, lo que multiplica superficie de dependencias (ADR-019) y procesos con escritura sobre el repo (ADR-015); el beneficio de ACP es justamente que sumar uno después sale casi gratis.
5. **Filtro de selección por presupuesto**: preferir agentes open source que acepten modelo configurable, para apuntarlos a modelos baratos vía LiteLLM o a la suscripción existente. Matiz: casi ningún agente cobra por sí mismo, el gasto dominante son los tokens del modelo, así que el filtro relevante es la configurabilidad del modelo y no el precio del agente.
6. **Vigilancia de versiones de los agentes del catálogo**, que reporte y no actualice, enganchada al cron de auditoría existente (ADR-008/ADR-014). Actualizar automáticamente binarios con permiso de escritura sobre el repo contradice ADR-002.

**Principio de protección**

No se filtran proveedores por origen geográfico. La posición registrada del Director es que los riesgos de captura por intereses de poder y dinero son equivalentes entre orígenes (se nombró explícitamente Estados Unidos junto a China) y no son controlables desde el proyecto.

Lo que sí se hace, porque es barato y no ralentiza ninguna iteración: excluir del alcance de cualquier ejecutor los secretos — variables de entorno y configuración de LiteLLM, donde ADR-012 ya señaló que se concentran las claves de todos los proveedores. Aplica por igual a todos los agentes, incluido Claude Code. Implementable con ACP sin piezas nuevas: `fs/read_text_file`, `fs/write_text_file` y los métodos de terminal son del cliente, así que la sala decide qué entrega.

Lo que no se hace: ocultar las ADR (ver corrección 4 de arriba), ni duplicar la protección contra acciones destructivas, que ya cubren ADR-006 y ADR-007 y están implementados.

Único chequeo por proveedor, con el mismo criterio para todos y sin excepción por origen: verificar antes de conectar su política de retención y de uso de datos para entrenamiento, distinguiendo plan gratuito de plan pago.

**Advertencias nuevas**

- **ACP v2 publicado en borrador, con documentación, esquema y guía de migración desde v1.** Para un proyecto que pinea todo (ADR-002, ADR-020), obliga a elegir versión explícitamente — resuelto en la decisión 2 de arriba.
- **La madurez de la librería de Python no está al nivel de Rust ni TypeScript.** La documentación oficial lista librerías en Python, Rust, TypeScript, Java y Kotlin. Verificado contra los releases reales: el SDK de Rust alcanzó `v1.0.0` (2026-06-24) y hoy está en `v2.0.0`; el de TypeScript está en `v1.3.0`; el de Python sigue en `v0.12.0` (pre-1.0, publicado 2026-08-01). Es la librería de Python la que importa para un ejecutor que vive dentro del stack Django de este proyecto.
- **El soporte remoto sigue incompleto.** Verificado hoy, mismo verbatim que ya citaba esta ADR: *"Full support for remote agents is a work in progress."* Sin cambios respecto de lo anotado antes. Sigue siendo el punto a reevaluar para ADR-025 §9.

**Sobre "que los agentes conversen entre ellos"**

Se planteó como extensión deseable. Conviene separar dos cosas que no tienen el mismo costo ni el mismo riesgo, y esta ADR no las decide acá (ver decisión 1 de arriba, que sí toma posición sobre la segunda):

- **Debate en la fase de plan** (varios modelos opinando sobre una propuesta antes de ejecutar): barato, sin efectos secundarios sobre el repositorio, y es exactamente el pilar 5 ya previsto en el mapa — desarrollado en la enmienda de ADR-024 de la misma fecha.
- **Ejecución concurrente** (dos agentes con permiso de escritura sobre el mismo árbol de trabajo): colisión de escrituras, permisos duplicados y costo multiplicado. Choca con el corte determinista de ADR-007, pensado para un solo actor.

## Abierto, no resuelto

- **Resuelto (2026-08-06, ver corrección 5 arriba y enmienda 2026-08-06 a ADR-025): no lo conserva.** `session/request_permission` es MAY, no MUST, y `fs/*`/`terminal/*` no son una restricción sobre el agente. La garantía depende de la disciplina de cada implementación del catálogo, no del protocolo. Además, el hook `PreToolUse` de ADR-007 es específico de Claude Code, sin base para asumir equivalente en el resto del catálogo. Candidato de mitigación (no decidido): aislamiento de proceso a nivel de sistema operativo, ver enmienda 2026-08-06 a ADR-025.
- Si conviene que IA CENTRAL hable ACP directamente o a través de una implementación como Goose — sin decidir.
- Qué pasa con `can_use_tool` de ADR-025 punto 1 si el ejecutor deja de ser el Claude Agent SDK — sin reevaluar.
- Qué agentes concretos cumplen el filtro de la decisión 5 de la enmienda de arriba — sin verificar.
- Qué métrica registra la sala por iteración para comparar combinaciones agente+modelo, más allá del costo que ya entrega `usage_update` — sin definir.
- Si la librería de Python alcanza, o si el ejecutor necesita un proceso separado en otro lenguaje — sin verificar.
- Si el catálogo se define por configuración de despliegue o por lista curada en el repo — sin decidir.

## Enmienda 2026-08-07: costo marginal de Claude Code, vigilancia del RFD de transporte remoto, y salud de mantenimiento del SDK de Python

(a) **La decisión 3 de la enmienda 2026-08-06 ("catálogo inicial") justificaba incluir a Claude Code por "costo marginal cero" vía la suscripción de ADR-016 — eso ya no aplica al Ejecutor nativo.** ADR-017 (enmienda 2026-08-07) estableció que el Ejecutor, por tener shell y lectura arbitraria por diseño, rompe la condición que permite montarle el credencial de suscripción — necesita clave de API de Workspace dedicada (ADR-028 punto 7), igual que cualquier otro agente del catálogo. Claude Code sigue siendo candidato válido del catálogo inicial, pero por las mismas razones que los demás (adaptador `claude-agent-acp` publicado, ver punto 2 de "Dirección encaminada"), no por costo marginal cero — ese costo ya no es cero.

(b) **Verificado el 2026-08-07 contra `https://agentclientprotocol.com/rfds/streamable-http-websocket-transport`**: el RFD "Streamable HTTP & WebSocket Transport" está en estado **Active** desde el 2026-07-02 (*"Moved to Active to reflect current Transports Working Group focus"*), apuntado a entrar en v1 como aditivo — verbatim: *"This RFD is targeted for inclusion in v1 as an additive feature, with more robust durability and reliability primitives coming in v2"* — con implementación de referencia en Goose (*"Phase 2 — Reference Implementation (in progress): Working implementation in Goose (`block/goose`)"*). Esto es un hecho distinto de que la página de transportes v1 siga describiendo Streamable HTTP como *"In discussion, draft proposal in progress"* en su cuerpo (ver ADR-028 punto 2): un RFD puede estar activo en el proceso de estandarización sin que la especificación v1 ya lo incorpore. Va a la vigilancia de versiones de la decisión 6 de la enmienda 2026-08-06 — si este RFD se estabiliza y Goose lo expone en producción, reevaluar si sigue conviniendo el puente stdio↔socket propio de ADR-028 para ese agente en particular.

(c) **El SDK de Python de ACP (`agent-client-protocol` en PyPI, `agentclientprotocol/python-sdk` en GitHub) lo mantiene efectivamente una sola persona.** Verificado contra la API de contribuidores de GitHub: PsiACE (Chojan Shang) concentra 37 de los commits, muy por delante del siguiente contribuidor humano (11). Vive bajo la organización oficial `agentclientprotocol`, no es un fork personal, pero la concentración de mantenimiento es real — mismo criterio de salud de mantenimiento que ADR-025 punto 8 aplicó a `cryptography` frente a wrappers de un solo mantenedor. Anotado como vigilancia en `docs/DEPENDENCIAS.md`, no como motivo para descartar el paquete: es la implementación oficial del protocolo, sin alternativa real.
