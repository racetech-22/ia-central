# ADR-037 - Chequeo automático del sistema vivo desplegado

Fecha: 2026-08-08
Estado: Aceptada

## Contexto

La decisión abierta `chequeo_http_sitio_desplegado` venía del hallazgo del 2026-08-07 registrado en ADR-018: la verificación de un commit puede dar todo en verde (suite, `check`) dentro de un contenedor de prueba mientras el sitio real sigue corriendo la imagen anterior. Ese día se resolvió a mano, recreando el contenedor y confirmando con `curl`.

El 2026-08-08 aparecieron tres fallas más, todas el mismo día, todas de la misma familia:

1. **El contenedor de producción corriendo código sin commitear, sin que nada avisara.** Pasó dos veces seguidas mientras se ajustaba `core/settings.py` (`CHANNEL_LAYERS`): cada `docker compose up -d --build web` dejaba el sitio real sirviendo cambios todavía no guardados en git, indistinguible desde afuera de un despliegue real.
2. **El WebSocket roto en producción con la suite en verde (32/32).** `RedisChannelLayer.receive()` tiraba `redis.exceptions.TimeoutError` cada ~5 segundos contra Redis real, pero los tests corren sobre `channels.layers.InMemoryChannelLayer` — nunca tocan Redis, así que el bug era invisible para la suite por diseño, no por un descuido puntual.
3. **`docs/estado.yml` marcando `pilar1_rutas_websocket` como `construido`** mientras el punto 2 estaba pasando — el archivo decía la verdad sobre qué código existe, no sobre si ese código funciona corriendo de verdad.

Las tres son la misma frase dicha tres veces: los chequeos deterministas que ya existen —ADR-018 sobre `docs/decisiones/INDEX.md`, ADR-029 sobre `docs/estado.yml`, ADR-032 sobre ARQUITECTURA.md §6— miden que los **archivos del repo** sean consistentes entre sí. Ninguno mide el **proceso corriendo**. Un repo perfectamente consistente puede describir un sistema que no funciona.

## Decisión

1. **El SHA del commit queda horneado en la imagen, como variable de entorno.** `Dockerfile` declara `ARG GIT_SHA=desconocido` y lo fija con `ENV GIT_SHA=${GIT_SHA}`; `docker-compose.yml` pasa `build.args.GIT_SHA` desde una variable de entorno del mismo nombre en el momento del build. "desconocido" es el default a propósito: un build que no reciba el argumento tiene que quedar detectable como tal, nunca heredar en silencio el SHA de un build anterior ni quedar vacío.

   Se descartó escribirlo a un archivo bajo `/app` (por ejemplo `/app/.git_sha`) — probado en vivo el 2026-08-08 y confirmado que no funciona en este proyecto: el servicio `web` monta `.:/app` como volumen (necesario para que el código Python se recargue sin rebuild), así que cualquier archivo escrito ahí durante el build queda tapado por el bind mount del host en tiempo de ejecución. Una variable de entorno no tiene ese problema.

2. **Endpoint `/salud/` público, sin autenticación**, que reporta `sha` (el de la variable de entorno anterior), `db` (una consulta trivial contra Postgres) y `redis` (una ida y vuelta real por el channel layer configurado en `settings.CHANNEL_LAYERS` — enviar un mensaje a un canal propio efímero y volver a leerlo, no un `PING` a Redis). Responde `200` si `db` y `redis` son ambos sanos, `503` si no. El `sha` no participa en ese `200`/`503`: si el commit desplegado coincide con `origin/master` es un juicio que el propio proceso no puede hacer sobre sí mismo — lo hace `scripts/chequeo_despliegue.sh` desde afuera, con acceso a `origin/master`.

3. **Management command `verificar_canal`**: una recepción bloqueante de 12 segundos contra el channel layer real (no el de memoria de los tests), eligiendo 12 para cruzar dos veces `RedisChannelLayer.brpop_timeout = 5`. Sale `0` si la espera completa sin ninguna excepción; distinto de cero si el channel layer la corta antes. Existe separado del endpoint `/salud/` (que también prueba Redis, pero con una ida y vuelta corta) porque el bug real del 2026-08-08 tardaba varios segundos en manifestarse — una prueba de menos de 5 segundos no lo habría reproducido.

4. **`scripts/chequeo_despliegue.sh`**, mismo estilo que `backup_postgres.sh`/`adr_audit.sh` (sin dependencias nuevas: `curl`/`grep -P`, nada de `jq` pese a estar instalado en este VPS — no es una dependencia que el proyecto haya declarado en ningún lado). Golpea `/salud/` desde afuera, compara el `sha` recibido contra `origin/master` consultado por `https://api.github.com/repos/racetech-22/ia-central/commits/master` —no `git ls-remote`: el remoto `origin` es SSH (`git@github.com:...`) y un cron puede no tener la clave cargada; la API pública anónima es el mismo protocolo que ya usa ADR-011—, corre `verificar_canal` dentro del contenedor `web`, y confirma que `/admin/login/` responde `200` y `/mapa/` responde `302` sin autenticar. Notifica por ntfy (ADR-018) solo si algo falla, con el detalle de qué; si todo pasa, no notifica nada.

5. **Cron cada 15 minutos**, agregado al crontab existente del usuario `fernando`. Ni cada minuto (el script tarda entre 15 y 20 segundos por corrida —domina la espera bloqueante de `verificar_canal`— y correrlo así de seguido satura sin ganar nada) ni una vez al día (tardaría hasta 24 horas en avisar de un despliegue roto, cuando el bug del 2026-08-08 se hizo evidente en minutos). Quince minutos es un techo razonable de cuánto puede durar un despliegue roto sin que nadie se entere.

### Por qué el endpoint es público

El repo ya es público (ADR-011): el código que expone `/salud/` es visible igual que el resto. El SHA no es secreto — es el mismo dato que cualquiera puede leer en GitHub. El endpoint no expone ningún dato de negocio (ni de `Proyecto`, ni de `Chat`, ni de nada de `apps/sala`), solo tres hechos sobre el proceso mismo. Con eso alcanza para que `scripts/chequeo_despliegue.sh` no necesite guardar ninguna credencial de superusuario — el mismo criterio que ya evitó esa necesidad para `/admin/login/`, que también se golpea sin autenticar, solo verificando el código de respuesta.

## Alternativas descartadas

- **Solo un chequeo de HTTP 200**, que era el alcance registrado originalmente en la decisión abierta: no habría detectado ninguna de las tres fallas del 2026-08-08. El sitio devolvía `200` en las tres — el problema nunca fue que el servidor no respondiera.
- **Chequeo autenticado, con credenciales de superusuario guardadas en el VPS para que el script pueda loguearse**: innecesario si el endpoint de salud no expone datos, y agrega una credencial más para rotar y proteger sin ganar cobertura real.
- **Resolverlo con un test más en la suite**: ya demostrado insuficiente el mismo 2026-08-08 — es exactamente el mecanismo que no vio el bug del channel layer, porque los tests corren contra `InMemoryChannelLayer` por diseño (necesario para que la suite no dependa de Redis, ver ADR-035). Un test más ahí tendría el mismo punto ciego.

## Consecuencias

- **Riesgo de falsos positivos y ruido en ntfy.** Un `--max-time 15` en cada `curl` puede disparar por latencia transitoria de red, no por una falla real; `verificar_canal` puede coincidir con una ventana de mantenimiento. Si se acumula ruido, la salida es ajustar `--max-time` o la frecuencia del cron, no bajar la exigencia del chequeo ni bajar su frecuencia por defecto.
- **`sha=desconocido` es fallo a propósito, no un estado neutro.** Un build que no recibió `GIT_SHA` queda marcado como tal, y `scripts/chequeo_despliegue.sh` lo trata igual que una desalineación real de versión — mejor un falso positivo evidente el día que alguien haga `docker compose build` sin exportar la variable, que un silencio que oculte justamente el caso que esta ADR existe para cazar.
- **El cron corre como el usuario `fernando`, igual que los otros tres.** Depende de que `crontab -l` siga teniendo la línea — mismo punto ciego que ya tienen `backup_postgres.sh`/`memory_audit.sh`/`adr_audit.sh`, no uno nuevo.
- **Este chequeo no reemplaza a los tres anteriores (ADR-018/029/032), los complementa.** Sigue haciendo falta que `INDEX.md`, `docs/estado.yml` y ARQUITECTURA.md §6 sean consistentes con los archivos reales — eso es necesario pero, como demostró el 2026-08-08, no suficiente: un repo consistente puede describir un sistema roto.
- Construido y verificado el 2026-08-08, incluida verificación adversarial de los tres casos que este chequeo tiene que detectar: desalineación de SHA, canal de Redis roto (reproduciendo el bug real con `socket_timeout=5`), y sitio inalcanzable.
