# ADR-017 - El orquestador autentica montando el credencial de suscripción, condicionado a que ninguna tool permita lectura arbitraria de rutas

Fecha: 2026-08-01
Estado: Aceptada

## Contexto

ADR-016 decidió que Fase 3 arranca con autenticación por suscripción. Quedaba por verificar el supuesto crítico: que eso funcione desde un proceso headless en un contenedor, y no solo desde la sesión interactiva de Claude Code.

Se probó empíricamente el 2026-08-01, con un contenedor descartable y aislado, en tres corridas:

1. Sin nada montado y sin clave de API → `Not logged in · Please run /login`, exit 1. Ningún mecanismo de autenticación ambiental oculto.
2. Con `~/.claude/.credentials.json` montado en solo lectura → el mismo error. Al investigarlo antes de darlo por concluyente, resultó ser un falso negativo: desajuste de UID (host `fernando`=1001, usuario del contenedor=1000) y el archivo es modo 600, así que el contenedor ni podía leerlo.
3. Mismo montaje, corriendo el contenedor con `--user 1001:1001` → `PONG`, exit 0. Respuesta real del modelo.

Se verificó después que el checksum de `~/.claude/.credentials.json` seguía idéntico al de una copia hecha antes de la prueba: el montaje `:ro` protegió el archivo del host de cualquier rotación de token durante la corrida.

Esto plantea una tensión aparente con ADR-015, que estableció que el agente autónomo debe tener una superficie de acción estrecha. Montar un credencial que abre la cuenta completa de Claude parece justo lo contrario.

## Decisión

1. El contenedor del orquestador monta `~/.claude/.credentials.json` en **solo lectura** (`:ro`) y corre con el UID del usuario propietario del archivo en el host.

2. Esta decisión queda **condicionada** a que ninguna tool del MCP server permita lectura de rutas arbitrarias del filesystem. Toda tool de lectura debe estar acotada a rutas concretas (el directorio del proyecto); ninguna puede aceptar una ruta libre elegida por el modelo.

3. Si en algún momento se agrega una tool que rompa esa condición, **esta ADR queda invalidada** y hay que reevaluar — probablemente pasando a clave de API dedicada para el orquestador.

### Por qué esto no contradice ADR-015

El riesgo no es que el credencial exista dentro del contenedor, sino que el LLM pueda leerlo y filtrarlo. ADR-015 ya elimina esa vía por diseño: el modelo no dispone de shell arbitrario, solo de tools nombradas e implementadas como código determinista. Con la condición del punto 2, el credencial es **entorno de ejecución del proceso, no una capacidad invocable por el agente**.

Comparativamente: Claude Code ya corre en este mismo VPS con shell completo y ese mismo credencial a su alcance (ver ADR-006). El contenedor del orquestador tendría estrictamente menos superficie que el actor que ya opera aquí a diario.

## Alternativas descartadas

- **Clave de API dedicada para el orquestador**: aislaría por completo el credencial de suscripción y sería la opción más limpia en términos de separación de identidades. Se descarta por coste (ver ADR-016), pero es la vía natural a la que volver si deja de cumplirse la condición del punto 2, o si Anthropic revierte el esquema de suscripción.
- **Copiar el credencial a una ruta propia del proyecto en vez de montar el original**: se descarta. Crearía una segunda copia que no se rota cuando se rote la original — un credencial desactualizado pero potencialmente válido, que es peor que montar el original. Además, la prueba demostró que el montaje `:ro` ya protege el archivo del host frente a rotación.
- **No containerizar el orquestador para evitar el montaje**: contradice ADR-015 (portabilidad vía Docker Compose) y no resuelve nada — el proceso necesitaría el credencial igualmente.

## Consecuencias

- **El UID queda acoplado al host.** El contenedor debe correr con el UID del propietario del archivo. Al migrar de servidor (ADR-002), si el usuario tiene otro UID hay que ajustarlo — debe quedar parametrizado en `docker-compose.yml`, nunca cableado a 1001.
- **La condición del punto 2 hay que verificarla activamente, no confiarla a la memoria.** Es exactamente la clase de disciplina que ADR-012 ya reconoció que se diluye si nadie la vigila. Candidata natural a incorporarse a la auditoría semanal de ADR-014, o a un test que falle si alguna tool acepta rutas no acotadas.
- Pendiente (Fase 3): implementar el montaje `:ro` y el UID parametrizado al crear el servicio del orquestador en `docker-compose.yml`.
- Pendiente (Fase 3): al diseñar el primer MCP server, verificar explícitamente que ninguna tool de lectura acepta rutas arbitrarias, y dejar constancia de esa verificación.

## Enmienda 2026-08-03: ambos pendientes resueltos

- El montaje `:ro` y el UID parametrizado (`ORCHESTRATOR_UID`, sin cablear a un número fijo) ya están implementados en el servicio real `orchestrator` de `docker-compose.yml` — ver ADR-021.
- La verificación de que ninguna tool de lectura acepta rutas arbitrarias ya se hizo, con constancia explícita, al diseñar `mcp_servers/django_project` (ver ADR-020): `security.py` es la autoridad única de esta condición, probada con 5 casos adversariales en `tests/test_security.py`. La condición del punto 2 de esta ADR deja de estar vacía — hoy hay una tool MCP real corriendo, acotada por esa verificación.

## Enmienda 2026-08-07: el Ejecutor es exactamente el caso que la condición del punto 2 anticipaba

El Ejecutor (ADR-027, ACP) tiene shell y lectura arbitraria por diseño — es un CLI de agente de código completo, no una tool MCP acotada. Montarle el credencial de suscripción rompería la condición del punto 2 por construcción: no hay forma de que un shell arbitrario cumpla "ninguna tool permite lectura de rutas arbitrarias del filesystem". Se resuelve exactamente como esta misma ADR ya indica en su punto 3 y en "Alternativas descartadas": clave de API dedicada, no la suscripción — ver ADR-028 punto 7 (Workspace de Anthropic con tope de gasto, ADR-025 punto 6).

Esta decisión sigue vigente sin cambios para `orchestrator`, que no tiene shell y cuya condición del punto 2 sigue satisfecha por `security.py` (ADR-020). No se invalida esta ADR — se confirma que su propia cláusula de invalidación (punto 3) es la que corresponde aplicar al Ejecutor, un actor distinto de `orchestrator` que esta ADR nunca contempló.
