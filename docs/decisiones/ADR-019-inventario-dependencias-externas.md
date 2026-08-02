# ADR-019 - Inventario versionado de herramientas y servicios externos del proyecto

Fecha: 2026-08-02
Estado: Aceptada

## Contexto

El proyecto ya incorpora varias herramientas y servicios externos, instalados de formas distintas y documentados de forma dispersa: Docker/Docker Compose y Postgres (ADR-002), Nginx y Certbot como paquetes del SO fuera de Docker (ADR-003), rclone como binario standalone (ADR-005), LiteLLM como imagen de Docker pineada (ADR-012), el Claude Agent SDK / CLI de Claude Code (ADR-012, ADR-017), el registrador y DNS del dominio (ADR-003), y ahora ntfy autohospedado (ADR-018). No existe un lugar único que reúna versión actual, dónde vive, de qué ADR sale, si necesita actualización periódica, y qué parte del sistema depende de cada una — el mismo patrón de "nadie lo está verificando de forma centralizada" que ya motivó ADR-014 y la corrección de INDEX.md, ahora aplicado a dependencias externas en vez de a documentación.

## Decisión

Se agrega `docs/DEPENDENCIAS.md`, en ruta fija, con una tabla: Herramienta | Versión/pin actual | Dónde vive | ADR de origen | Política de actualización | Qué depende de ella. Se puebla con las dependencias ya identificadas en el Contexto.

Criterio de inclusión: de qué depende el sistema para funcionar, no qué está instalado en el VPS. Por eso el inventario incluye también servicios externos que no son software instalado (registrador/DNS), porque su caída o expiración impacta igual al sistema.

Política de actualización: no se automatiza ninguna. Todas las versiones quedan pineadas a un valor concreto (mismo criterio que LiteLLM en ADR-012, extendido a todo el inventario); subir de versión es una acción deliberada de Fernando o Claude Code, nunca un proceso desatendido — un updater automático sobre software que corre con credenciales (rclone, ntfy, LiteLLM) es superficie de riesgo nueva sin beneficio claro en un proyecto de este tamaño.

Mantenimiento: se actualiza `docs/DEPENDENCIAS.md` en el mismo commit que se agregue, cambie de versión, o se retire cualquier dependencia externa — mismo hábito ya exigido para ARQUITECTURA.md §6, CHANGELOG.md y `docs/decisiones/INDEX.md`.

## Alternativas descartadas

- **Dejar la información dispersa en cada ADR individual**: es lo que había hasta ahora, y es el problema que se busca resolver.
- **Mecanismo de actualización automática (tipo Renovate/Dependabot)**: descartado por ahora — agrega otra dependencia externa para un beneficio marginal en un stack de este tamaño; revisar si el número de dependencias crece lo suficiente como para justificarlo.
- **Que la auditoría semanal de ADR-014 también verifique este inventario**: se difiere, mismo criterio usado para no sumarle todavía la verificación del defecto equivalente en `memory_audit.sh` (ver ADR-018).

## Consecuencias

- `docs/DEPENDENCIAS.md` es la referencia para responder "qué corre, en qué versión, y quién más lo necesita" antes de tocar cualquier dependencia externa — útil en particular antes de una migración de servidor (ADR-002).
- El inventario incluye dependencias que no son software instalado (registrador/DNS), porque el criterio es el impacto sobre el funcionamiento del sistema, no la presencia física en el VPS.
- No hay enforcement automático de que se actualice, a diferencia de `INDEX.md` (ADR-018). Queda anotado como candidato futuro, igual que la extensión de ADR-014 a este inventario.
