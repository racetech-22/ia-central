# ADR-026 - Servidor ASGI: Daphne

Fecha: 2026-08-03
Estado: Aceptada

## Contexto

ADR-025 §9.7 dejó explícitamente pendiente "servidor ASGI a elegir y pinear con el criterio conservador de ADR-020". Es prerequisito de todo lo demás de esa sección: sin esta decisión no se puede tocar `docker-compose.yml` ni la configuración de Nginx, y la migración de `web` de WSGI a ASGI es el cambio más riesgoso de la lista (ADR-025 §9.9).

El servicio `web` corre hoy con `runserver` de Django sobre WSGI, detrás de Nginx + Certbot (ADR-003). La sala de discusión necesita WebSocket en dos direcciones distintas: el navegador de Fernando contra IA CENTRAL, y el agente remoto de cada proyecto externo contra IA CENTRAL (ADR-025 §9.1).

Datos verificados en PyPI el 2026-08-03, no asumidos — contra `pypi.org/pypi/<paquete>/json`, no contra la página HTML del proyecto: la página HTML puede servir contenido cacheado, el mismo problema de CDN que ADR-011 ya documentó para `raw.githubusercontent.com`; el JSON de PyPI no tiene ese síntoma conocido:

| | Daphne | Uvicorn |
|---|---|---|
| Última versión | 4.2.3, publicada el 2026-07-21 | 0.52.1, publicada el 2026-08-01 |
| Cadencia reciente | 4.0.0 (oct 2022), 4.1.0 (feb 2024), 4.2.0 (may 2025), 4.2.1 (jul 2025), 4.2.2 (jun 2026), 4.2.3 (jul 2026) | 15 publicaciones entre el 2026-02-16 y el 2026-08-01 |
| Owner en PyPI | Django Software Foundation | Encode |
| Classifier | 4 - Beta | 4 - Beta |

El classifier no distingue: ambos declaran `4 - Beta`.

`4.2.2` corrigió dos vulnerabilidades de seguridad, confirmadas contra el changelog real del proyecto (`github.com/django/daphne/blob/main/CHANGELOG.txt`): **CVE-2026-44545**, denegación de servicio por tamaño de mensaje WebSocket sin límite (los límites de tamaño de mensaje y de frame ahora tienen default de 1 MiB, configurables vía los flags `--websocket-max-message-size`/`--websocket-max-frame-size`, `0` los desactiva); y **CVE-2026-44546**, inyección de headers en el handshake de upgrade de WebSocket (valores de header con ciertos bytes de control se parseaban como un único header en Twisted pero como headers separados en autobahn). `4.2.3` (2026-07-21) agrega únicamente esos mismos dos flags al comando `runserver` para uso en desarrollo — sin cambios de seguridad ni de comportamiento en producción respecto a `4.2.2`. Pinear la última patch (`4.2.3` sobre `4.2.2`) no contradice el criterio conservador de ADR-020, que apunta a reworks mayores de API, no a parches sin cambio de comportamiento.

## Decisión

El servidor ASGI de IA CENTRAL es Daphne, pineado en `daphne==4.2.3`.

**Pendiente (Fase 3):** no está agregado a ningún `requirements.txt` ni a `docker-compose.yml`, y `web` sigue corriendo `runserver` sobre WSGI. Esta ADR fija la elección, no describe un artefacto existente.

Motivos:

1. **Mismo mantenedor que el resto del stack de WebSocket.** Channels, `channels_redis` y Daphne son todos de la Django Software Foundation. Es el criterio que ADR-025 punto 8 ya aplicó al descartar wrappers de terceros para campos cifrados en favor de la librería base de PyCA: preferir lo que mantiene el dueño del ecosistema antes que una pieza equivalente de un tercero.
2. **Es el camino documentado por Channels.** Verbatim de su página de despliegue: *"The Channels project maintains an official ASGI HTTP/WebSocket server, Daphne, and it's this that we'll talk about configuring."* Uvicorn aparece en esa misma página únicamente bajo "Alternative Web Servers", sin configuración documentada. El ejemplo de Nginx de esa página ya incluye las cabeceras `Upgrade`/`Connection` que ADR-025 §9.7 necesita.
3. **Un solo proceso para HTTP y WebSocket.** Daphne auto-negocia entre ambos protocolos, así que Nginx apunta a un único upstream y las conexiones WebSocket comparten cookies con las vistas normales sin separar por dominio ni por path.

## Alternativas descartadas

- **Uvicorn (`0.52.1`)**: funciona perfectamente con Channels — la propia documentación dice que los servidores ASGI son intercambiables si respetan la especificación — y su cadencia de publicación es mucho más alta (15 releases entre febrero y agosto de 2026, contra dos de Daphne en el mismo período). Se descarta por dos motivos, ninguno técnico-funcional: no es el servidor que la documentación de Channels configura (lo que significa resolver a mano lo que ahí ya está resuelto), y su versionado 0.x con publicaciones frecuentes implica más superficie de actualización para un proyecto que pinea todo y prueba cada versión candidata en cuarentena antes de fijarla (política pendiente registrada en `docs/DEPENDENCIAS.md`). Queda como plan B real y barato: ambos servidores consumen el mismo `asgi.py`, así que cambiar de uno a otro no toca código de aplicación.
- **Mantener WSGI para HTTP y sumar un servidor ASGI solo para WebSocket** (posibilidad que la propia documentación de Channels menciona para quien sea conservador con la estabilidad): descartado. Obliga a poner algo delante que separe el tráfico por path o dominio, duplica la configuración de Nginx, y rompe el compartir cookies entre WebSocket y vistas normales. La complejidad añadida es mayor que el riesgo que evita.
- **Hypercorn y otros servidores ASGI**: no evaluados. La comparación se acotó al par que la documentación de Channels nombra explícitamente; si en el futuro Daphne dejara de mantenerse, la reevaluación debería incluirlos en vez de saltar directo a Uvicorn por descarte.

## Consecuencias

- **Pendiente (Fase 3)**: agregar `daphne==4.2.3` al `requirements.txt` correspondiente, crear `core/asgi.py` con el `ProtocolTypeRouter` que Channels requiere, y cambiar el comando del servicio `web` en `docker-compose.yml` para que corra Daphne en vez de `runserver`.
- **Pendiente (Fase 3)**: alta de `daphne` en `docs/DEPENDENCIAS.md` (ADR-019), en el mismo commit en que se agregue a `requirements.txt`, no antes.
- **Pendiente (Fase 3)**: verificar después de la migración que el admin de Django y `https://aicentral.network/admin/login/` siguen respondiendo como antes, con el mismo criterio de verificación end-to-end de ADR-021/ADR-022/ADR-023. Es el riesgo operativo que ADR-025 §9.9 ya había anotado.
- Cierra el pendiente "servidor ASGI a elegir" de ADR-025 §9.7. Esa línea debe actualizarse para apuntar a esta ADR en vez de dejar la elección abierta.
- **Pendiente (Fase 3)**: una vez instalado, los límites de tamaño de mensaje y de frame de WebSocket de Daphne quedan en su default de 1 MiB (configurables por CLI, `0` los desactiva) — restricción de diseño real para las tramas de ADR-025 §9.3. Hoy no bloquea nada porque lo durable viaja por POST HTTP fuera del socket (ADR-025 §9.2), pero hay que tenerlo presente si alguna trama (`stream`, `permission_request`, etc.) creciera por encima de ese límite.
- La cadencia de publicación de Daphne es baja, y eso hay que vigilarlo activamente en vez de darlo por bueno: tiene dueño institucional y una publicación de julio de 2026, lo que lo distingue de los paquetes abandonados que ADR-025 punto 8 descartó (dos años sin actualizar y sin organización detrás). Si en una revisión futura de versiones Daphne acumulara dos años sin publicaciones, esta decisión debe reevaluarse — no dar por sentado que sigue siendo la opción correcta solo porque ya está en el repo.
