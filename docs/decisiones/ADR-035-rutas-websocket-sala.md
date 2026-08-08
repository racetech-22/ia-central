# ADR-035 - Rutas de WebSocket de la sala

Fecha: 2026-08-08
Estado: Aceptada

## Contexto

ADR-025 §9.7 dejó anotado, y `core/asgi.py` lo repite en un comentario en el propio código: el `ProtocolTypeRouter` solo tiene la rama `"http"`, sin `URLRouter` ni consumers para `"websocket"`, y esa es la subtarea siguiente del pilar 1. Todo lo demás de esa migración está construido desde el 2026-08-04: Daphne, Channels, `channels_redis` y el servicio `redis` sin puertos expuestos, más las cabeceras `Upgrade`/`Connection` en el Nginx que corre fuera de Docker (ADR-003).

El modelo de datos quedó completo con ADR-033 y ADR-034, pero sin esta capa nada de eso llega a una pantalla: el channel layer existe precisamente porque una solicitud de permiso entra por un lado y tiene que salir por el navegador del Director (ADR-025 §9.7).

## Decisión

1. **Rama `"websocket"` envuelta en `AllowedHostsOriginValidator(AuthMiddlewareStack(URLRouter(...)))`.** La validación de origen no es opcional: sin ella, cualquier página de cualquier dominio puede abrir un socket contra la sala usando la cookie de sesión del Director. Es la contraparte de `CSRF_TRUSTED_ORIGINS` para WebSocket, que no pasa por el middleware CSRF de Django.

2. **Solo superusuario, y un grupo por chat (`chat_<id>`).** Mismo criterio que `/mapa/` en ADR-029: el sistema tiene un solo usuario real y no se inventan roles antes de que existan. El grupo por chat es lo que permite que un evento entre por un productor y salga por el navegador sin acoplarlos.

3. **El socket es de empuje: el navegador no manda nada que mute estado.** Solo se acepta un `ping`. Cuando existan las decisiones de permiso, van a viajar por HTTP, no por acá. Es la misma separación que ADR-025 §9.2 ya fijó para el protocolo saliente —lo durable por HTTP idempotente con reintento, lo cosmético por el socket sin garantía de entrega— extendida al tramo del navegador. Una decisión de permiso perdida por una desconexión sería exactamente el modo de falla que el diseño fail-closed de §9.4 existe para impedir.

4. **Reconexión con backoff exponencial y tope de 60 s, con el estado de conexión visible en pantalla.** Los parámetros son los de ADR-025 §9.5. Que el estado sea visible no es cosmético: si el socket está caído, lo que se ve en pantalla puede estar desactualizado, y el Director tiene que saberlo sin adivinarlo.

5. **Vista andamio bajo `/sala/`**, HTML y JavaScript a mano, sin frameworks ni CDNs — mismo criterio que la vista de `/mapa/` (ADR-029). Su propósito es hacer verificable de punta a punta que el socket abre sobre `wss` contra el dominio real, no ser la pantalla final.

## Alcance

Cierra la subtarea de rutas de WebSocket. **No** construye la sala: `pilar1_sala_navegador` sigue en `pendiente`, porque no hay ni conversación ni aprobaciones en pantalla. Tampoco construye el consumer del agente remoto de ADR-025 §9 — ese sirve a destinos externos, cuyo aislamiento sigue abierto, y el caso nativo no lo necesita: el cliente ACP habla con el Ejecutor por un socket de red interna (ADR-028, ADR-031), no por WebSocket.

## Alternativas descartadas

- **Sin `AllowedHostsOriginValidator`**: descartada por el punto 1. Es la única barrera de origen que tiene el canal WebSocket.
- **Aceptar decisiones de permiso por el socket**: descartada por el punto 3.
- **Consumer del agente remoto en la misma entrega**: descartada por el Alcance — sería construir para un caso cuyo aislamiento de proceso todavía no está decidido.
- **Un framework de front-end o un CDN**: descartada por el punto 5, mismo criterio que ADR-029.

## Consecuencias

- **Primera pieza del pilar 1 que produce algo visible en el navegador.** Hasta acá Fase 3 corría headless por diseño (ARQUITECTURA §5); esto no cambia esa decisión, agrega el andamio mínimo para verificar la capa.
- **Los chats se crean desde el admin de Django por ahora.** No hay pantalla de creación: sería inventar interfaz antes de tener la conversación.
- **La verificación tiene que incluir recrear el contenedor `web`.** El hallazgo del 2026-08-07 fue exactamente un contenedor de larga vida que no se recreó tras un cambio: la suite en verde no prueba que el sitio real esté corriendo el código nuevo.
- **Queda sin resolver la autorización por chat.** Hoy cualquier superusuario puede conectarse a cualquier chat, porque hay un solo usuario. Cuando exista más de uno, hace falta una comprobación de pertenencia — anotado, no implementado.
- **El consumer no persiste nada.** Solo reenvía lo que llega por el grupo. Quién escribe en `ActualizacionSesion` y `LlamadaHerramienta` (ADR-034) es el cliente ACP de ADR-031, que no existe todavía.
