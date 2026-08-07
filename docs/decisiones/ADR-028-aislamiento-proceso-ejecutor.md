# ADR-028 - Aislamiento de proceso del rol Ejecutor

Fecha: 2026-08-07
Estado: Aceptada

## Contexto

La enmienda 2026-08-06 a ADR-025 registró, sin decidirlo, un candidato de mitigación: aislamiento a nivel de sistema operativo por proceso de Ejecutor, motivado por dos hallazgos de ese mismo día — `session/request_permission` de ACP es `MAY`, no `MUST` (no hay garantía de protocolo), y la corrección a ADR-027 de que `fs/*`/`terminal/*` no logran ninguna exclusión de secretos "sin piezas nuevas" para agentes locales. Esta ADR baja ese candidato a diseño concreto y lo acepta.

## Decisión

1. **El Ejecutor nativo corre como servicio propio de `docker-compose.yml`, no como usuario restringido del host.** Motivo: el contrato de portabilidad de ADR-002 (un usuario de host no viaja con `docker compose up`), el precedente directo de `admin-tasks` (ADR-023) y `orchestrator` (ADR-015), y que el aislamiento por namespaces del kernel es un límite estructural, no una lista de patrones a mantener — la lección que ADR-006 ya dejó documentada sobre por qué un `deny` de patrones no es hermético.

2. **Transporte: el cliente ACP vive del lado de IA CENTRAL; el contenedor del Ejecutor corre el CLI del agente más un puente stdio↔socket**, escuchando solo en la red interna, sin `ports:`. El stream es el mismo JSON-RPC delimitado por saltos de línea que ACP v1 define para stdio, sin protocolo nuevo. Verbatim de la referencia autoritativa de transportes (`https://agentclientprotocol.com/protocol/v1/transports.md`), sección *Custom Transports*: *"Agents and clients MAY implement additional custom transport mechanisms to suit their specific needs. The protocol is transport-agnostic and can be implemented over any communication channel that supports bidirectional message exchange."* La misma página, sección *Streamable HTTP*, describe ese transporte alternativo (HTTP/WebSocket) todavía como *"In discussion, draft proposal in progress"* — es el texto vigente del cuerpo de la especificación v1, no una etiqueta del proceso de RFD (ese es un hecho distinto, ver la enmienda de esta fecha a ADR-027 punto b). Se descarta usar el transporte web del SDK de Python (`create_asgi_app`/`create_http_stream`/`create_websocket_stream`) porque su propia documentación lo marca explícitamente — verbatim, `https://agentclientprotocol.github.io/python-sdk/web-transport/`: *"Experimental. The remote web transports are experimental and may change."* — lo que contradice la decisión 2 de la enmienda 2026-08-06 a ADR-027 (implementar contra v1 estable, no contra superficie en borrador); y porque no ahorra el puente igual: ese servidor sirve agentes escritos en Python vía ASGI, no CLIs externos como los del catálogo de ADR-027. Supuesto técnico verificado en vivo el 2026-08-07 contra el código fuente real (`agentclientprotocol/python-sdk`, `src/acp/core.py`): `connect_to_agent(client, input_stream, output_stream=None, ...)` acepta, en vez de streams de bytes, un único objeto `Transport` como `input_stream` — `Transport` es un `Protocol` mínimo (`send`/`receive`/`close` sobre mensajes ya decodificados, `src/acp/_transport.py`), trivialmente implementable sobre un socket.

3. **Árbol de trabajo: un clon propio de git en volumen propio, no el directorio desplegado.** Motivo: montar la raíz del repo montaría `.env` con ella, y la exclusión de secretos dependería de acordarse de taparlo; un clon fresco no lo tiene por construcción, porque está en `.gitignore`. Es el único punto de escritura del contenedor.

4. **Superficie reducida deliberadamente**: sin `env_file`, sin socket de Docker, sin la configuración de LiteLLM, sin credencial de suscripción.

5. **Endurecimiento del contenedor**: `read_only` en el rootfs con `tmpfs` para `/tmp` y el `HOME`/caché que cada CLI necesite, `cap_drop: [ALL]`, `security_opt: [no-new-privileges]`, `pids_limit` y tope de memoria, usuario no-root con UID parametrizado por `ARG` igual que `ORCHESTRATOR_UID` de ADR-021, sin `ports:`.

6. **Red: solo redes `internal: true`**, una con `web` para el socket ACP y otra con `litellm`. Verbatim de la especificación de Compose (`https://docs.docker.com/reference/compose-file/networks/`): *"By default, Compose provides external connectivity to networks. `internal`, when set to `true`, lets you create an externally isolated network."* Consecuencia buscada: todo el tráfico de modelo queda forzado por LiteLLM, que pasa a ser punto de medición y tope de gasto.

   **Enmienda 2026-08-07 (ADR-031):** el borde de red del socket ACP cambia de dueño — va entre el servicio cliente ACP y el Ejecutor, no entre `web` y el Ejecutor, porque ADR-031 saca el cliente ACP del proceso `web`/Daphne. `web` deja de necesitar ver al Ejecutor. La red hacia `litellm` no cambia.

7. **Credencial: clave de API de Workspace con tope de gasto (ADR-025 punto 6), nunca la suscripción.**

## Alcance

Esta ADR decide el aislamiento de proceso del Ejecutor **nativo únicamente**. Dos límites que la enmienda 2026-08-06 a ADR-025 dejó abiertos siguen sin resolver acá, y esta ADR no los cierra por omisión sino a propósito:

- **Destinos externos**: para un proyecto externo (por ejemplo TacoraGo) no hay Docker Compose propio de IA CENTRAL corriendo en esa máquina — el aislamiento de proceso depende de cómo se instale el agente ahí. Queda dentro del alcance de la pantalla "conectar proyecto nuevo" (ADR-025 punto 5), sin resolver.
- **Escritura legítima fuera del árbol de trabajo**: si el Ejecutor necesita escribir fuera de su propio árbol de trabajo por una razón legítima, esta ADR no lo contempla — declarado explícitamente fuera de alcance, no una omisión sin marcar.

## Alternativas descartadas

- **Usuario restringido del host en vez de contenedor propio**: descartado por el motivo del punto 1 — no viaja con la portabilidad de ADR-002, no tiene el precedente de `admin-tasks`/`orchestrator`, y depende de una lista de restricciones del lado del proceso host en vez de namespaces del kernel.
- **Transporte web del SDK de Python de ACP** (`create_asgi_app`/`create_http_stream`/`create_websocket_stream`) como alternativa al puente stdio↔socket propio: descartado por el motivo del punto 2 — marcado *"Experimental... may change"* por su propia documentación, y de todos modos no sirve para conectar CLIs externos, solo agentes escritos en Python.

## Consecuencias

- El Ejecutor pierde `git push`: pasa a ser una tool angosta del lado de IA CENTRAL, coherente con ADR-015 (la lista de tools ES la política de seguridad).
- El Ejecutor pierde acceso web, lo que choca con la disciplina de verificar versiones en vivo de ADR-020/ADR-026 — mitigado porque esa verificación es trabajo del Consultor (ADR-024, enmienda 2026-08-06), no del Ejecutor.
- Candidato registrado si el punto anterior molesta en la práctica: proxy de salida con allowlist, nunca abrir la red del Ejecutor sin acotar.
- **Riesgo operativo de la segmentación de redes — el cambio de mayor riesgo de esta ADR.** Hoy `web`, `db`, `redis`, `litellm`, `docker-proxy` y `admin-tasks` conviven en la red por defecto que crea Compose, sin redes declaradas explícitamente. Introducir redes `internal: true` para el Ejecutor obliga a declarar redes explícitas para todo el stack y verificar, uno por uno, que cada servicio sigue viendo lo que necesita: `web`↔`db`, `web`↔`redis` (channel layer de ADR-026), `orchestrator`↔`litellm`, `orchestrator`↔`docker-proxy`, `admin-tasks`↔`db`. No es un cambio aislado al Ejecutor, toca la topología de red de todo el stack — exige verificación end-to-end antes de mergear, mismo criterio que ADR-021/ADR-022/ADR-023 aplicaron a cada tool nueva antes de darla por buena. Actualización 2026-08-07 (ADR-031): la lista suma `cliente-acp`↔Ejecutor, `cliente-acp`↔`db` y `cliente-acp`↔`redis`, y ya no necesita `web`↔Ejecutor.
- **Resuelto en ADR-030 (2026-08-07): granularidad del contenedor del Ejecutor y su ciclo de vida.** Uno por chat, no por proyecto. Población fija declarada en `docker-compose.yml` — sin creación dinámica de contenedores ni acceso a la API de Docker desde ningún componente de la aplicación. Reciclado estructural por terminación del proceso más `restart: always`, apagado por inactividad, contabilidad de asignaciones del lado de la sala (Postgres, no el `orchestrator`), durabilidad del trabajo vía rama propia por chat.
- **Resuelto en ADR-031 (2026-08-07): dónde corre el proceso cliente ACP del lado de IA CENTRAL.** Servicio propio de `docker-compose.yml`, no dentro de `web`/Daphne, construido con la misma imagen que `web` y otro `command` (patrón de `admin-tasks`, ADR-023). Motivo principal: las sesiones de trabajo del Ejecutor no deben morir en cada reinicio de `web`, incluido el que puede disparar `restart_web` (ADR-022). Los pedidos de permiso llegan al navegador por el channel layer de Redis de ADR-026. Enmienda además el punto 6 de esta ADR, ver ahí.
- **Pendiente (Fase 3)** en su totalidad, convención de ADR-014: no hay una sola línea de esto implementada — ni el servicio en `docker-compose.yml`, ni el puente stdio↔socket, ni el clon propio, ni el endurecimiento, ni las redes `internal: true`.
