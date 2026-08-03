# ADR-022 - Segunda tanda de tools con efectos reales: `restart_web` vía proxy de la API de Docker

Fecha: 2026-08-03
Estado: Aceptada

## Contexto

ADR-020 dejó deliberadamente afuera `run_migrations`, `restart_web` y `run_tests` — las tres tools con efectos reales sobre el sistema, para una decisión aparte sobre su propio diseño de seguridad. Este ADR es esa decisión.

Diseño acordado con Fernando: en vez de montar `/var/run/docker.sock` directo en el contenedor `orchestrator` (control total del host si el proceso se compromete), se pone un proxy de la API de Docker en el medio — `tecnativa/docker-socket-proxy` — que solo permite las operaciones puntuales que estas tools necesitan.

**Hallazgo del Paso 0, verificado contra el código fuente real de `tecnativa/docker-socket-proxy` en el tag `v0.4.2` (commit `2f04313b`, `Dockerfile` + `haproxy.cfg`, no solo el README)**: el proxy no puede aislar "ejecutar un comando dentro de un contenedor ya corriendo" (`exec`) de "crear o borrar contenedores nuevos". La regla real de `haproxy.cfg` para la variable `CONTAINERS` es:

```
http-request allow if { path,url_dec -m reg -i ^(/v[\d\.]+)?/containers } { env(CONTAINERS) -m bool }
```

Sin ancla al final — matchea *cualquier* ruta que empiece con `/containers`, no solo `/containers/{id}/exec` (el primer paso de un `docker exec`, `POST /containers/{id}/exec`). Habilitar `CONTAINERS=1` para permitir ese paso también habilita `POST /containers/create`, `DELETE /containers/{id}`, y el resto del CRUD de contenedores — no existe una variable más granular tipo `ALLOW_EXEC_CREATE` que aísle solo el exec. Las únicas excepciones con esa granularidad son `ALLOW_START`/`ALLOW_STOP`/`ALLOW_RESTARTS`, que sí son ACLs independientes de `CONTAINERS` en el mismo archivo — confirmado que `restart` (lo único que necesita `restart_web`) se puede aislar limpio sin tocar `CONTAINERS` en absoluto.

Presentada esta disyuntiva a Fernando (aceptar el riesgo residual de `CONTAINERS=1`, entregar solo `restart_web` por ahora, o construir un sidecar propio en vez del proxy genérico), se decidió: **entregar únicamente `restart_web` en esta tanda**. `run_migrations` y `run_tests` (que necesitan `exec`) quedan fuera, pendientes de un mecanismo distinto que si logre el aislamiento real — no se inventa una solución de compromiso ahora.

## Decisión

**Servicio `docker-proxy`** en `docker-compose.yml`: imagen `tecnativa/docker-socket-proxy:v0.4.2` (pin exacto). Monta el socket real del host en solo lectura (`/var/run/docker.sock:/var/run/docker.sock:ro`) — el proxy solo necesita leerlo para hablar con el daemon, nunca escribirlo. Variables de entorno:

```
POST=1
ALLOW_RESTARTS=1
```

Todo lo demás queda en su default (`0`/deshabilitado) — en particular `CONTAINERS`, `EXEC`, `IMAGES`, `VOLUMES`, `BUILD`, `NETWORKS`, `SECRETS`, `AUTH`. Verificado en vivo (no asumido): con esta configuración, `client.containers.list()` y `client.containers.create(...)` devuelven `403 Forbidden` desde dentro de `orchestrator`, mientras que el reinicio del contenedor real funciona. Sin `ports:` — solo alcanzable por la red interna de Docker Compose, nunca publicado al host (`privileged: true` es requisito de la propia imagen para conectar con el socket, documentado en su README).

**Servicio `orchestrator`**: sin montar el socket directo. `DOCKER_HOST=tcp://docker-proxy:2375` en su lugar — la única forma de llegar a la API de Docker es a través del proxy.

**Mecanismo de cliente**: SDK de Python `docker==7.2.0` (no el CLI de `docker` + `DOCKER_HOST` en un subprocess) — evita instalar el CLI y shellear, es HTTP puro desde Python, menos superficie.

**`restart_web()` usa `client.api.restart(nombre, timeout=10)`** (el cliente de bajo nivel de docker-py), no `client.containers.get(nombre).restart()` (el cliente de alto nivel): este último hace primero un `GET /containers/{id}/json` (inspect) antes de reiniciar, que necesitaría `CONTAINERS=1` — el de bajo nivel llama directo a `POST /containers/{id}/restart`, sin inspect previo, así que alcanza con `POST` + `ALLOW_RESTARTS`. El nombre del contenedor (`ia-central-web-1`, el nombre real que genera `docker-compose.yml` para el proyecto `ia-central`, servicio `web`, instancia `1`) es una constante fija en `tools.py` — nunca se compone a partir de nada que venga del modelo, ni siquiera parcialmente.

## Alternativas descartadas

- **Montar `/var/run/docker.sock` directo en `orchestrator`**: descartado desde el planteo inicial de Fernando — control total del host si el proceso se compromete.
- **Habilitar `CONTAINERS=1` para tener también `run_migrations`/`run_tests` en esta entrega**: descartado tras el hallazgo del Paso 0 — el costo (poder crear/borrar contenedores) es exactamente lo que se buscaba evitar con el proxy en primer lugar. Ver "Presentada esta disyuntiva a Fernando" arriba.
- **Sidecar HTTP propio (no el proxy genérico de Tecnativa) que exponga solo "correr migrate"/"correr tests"**: es la vía que sí lograría aislamiento real para `exec`, pero es más trabajo de implementación y queda fuera de esta entrega — candidata concreta para cuando se decida agregar `run_migrations`/`run_tests`.
- **`client.containers.get(nombre).restart()` (API de alto nivel de docker-py)**: descartado porque requeriría `CONTAINERS=1` (por el inspect previo) para algo que `client.api.restart()` resuelve con una sola llamada `POST` ya cubierta por `ALLOW_RESTARTS`.

## Consecuencias

- `mcp_servers/django_project/tools.py` gana `restart_web()`, registrada en `server.py` y en `allowed_tools` de `orchestrator/orchestrator.py`.
- `orchestrator/requirements.txt` y `mcp_servers/django_project/requirements.txt` ganan `docker==7.2.0` (mismo criterio de duplicar pines que ya se usa para `mcp`, ver ADR-021: el subproceso stdio corre dentro del contenedor `orchestrator`).
- Verificado end-to-end, contenedor real: `docker compose ps web` mostró el uptime resetear (de "Up 6 minutos" a "Up 12 segundos") tras invocar `restart_web` a través del flujo completo del agente (`orchestrator.run(...)`, no llamando la función de Python directo).
- Tests: caso feliz de `restart_web` corre contra un contenedor descartable (`ia-central-test-restart-target`), creado y borrado desde el host **fuera** de la suite de pytest — el proxy deliberadamente no permite que la suite lo cree por su cuenta (`CONTAINERS=0`), así que ese paso de setup/teardown no puede vivir dentro del test. Documentado explícitamente en el propio archivo de test para que quede claro que no es un descuido.
- Test adversarial (mismo espíritu que los 5 casos de `security.py` en ADR-020): confirma en vivo que el proxy rechaza listar y crear contenedores con `403` — si empieza a fallar, alguien habilitó más superficie de la que esta ADR autoriza.
- Corregido de paso un test que ya estaba roto sin relación directa con esta entrega: `test_sdk_boundary.py` nunca se había actualizado cuando ADR-021 creó `orchestrator/orchestrator.py` — `ALLOWED_SDK_IMPORT_PATHS` seguía vacío, haciendo fallar el test porque `orchestrator.py` sí importa `claude_agent_sdk` (es exactamente su interfaz designada). Corregido a `{"orchestrator/orchestrator.py"}`.
- `run_migrations` y `run_tests` siguen sin implementar — no es un olvido, es la consecuencia directa del hallazgo del Paso 0. Cualquier implementación futura de estas dos necesita resolver primero cómo aislar `exec` de creación/borrado de contenedores (candidato: sidecar propio, ver alternativas descartadas), no reutilizar `CONTAINERS=1` en este mismo proxy.
