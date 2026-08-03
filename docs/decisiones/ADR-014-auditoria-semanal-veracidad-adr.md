# ADR-014 - Auditoría semanal de veracidad de las ADR contra el repo

Fecha: 2026-08-01
Estado: Aceptada

## Contexto

El 2026-08-01 se detectó dos veces el mismo problema: una ADR afirmaba que algo estaba hecho cuando no lo estaba. ADR-011 decía que se agregaba una instrucción a CLAUDE.md que en realidad nunca se agregó. ADR-012 afirmaba en su sección de Consecuencias que se agregaba LiteLLM a `docker-compose.yml`, cuando ese archivo solo define `db` y `web` — la frase estaba en presente, describiendo trabajo de Fase 3 todavía no implementado. Nadie estaba verificando que las ADR dijeran la verdad sobre el estado real del repositorio; el pipeline de verificación de ADR-001 (captura → verificación → promoción) no se estaba aplicando a la propia documentación de decisiones.

## Decisión

Se agrega `scripts/adr_audit.sh`, siguiendo el mismo patrón ya probado de `scripts/memory_audit.sh` (ADR-008): corre `claude -p` en modo no interactivo con acceso restringido a herramientas de lectura (`Read,Glob,Grep`, sin `Bash`/`Write`/`Edit` — la auditoría solo lee, nunca corrige nada por sí sola), envuelto en `timeout 300`, dejando el resultado en `/home/fernando/adr-audit.log` con marca `ADR_AUDIT_STATUS=OK|FAILED`.

El prompt le pide revisar todas las `docs/decisiones/ADR-*.md` y verificar tres cosas: (a) que toda afirmación de tipo "se agrega/crea/modifica X" se corresponda con el estado real del repo, aplicando la convención de tiempo verbal agregada a CLAUDE.md en esta misma ADR (presente = ya existe; pendiente sin marcar = ambigüedad; pendiente marcado con fase = correcto, no discrepancia); (b) que ARQUITECTURA.md §6 liste todas las ADR existentes; (c) que CHANGELOG.md tenga entrada para cada una.

Se programa por `crontab` del usuario `fernando` (sin sudo) los domingos a las 04:45 — semanal, no mensual, y en un horario que no choca con el backup diario (03:00) ni con la auditoría mensual de memoria (día 1, 04:15).

Como parte de la misma corrección, se agrega a CLAUDE.md (sección "Cómo mantener la documentación") la convención de redacción que hace posible que esta auditoría distinga discrepancias reales de ruido: el presente se reserva para lo que ya existe en el repo al escribir la ADR; cualquier afirmación sobre algo no implementado debe marcarse explícitamente como pendiente y con la fase correspondiente (ej. `**Pendiente (Fase 3):** ...`).

Se corrigió también la redacción de ADR-012 (la frase sobre LiteLLM en `docker-compose.yml`, marcada ahora como `**Pendiente (Fase 3):**`) como parte de esta misma corrección, no como hallazgo separado.

## Alternativas descartadas

- **Extender `scripts/memory_audit.sh` para que también audite las ADR, en vez de un script separado**: descartado — son auditorías de propósitos distintos (higiene de memoria vs. veracidad de documentación de decisiones) con cadencias distintas (mensual vs. semanal). Combinarlas complicaría leer cada log por separado y acoplaría dos cosas que cambian de frecuencia de forma independiente.
- **Cadencia mensual, igual que la auditoría de memoria**: descartada — la deriva entre lo que una ADR afirma y lo que el repo realmente tiene se produce en el momento de escribir la ADR, no un mes después. Una cadencia mensual dejaría hasta 30 días de documentación incorrecta sin detectar. Semanal reduce esa ventana sin generar carga operativa significativa (la auditoría es de solo lectura y corta).
- **No distinguir discrepancia de ambigüedad de caso correcto, y reportar toda afirmación en presente sobre trabajo futuro**: descartado en la segunda iteración de esta ADR, tras comprobar en la práctica que sin esa distinción la auditoría iba a marcar como problema cada consecuencia a futuro correctamente diferida (ADR-005 §Fase 5, ADR-013) todas las semanas, enterrando en ruido los hallazgos reales como el de ADR-012.

## Consecuencias

- Probado manualmente dos veces antes de dejarlo en cron. La primera corrida (antes de refinar el prompt y la convención) encontró la discrepancia real de ADR-012 sin falsos positivos. La segunda corrida (tras corregir ADR-012 y agregar la distinción discrepancia/ambigüedad/correcto) confirmó cero discrepancias, cero ambigüedades, y reconoció correctamente ADR-005/012/013 como casos de pendiente-bien-marcado, no como problemas.
- Esta convención de redacción aplica hacia adelante, para ADR nuevas — no se reescribieron retroactivamente las secciones de Decisión de las ADR anteriores a esta, que ya usan tiempo presente de forma declarativa (es el modo natural de un registro de decisión: "se decide hacer X"), a diferencia de afirmaciones puntuales de existencia de un artefacto concreto, que es donde apareció el problema real.
- Si en el futuro la auditoría empieza a dar falsos positivos o negativos de forma sistemática, hay que ajustar el prompt de `scripts/adr_audit.sh` — igual que se hizo acá, probando en vivo antes de confiar en el resultado.
- Igual que `memory_audit.sh` (ADR-008), si se migra el proyecto a otro servidor (ADR-002) hay que recrear la entrada de `crontab` — el script sí viaja versionado con el repo.

## Enmienda (2026-08-02): agregada verificación (d), integridad de `docs/decisiones/INDEX.md`

Tras agregar `docs/decisiones/INDEX.md` (ver enmienda del mismo día a ADR-011), se extiende el prompt de `scripts/adr_audit.sh` con una cuarta verificación: que el índice liste exactamente los archivos ADR reales del directorio, sin faltantes, sin entradas huérfanas (archivo renombrado sin reflejar en el índice), y sin duplicados de número. Mismo criterio de prioridad que las discrepancias de contenido — un índice desactualizado rompe el mecanismo completo de ADR-011 para sesiones fetch-only, no es un detalle menor.

Se agrega además en la misma corrección (ver ADR-018) una marca grepeable `ADR_CONTENT_STATUS=CLEAN|DISCREPANCIES_FOUND`, independiente de `ADR_AUDIT_STATUS`: esta última solo refleja si la llamada a `claude -p` se ejecutó sin errores, no si el contenido de la auditoría encontró algo. Sin esa segunda marca, una corrida que sí detecta una discrepancia real terminaba igual con `ADR_AUDIT_STATUS=OK`.

## Enmienda (2026-08-03): agregada verificación (e), coherencia interna de cada ADR consigo misma

Al revisar ADR-025 en conversación con Fernando se encontraron dos referencias rotas que ni (a)/(b)/(c) ni (d) detectan, porque ninguna de esas cuatro verificaciones compara un documento contra sí mismo: una frase de §9.4 decía "es lo que hace que el paso 5 funcione" cuando la lista de esa sección tiene cuatro pasos, no cinco; y la sección "Consecuencias" decía "cinco decisiones concretas" cuando, tras tres enmiendas sucesivas, la lista de "Decisión / dirección encaminada" ya tenía nueve puntos. Ambas son del mismo tipo: una ADR que crece por enmiendas deja atrás números y referencias que apuntaban a un estado anterior del propio documento — un problema distinto de que el repo no coincida con lo que la ADR afirma (eso ya lo cubren (a)/(b)/(c)/(d)).

Se extiende el prompt de `scripts/adr_audit.sh` con una quinta verificación, (e), de coherencia interna — no contra el repo, contra el propio texto: (e1) toda referencia del tipo "punto N"/"paso N"/"§N"/"sección N" debe apuntar a un elemento que exista con ese número dentro del mismo documento; (e2) toda referencia a otra ADR ("ver ADR-NNN") debe corresponder a un archivo real de `docs/decisiones/`; (e3) todo conteo en palabras o cifras que describa una lista del propio documento ("cinco decisiones", "tres razones") debe coincidir con la cantidad real de elementos de esa lista. Mismo criterio de prioridad que (d): una referencia interna rota es tan fuente de verdad rota como un índice desactualizado, no un detalle menor. La marca `ADR_CONTENT_STATUS` pasa a considerar también (e1)/(e2)/(e3) para decidir entre `CLEAN` y `DISCREPANCIES_FOUND`.

Diferencia deliberada respecto a (d): para (e3) el prompt indica recomendar por defecto **eliminar** el número en discrepancia en vez de actualizarlo al valor correcto — actualizarlo (ej. "cinco" → "nueve") deja el mismo tipo de conteo hardcodeado que la próxima enmienda va a volver a desactualizar; sacarlo corta el problema en la raíz en vez de patearlo hacia adelante. No se aplicó esta misma lógica a (e1)/(e2) porque una referencia rota a "punto N" o "ADR-NNN" no tiene un equivalente sin número que siga siendo útil — ahí sí corresponde corregir el número al que corresponde.
