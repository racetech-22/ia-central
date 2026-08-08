# ADR-036 - Cuarto principio rector: máxima capacidad, operador único

Fecha: 2026-08-08
Estado: Aceptada

## Contexto

Los tres principios rectores de ARQUITECTURA.md §1 —portable, verificable, configurable desde el panel— dicen qué debe cumplir lo que se construye, pero no dan criterio para decidir cuándo una restricción está justificada. Sin ese criterio, cada decisión de seguridad se discute de cero y la tendencia por defecto es angostar, porque angostar siempre parece prudente.

La sesión del 2026-08-08 lo hizo evidente: el Consultor recomendó al Director rechazar aprobaciones amplias de comandos rutinarios de Claude Code alrededor de ocho veces en una jornada, y propuso ocultar las opciones `allow_always`/`reject_always` de la sala. Ninguna de las dos cosas protegía de nada real —el Director es el único operador y ya tiene acceso SSH completo— y las dos costaban fricción. La segunda se corrigió en ADR-034 punto 4 al notarlo.

## Decisión

Se agrega un cuarto principio rector a ARQUITECTURA.md §1: **el sistema debe funcionar con la máxima potencia y eficiencia posibles para el Director, que es su único operador hasta decisión en contrario, y toda restricción debe justificarse contra un modo de falla real.**

Criterio operativo para decidir si un límite se justifica:

- **Un límite que protege del operador se descarta.** No hay un segundo usuario ni un tercero hostil. Roles, permisos por usuario y superficies angostadas "por las dudas" son ceremonia, no seguridad — ADR-006 ya dejó asentado que la defensa real es que solo el Director tiene acceso SSH.
- **Un límite que protege de una equivocación irreversible o de un agente descontrolado se conserva y se refuerza.** El hook de ADR-007, el fail-closed de ADR-025 §9.4 y el aislamiento del Ejecutor de ADR-028 no desconfían del Director: existen porque un modelo puede equivocarse en un comando sin vuelta atrás.
- **Un límite de recurso no es un límite de política.** El techo de 2-3 Ejecutores simultáneos de ADR-030 sale de la RAM del VPS. La salida correcta es ampliar el recurso, no rediseñar alrededor de la restricción.

## Consecuencias

- Cambia el criterio con el que el Consultor recomienda aprobar o rechazar prompts de Claude Code: aprobación amplia para lectura y rutina, revisión caso por caso reservada a lo que borra datos, toca la base de producción o publica hacia afuera.
- ADR-034 punto 4 (mostrar `allow_always`/`reject_always`) queda respaldado por este principio, no solo por el argumento puntual que lo motivó.
- **Este principio no relaja ninguna decisión de seguridad ya tomada.** Las tres que nombra explícitamente —ADR-007, ADR-025 §9.4, ADR-028— caen del lado que se conserva. Si en el futuro se invoca este principio para levantar alguna de ellas, es un uso incorrecto: ninguna protege del Director.
- Queda como criterio de revisión hacia atrás: cuando se toque una decisión vieja, vale preguntarse si sus restricciones protegían de un operador que no existe.
