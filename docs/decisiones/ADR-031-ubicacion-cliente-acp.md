# ADR-031 - Ubicación del proceso cliente ACP del lado de IA CENTRAL

Fecha: 2026-08-07
Estado: Aceptada

## Contexto

ADR-028 dejó tres pendientes explícitos. ADR-030 cerró el de granularidad y ciclo de vida del contenedor del Ejecutor. Esta ADR cierra el segundo: dónde corre el proceso cliente ACP — dentro del proceso `web`/Daphne, el mismo que sirve la sala, o como servicio propio de `docker-compose.yml`. El tercero (escritura legítima del Ejecutor fuera de su árbol de trabajo) sigue abierto y esta ADR no lo toca.

Tres hechos del repo entran como dados, verificados en esta sesión contra el commit `ed1b9b8bc84c7803c350b71967fa02f35bcf57e7`:

- **`web` se reinicia como parte de la operación normal.** `restart_web` es una tool real y funcionando desde ADR-022, invocable por el `orchestrator`; y todo despliegue que reconstruya la imagen recrea el contenedor.
- **El channel layer de Redis existe y está construido** (`pilar1_migracion_asgi`, construido el 2026-08-04; Daphne + Channels + `channels_redis`, ADR-026).
- **Hay precedente directo de un servicio que reusa la imagen de `web` con otro `command`**: `admin-tasks` (ADR-023), sin `ports:`, misma imagen, sin dependencias nuevas.

## Decisión

1. **El cliente ACP corre como servicio propio de `docker-compose.yml`, no dentro del proceso `web`/Daphne.** Motivo principal: atar la vida de las sesiones de trabajo del Ejecutor a la vida del servidor web las corta en cada reinicio de `web`, incluido el que puede disparar `restart_web` (ADR-022) y el de cada despliegue. Una sesión de Ejecutor es trabajo en curso de larga duración; el servidor web es un proceso que se recicla seguido por razones que no tienen nada que ver con ese trabajo.

   Dos motivos secundarios, ambos de peso propio. (a) La conexión con el Ejecutor es estado vivo dentro de un proceso concreto: no sobrevive al día en que `web` corra en más de un worker, y el channel layer no lo arregla porque resuelve el pasaje de mensajes entre procesos, no la propiedad de un socket. (b) El cliente ACP interpreta la salida de un agente con shell completo; conviene que ese parseo no comparta proceso con el que atiende el tráfico HTTP público.

2. **Se construye con la misma imagen que `web`, con otro `command` — el patrón de `admin-tasks` (ADR-023).** Consecuencia buscada: hereda la configuración de Django, el acceso al ORM sobre Postgres y el channel layer ya configurado, sin duplicar código ni agregar una sola dependencia nueva al inventario de ADR-019. Es lo que hace que "servicio aparte" no cueste lo que normalmente cuesta un servicio aparte.

3. **Los pedidos de permiso del Ejecutor llegan al navegador por el channel layer de Redis ya existente (ADR-026), no por una conexión nueva ni por un canal propio.** El cliente ACP escribe al channel layer; `web` los empuja al WebSocket de la sala. Es exactamente para lo que `channels_redis` está en el stack.

4. **Sin `ports:`.** Alcanzable solo por redes internas de Compose, mismo criterio que `admin-tasks` (ADR-023) y `docker-proxy` (ADR-022).

5. **Aclaración a ADR-030 punto 5, que esta ADR vuelve ambiguo si no se dice:** "la contabilidad de asignaciones vive del lado de la sala" debe leerse como *el subsistema de la sala* — este servicio más `web`, compartiendo la misma base Postgres — y nunca como el `orchestrator`. El argumento de ADR-030 para excluir al `orchestrator` (es `sleep infinity`, invocado a mano, y es deliberadamente el agente más angosto del sistema) sigue en pie sin cambios. Quien escribe la tabla de asignaciones es este servicio, que es el que sabe si un Ejecutor está realmente conectado.

## Enmienda a ADR-028

**ADR-028 punto 6 queda enmendado por esta ADR, no solo complementado.** Ese punto dice que el Ejecutor lleva "solo redes `internal: true`, una con `web` para el socket ACP y otra con `litellm`". Al mudarse el cliente ACP fuera de `web`, ese borde cambia de dueño: la red interna del socket ACP va entre el **servicio cliente ACP** y el Ejecutor, no entre `web` y el Ejecutor. `web` deja de necesitar ver al Ejecutor en absoluto. La red hacia `litellm` no cambia.

Consecuencia sobre el riesgo que ADR-028 ya había marcado como el mayor de esa ADR: la lista de bordes a verificar end-to-end al declarar redes explícitas crece, y hay que actualizarla. Suma `cliente-acp`↔Ejecutor, `cliente-acp`↔`db` y `cliente-acp`↔`redis`; y quita `web`↔Ejecutor, que ya no hace falta.

## Alcance

Cierra únicamente `ubicacion_cliente_acp`. Sigue abierta `escritura_fuera_arbol_trabajo_ejecutor` de ADR-028, y todo lo que ADR-028 dejó fuera de alcance para destinos externos.

## Alternativas descartadas

- **Dentro del proceso `web`/Daphne**: descartada por el punto 1. Es la opción más simple en cantidad de piezas y la que ADR-028 nombraba primero, pero paga esa simplicidad con la fragilidad de acoplar sesiones de trabajo largas al ciclo de vida de un servidor web que se reinicia por motivos ajenos.
- **Dentro del `orchestrator`**: ya descartada en ADR-030 punto 5 por los mismos dos motivos, que no cambian acá.
- **Proceso suelto en el host (systemd o tmux)**: descartada por el mismo motivo que ADR-015 descartó eso mismo para el `orchestrator` — no viaja con `docker compose up`, rompe el contrato de portabilidad de ADR-002.
- **Imagen propia en vez de reusar la de `web`**: descartada por el punto 2 — obligaría a duplicar dependencias y configuración de Django para no ganar nada; `admin-tasks` ya probó que el patrón de imagen compartida funciona.

## Consecuencias

- **Las sesiones del Ejecutor sobreviven a los reinicios de `web`**, que es el objetivo de la decisión.
- **Un servicio más en el inventario** que operar, observar y arrancar. Mitigado porque comparte imagen con `web`: no agrega build, ni dependencias, ni entrada nueva en `docs/DEPENDENCIAS.md`.
- **Dependencia dura del channel layer de Redis para los pedidos de permiso.** Si Redis no está, el pedido de permiso no llega a la pantalla. Lo correcto es que eso resulte en fail-closed —el Ejecutor no avanza sin aprobación, mismo criterio que ADR-025 §9— pero **eso hay que verificarlo en la implementación, no asumirlo**: un pedido que se pierde en silencio y un Ejecutor que sigue adelante sería exactamente el modo de falla que todo el diseño de permisos existe para impedir.
- **La topología de red del stack se toca de nuevo.** ADR-028 ya había señalado la segmentación de redes como su cambio de mayor riesgo; esta ADR cambia uno de los bordes de esa lista antes de que se haya implementado ninguno. Es más barato ahora que después, pero obliga a que la verificación end-to-end de ADR-028 se haga contra la lista corregida de esta ADR, no contra la original.
- **`web` queda sin ninguna conexión al Ejecutor**, lo cual reduce su superficie: el proceso que atiende el tráfico público deja de hablar con el contenedor que tiene shell.
- **Supuesto heredado, no reverificado acá**: que `connect_to_agent` del SDK de Python de ACP acepta un `Transport` propio sobre socket. Eso lo verificó ADR-028 el 2026-08-07 contra el código fuente real; esta ADR se apoya en esa verificación sin repetirla, y si aquella resultara incorrecta esta decisión también hay que revisarla.
- **Pendiente (Fase 3) en su totalidad**, convención de ADR-014: no hay una sola línea implementada — ni el servicio, ni el puente hacia el channel layer, ni la tabla de asignaciones, ni las redes.
