# ADR-003 - Nginx y Certbot fuera de Docker para TLS de borde

Fecha: 2026-07-30
Estado: Aceptada

## Contexto

IA CENTRAL necesita quedar expuesto en `aicentral.network` con HTTPS. ADR-002 establece que "todo el stack se empaqueta con Docker + Docker Compose" como principio general de portabilidad. Sin embargo, Fernando ya administra Nginx + Certbot directamente en el sistema operativo (fuera de Docker) en sus otros VPS existentes, con renovación automática vía el cron/systemd timer que instala Certbot por defecto. Replicar ese mismo patrón operativo en el VPS de IA CENTRAL reduce la carga de mantener dos formas distintas de terminar TLS entre servidores.

## Decisión

Se instalan Nginx y Certbot directamente en el sistema operativo del VPS (fuera de Docker), como excepción puntual y acotada al principio de "todo en Docker" de ADR-002:

- Nginx actúa como reverse proxy de borde: recibe tráfico en 80/443 para `aicentral.network` y hace `proxy_pass` a `http://127.0.0.1:8000` (el puerto que publica el contenedor `web`).
- Certbot (con el plugin `certbot-nginx`) gestiona la emisión y renovación automática del certificado TLS de Let's Encrypt, reconfigurando el server block de Nginx directamente.
- El resto del stack (Django, Postgres) sigue empaquetado 100% en Docker vía `docker-compose.yml`, sin cambios.

Como consecuencia directa, Django corre detrás de un proxy que termina TLS: se agregaron `CSRF_TRUSTED_ORIGINS` y `SECURE_PROXY_SSL_HEADER` en `core/settings.py` (ambos leídos/derivados de variables de entorno) para que reconozca correctamente las peticiones HTTPS reenviadas por Nginx.

## Alternativas descartadas

- **Nginx como contenedor Docker adicional** (por ejemplo, `nginx` + `certbot` containerizados con volúmenes compartidos para los certificados): mantiene la pureza del principio "todo en Docker" de ADR-002, pero introduce un patrón de gestión de certificados distinto al que Fernando ya opera en el resto de su infraestructura. Se prioriza la consistencia operativa entre servidores por sobre la pureza arquitectónica. Descartado por ahora.
- **Traefik como reverse proxy con renovación automática integrada**: simplifica el manejo de certificados sin salir de Docker, pero introduce una herramienta nueva que Fernando no usa en ningún otro servidor. Descartado por consistencia.

## Consecuencias

- El VPS de IA CENTRAL deja de ser 100% Docker: Nginx y Certbot viven como paquetes del sistema operativo (`apt`), no como contenedores. Esto hay que tenerlo en cuenta si el proyecto se migra a otro servidor (ver ADR-002): el paso de migración deja de ser únicamente `docker compose up` y ahora también incluye reinstalar/replicar la configuración de Nginx + Certbot del host (el server block vive en `/etc/nginx/sites-available/`, fuera del repositorio versionado).
- La renovación de certificados queda a cargo del temporizador que instala Certbot por defecto en el sistema, fuera del ciclo de vida de `docker compose`.
- `core/settings.py` gana `CSRF_TRUSTED_ORIGINS` (vía `DJANGO_CSRF_TRUSTED_ORIGINS`) y `SECURE_PROXY_SSL_HEADER` fijo en `("HTTP_X_FORWARDED_PROTO", "https")`, que depende de que Nginx reenvíe el header `X-Forwarded-Proto`.
- Con `DJANGO_DEBUG=False` en producción, `runserver` deja de servir archivos estáticos. Nginx los sirve directo desde `staticfiles/` (generado con `manage.py collectstatic`, accesible en el host porque `docker-compose.yml` monta `.:/app`) vía `location /static/ { alias ...; }`. Esto requirió `chmod o+x /home/fernando` para que el usuario `www-data` pueda atravesar el home hasta ese directorio (solo tránsito, no listado).

## Enmienda 2026-08-02: `db` y `web` no seguían el patrón de borde único de Nginx

La auditoría de solo lectura del 2026-08-02 detectó que `docker-compose.yml` publicaba `db` (`5432`) y `web` (`8000`) en `0.0.0.0` desde el skeleton inicial — alcanzables directo desde internet, bypaseando Nginx por completo. Esto nunca se decidió en esta ni en ninguna otra ADR; quedó así sin que nadie lo revisara, en contraste con `ntfy` (ADR-018), que sí se publicó explícitamente solo en `127.0.0.1`.

Corrección aplicada, mismo patrón que `ntfy`: `web` pasa a publicarse en `127.0.0.1:8000:8000` (Nginx, que corre en el host fuera de Docker, sigue alcanzándolo igual — su `proxy_pass` ya apuntaba a `127.0.0.1:8000`). `db` deja de publicar puerto alguno: `scripts/backup_postgres.sh` usa `docker compose exec -T db pg_dump` (red interna de Docker), y `web` alcanza a `db` por el hostname `db` en esa misma red interna — ningún caso de uso real requería acceso a Postgres desde el host. Verificado con `ss -tlnp` (ya no aparece `5432`; `8000` solo en `127.0.0.1`) y `curl` a `https://aicentral.network/admin/login/` (200 OK) tras recrear los contenedores.
