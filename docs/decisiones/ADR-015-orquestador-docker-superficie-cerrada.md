# ADR-015 - El orquestador corre como servicio de Docker Compose, con superficie de acción cerrada

Fecha: 2026-08-01
Estado: Aceptada

## Contexto

Fase 3 requiere que el agente orquestador corra como proceso persistente en el VPS (ADR-009 ya descartó ejecutarlo desde Cowork). Había tres formas de sostener ese proceso: un servicio systemd, una sesión de tmux (como el alias `iac` que ya se usa para Claude Code), o un servicio más dentro de `docker-compose.yml` junto a `web` y `db`.

Además, ARQUITECTURA.md §2 establece que el orquestador debe poder operar sobre su propio proyecto: leer y modificar código Django, correr migraciones, usar Claude Code como motor de desarrollo. La forma habitual de darle esa capacidad desde un contenedor es montarle el socket de Docker (`/var/run/docker.sock`) y el repo del host. Pero quien controla el socket de Docker puede levantar un contenedor privilegiado y obtener control total del host — eso anularía en la práctica el trabajo de ADR-006 y ADR-007.

## Decisión

1. El orquestador corre como **servicio dentro de `docker-compose.yml`**, con `restart: always`, junto a `web` y `db`.

2. **El LLM nunca dispone de un shell arbitrario.** Todo lo que el orquestador necesite hacer sobre la infraestructura se expone como tools MCP discretas y nombradas (`run_migrations`, `restart_web`, `run_tests`, `read_file`, `git_status`…), implementadas cada una como una función concreta en `mcp_servers/`. El agente pide `restart_web()`; no compone comandos.

3. La frontera de seguridad **no es "que no exista socket de Docker en el stack"**, sino que el modelo no pueda componer comandos arbitrarios. El MCP server puede tener acceso al socket y ejecutar `docker compose restart web` por debajo, porque eso es código Python determinista, versionado y auditable — no una decisión del modelo en tiempo de ejecución.

4. El catálogo de tools **no se diseña por adelantado**. Se arranca con las tres o cuatro que Fase 3 necesita de verdad, y cada caso de "el orquestador quiso hacer X y no pudo" se trata como una decisión deliberada de agregar (o no) esa capacidad.

## Alternativas descartadas

- **Servicio systemd**: es el patrón estándar para procesos persistentes en Linux y da reinicio automático y arranque en boot. Se descarta porque vive fuera del contrato de portabilidad que fija ADR-002 ("migrar de servidor debe ser `docker compose up` más restore de datos"): habría que recrearlo a mano en cada servidor nuevo, y justamente para la pieza más importante del sistema. Docker Compose con `restart: always` da el mismo comportamiento sin salirse del principio rector de ADR-001.
- **Sesión de tmux**: simple y ya familiar (es como corre Claude Code hoy con el alias `iac`), pero no se reinicia sola si el proceso muere ni arranca sola si el VPS reinicia — depende de que alguien reabra la sesión. Inaceptable para un proceso que debe operar desatendido.
- **Montar el socket de Docker y el repo en el contenedor del orquestador, dándole shell**: es la vía rápida y la que más flexibilidad daría al agente. Se descarta porque equivale a control total del host, y porque ADR-006 ya estableció empíricamente que una lista de denegación sobre un shell abierto es inherentemente incompleta. Una interfaz estrecha de operaciones permitidas sí es verificable.
- **Controlar un shell amplio con hooks tipo ADR-007**: los hooks funcionan bien como red de seguridad contra comandos destructivos conocidos, pero son igualmente una lista de patrones — sirven para complementar una superficie cerrada, no para sustituirla.

## Consecuencias

- Cada capacidad nueva del orquestador requiere escribir una tool en `mcp_servers/`, no simplemente dejarlo ejecutar un comando. Es más trabajo por adelantado, y la fricción será mayor al principio de Fase 3, cuando aún no se sabe bien qué capacidades hacen falta.
- A cambio, se sabe en todo momento con exactitud qué puede hacer el agente autónomo. **La lista de tools ES la política de seguridad**, y es legible y versionada en el repo.
- El registro de capacidades solicitadas y no disponibles es información valiosa por sí misma: muestra qué quiere hacer el agente por su cuenta.
- **Esto no restringe el desarrollo de Fernando.** Claude Code sigue corriendo en la sesión tmux `iac` con shell completo, bajo las reglas de `.claude/settings.json` y el hook de ADR-007. Son dos actores con perfiles de riesgo distintos: uno supervisado, otro desatendido.
- Pendiente (Fase 3): agregar el servicio del orquestador a `docker-compose.yml` y crear el primer MCP server en `mcp_servers/`.
- Pendiente (Fase 3): mecanismo de verificación de la frontera de ADR-012 — un lint o test que falle si algo fuera de la interfaz interna importa el SDK directamente. Sugerido por Claude Code al redactar ADR-012.
