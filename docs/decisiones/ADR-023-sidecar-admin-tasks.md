# ADR-023 - Sidecar `admin-tasks`: `run_migrations`/`run_tests` sin tocar Docker en absoluto

Fecha: 2026-08-03
Estado: Aceptada

## Contexto

ADR-020 dejó `run_migrations`, `restart_web` y `run_tests` deliberadamente afuera de la primera entrega de tools. ADR-022 resolvió `restart_web` vía un proxy de la API de Docker (`tecnativa/docker-socket-proxy`), pero encontró que ese mismo proxy no puede aislar `exec` (lo que necesitarían `run_migrations`/`run_tests` para correr dentro del contenedor `web`) de crear/borrar contenedores nuevos — `CONTAINERS` es una variable todo-o-nada en ese proxy. Presentada esa disyuntiva, se decidió no forzar `CONTAINERS=1` para esto y buscar un mecanismo distinto.

Este ADR es ese mecanismo: en vez de `exec` dentro de `web` vía la API de Docker, un servicio nuevo — `admin-tasks` — construido con la misma imagen que `web` (mismo `Dockerfile`, mismo código, mismas dependencias), conectado a `db` por la red interna igual que `web`. Este servicio no toca el socket de Docker ni la API de Docker en ningún momento — su única capacidad es correr dos comandos de Django management fijos contra la base de datos real. Blast radius si se compromete: como mucho, lo que la propia app Django ya puede hacer contra su base — nada a nivel de host ni de otros contenedores. Evita por completo la disyuntiva de granularidad de ADR-022, porque ni siquiera intenta hablar con Docker.

## Decisión

**`admin_tasks_server.py`** (raíz del repo, incluido en la imagen de `web`/`admin-tasks` porque el `Dockerfile` ya hace `COPY . .`): servidor HTTP mínimo con `http.server` de la librería estándar — sin Flask/FastAPI ni ninguna dependencia nueva, no hace falta para dos endpoints fijos sin parámetros:

- `POST /run-migrations` → `["python", "manage.py", "migrate"]`.
- `POST /run-tests` → `["python", "manage.py", "test", "apps"]` — **no** `test` a secas: verificado en la práctica que el descubrimiento por defecto de `manage.py test` recorre todo `/app`, incluyendo `mcp_servers/django_project/tests/` (una suite de pytest ajena a Django, que falla al importarse en esta imagen por no tener `pytest`/`anyio` instalados — y no tiene por qué tenerlos, no es la suite de este servicio). Acotado a `apps` (el paquete real de las apps Django, ver `core/settings.py` `INSTALLED_APPS`) da un "0 tests ran" limpio hoy, en vez de errores de import de un paquete no relacionado.
- Cualquier otro método/ruta → `404`. Nada de rutas genéricas.
- Token compartido en `Authorization: Bearer <ADMIN_TASKS_TOKEN>` (comparación con `hmac.compare_digest`, no `==`) — defensa en profundidad, no la única barrera: el servicio ya solo es alcanzable por la red interna de Docker Compose (sin `ports:`).
- Ambos comandos devuelven stdout+stderr combinados (truncado a ~200KB, mismo límite que `read_file`) más el código de salida real del proceso.

**Servicio `admin-tasks`** en `docker-compose.yml`: `build: .` (mismo contexto que `web`), `command: ["python", "admin_tasks_server.py"]` (pisa el `CMD` del `Dockerfile`), `env_file: .env` (mismas credenciales de `db` que ya usa `web`), sin `ports:`.

**Tools nuevas** en `mcp_servers/django_project/tools.py`: `run_migrations()`/`run_tests()`, sin parámetros, vía `urllib.request` (librería estándar, no `requests`) haciendo `POST` a `http://admin-tasks:8100/<ruta-fija>` con el token leído de `ADMIN_TASKS_TOKEN`.

## Alternativas descartadas

- **Habilitar `CONTAINERS=1` en el proxy de ADR-022 para hacer `exec`**: es la alternativa que este ADR reemplaza — descartada en ADR-022 por exponer creación/borrado de contenedores como efecto colateral.
- **Flask/FastAPI para el sidecar**: no hace falta agregar una dependencia nueva para dos endpoints POST fijos sin parámetros — `http.server` de la librería estándar alcanza.
- **`requests` en vez de `urllib.request`**: mismo criterio, evitar una dependencia nueva cuando la librería estándar ya resuelve esto.
- **`manage.py test` sin acotar**: descartado tras comprobar en la práctica que recorre `mcp_servers/` y falla por imports faltantes de un paquete no relacionado con la app Django.

## Consecuencias

- Cierra los dos pendientes que quedaban de ADR-020/ADR-022: `run_migrations` y `run_tests` ya existen y funcionan.
- Verificado end-to-end (vía el flujo completo del agente, no llamando las funciones de Python directo): `run_migrations` devolvió `EXIT_CODE=0` con la salida real de Django ("No migrations to apply"); `run_tests` devolvió `EXIT_CODE=0` con "0 tests ran" (limpio, sin tests propios de la app todavía).
- Tests: adversarial confirmando `401` sin token correcto (probado directo contra el sidecar, no a través de `tools.py`); caso feliz de `run_migrations` contra la base de desarrollo real (no destructivo — reaplicar migraciones ya aplicadas es un no-op de Django); caso feliz de `run_tests` confirmando salida coherente ("0 tests ran"), no un error.
- `admin-tasks` duplica el build de `web` (misma imagen, dos contenedores) — mismo patrón que cualquier sidecar con el mismo código base; no agrega una dependencia nueva al inventario (`docs/DEPENDENCIAS.md`) porque no trae ningún paquete que `web` no tuviera ya.
- `ADMIN_TASKS_TOKEN` es una variable nueva en `.env`/`env.example`, compartida entre `admin-tasks` y `orchestrator` — generada una sola vez, nunca impresa ni logueada.
- El diseño de esta ADR es deliberadamente el más simple posible para el problema que resuelve (dos comandos fijos, sin parámetros): si en el futuro se necesitan más comandos de management, revisar si este mismo sidecar alcanza o si conviene repensarlo — no es un framework genérico de "correr cualquier comando", y no debería convertirse en uno sin una decisión aparte.
